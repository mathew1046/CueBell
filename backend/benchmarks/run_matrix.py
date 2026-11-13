"""Run real-provider ablations with isolated local relay processes and fixed audio.

Each variant has its own trace, client results, configuration, and server process.
The access code is passed through the child environment, never logged. This command
spends the provider budget approved for the benchmark; it does not generate speech.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import random
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx


def usage(root: Path) -> dict:
    """Read completed and in-flight trace records without requiring a stopped server."""
    calls, seconds = 0, 0.0
    for path in root.glob("*-server.jsonl"):
        for line in path.read_text().splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue  # A concurrent append can leave the last line incomplete.
            calls += row.get("event") == "openai_request"
            if row.get("event") == "gnani_stream_end":
                seconds += row["elapsed_ms"] / 1000
    return {"openai_attempts": calls, "gnani_connection_seconds": round(seconds, 3)}


async def wait_ready(process, port: int) -> None:
    async with httpx.AsyncClient(timeout=1, trust_env=False) as client:
        for _ in range(150):
            if process.returncode is not None:
                raise RuntimeError(f"Relay exited during startup: {process.returncode}")
            try:
                response = await client.get(f"http://127.0.0.1:{port}/health")
                if response.status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(0.2)
    raise TimeoutError("Local relay did not become ready in 30 seconds")


async def stop(process) -> None:
    if process.returncode is not None:
        return
    process.terminate()
    try:
        await asyncio.wait_for(process.wait(), timeout=15)
    except TimeoutError:
        process.kill()
        await process.wait()


async def variant(args, name: str, index: int, port: int) -> dict:
    label = f"{args.prefix}-{name}"
    output = args.output / f"{label}.jsonl"
    trace = args.output / f"{label}-server.jsonl"
    if output.exists() or trace.exists():
        raise FileExistsError(f"Refusing to overwrite benchmark evidence: {label}")
    config = args.configs / f"{name}.json"
    settings = json.loads(config.read_text())
    source = args.baseline_source if name == "baseline" else args.source
    command = [
        sys.executable,
        str(args.scripts / "serve.py"),
        "--source",
        str(source),
        "--env-file",
        str(args.env_file),
        "--access-code-file",
        str(args.access_code_file),
        "--config",
        str(config),
        "--trace",
        str(trace),
        "--port",
        str(port),
    ]
    record = {
        "label": label,
        "variant": name,
        "order": index,
        "started": datetime.now(UTC).isoformat(),
        "configuration": settings,
        "source": str(source),
        "cases": args.case,
        "mode": args.mode,
        "repeat": args.repeat,
        "tail_silence_s": args.tail_silence,
        "manifest": str(args.manifest),
        "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "client_sha256": hashlib.sha256(
            (args.scripts / "run_pipeline.py").read_bytes()
        ).hexdigest(),
        "server_trace": str(trace),
        "client_results": str(output),
    }
    print(f"Starting {label} on loopback port {port}", flush=True)
    with (args.output / f"{label}.server.log").open("w") as server_log:
        server = await asyncio.create_subprocess_exec(
            *command,
            stdout=server_log,
            stderr=asyncio.subprocess.STDOUT,
        )
        client = None
        try:
            await wait_ready(server, port)
            client_command = [
                sys.executable,
                str(args.scripts / "run_pipeline.py"),
                "--base-url",
                f"http://127.0.0.1:{port}",
                "--manifest",
                str(args.manifest),
                "--label",
                label,
                "--output",
                str(output),
                "--mode",
                args.mode,
                "--repeat",
                str(args.repeat),
                "--tail-silence",
                str(args.tail_silence),
                "--max-stream-seconds",
                "90",
            ]
            for case in args.case:
                client_command.extend(["--case", case])
            env = dict(os.environ)
            env["CUEBELL_BENCH_ACCESS_CODE"] = args.access_code_file.read_text().strip()
            with (args.output / f"{label}.client.log").open("w") as client_log:
                client = await asyncio.create_subprocess_exec(
                    *client_command,
                    env=env,
                    stdout=client_log,
                    stderr=asyncio.subprocess.STDOUT,
                )
                record["client_exit_code"] = await client.wait()
            summary = output.with_suffix(".summary.json")
            if summary.exists():
                record["summary"] = json.loads(summary.read_text())
        finally:
            if client is not None:
                await stop(client)
            await stop(server)
            record["server_exit_code"] = server.returncode
    record["finished"] = datetime.now(UTC).isoformat()
    record["observed_cumulative_usage"] = usage(args.output)
    (args.output / f"{label}.run.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n"
    )
    print(f"Finished {label}; client exit {record.get('client_exit_code')}", flush=True)
    return record


async def run(args) -> None:
    args.output.mkdir(parents=True, exist_ok=True)
    names = args.variants.copy()
    if args.shuffle:
        random.Random(args.seed).shuffle(names)
    # Reserve headroom before each wave. Observed usage excludes active connections;
    # conservative per-wave reservations account for all variants launched together.
    corpus = json.loads(args.manifest.read_text())
    selected = [
        case
        for case in corpus["cases"]
        if case["id"] in args.case or not args.case and case.get("mode", "monitor") == args.mode
    ]
    if not selected or set(args.case) - {case["id"] for case in selected}:
        raise ValueError("Unknown or empty case selection")
    count = len(selected) * args.repeat
    reserve_calls = sum(2 + 4 * len(case["sequence"]) for case in selected) * args.repeat
    results = []
    for first in range(0, len(names), args.concurrency):
        wave = names[first : first + args.concurrency]
        used = usage(args.output)
        if used["openai_attempts"] + reserve_calls * len(wave) > args.call_ceiling:
            raise RuntimeError(f"Insufficient approved OpenAI budget for next wave: {used}")
        if used["gnani_connection_seconds"] + count * 90 * len(wave) > args.minute_ceiling * 60:
            raise RuntimeError(f"Insufficient approved Gnani budget for next wave: {used}")
        results.extend(
            await asyncio.gather(
                *[
                    variant(args, name, first + offset, args.port + offset)
                    for offset, name in enumerate(wave)
                ]
            )
        )
    manifest = {
        "variants": results,
        "variant_order": names,
        "concurrency": args.concurrency,
        "seed": args.seed,
        "usage": usage(args.output),
        "note": "Small screening samples are not a production latency or accuracy guarantee.",
    }
    (args.output / f"{args.prefix}-matrix.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variants", nargs="+", required=True)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--baseline-source", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--access-code-file", type=Path, required=True)
    parser.add_argument("--configs", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--mode", choices=["monitor", "request"], default="monitor")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--tail-silence", type=float, default=24)
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--concurrency", type=int, choices=[1, 2], default=2)
    parser.add_argument("--shuffle", action="store_true")
    parser.add_argument("--seed", type=int, default=20261113)
    parser.add_argument("--call-ceiling", type=int, default=600)
    parser.add_argument("--minute-ceiling", type=float, default=120)
    args = parser.parse_args()
    if args.repeat < 1 or args.call_ceiling > 600 or args.minute_ceiling > 120:
        parser.error("Invalid repeat or budget above the approved campaign limit")
    if len(args.variants) != len(set(args.variants)):
        parser.error("Variant names must be unique within a campaign")
    args.scripts = Path(__file__).resolve().parent
    for name in (
        "source",
        "baseline_source",
        "env_file",
        "access_code_file",
        "configs",
        "manifest",
        "output",
    ):
        setattr(args, name, getattr(args, name).resolve())
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
