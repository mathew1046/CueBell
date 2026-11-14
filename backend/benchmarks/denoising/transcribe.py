"""Paired real-time Gnani recognition of sourced before/after recordings.

Reference text is used ONLY for offline scoring, never as a provider hint.
This is an ASR-quality experiment, not an end-to-end CueBell alert benchmark.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import hashlib
import json
import math
import random
import re
import time
import unicodedata
import wave
from pathlib import Path

from app.config import Settings
from app.gnani import parse_message, prisma


def words(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text).lower().replace("’", "'")
    # Python's \w excludes combining vowel marks in Indic scripts. Keep marks
    # with their word so a language/script switch cannot inflate word counts.
    categories = [unicodedata.category(char)[0] for char in normalized]
    cleaned = []
    for i, char in enumerate(normalized):
        internal_apostrophe = (
            char == "'" and 0 < i < len(normalized) - 1
            and categories[i - 1] in "LMN" and categories[i + 1] in "LMN"
        )
        cleaned.append(char if categories[i] in "LMN" or internal_apostrophe else " ")
    return "".join(cleaned).split()


def error_counts(reference: str, hypothesis: str) -> dict:
    if re.search(r"<[^>]*>", reference):
        raise ValueError("Reference contains untranscribed/unknown speech markers")
    ref, hyp = words(reference), words(hypothesis)
    previous = [(i, 0, i, 0) for i in range(len(hyp) + 1)]
    # Tuple: total errors, substitutions, insertions, deletions.
    for i, target in enumerate(ref, 1):
        current = [(i, 0, 0, i)]
        for j, recognized in enumerate(hyp, 1):
            if target == recognized:
                current.append(previous[j - 1])
            else:
                e, s, ins, d = previous[j - 1]
                substitution = (e + 1, s + 1, ins, d)
                e, s, ins, d = current[-1]
                insertion = (e + 1, s, ins + 1, d)
                e, s, ins, d = previous[j]
                deletion = (e + 1, s, ins, d + 1)
                current.append(min((substitution, insertion, deletion), key=lambda t: t[0]))
        previous = current
    errors, substitutions, insertions, deletions = previous[-1]
    return {"reference_words": len(ref), "hypothesis_words": len(hyp), "errors": errors,
            "substitutions": substitutions, "insertions": insertions, "deletions": deletions,
            "wer": errors / len(ref) if ref else None}


async def recognize(settings: Settings, path: Path, record: dict, output: Path) -> dict:
    with wave.open(str(path)) as wav:
        if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) != (1, 2, 16000):
            raise ValueError("Expected mono PCM16/16k audio")
        pcm = wav.readframes(wav.getnframes())
    events, finals, pending = [], {}, set()
    result = {**record, "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
              "source_audio_seconds": len(pcm) / 32000, "status": "running",
              "scoring_version": "unicode-marks-v2"}
    started = time.monotonic()
    opened = None
    receiver = None
    try:
        async with asyncio.timeout(len(pcm) / 32000 + 30), prisma(settings) as socket:
            opened = time.monotonic()

            async def receive():
                async for raw in socket:
                    message = parse_message(raw)
                    events.append({"elapsed_s": time.monotonic() - opened, "message": message})
                    kind, utterance = message.get("type"), message.get("utterance_id")
                    if kind in {"speech_start", "processing"} and utterance:
                        pending.add(utterance)
                    if kind == "transcript" and message.get("is_final") is not False:
                        if utterance:
                            pending.discard(utterance)
                        key = message.get("segment_id") or utterance or f"segment-{len(finals)}"
                        finals[key] = message
                    if kind == "error":
                        result.setdefault("provider_errors", []).append(message)

            receiver = asyncio.create_task(receive())
            # Final partial frame and 2.016s transport silence; stored recordings
            # remain untouched. Silence is paced exactly like source audio.
            frames = [pcm[i:i + 1024].ljust(1024, b"\0") for i in range(0, len(pcm), 1024)]
            frames.extend([bytes(1024)] * 63)
            anchor = time.monotonic()
            last_sent = anchor - 0.032
            rebase_count, maximum_lateness = 0, 0.0
            for i, frame in enumerate(frames):
                target = max(anchor + i * 0.032, last_sent + 0.028)
                await asyncio.sleep(max(0, target - time.monotonic()))
                now = time.monotonic()
                maximum_lateness = max(maximum_lateness, now - target)
                if now - target > 0.064:
                    anchor += now - target
                    rebase_count += 1
                await socket.send(frame)
                last_sent = time.monotonic()
            await socket.send(json.dumps({"type": "commit"}))
            # Fixed observation window avoids selecting a short wait only for the
            # condition that produces an early transcript.
            await asyncio.sleep(10)
            result.update(sent_frames=len(frames), schedule_rebases=rebase_count,
                          maximum_send_lateness_ms=maximum_lateness * 1000,
                          unfinished_utterance_ids=sorted(pending),
                          connection_seconds=time.monotonic() - opened)
            if receiver.done():
                receiver.result()
            result["status"] = (
                "completed" if finals and not pending and not result.get("provider_errors")
                else "inconclusive"
            )
    except Exception as error:
        # Do not print connection headers or credential-bearing objects.
        result.update(status="error", error_type=type(error).__name__)
    finally:
        if receiver is not None:
            receiver.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await receiver
        result["connection_seconds"] = time.monotonic() - opened if opened else 0
        result["attempt_seconds"] = time.monotonic() - started
        result["transcript"] = " ".join(m.get("text", "") for m in finals.values()).strip()
        result["events"] = events
        result["reference_score_eligible"] = not re.search(r"<[^>]*>", record["reference"])
        result["score"] = (error_counts(record["reference"], result["transcript"])
                           if result["reference_score_eligible"] else None)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


async def run(args) -> None:
    manifest = json.loads(args.manifest.read_text())
    records = manifest["records"]
    if args.id:
        records = [r for r in records if r["id"] in args.id]
        if {r["id"] for r in records} != set(args.id):
            raise ValueError("Unknown selected ID")
    if args.output.exists():
        raise ValueError("Refusing to overwrite provider evidence")
    settings = Settings()
    if not settings.gnani_api_key:
        raise ValueError("GNANI_API_KEY is not configured")
    # Preserve released language/default VAD settings for both conditions.
    rng = random.Random(20261114)
    rng.shuffle(records)
    trials = []
    for record in records:
        arms = list(args.arm)
        rng.shuffle(arms)
        for arm in arms:
            directory = args.before if arm == "before" else args.after
            path = directory / f"{record['id']}.wav"
            if not path.is_file():
                raise ValueError(f"Missing audio: {path}")
            trials.append((record, arm, path))
    worst_case_reservation = sum(math.ceil(r[0]["duration_s"]) + 35 for r in trials)
    if worst_case_reservation > args.max_connection_seconds:
        raise ValueError("Conservative trial reservation exceeds remaining authorization")
    args.output.mkdir(parents=True)
    results = []
    for offset in range(0, len(trials), args.concurrency):
        batch = trials[offset:offset + args.concurrency]
        remaining = args.max_connection_seconds - sum(r["attempt_seconds"] for r in results)
        if remaining < sum(record["duration_s"] + 35 for record, _, _ in batch):
            raise ValueError("Insufficient remaining budget for the next trial batch")
        tasks = []
        for record, arm, path in batch:
            trial = {"id": record["id"], "arm": arm,
                     "reference": record["source_transcript"]["text"]}
            tasks.append(recognize(settings, path, trial,
                                   args.output / f"{record['id']}-{arm}.json"))
        completed = await asyncio.gather(*tasks)
        results.extend(completed)
        for result in completed:
            print(json.dumps({"id": result["id"], "arm": result["arm"],
                              "status": result["status"],
                              "wer": result["score"]["wer"] if result["score"] else None}),
                  flush=True)
        summary = {"schema": 1, "model": "prisma-v3.0", "language": settings.gnani_language_code,
                     "reference_hints_sent": False, "new_luna_calls": 0,
                     "scoring_version": "unicode-marks-v2",
                    "concurrency": args.concurrency,
                    "normalization": ("Unicode NFKC, lowercase, punctuation removed; "
                                      "apostrophes retained; no numeric/spelling rewriting"),
                   "connection_seconds": sum(r["connection_seconds"] for r in results),
                   "results": [{k: v for k, v in r.items() if k != "events"} for r in results]}
        (args.output / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path)
    parser.add_argument("--arm", action="append", choices=["before", "after"], required=True)
    parser.add_argument("--id", action="append")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-connection-seconds", type=float, required=True)
    parser.add_argument("--concurrency", type=int, choices=[1, 2], default=1)
    args = parser.parse_args()
    if "after" in args.arm and args.after is None:
        parser.error("--after is required for the after arm")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
