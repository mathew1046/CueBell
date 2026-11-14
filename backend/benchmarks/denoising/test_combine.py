import copy
import json
from pathlib import Path

import pytest

from benchmarks.denoising.combine import combine


def manifests(tmp_path: Path) -> dict[str, Path]:
    data = {
        "sample_rate": 16000,
        "fixtures": [{"id": "speech", "audio_path": "original.wav", "sha256": "original",
                      "language": "hi", "text": "reference", "speech_end_s": 2.0,
                      "duration_s": 4.0}],
        "cases": [{"id": "positive", "language": "hi", "request": "notify",
                   "kind": "positive", "expected": {"alert": True, "token": "442"},
                   "sequence": [{"fixture_id": "speech", "silence_after_s": 0}]}],
        "metadata": {"required_replay_flags": {"leading_silence": 0, "tail_silence": 0}},
    }
    arms = {}
    for name in ("raw", "enhanced"):
        item = copy.deepcopy(data)
        item["fixtures"][0]["audio_path"] = f"{name}.wav"
        item["fixtures"][0]["sha256"] = name
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(item))
        arms[name] = path
    return arms


def test_interleaving_preserves_references_and_maps_distinct_audio(tmp_path: Path):
    result = combine(manifests(tmp_path), 42)
    assert {case["acoustic_arm"] for case in result["cases"]} == {"raw", "enhanced"}
    fixtures = {fixture["id"]: fixture for fixture in result["fixtures"]}
    for case in result["cases"]:
        fixture = fixtures[case["sequence"][0]["fixture_id"]]
        assert fixture["speech_end_s"] == 2.0
        assert fixture["sha256"] == case["acoustic_arm"]
        assert case["expected"] == {"alert": True, "token": "442"}


@pytest.mark.parametrize("change", ["endpoint", "ground_truth"])
def test_rejects_artificial_latency_or_quality_advantage(tmp_path: Path, change: str):
    arms = manifests(tmp_path)
    modified = json.loads(arms["enhanced"].read_text())
    if change == "endpoint":
        modified["fixtures"][0]["speech_end_s"] += 0.016
    else:
        modified["cases"][0]["expected"]["token"] = "443"
    arms["enhanced"].write_text(json.dumps(modified))
    with pytest.raises(ValueError, match="Matched (fixture|case) changed"):
        combine(arms, 42)
