#!/usr/bin/env python
"""Diagnose the state of a model run under predictions/<model_id>/."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


FILENAME_RE = re.compile(
    r"^(?P<file_id>\d{3})_(?P<run_id>\d{2})_(?P<date>\d{8})_(?P<kind>prediction|results)\.json$"
)


@dataclass(frozen=True)
class FileRecord:
    path: Path
    file_id: str
    run_id: str
    date_stamp: str
    kind: str


def parse_record(path: Path) -> Optional[FileRecord]:
    match = FILENAME_RE.match(path.name)
    if not match:
        return None
    return FileRecord(
        path=path,
        file_id=match.group("file_id"),
        run_id=match.group("run_id"),
        date_stamp=match.group("date"),
        kind=match.group("kind"),
    )


def discover_ids(data_dir: Path, suffix: str) -> List[str]:
    if not data_dir.exists():
        return []
    return sorted(p.stem for p in data_dir.glob(f"*.{suffix}") if p.stem.isdigit())


def load_json(path: Path) -> Tuple[Optional[dict], Optional[str]]:
    try:
        with open(path, "r") as f:
            return json.load(f), None
    except Exception as exc:
        return None, str(exc)


def is_bad_prediction(path: Path) -> Tuple[bool, Optional[str]]:
    payload, error = load_json(path)
    if error:
        return True, f"Unreadable JSON: {error}"
    if payload is None:
        return True, "Missing JSON payload"
    if payload.get("error"):
        return True, str(payload["error"])
    return False, None


def collect_records(paths: Iterable[Path]) -> Dict[Tuple[str, str], List[FileRecord]]:
    grouped: Dict[Tuple[str, str], List[FileRecord]] = defaultdict(list)
    for path in paths:
        record = parse_record(path)
        if record is None:
            continue
        grouped[(record.file_id, record.run_id)].append(record)
    for records in grouped.values():
        records.sort(key=lambda r: (r.date_stamp, r.path.name))
    return grouped


def summarize_group(records: List[FileRecord]) -> Tuple[Optional[FileRecord], List[FileRecord]]:
    if not records:
        return None, []
    return records[-1], records[:-1]


def build_expected_run_ids(expected_runs: int) -> List[str]:
    return [f"{i:02d}" for i in range(1, expected_runs + 1)]


def analyze_model(
    project_root: Path,
    model_id: str,
    expected_runs: int,
) -> dict:
    model_dir = project_root / "predictions" / model_id
    sample_pred_dir = model_dir / "predictions" / "sample"
    eval_pred_dir = model_dir / "predictions" / "eval"
    eval_res_dir = model_dir / "results" / "eval"

    sample_ids = discover_ids(project_root / "data" / "sample", "png")
    eval_png_ids = set(discover_ids(project_root / "data" / "eval", "png"))
    eval_json_ids = set(discover_ids(project_root / "data" / "eval", "json"))
    eval_ids = sorted(eval_png_ids | eval_json_ids)
    run_ids = build_expected_run_ids(expected_runs)

    sample_preds = collect_records(sample_pred_dir.glob("*_prediction.json"))
    eval_preds = collect_records(eval_pred_dir.glob("*_prediction.json"))
    eval_results = collect_records(eval_res_dir.glob("*_results.json"))

    diagnostics = {
        "model_id": model_id,
        "model_dir": str(model_dir),
        "expected_runs": run_ids,
        "sample_ids": sample_ids,
        "eval_ids": eval_ids,
        "summary": {},
        "sample": [],
        "eval": [],
        "duplicates": [],
        "orphan_results": [],
        "nonstandard_files": [],
    }

    for folder in (sample_pred_dir, eval_pred_dir, eval_res_dir):
        if folder.exists():
            for path in folder.iterdir():
                if path.is_file() and parse_record(path) is None:
                    diagnostics["nonstandard_files"].append(str(path))

    sample_ok = sample_missing = sample_bad = 0
    eval_ok = eval_missing = eval_bad = eval_missing_result = 0
    result_count = 0

    for file_id in sample_ids:
        for run_id in run_ids:
            latest, duplicates = summarize_group(sample_preds.get((file_id, run_id), []))
            if duplicates:
                diagnostics["duplicates"].append(
                    {
                        "split": "sample",
                        "file_id": file_id,
                        "run_id": run_id,
                        "files": [str(r.path) for r in duplicates + ([latest] if latest else [])],
                    }
                )
            if latest is None:
                sample_missing += 1
                diagnostics["sample"].append(
                    {"file_id": file_id, "run_id": run_id, "status": "missing_prediction"}
                )
                continue

            bad, reason = is_bad_prediction(latest.path)
            if bad:
                sample_bad += 1
                diagnostics["sample"].append(
                    {
                        "file_id": file_id,
                        "run_id": run_id,
                        "status": "bad_prediction",
                        "prediction": str(latest.path),
                        "reason": reason,
                    }
                )
            else:
                sample_ok += 1
                diagnostics["sample"].append(
                    {
                        "file_id": file_id,
                        "run_id": run_id,
                        "status": "ok",
                        "prediction": str(latest.path),
                    }
                )

    for file_id in eval_ids:
        for run_id in run_ids:
            latest_pred, pred_duplicates = summarize_group(eval_preds.get((file_id, run_id), []))
            latest_res, res_duplicates = summarize_group(eval_results.get((file_id, run_id), []))

            if pred_duplicates:
                diagnostics["duplicates"].append(
                    {
                        "split": "eval_prediction",
                        "file_id": file_id,
                        "run_id": run_id,
                        "files": [str(r.path) for r in pred_duplicates + ([latest_pred] if latest_pred else [])],
                    }
                )
            if res_duplicates:
                diagnostics["duplicates"].append(
                    {
                        "split": "eval_result",
                        "file_id": file_id,
                        "run_id": run_id,
                        "files": [str(r.path) for r in res_duplicates + ([latest_res] if latest_res else [])],
                    }
                )

            entry = {"file_id": file_id, "run_id": run_id}
            if latest_pred is None:
                eval_missing += 1
                entry["status"] = "missing_prediction"
                diagnostics["eval"].append(entry)
                continue

            bad, reason = is_bad_prediction(latest_pred.path)
            entry["prediction"] = str(latest_pred.path)

            if bad:
                eval_bad += 1
                entry["status"] = "bad_prediction"
                entry["reason"] = reason
                if latest_res is not None:
                    result_count += 1
                    entry["result"] = str(latest_res.path)
                diagnostics["eval"].append(entry)
                continue

            if latest_res is None:
                eval_missing_result += 1
                entry["status"] = "missing_result"
                diagnostics["eval"].append(entry)
                continue

            eval_ok += 1
            result_count += 1
            entry["status"] = "ok"
            entry["result"] = str(latest_res.path)
            diagnostics["eval"].append(entry)

    for key, records in eval_results.items():
        if key not in eval_preds:
            latest_res, _ = summarize_group(records)
            if latest_res is not None:
                diagnostics["orphan_results"].append(str(latest_res.path))

    diagnostics["summary"] = {
        "sample": {
            "ok": sample_ok,
            "missing_prediction": sample_missing,
            "bad_prediction": sample_bad,
            "expected_total": len(sample_ids) * len(run_ids),
        },
        "eval": {
            "ok": eval_ok,
            "missing_prediction": eval_missing,
            "bad_prediction": eval_bad,
            "missing_result": eval_missing_result,
            "results_present": result_count,
            "expected_total": len(eval_ids) * len(run_ids),
        },
        "duplicate_keys": len(diagnostics["duplicates"]),
        "orphan_results": len(diagnostics["orphan_results"]),
        "nonstandard_files": len(diagnostics["nonstandard_files"]),
    }
    return diagnostics


def print_report(diagnostics: dict, show_details: bool) -> None:
    summary = diagnostics["summary"]
    print(f"Model: {diagnostics['model_id']}")
    print(f"Directory: {diagnostics['model_dir']}")
    print(f"Expected runs: {', '.join(diagnostics['expected_runs'])}")
    print("")
    print("Sample:")
    print(
        "  ok={ok} missing_prediction={missing_prediction} bad_prediction={bad_prediction} total={expected_total}".format(
            **summary["sample"]
        )
    )
    print("Eval:")
    print(
        "  ok={ok} missing_prediction={missing_prediction} bad_prediction={bad_prediction} missing_result={missing_result} results_present={results_present} total={expected_total}".format(
            **summary["eval"]
        )
    )
    print(
        "Other: duplicate_keys={duplicate_keys} orphan_results={orphan_results} nonstandard_files={nonstandard_files}".format(
            **summary
        )
    )

    if not show_details:
        return

    def emit(title: str, rows: List[dict]) -> None:
        if not rows:
            return
        print("")
        print(title)
        for row in rows:
            print(json.dumps(row, sort_keys=True))

    emit(
        "Sample Issues",
        [row for row in diagnostics["sample"] if row["status"] != "ok"],
    )
    emit(
        "Eval Issues",
        [row for row in diagnostics["eval"] if row["status"] != "ok"],
    )
    emit("Duplicates", diagnostics["duplicates"])
    if diagnostics["orphan_results"]:
        print("")
        print("Orphan Results")
        for path in diagnostics["orphan_results"]:
            print(path)
    if diagnostics["nonstandard_files"]:
        print("")
        print("Nonstandard Files")
        for path in diagnostics["nonstandard_files"]:
            print(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model_id", help="Model ID under predictions/<model_id>/")
    parser.add_argument(
        "--expected-runs",
        type=int,
        default=3,
        help="Expected number of runs per page (default: 3)",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Project root containing predictions/ and data/ (default: repo root)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the full diagnostic payload as JSON",
    )
    parser.add_argument(
        "--details",
        action="store_true",
        help="Print detailed issue lists in text mode",
    )
    args = parser.parse_args()

    diagnostics = analyze_model(
        project_root=args.project_root,
        model_id=args.model_id,
        expected_runs=args.expected_runs,
    )

    if args.json:
        print(json.dumps(diagnostics, indent=2, sort_keys=True))
    else:
        print_report(diagnostics, show_details=args.details)


if __name__ == "__main__":
    main()
