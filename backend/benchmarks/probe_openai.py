"""Small paid compatibility probes; these are not speech latency benchmarks."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

from serve import MeasuredIntelligence, Trace


async def probe(args):
    sys.path.insert(0, str(args.source.resolve()))
    from app.config import Settings
    from app.intelligence import OpenAIFallback

    settings = Settings(_env_file=args.env_file, openai_model="gpt-6-luna")
    trace = Trace(args.trace, [settings.openai_api_key, settings.gnani_api_key])
    request = "Notify me when pharmacy token 442 is called. Vibrate."
    variants = {
        "reasoning_low": {"reasoning": {"effort": "low"}},
        "reasoning_none": {"reasoning": {"effort": "none"}},
        "fast": {"service_tier": "fast"},
        "low_fast": {"reasoning": {"effort": "low"}, "service_tier": "fast"},
    }
    results = []
    try:
        for label, options in variants.items():
            measured = MeasuredIntelligence(OpenAIFallback, settings, trace)
            delegate = measured.instance()
            original_parse = delegate.client.responses.parse

            async def configured(*positional, _parse=original_parse, _options=options, **kwargs):
                return await _parse(*positional, **{**kwargs, **_options})

            delegate.client.responses.parse = configured
            started = time.monotonic()
            trace.emit("probe_start", label=label, options=options)
            try:
                result = await measured.intent(request)
                row = {"label": label, "options": options, "result": result.model_dump()}
            except Exception as exc:
                row = {
                    "label": label,
                    "options": options,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            finally:
                await measured.close()
            row["elapsed_ms"] = round((time.monotonic() - started) * 1000, 3)
            results.append(row)
            trace.emit("probe_end", **row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
    finally:
        trace.file.close()
    args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(probe(args))


if __name__ == "__main__":
    main()
