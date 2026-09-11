#!/usr/bin/env python3
"""Generate deterministic crawler-readable pages from the published results.

No network or third-party dependencies. Run after changing results/pricing or
site copy; Pages also runs this before deployment. --check detects stale output.
"""
import argparse
import html
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://dorrit.pairsys.ai/"
REPO = "https://github.com/PAIR-Systems-Inc/little-dorrit-editor"
TITLE = "Little Dorrit: Vision Model Benchmark & Leaderboard"
DESCRIPTION = (
    "Compare vision language models on handwritten editing corrections. "
    "Explore F1 scores, precision, recall, token prices, and benchmark results."
)


def scores(models):
    """Match processModelResults in leaderboard.js, including legacy matches."""
    rows = []
    for model in models:
        tp = fp = fn = 0
        for file in model.get("file_results", []):
            details = file.get("details")
            matches = details if isinstance(details, list) else (details or {}).get("edit_matches", [])
            for edit in matches:
                tp += edit.get("tp") or 0
                fp += edit.get("fp") or 0
                fn += edit.get("fn") or 0
        precision = tp / (tp + fp) if tp + fp else 0
        recall = tp / (tp + fn) if tp + fn else 0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0
        rows.append({**model, "precision": precision, "recall": recall, "f1_score": f1})
    return sorted(rows, key=lambda row: -row["f1_score"])


def name(row):
    label = re.sub(r"\s*\(OR\)", "", row["model_name"]) + row.get("display_suffix", "")
    route = " · OpenRouter" if row.get("model_id", "").startswith("or_") else ""
    return f"{label}{route} · {row.get('shots', 2)}-shot"


def price_pair(row, pricing):
    price = pricing.get("models", {}).get(row["model_id"], {})
    values = [price.get("input_per_million"), price.get("output_per_million")]
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v >= 0 for v in values):
        return ["Unknown", "Unknown"]
    return [f"${value:,.4f}" if 0 < value < .01 else f"${value:,.2f}" for value in values]


def ranking_table(rows):
    headings = ["Rank", "Model / route / shots", "F1", "95% CI", "Precision", "Recall", "Eval date", "Date released"]
    table = ['<div class="static-table-scroll" tabindex="0" role="region" aria-label="Scrollable benchmark rankings"><table class="static-table">',
             '<caption>All benchmark models, ordered by F1. Confidence intervals are calculated in the interactive view.</caption>',
             '<thead><tr>' + ''.join(f'<th scope="col">{text}</th>' for text in headings) + '</tr></thead><tbody>']
    for rank, row in enumerate(rows, 1):
        cells = [str(rank), name(row), f"{row['f1_score']:.4f}", "See interactive view", f"{row['precision']:.4f}", f"{row['recall']:.4f}",
                 (row.get("date") or "Unknown").split("T")[0], row.get("release_display") or row.get("release_date") or "Unknown"]
        rendered = ''.join(f'<th scope="row">{html.escape(value)}</th>' if i == 1 else f'<td>{html.escape(value)}</td>' for i, value in enumerate(cells))
        table.append(f'<tr data-model-id="{html.escape(row["model_id"], quote=True)}">{rendered}</tr>')
    return '\n'.join(table) + '\n</tbody></table></div>'


def metadata(canonical, title):
    graph = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "WebSite", "@id": BASE + "#website", "url": BASE, "name": "Little Dorrit Editor Benchmark", "inLanguage": "en"},
            {"@type": "WebPage", "@id": canonical + "#webpage", "url": canonical, "name": title,
             "description": DESCRIPTION, "inLanguage": "en", "isPartOf": {"@id": BASE + "#website"}, "mainEntity": {"@id": BASE + "#dataset"}},
            {"@type": "Dataset", "@id": BASE + "#dataset", "url": BASE + "rankings.html",
             "name": "Little Dorrit Editor benchmark results",
             "description": "Model evaluations on handwritten corrections to printed pages from Little Dorrit. Results include edit-level matches used to calculate precision, recall, and F1.",
             "isAccessibleForFree": True, "inLanguage": "en",
             "creator": {"@type": "Organization", "name": "Little Dorrit Editor Contributors", "url": REPO},
             "license": REPO + "/blob/main/LICENSE",
             "citation": BASE + "technical-report.pdf",
             "variableMeasured": ["F1", "Precision", "Recall"],
             "distribution": {"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": BASE + "results.json"}},
        ],
    }
    markdown = "index.md" if canonical == BASE else "rankings.md"
    escaped_title = html.escape(title, quote=True)
    return f'''<title>{escaped_title}</title>
    <meta name="description" content="{DESCRIPTION}">
    <meta name="robots" content="index, follow, max-image-preview:large">
    <link rel="canonical" href="{canonical}">
    <link rel="alternate" type="text/markdown" href="{BASE}{markdown}" title="Markdown version">
    <link rel="describedby" href="{BASE}llms.txt" type="text/plain">
    <link rel="icon" href="/dorrit.png" type="image/png">
    <meta property="og:type" content="website">
    <meta property="og:site_name" content="Little Dorrit Editor Benchmark">
    <meta property="og:title" content="{escaped_title}">
    <meta property="og:description" content="{DESCRIPTION}">
    <meta property="og:url" content="{canonical}">
    <meta property="og:image" content="{BASE}dorrit.png">
    <meta property="og:image:alt" content="Portrait of Little Dorrit, the benchmark’s namesake">
    <meta name="twitter:card" content="summary">
    <meta name="twitter:title" content="{escaped_title}">
    <meta name="twitter:description" content="{DESCRIPTION}">
    <meta name="twitter:image" content="{BASE}dorrit.png">
    <meta name="twitter:image:alt" content="Portrait of Little Dorrit, the benchmark’s namesake">
    <script type="application/ld+json">{json.dumps(graph, ensure_ascii=False).replace('<', chr(92) + 'u003c')}</script>'''


