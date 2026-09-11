#!/usr/bin/env python3
"""Refresh public OpenRouter quotes; direct API overrides must be verified.

No API key required. Snapshot only exact configured model IDs; never substitute
an alias, route, or newer model for a missing listing.
"""
import json
import math
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CATALOG_URL = "https://openrouter.ai/api/v1/models"


def main():
    config = tomllib.loads((ROOT / "config/models.toml").read_text())
    with urlopen(Request(CATALOG_URL, headers={"User-Agent": "Dorrit-Pricing/1.0"}), timeout=60) as response:
        catalog = {model["id"]: model for model in json.load(response)["data"]}
    overrides = json.loads((ROOT / "config/model_pricing_overrides.json").read_text())
    models = {}
    for row in json.loads((ROOT / "docs/results.json").read_text()):
        model_id = row["model_id"]
        configured = config.get(model_id, {})
        api_id = configured.get("model_name")
        route = "OpenRouter" if "openrouter.ai" in configured.get("endpoint", "") else "Direct API"
        if model_id in overrides:
            models[model_id] = {**overrides[model_id], "api_model": api_id}
        elif route == "OpenRouter" and api_id in catalog:
            pricing = catalog[api_id].get("pricing", {})
            if pricing.get("prompt") is None or pricing.get("completion") is None:
                continue
            input_price, output_price = float(pricing["prompt"]) * 1e6, float(pricing["completion"]) * 1e6
            if not all(math.isfinite(p) and p >= 0 for p in [input_price, output_price]):
                continue
            models[model_id] = {
                "api_model": api_id, "route": route,
                "input_per_million": input_price,
                "output_per_million": output_price,
                "source": f"https://openrouter.ai/{api_id}",
                "verified_at": datetime.now(timezone.utc).date().isoformat(),
                "provider_pricing": pricing,
            }
    snapshot = {
        "fetched_at": datetime.now(timezone.utc).isoformat(), "currency": "USD",
        "basis": "Standard uncached text token rates. OpenRouter quotes use the listed starting rate. Actual routing, context tiers, images, caching, and reasoning usage can change the bill.",
        "catalog_source": CATALOG_URL, "models": models,
    }
    (ROOT / "docs/pricing.json").write_text(json.dumps(snapshot, indent=2) + "\n")
    print(f"Saved verified quotes for {len(models)} leaderboard entries")


if __name__ == "__main__":
    main()
