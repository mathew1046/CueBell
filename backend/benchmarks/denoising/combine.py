"""Interleave matched acoustic conditions without changing reference timing or labels."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import random
import re
from pathlib import Path


def combine(arms: dict[str, Path], seed: int) -> dict:
    if len(arms) < 2 or any(not re.fullmatch(r"[a-zA-Z0-9_-]+", name) for name in arms):
        raise ValueError("At least two distinctly named acoustic conditions are required")
    loaded = {name: json.loads(path.read_text()) for name, path in arms.items()}
    first = next(iter(loaded.values()))
    reference_cases = {case["id"]: case for case in first["cases"]}
    reference_fixtures = {fixture["id"]: fixture for fixture in first["fixtures"]}
    cases_by_arm = {}
    fixtures = []
    sources = []
    for name, data in loaded.items():
        if data.get("sample_rate") != 16000:
            raise ValueError("All arms must use 16 kHz audio")
        if data.get("metadata", {}).get("required_replay_flags") != {
            "leading_silence": 0,
            "tail_silence": 0,
        }:
            raise ValueError("All arms must have baked-in timing and zero added replay silence")
        cases = {case["id"]: case for case in data["cases"]}
        items = {fixture["id"]: fixture for fixture in data["fixtures"]}
        if len(cases) != len(data["cases"]) or set(cases) != set(reference_cases):
            raise ValueError("Acoustic arms must contain the same unique cases")
        if len(items) != len(data["fixtures"]) or set(items) != set(reference_fixtures):
            raise ValueError("Acoustic arms must contain the same unique fixtures")
        for case_id, case in cases.items():
            for field in ("language", "request", "kind", "mode", "expected", "sequence"):
                if case.get(field) != reference_cases[case_id].get(field):
                    raise ValueError(f"Matched case changed {field}: {name}/{case_id}")
        for fixture_id, fixture in items.items():
            for field in ("language", "text", "speech_end_s", "duration_s", "source_scripts"):
                if fixture.get(field) != reference_fixtures[fixture_id].get(field):
                    raise ValueError(f"Matched fixture changed {field}: {name}/{fixture_id}")
            rewritten = copy.deepcopy(fixture)
            rewritten["id"] = f"{name}__{fixture_id}"
            audio = Path(fixture["audio_path"])
            rewritten["audio_path"] = str(
                (arms[name].parent / audio).resolve() if not audio.is_absolute() else audio
            )
            fixtures.append(rewritten)
        cases_by_arm[name] = cases
        sources.append({
            "arm": name,
            "path": str(arms[name].resolve()),
            "sha256": hashlib.sha256(arms[name].read_bytes()).hexdigest(),
            "metadata": data.get("metadata", {}),
        })
    rng = random.Random(seed)
    case_ids = list(reference_cases)
    rng.shuffle(case_ids)
    combined_cases = []
    for case_id in case_ids:
        order = list(arms)
        rng.shuffle(order)
        for name in order:
            case = copy.deepcopy(cases_by_arm[name][case_id])
            case.update(id=f"{case_id}__{name}", base_case_id=case_id, acoustic_arm=name)
            for segment in case["sequence"]:
                segment["fixture_id"] = f"{name}__{segment['fixture_id']}"
            combined_cases.append(case)
    metadata = copy.deepcopy(first.get("metadata", {}))
    metadata.update(
        audio_processing="matched acoustic arms; see each source manifest",
        comparison_design="Seeded case blocks with condition order shuffled within each block",
        comparison_seed=seed,
        source_manifests=sources,
        ground_truth="Unchanged labels, scripts, source endpoints and duration across all arms",
    )
    return {"version": 1, "sample_rate": 16000, "fixtures": fixtures,
            "cases": combined_cases, "metadata": metadata}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", action="append", required=True, help="NAME=MANIFEST.json")
    parser.add_argument("--seed", type=int, default=20261114)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    arms = {}
    for value in args.arm:
        name, separator, path = value.partition("=")
        if not separator or not path or name in arms:
            parser.error("Use distinct NAME=MANIFEST.json arguments")
        arms[name] = Path(path)
    result = combine(arms, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(args.output)


if __name__ == "__main__":
    main()
