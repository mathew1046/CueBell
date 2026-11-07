import catalogs from './catalogs.json' with { type: 'json' };
import type { Language } from './languages';

export type Parameters = Record<string, string | number>;
export function translate(language: Language, message: string, parameters: Parameters = {}): string {
  const catalog = (catalogs as Record<string, Record<string, string>>)[language];
  return (catalog?.[message] || message).replace(/\{(\w+)\}/g, (placeholder, name: string) => {
    const value = parameters[name];
    if (value === undefined) return placeholder;
    // Isolate identifiers inside RTL sentences without changing their characters/leading zeros.
    return language === 'ur' || language === 'sd' ? `\u2068${value}\u2069` : String(value);
  });
}

/** Localize known service messages without sending private runtime text to a translator. */
export function translateServiceMessage(language: Language, message: string, fallback: string): string {
  if (language === 'en' || !message) return message;
  const catalog = (catalogs as Record<string, Record<string, string>>)[language];
  if (catalog?.[message]) return translate(language, message);
  const gap = /^Listening again after a (\d+)s gap\. Check the display\.$/.exec(message);
  if (gap) return translate(language, 'Listening again after a {seconds}s gap. Check the display.', { seconds: gap[1] });
  const retry = /^(.*) Retrying in (\d+)s\.$/.exec(message);
  if (retry) return `${translateServiceMessage(language, retry[1], fallback)} ${translate(language, 'Retrying in {seconds}s.', { seconds: retry[2] })}`;
  const ended = /^(.*) Try again from the app\.$/.exec(message);
  if (ended) return `${translateServiceMessage(language, ended[1], fallback)} ${translate(language, 'Try again from the app.')}`;
  return message.split('\n').length > 1
    ? message.split('\n').map(line => translateServiceMessage(language, line, fallback)).join('\n')
    : translate(language, fallback);
}
