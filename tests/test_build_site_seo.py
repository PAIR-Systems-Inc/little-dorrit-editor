"""Crawler snapshots must be accurate, escaped, and reproducible."""
import importlib.util
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("build_site_seo", Path(__file__).resolve().parents[1] / "scripts/build_site_seo.py")
seo = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(seo)


def test_scores_match_client_aggregation_and_legacy_shape():
    rows = seo.scores([
        {"model_id": "a", "file_results": [{"details": [{"tp": .5, "fp": .5, "fn": 1}]}, {"details": {"edit_matches": [{"tp": 1, "fp": 0, "fn": 0}]}}]},
        {"model_id": "empty", "file_results": []},
    ])
    assert rows[0]["precision"] == .75
    assert rows[0]["recall"] == .6
    assert rows[0]["f1_score"] == pytest.approx(2 / 3)
    assert rows[1]["f1_score"] == 0


def test_unknown_prices_are_not_zero():
    row = {"model_id": "a"}
    assert seo.price_pair(row, {}) == ["Unknown", "Unknown"]
    assert seo.price_pair(row, {"models": {"a": {"input_per_million": 0, "output_per_million": 0}}}) == ["$0.00", "$0.00"]
    assert seo.price_pair(row, {"models": {"a": {"input_per_million": -1, "output_per_million": 0}}}) == ["Unknown", "Unknown"]


def test_table_escapes_names_and_retains_columns():
    row = {"model_id": 'a"', "model_name": '<script>alert("x")</script>', "f1_score": .5, "precision": .5, "recall": .5}
    table = seo.ranking_table([row])
    assert "<script>" not in table
    assert "&lt;script&gt;" in table
    assert table.count('scope="col"') == 8
    assert table.count('scope="row"') == 1
    assert 'data-model-id="a&quot;"' in table


def test_build_is_deterministic_and_valid(tmp_path):
    model = {"model_id": "or_test", "model_name": "Test (OR)", "shots": 0, "date": "2026-09-01T00:00:00", "file_results": [{"details": [{"tp": 1}]}]}
    (tmp_path / "results.json").write_text(json.dumps([model]))
    (tmp_path / "pricing.json").write_text(json.dumps({"fetched_at": "2026-09-02T00:00:00", "models": {}}))
    (tmp_path / "index.html").write_text('\n'.join(f'<!-- {key}:START --><!-- {key}:END -->' for key in ["SEO", "STATIC_RESULTS", "UPDATED"]))
    first = seo.build(tmp_path)
    (tmp_path / "index.html").write_text(first["index.html"])
    assert seo.build(tmp_path) == first
    assert "0-shot" in first["rankings.md"]
    assert "Unknown" in first["rankings.md"]
    assert 'datetime="2026-09-01"' in first["index.html"]
    root = ET.fromstring(first["sitemap.xml"])
    urls = [element.text for element in root.iter() if element.tag.endswith("}loc")]
    assert urls == [seo.BASE, seo.BASE + "rankings.html", seo.BASE + "technical-report.pdf"]
    assert "lastmod" not in first["sitemap.xml"]
    schema = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', first["index.html"]).group(1))
    assert {node["@type"] for node in schema["@graph"]} == {"WebSite", "WebPage", "Dataset"}
    assert first["llms.txt"].startswith("# Little Dorrit")
    assert "Disallow:" not in first["robots.txt"]


def test_marker_errors_fail_closed():
    with pytest.raises(ValueError):
        seo.replace_block("missing", "SEO", "content")
