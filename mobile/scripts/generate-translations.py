"""Explicit build-time translation of PUBLIC UI copy; never called by the app.

Run from mobile/: node scripts/extract-translations.mjs
Then: python3 scripts/generate-translations.py
Existing translations are preserved. Review generated copy with native speakers.
"""
import concurrent.futures
import json
from pathlib import Path
import re
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1] / 'src/lib/i18n'
SOURCE = json.loads((ROOT / 'en.json').read_text())
DEST = ROOT / 'catalogs.json'
CODES = re.findall(r"code: '([^']+)'", (ROOT / 'languages.ts').read_text())
existing = json.loads(DEST.read_text()) if DEST.exists() else {}


def translate(code, messages):
    # Keep interpolation placeholders opaque to translation and verify their round-trip.
    def protect(message):
        names = re.findall(r'\{\w+\}', message)
        for i, name in enumerate(names):
            message = message.replace(name, str(123456789 + i), 1)
        return message, names
    protected = [protect(message) for message in messages]
    query = '\n'.join(message for message, _ in protected)
    url = 'https://translate.googleapis.com/translate_a/single?' + urllib.parse.urlencode({
        'client': 'gtx', 'sl': 'en', 'tl': code, 'dt': 't', 'q': query,
    })
    last_error = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                data = json.load(response)
            lines = ''.join(part[0] for part in data[0] if part[0]).split('\n')
            if len(lines) != len(messages):
                raise ValueError('Translation changed message boundaries')
            result = {}
            for source, translated, (_, names) in zip(messages, lines, protected):
                for i, name in enumerate(names):
                    # Providers can localize numerals (Ol Chiki / Meitei). Recover the marker.
                    translated = ''.join(str(int(char)) if char.isdecimal() else char for char in translated)
                    translated, count = re.subn(str(123456789 + i), lambda _: name, translated)
                    if count != 1:
                        raise ValueError(f'Placeholder lost: {source}')
                if sorted(re.findall(r'\{\w+\}', source)) != sorted(re.findall(r'\{\w+\}', translated)):
                    raise ValueError(f'Placeholders changed: {source}')
                result[source] = translated.strip()
            return result
        except Exception as error:
            last_error = error
            time.sleep(attempt + 1)
    # A short batch or isolated string often fixes line/placeholder mangling.
    if len(messages) > 1:
        middle = len(messages) // 2
        return translate(code, messages[:middle]) | translate(code, messages[middle:])
    raise RuntimeError(f'{code}: {messages}: {last_error}')


def generate(code):
    catalog = {key: value for key, value in existing.get(code, {}).items() if key in SOURCE}
    missing = [key for key in SOURCE if key not in catalog]
    batch = []
    for message in missing:
        if sum(len(item) for item in batch) + len(message) > 1800 and batch:
            catalog.update(translate(code, batch))
            batch = []
        batch.append(message)
    if batch:
        catalog.update(translate(code, batch))
    print(f'{code}: {len(catalog)} messages', flush=True)
    return code, catalog


if __name__ == '__main__':
    catalogs = {'en': SOURCE}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(generate, code) for code in CODES if code != 'en']
        errors = []
        for future in concurrent.futures.as_completed(futures):
            try:
                code, catalog = future.result()
            except Exception as error:
                errors.append(str(error))
                continue
            catalogs[code] = catalog
            # Checkpoint complete languages so a provider failure does not discard work.
            DEST.write_text(json.dumps(existing | catalogs, ensure_ascii=False, indent=2) + '\n')
    if errors:
        raise RuntimeError('\n'.join(errors))
    DEST.write_text(json.dumps({code: catalogs[code] for code in CODES}, ensure_ascii=False, indent=2) + '\n')
