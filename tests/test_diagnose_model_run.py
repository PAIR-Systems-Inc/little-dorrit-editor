"""Tests for the model run diagnostic utility."""

import importlib.util
import json
from pathlib import Path
import sys


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "diagnose_model_run.py"
SPEC = importlib.util.spec_from_file_location("diagnose_model_run", MODULE_PATH)
diagnose_model_run = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = diagnose_model_run
SPEC.loader.exec_module(diagnose_model_run)


def test_analyze_model_reports_bad_missing_and_duplicate_files(tmp_path):
    project_root = tmp_path
    (project_root / "data" / "sample").mkdir(parents=True)
    (project_root / "data" / "eval").mkdir(parents=True)
    (project_root / "data" / "sample" / "001.png").write_text("")
    (project_root / "data" / "eval" / "003.png").write_text("")
    (project_root / "data" / "eval" / "003.json").write_text("{}")

    model_dir = project_root / "predictions" / "test-model"
    sample_dir = model_dir / "predictions" / "sample"
    eval_pred_dir = model_dir / "predictions" / "eval"
    eval_res_dir = model_dir / "results" / "eval"
    sample_dir.mkdir(parents=True)
    eval_pred_dir.mkdir(parents=True)
    eval_res_dir.mkdir(parents=True)

    (sample_dir / "001_01_20250101_prediction.json").write_text(
        json.dumps({"edits": [], "annotator": "Test"})
    )
    (eval_pred_dir / "003_01_20250101_prediction.json").write_text(
        json.dumps({"edits": [], "annotator": "Test", "error": "provider flake"})
    )
    (eval_pred_dir / "003_02_20250101_prediction.json").write_text(
        json.dumps({"edits": [], "annotator": "Test"})
    )
    (eval_pred_dir / "003_02_20250102_prediction.json").write_text(
        json.dumps({"edits": [], "annotator": "Test"})
    )
    (eval_res_dir / "003_01_20250101_results.json").write_text(json.dumps({"details": []}))

    diagnostics = diagnose_model_run.analyze_model(
        project_root=project_root,
        model_id="test-model",
        expected_runs=2,
    )

    assert diagnostics["summary"]["sample"]["ok"] == 1
    assert diagnostics["summary"]["sample"]["missing_prediction"] == 1
    assert diagnostics["summary"]["eval"]["bad_prediction"] == 1
    assert diagnostics["summary"]["eval"]["missing_result"] == 1
    assert diagnostics["summary"]["duplicate_keys"] == 1
    assert diagnostics["summary"]["orphan_results"] == 1