def replace_block(source, key, content):
    pattern = rf"<!-- {key}:START -->.*?<!-- {key}:END -->"
    if len(re.findall(pattern, source, re.S)) != 1:
        raise ValueError(f"Expected exactly one {key} generated block")
    return re.sub(pattern, lambda _: f"<!-- {key}:START -->\n{content}\n    <!-- {key}:END -->", source, flags=re.S)


def markdown_cell(value):
    return str(value).replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ").replace("<", "&lt;").replace(">", "&gt;")


def build(site):
    rows = scores(json.loads((site / "results.json").read_text()))
    if not rows:
        raise ValueError("Cannot publish an empty leaderboard")
    pricing = json.loads((site / "pricing.json").read_text())
    latest = max((row.get("date") or "")[:10] for row in rows)
    table = ranking_table(rows)
    notes = '<p>Scores pool edit-level true positives, false positives, and false negatives across evaluated pages and runs. Higher is better. Small score differences may not be meaningful; use the interactive F1 confidence intervals when comparing models.</p><p>* Claude-family images are resized and recompressed as needed for Anthropic’s image limit. Other model-specific caveats appear in the interactive view.</p>'
    downloads = '<p><a href="/">Interactive leaderboard</a> · <a href="/rankings.md">Rankings and pricing in Markdown</a> · <a href="/results.json">Raw results JSON</a> · <a href="/pricing.json">Pricing JSON</a> · <a href="/technical-report.pdf">Technical report</a></p>'
    caveats = ''.join(f'<li>{html.escape(name(row))}: {html.escape(row["display_note"])}</li>' for row in rows if row.get("display_note"))
    if caveats:
        notes += f'<details><summary>Model-specific caveats</summary><ul>{caveats}</ul></details>'
    snapshot = f'''<section id="static-results" class="static-results" aria-labelledby="static-results-title">
    <h2 id="static-results-title">Benchmark rankings</h2>
    <p>{len(rows)} models. Latest benchmark run: <time datetime="{latest}">{latest}</time>. This snapshot is available without JavaScript.</p>
    {table}
    {notes}
    {downloads}
    </section>'''
    source = (site / "index.html").read_text()
    source = replace_block(source, "SEO", metadata(BASE, TITLE))
    source = replace_block(source, "STATIC_RESULTS", snapshot)
    source = replace_block(source, "UPDATED", f'<p class="updated">Latest benchmark run: <time id="last-updated" datetime="{latest}">{latest}</time></p>')

    ranking_md = f"# Little Dorrit benchmark rankings\n\n{len(rows)} models. Latest benchmark run: {latest}.\n\n"
    ranking_md += "Scores pool edit-level TP, FP, and FN across evaluated pages and runs. Precision = TP / (TP + FP); recall = TP / (TP + FN); F1 is their harmonic mean. Higher is better. Zero-denominator scores are zero. F1 confidence intervals are calculated in the interactive site; small differences may not be meaningful.\n\n"
    ranking_md += f"Pricing snapshot: {pricing['fetched_at'][:10]} (UTC). Prices are USD per million tokens for the exact benchmark route. Standard uncached text rates; OpenRouter starting rates may vary by provider. Unknown means unverified, not free. These are not measured costs per page. Images, caching, context tiers, reasoning, and fees can change actual bills. Historical usage is unknown when not recorded.\n\n"
    ranking_md += "| Rank | Model / route / shots | F1 | Precision | Recall | Input / 1M | Output / 1M | Evaluated | Released |\n|---:|:---|---:|---:|---:|---:|---:|:---|:---|\n"
    for rank, row in enumerate(rows, 1):
        cells = [rank, name(row), f"{row['f1_score']:.4f}", f"{row['precision']:.4f}", f"{row['recall']:.4f}", *price_pair(row, pricing), (row.get("date") or "Unknown")[:10], row.get("release_display") or row.get("release_date") or "Unknown"]
        ranking_md += "| " + " | ".join(map(markdown_cell, cells)) + " |\n"
    ranking_md += "\n## Caveats\n\n* marks an image-preprocessing caveat. Claude-family images are resized and recompressed for Anthropic’s image limit. See each model’s notes below.\n\n"
    ranking_md += '\n'.join(f'- {markdown_cell(name(row))}: {markdown_cell(row["display_note"])}' for row in rows if row.get("display_note"))
    ranking_md += f"\n\n## Sources\n\n- [Raw results]({BASE}results.json)\n- [Pricing and per-model verification/source URLs]({BASE}pricing.json)\n- [Technical report]({BASE}technical-report.pdf)\n- [Interactive leaderboard]({BASE})\n"

    intro = f'''# Little Dorrit Editor Benchmark

> Vision language models reading handwritten corrections on printed pages from Charles Dickens’ Little Dorrit.

Given a scanned page, each model identifies the edits and returns the original text, intended correction, and location as JSON. Recognizing words is only part of the task: a model must also interpret carets, crossed-out phrases, and handwritten punctuation.

## Task and evaluation

Each correction includes an edit type (insertion, deletion, replacement, punctuation, capitalization, or italicize), original text, corrected text, line number, and the supplied page identifier. Line 0 is for titles or headings; body text begins at line 1. Predicted edits are compared with ground truth using an LLM judge. Scores aggregate TP, FP, and FN across pages and runs.

The interactive site offers Performance, Token price, Value & frontier, Rankings, and Detailed results. Performance defaults to all models. The value view compares F1 with an illustrative token workload, using logarithmic cost spacing and linear F1. It is not a measured cost-per-page chart. Confidence intervals help interpret close F1 scores; a point-estimate Pareto frontier does not incorporate that uncertainty.

## Data and documentation

- [Complete rankings, pricing, and caveats]({BASE}rankings.md)
- [Static HTML rankings]({BASE}rankings.html)
- [Raw edit-level results]({BASE}results.json)
- [Dated pricing snapshot and sources]({BASE}pricing.json)
- [Technical report]({BASE}technical-report.pdf)
- [Example page]({BASE}001.png)
- [Code and experiment configurations]({REPO})
- [Dataset](https://huggingface.co/datasets/pairsys/little-dorrit-editor)
'''
    llms = f'''# Little Dorrit Editor Benchmark

> A benchmark of vision language models interpreting handwritten editorial corrections on printed pages from Little Dorrit.

Use the dated results and exact model routes. Higher F1 is better, but small differences may not be meaningful. Missing prices or historical usage mean unknown, not zero. Token-price comparisons are not measured cost per page. OpenRouter and direct API entries are distinct benchmark routes.

## Benchmark

- [Overview and methodology]({BASE}index.md): Task, scoring, view definitions, and source links.
- [Rankings and token prices]({BASE}rankings.md): All models, dated prices, and preprocessing caveats.
- [Raw results]({BASE}results.json): Edit-level evaluated results.
- [Pricing snapshot]({BASE}pricing.json): Exact routes, source URLs, and verification dates.

## Optional

- [Technical report]({BASE}technical-report.pdf): Detailed benchmark methodology.
- [Repository]({REPO}): Code and experiment configurations.
- [Dataset](https://huggingface.co/datasets/pairsys/little-dorrit-editor): Annotated benchmark data.
'''
    standalone = f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
{metadata(BASE + 'rankings.html', 'Little Dorrit Benchmark Rankings — All Models')}
<link rel="stylesheet" href="/css/styles.css?v=explorer-10"></head><body>
<a class="skip-link" href="#main-content">Skip to content</a>
<header><h1>Little Dorrit benchmark rankings</h1><p><a href="/">Open the interactive leaderboard</a></p></header>
<main id="main-content" tabindex="-1">{snapshot}</main>
<footer><p><a href="/index.md">Methodology in Markdown</a> · <a href="/llms.txt">llms.txt</a></p></footer>
</body></html>
'''
    # Omit lastmod rather than invent a modification date for the page or PDF.
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + ''.join(f'  <url><loc>{BASE}{path}</loc></url>\n' for path in ['', 'rankings.html', 'technical-report.pdf']) + '</urlset>\n'
    return {"index.html": source, "rankings.html": standalone, "index.md": intro, "rankings.md": ranking_md,
            "llms.txt": llms, "robots.txt": f"User-agent: *\nAllow: /\n\nSitemap: {BASE}sitemap.xml\n", "sitemap.xml": sitemap}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    site = ROOT / "docs"
    outputs = build(site)
    stale = []
    for name_, content in outputs.items():
        path = site / name_
        if args.check:
            if not path.exists() or path.read_text() != content:
                stale.append(name_)
        else:
            path.write_text(content)
    if stale:
        raise SystemExit("Stale generated site files: " + ", ".join(stale))
    print(f"{'Checked' if args.check else 'Generated'} {len(outputs)} SEO/static files")


if __name__ == "__main__":
    main()
