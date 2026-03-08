"""Tests for the leaderboard results builder."""

import importlib.util
import json
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_site_results.py"
SPEC = importlib.util.spec_from_file_location("build_site_results", MODULE_PATH)
build_site_results = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(build_site_results)


def test_collect_model_results_merges_release_metadata(tmp_path):
    predictions_dir = tmp_path / "predictions"
    model_dir = predictions_dir / "test-model"
    results_dir = model_dir / "results" / "eval"
    results_dir.mkdir(parents=True)

    (model_dir / "config.json").write_text(json.dumps({
        "display_name": "Test Model",
        "shots": 2,
    }))
    (results_dir / "003_01_20250101_results.json").write_text(json.dumps({
        "model_name": "test-model",
        "date": "2025-04-01T12:00:00",
        "details": [],
    }))

    metadata_path = tmp_path / "model_release_dates.json"
    metadata_path.write_text(json.dumps({
        "test-model": {
            "release_date": "2024-01-15",
            "release_display": "2024-01-15",
            "release_source": "https://example.com/test-model",
            "release_notes": "Release metadata should be copied through.",
            "display_suffix": "*",
            "display_note": "Synthetic caveat for display metadata."
        }
    }))

    release_metadata = build_site_results.load_release_metadata(metadata_path)
    results = build_site_results.collect_model_results(
        predictions_dir,
        shot_filter=2,
        release_metadata=release_metadata,
    )

    assert len(results) == 1
    assert results[0]["model_id"] == "test-model"
    assert results[0]["release_date"] == "2024-01-15"
    assert results[0]["release_display"] == "2024-01-15"
    assert results[0]["release_source"] == "https://example.com/test-model"
    assert results[0]["release_notes"] == "Release metadata should be copied through."
    assert results[0]["display_suffix"] == "*"
    assert results[0]["display_note"] == "Synthetic caveat for display metadata."
