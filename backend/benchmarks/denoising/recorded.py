"""Source unmodified real recordings from Microsoft's DNS5 speakerphone dev set.

Only format conversion to CueBell's PCM format is performed; no speech, noise,
mixtures, reverberation, gain changes, or padding is generated. HTTP ranges avoid
downloading the entire 3 GB archive. ZIP CRCs and per-file SHA256 are preserved.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import struct
import subprocess
import urllib.error
import urllib.request
import wave
import zipfile
import zlib
from collections import Counter
from pathlib import Path

URL = "https://dnschallengepublic.blob.core.windows.net/dns5archive/V5_dev_testset.zip"
SOURCE_PAGE = "https://github.com/microsoft/DNS-Challenge"
PREFIX = "V5_dev_testset/Track2_Speakerphone/noisy/"
TRANSCRIPTS = "V5_dev_testset/Track2_Speakerphone/transcripts/v5_devset_transcripts_track2.tsv"


class RemoteZip:
    def __init__(self, cache: Path):
        self.cache = cache
        cache.mkdir(parents=True, exist_ok=True)
        header_path = cache / "http-headers.json"
        if header_path.exists():
            self.headers = json.loads(header_path.read_text())
        else:
            with self.open(urllib.request.Request(URL, method="HEAD")) as response:
                self.headers = dict(response.headers)
            header_path.write_text(json.dumps(self.headers, indent=2) + "\n")
        lower = {k.lower(): v for k, v in self.headers.items()}
        self.size = int(lower["content-length"])
        self.etag = lower["etag"]
        tail = self.read(self.size - 65536, self.size - 1)
        end = tail.rfind(b"PK\x05\x06")
        if end < 0:
            raise ValueError("ZIP end record missing")
        fields = struct.unpack_from("<4s4H2LH", tail, end)
        central_size, self.central_offset = fields[5:7]
        if central_size == 0xFFFFFFFF or self.central_offset == 0xFFFFFFFF:
            raise ValueError("ZIP64 archive requires a different reader")
        central = self.read(self.central_offset, self.central_offset + central_size - 1)
        self.index = zipfile.ZipFile(io.BytesIO(central + tail[end:]))

    @staticmethod
    def open(request: urllib.request.Request):
        for attempt in range(3):
            try:
                return urllib.request.urlopen(request, timeout=20)
            except (urllib.error.URLError, TimeoutError):
                if attempt == 2:
                    raise
        raise AssertionError("unreachable")

    def read(self, start: int, end: int) -> bytes:
        cached = self.cache / f"range-{start}-{end}.bin"
        if cached.exists():
            data = cached.read_bytes()
        else:
            request = urllib.request.Request(
                URL, headers={"Range": f"bytes={start}-{end}", "If-Match": self.etag}
            )
            with self.open(request) as response:
                if response.status != 206:
                    raise ValueError("Server did not honor bounded HTTP range")
                expected = f"bytes {start}-{end}/{self.size}"
                if response.headers.get("Content-Range") != expected:
                    raise ValueError("Unexpected Content-Range")
                data = response.read(end - start + 2)
            if len(data) != end - start + 1:
                raise ValueError("Incomplete HTTP range")
            cached.write_bytes(data)
        if len(data) != end - start + 1:
            raise ValueError("Invalid cached HTTP range length")
        return data

    def member(self, name: str) -> bytes:
        info = self.index.getinfo(name)
        position = info.header_offset + self.central_offset
        header = struct.unpack("<4s5H3L2H", self.read(position, position + 29))
        if header[0] != b"PK\x03\x04":
            raise ValueError("Invalid local ZIP header")
        start = position + 30 + header[-2] + header[-1]
        compressed = self.read(start, start + info.compress_size - 1)
        if info.compress_type == zipfile.ZIP_DEFLATED:
            data = zlib.decompress(compressed, -15)
        elif info.compress_type == zipfile.ZIP_STORED:
            data = compressed
        else:
            raise ValueError("Unsupported ZIP compression")
        if len(data) != info.file_size or zlib.crc32(data) != info.CRC:
            raise ValueError(f"ZIP length/CRC mismatch: {name}")
        return data


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--count", type=int, default=12)
    parser.add_argument("--distance", choices=["near", "far"])
    parser.add_argument("--inspect", action="store_true")
    args = parser.parse_args()
    source = RemoteZip(args.cache)
    members = sorted(
        name for name in source.index.namelist()
        if name.startswith(PREFIX) and name.endswith(".wav")
    )
    transcript_bytes = source.member(TRANSCRIPTS)
    text = transcript_bytes.decode("utf-8-sig")
    # The official TSV is headerless: integer index, filename, transcript.
    rows = []
    for row in csv.reader(io.StringIO(text), delimiter="\t"):
        if len(row) != 3 or not row[1].endswith(".wav"):
            raise ValueError("Unexpected DNS5 transcript row")
        rows.append({"index": row[0], "filename": row[1], "text": row[2]})
    if args.inspect:
        print(json.dumps({
            "archive_headers": source.headers,
            "categories": dict(Counter(Path(n).stem.split("_")[2] for n in members)),
            "sample_names": members[:16], "transcript_sample": rows[:4],
        }, indent=2))
        return
    if not args.output or args.output.exists():
        parser.error("Provide a new --output directory")
    if not 1 <= args.count <= 50:
        parser.error("--count must be between 1 and 50")
    # A fixed filename-hash ranking is independent of enhancement outcomes.
    eligible = [n for n in members if n.lower().endswith("_primary.wav")
                and Path(n).stem.split("_")[3].lower() in {"near", "far"}
                and (not args.distance or Path(n).stem.split("_")[3].lower() == args.distance)]
    categories = sorted({Path(n).stem.split("_")[2].lower() for n in eligible})
    selected = []
    for category in categories:
        options = [n for n in eligible if Path(n).stem.split("_")[2].lower() == category]
        selected.append(min(options, key=lambda n: sha(n.encode())))
    controls = [n for n in selected if Path(n).stem.split("_")[2].lower() == "nonoise"]
    noisy = [n for n in selected if n not in controls]
    selected = sorted(noisy, key=lambda n: sha(n.encode()))[:args.count - len(controls)] + controls
    if len(selected) != args.count:
        raise ValueError(f"Only {len(selected)} distinct primary-speaker noise categories")
    out = args.output.resolve()
    (out / "source").mkdir(parents=True)
    (out / "before").mkdir()
    (out / "source" / "transcripts.tsv").write_bytes(transcript_bytes)
    inputs, records = [], []
    for index, name in enumerate(selected, 1):
        parts = Path(name).stem.split("_")
        label = f"{index:02d}-{parts[2].lower()}-{parts[3].lower()}"
        content = source.member(name)
        original = out / "source" / Path(name).name
        original.write_bytes(content)
        destination = out / "before" / f"{label}.wav"
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
            "-i", str(original), "-map", "0:a:0", "-ar", "16000", "-ac", "1",
            "-c:a", "pcm_s16le", "-bitexact", str(destination),
        ], check=True)
        with wave.open(str(destination)) as wav:
            if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) != (1, 2, 16000):
                raise ValueError("Conversion did not produce mono PCM16/16k")
            count = wav.getnframes()
            pcm = wav.readframes(count)
        matches = [r for r in rows if r["filename"] == Path(name).name]
        if len(matches) != 1:
            raise ValueError(f"Expected one source transcript for {name}; found {len(matches)}")
        reference = {
            "id": label, "case_id": label, "variant": "real-recorded",
            "relative_path": f"before/{label}.wav", "sha256": sha(destination.read_bytes()),
            "pcm_sha256": sha(pcm), "sample_count": count, "sample_zero_offset": 0,
        }
        inputs.append(reference)
        records.append({**reference, "noise_category": parts[2], "distance": parts[3],
            "source_member": name, "source_sha256": sha(content),
            "source_crc32": f"{source.index.getinfo(name).CRC:08x}",
            "source_transcript": matches[0], "duration_s": count / 16000,
        })
        print(json.dumps({"downloaded": label, "duration_s": count / 16000}), flush=True)
    (out / "device-inputs.json").write_text(json.dumps({
        "schema_version": 1, "sample_rate": 16000, "frame_samples": 512, "inputs": inputs,
    }, indent=2) + "\n")
    (out / "manifest.json").write_text(json.dumps({
        "schema": 1, "dataset": "Microsoft DNS5 dev Track2 Speakerphone real recordings",
        "source_url": URL, "source_page": SOURCE_PAGE, "http_headers": source.headers,
        "selection": ("One primary-speaker recording per case-insensitive category; "
                      "SHA256 filename ranking; reserve a NoNoise control only if eligible. "
                      "No outcome-based selection."),
        "distance_filter": args.distance, "no_noise_control_count": len(controls),
        "transformation": ("FFmpeg mono PCM16 16k conversion only; "
                           "no synthesis/mixing/gain/padding/trim"),
        "clean_reference_available": False, "transcript_source": TRANSCRIPTS,
        "transcript_sha256": sha(transcript_bytes), "records": records,
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
