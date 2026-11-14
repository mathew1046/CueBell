"""Probe the released Luna observer on complete real-recording Gnani transcripts.

This is a downstream component check, not a live notification latency test.
Neither source annotations nor expected platform numbers are sent to the model.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

from app.config import Settings
from app.intelligence import OpenAIFallback
from app.models import MonitoringTask, Segment
from app.validation import grounded_stop_request, validate_match

from .audio import sha256

TASK = MonitoringTask(
    subject="Railway train and platform announcements",
    condition=("A spoken announcement gives train arrival, departure, platform, service "
               "or railway platform safety information."),
    summary="Train and platform announcements",
    request_evidence="Notify me of train and platform announcements.",
    identifiers=[],
)


async def run(args) -> dict:
    summary = json.loads(args.asr_summary.read_text())
    eligible = [r for r in summary["results"]
                if r["status"] == "completed" and r["transcript"].strip()]
    if len(eligible) > args.max_calls:
        raise ValueError("Model-call reservation exceeds the specified remaining allowance")
    if args.output.exists():
        raise ValueError("Refusing to overwrite model evidence")
    settings = Settings(openai_model="gpt-6-luna")
    provider = OpenAIFallback(settings)
    args.output.mkdir(parents=True)
    original_parse = provider.client.responses.parse
    current = {}

    async def traced_parse(**kwargs):
        current["request"] = {key: kwargs[key] for key in (
            "model", "input", "max_output_tokens", "reasoning", "service_tier", "text",
            "prompt_cache_options") if key in kwargs}
        response = await original_parse(**kwargs)
        current.update({"response_id": response.id, "response_status": response.status,
                        "response_model": response.model,
                        "usage": response.usage.model_dump() if response.usage else None})
        return response

    provider.client.responses.parse = traced_parse
    report = {
        "schema_version": 1, "model": "gpt-6-luna", "task": TASK.model_dump(),
        "component": "OpenAIFallback.observe + validate_match, whole transcript as one segment",
        "expected_facts_sent": False, "audio_source_metadata_sent": False,
        "live_notification_latency_measured": False,
        "asr_summary_sha256": sha256(args.asr_summary),
        "settings": {name: getattr(settings, name) for name in (
            "openai_model", "openai_reasoning_effort", "openai_max_output_tokens",
            "openai_service_tier", "openai_verbatim_location_hint", "openai_compact_input")},
        "excluded": [{"id": r["id"], "arm": r["arm"],
                      "reason": "incomplete ASR or empty transcript"}
                     for r in summary["results"] if r not in eligible],
        "attempts": [], "attempt_count": 0,
    }
    (args.output / "summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    try:
        for record in eligible:
            current = {"id": record["id"], "arm": record["arm"], "status": "running",
                       "transcript": record["transcript"],
                       "audio_sha256": record["input_sha256"]}
            destination = args.output / f"{record['id']}-{record['arm']}.json"
            destination.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n")
            window = [Segment(id="s1", text=record["transcript"], received_at=0.0)]
            started = time.monotonic()
            try:
                extracted = await provider.observe(window, [], TASK)
                current.update({"status": "completed", "extraction": extracted.model_dump(),
                                "validated_events": [
                                    validate_match(event, window, TASK).model_dump()
                                    for event in extracted.events],
                                "grounded_stop_request": bool(
                                    extracted.stop_request and grounded_stop_request(
                                        extracted.stop_request, window))})
            except Exception as error:
                current.update({"status": "error", "error_type": type(error).__name__,
                                "http_status": getattr(error, "status_code", None)})
            current["elapsed_seconds"] = time.monotonic() - started
            destination.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n")
            report["attempts"].append(current)
            report["attempt_count"] = len(report["attempts"])
            (args.output / "summary.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n")
            print(json.dumps({k: current[k] for k in ("id", "arm", "status")}), flush=True)
    finally:
        await provider.client.close()
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asr-summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-calls", type=int, required=True)
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
