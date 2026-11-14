"""Prepare published station field recordings without synthesizing or mixing audio."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .audio import audio_reference, sha256

SOURCES = [
    {
        "id": "01-india-station-pa", "author": "soundstew", "sound_id": 99516,
        "title": "file0266.wav", "location": "Railway station in India (unspecified)",
        "license_url": "http://creativecommons.org/licenses/by-nc/3.0/",
        "recordist_description": (
            "Recorded at a railway station in India announcing the train arrival "
            "and departure information."),
        "uploader_annotated_facts": {},
    },
    {
        "id": "02-slough-platform-four", "author": "AlienXXX", "sound_id": 129351,
        "title": "Platform 4 for the 0700h to Reading.wav", "location": "Slough, UK",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "recordist_description": (
            "Female voice announcement at Slough train station for the 07:00 train "
            "to Reading. Recorded on 23 Sep 2011 with a Zoom H1, built in mics."),
        "uploader_annotated_facts": {"platform": "4", "departure_time": "07:00",
                                     "destination": "Reading"},
    },
    {
        "id": "03-slough-through-train", "author": "AlienXXX", "sound_id": 129331,
        "title": "Stand clear platform 3.wav", "location": "Slough, UK",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "recordist_description": (
            'Starts with "stand clear platform 3, through train approaching. Stand clear '
            'platform 3." Then the train goes past; platform and newspaper noises follow. '
            "Recorded on 23 Sep 2011 with a Zoom H1 using built in mics."),
        "uploader_annotated_facts": {"platform": "3", "event": "through train approaching"},
    },
    {
        "id": "04-slough-distant-pa", "author": "AlienXXX", "sound_id": 129353,
        "title": "Indistinct announcement non-stopping train on platform 2.wav",
        "location": "Slough, UK", "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "recordist_description": (
            "Indistinct announcement about a non-stopping train on platform 2, followed by "
            "the passing train. Recorded a couple of platforms away at Slough on 23 Sep "
            "2011 with a Zoom H1 using built in mics."),
        "uploader_annotated_facts": {"platform": "2", "event": "non-stopping train"},
    },
    {
        "id": "05-southall-platform-pa", "author": "JWS24", "sound_id": 790794,
        "title": "Train Station Announcment", "location": "Southall, UK",
        "license_url": "http://creativecommons.org/publicdomain/zero/1.0/",
        "recordist_description": (
            "Platform announcement over the PA at Southall station; recorded in 2002 "
            "with a Sanyo portable Minidisc recorder and a battery powered lapel mic. "
            "Transferred and edited in Pro Tools in March 2025."),
        "uploader_annotated_facts": {},
    },
]


def prepare(output: Path, cache: Path) -> dict:
    output, cache = output.resolve(), cache.resolve()
    if output.exists():
        raise ValueError("Refusing to overwrite field-recording evidence")
    cache.mkdir(parents=True, exist_ok=True)
    (output / "source").mkdir(parents=True)
    (output / "before").mkdir()
    records = []
    for source in SOURCES:
        sid = source["sound_id"]
        page_url = f"https://freesound.org/people/{source['author']}/sounds/{sid}/"
        page = cache / f"{sid}.html"
        if not page.exists():
            with urllib.request.urlopen(page_url, timeout=60) as response:
                page.write_bytes(response.read())
        html = page.read_text()
        candidates = set(re.findall(
            rf"https://cdn\.freesound\.org/previews/\d+/{sid}_\d+-hq\.mp3", html))
        if len(candidates) != 1 or source["license_url"] not in html:
            raise ValueError(f"Source page preview/license requires review: {page_url}")
        media_url = candidates.pop()
        original = cache / f"{sid}-hq.mp3"
        if not original.exists():
            with urllib.request.urlopen(media_url, timeout=90) as response:
                original.write_bytes(response.read())
        name = source["id"]
        (output / "source" / f"{name}.html").write_bytes(page.read_bytes())
        (output / "source" / f"{name}.mp3").write_bytes(original.read_bytes())
        destination = output / "before" / f"{name}.wav"
        command = ["ffmpeg", "-nostdin", "-v", "error", "-i", str(original),
                   "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
                   "-map_metadata", "-1", str(destination)]
        subprocess.run(command, check=True)
        record = {**source, **audio_reference(destination, output),
                  "source_page_url": page_url, "source_media_url": media_url,
                  "source_page_sha256": sha256(page), "source_media_sha256": sha256(original),
                  "source_media_format": "public high-quality MP3 preview, lossy",
                  "source_transcript": {"text": "<UNVERIFIED_TRANSCRIPT/>",
                                        "status": "No complete independent reference available"},
                  "selection": "Entire published preview; selected before denoising outcomes",
                  "conversion_command": command}
        records.append(record)
        print(json.dumps({"id": name, "duration_s": record["duration_s"],
                          "source_media_url": media_url}), flush=True)
    manifest = {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
                "source_kind": "station field recordings, not synthesized speech/noise mixtures",
                "source_audio_unchanged_except_format_conversion": True,
                "selection_policy": "Five complete uploader-described station PA recordings",
                "reference_policy": (
                    "Uploader facts are partial annotations, not full WER references"),
                "sample_rate": 16000, "records": records}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    inputs = [{"id": r["id"], "case_id": r["id"], "variant": "real-station-pa",
               **{key: r[key] for key in ("relative_path", "sha256", "pcm_sha256",
                                         "sample_count", "sample_zero_offset")}} for r in records]
    (output / "device-inputs.json").write_text(json.dumps(
        {"schema_version": 1, "sample_rate": 16000, "frame_samples": 512, "inputs": inputs},
        indent=2) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.output, args.cache)


if __name__ == "__main__":
    main()
