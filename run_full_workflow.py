"""Execute the Opportunity Discovery Framework end-to-end (Phase 0-4).

This runner orchestrates:
1) Phase 0 watchlist scan (delegates to watchlist_scanner.py)
2) Phase 1 candidate generation from watchlist + specialty sources
3) Phase 2 binary kill gates
4) Phase 3 lightweight deep validation and scoring
5) Phase 4 ranking and reporting outputs
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

import httpx


@dataclass
class Candidate:
    name: str
    source_type: str
    data_source: str
    source_detail: str
    query_pattern: str
    example_queries: list[str]
    monetization_model: str
    status: str = "pending"
    kill_reason: str = ""
    data_accessible: bool = False
    demand_signal_count: int = 0
    pain_signal_count: int = 0
    competition_signal: str = ""
    score_data_quality: int = 0
    score_search_demand: int = 0
    score_competition_gap: int = 0
    score_monetization_clarity: int = 0
    score_build_feasibility: int = 0
    score_defensibility: int = 0
    composite: float = 0.0
    verdict: str = "KILL"


def run_phase0(state_dir: Path, output_dir: Path, lookback_days: int) -> None:
    cmd = [
        "python",
        "watchlist_scanner.py",
        "--state-dir",
        str(state_dir),
        "--output-dir",
        str(output_dir),
        "--lookback-days",
        str(lookback_days),
    ]
    subprocess.run(cmd, check=True)


def load_watchlist(output_dir: Path) -> list[dict]:
    leads_file = output_dir / "watchlist_leads.json"
    if not leads_file.exists():
        return []
    return json.loads(leads_file.read_text())


def pick_lead(leads: list[dict], contains: str) -> dict | None:
    contains = contains.lower()
    for lead in leads:
        blob = f"{lead.get('title', '')} {lead.get('description', '')}".lower()
        if contains in blob and not lead.get("is_reserved", False):
            return lead
    return None


def fetch_ok(client: httpx.Client, url: str) -> bool:
    try:
        r = client.get(url, timeout=25, follow_redirects=True)
        return r.status_code < 400
    except Exception:
        return False


def bing_autocomplete_count(client: httpx.Client, query: str) -> int:
    """Count autocomplete suggestions as demand evidence."""
    try:
        r = client.get("https://api.bing.com/osjson.aspx", params={"query": query}, timeout=25)
        payload = r.json()
    except Exception:
        return 0
    if not isinstance(payload, list) or len(payload) < 2:
        return 0
    suggestions = payload[1]
    return len(suggestions) if isinstance(suggestions, list) else 0


def fetch_bing_rss(client: httpx.Client, query: str) -> str:
    try:
        r = client.get("https://www.bing.com/search", params={"q": query, "format": "rss"}, timeout=25)
        return r.text
    except Exception:
        return ""


def domain_diversity(blob: str) -> int:
    domains = set(re.findall(r"https?://([^/\"'\s<]+)", blob.lower()))
    return len(domains)


def evaluate_candidates(candidates: list[Candidate]) -> list[Candidate]:
    with httpx.Client(headers={"user-agent": "Mozilla/5.0 (compatible; workflow-runner/1.0)"}) as client:
        for c in candidates:
            c.data_accessible = fetch_ok(client, c.data_source)
            if not c.data_accessible:
                c.status = "killed"
                c.kill_reason = "Data source unreachable"
                continue

            # Demand gate
            demand_hits = 0
            serp_blob = ""
            for q in c.example_queries:
                demand_hits += bing_autocomplete_count(client, q)
                serp_blob += fetch_bing_rss(client, q)
            c.demand_signal_count = demand_hits

            if demand_hits < 3:
                c.status = "killed"
                c.kill_reason = "Insufficient search signals"
                continue

            diversity = domain_diversity(serp_blob)
            c.competition_signal = f"~{diversity} unique domains in sampled SERPs"
            if diversity <= 1:
                c.status = "killed"
                c.kill_reason = "SERP appears too thin/noisy to validate"
                continue

            # Phase 3 scoring (heuristic but evidence-backed)
            c.pain_signal_count = bing_autocomplete_count(client, f"site:reddit.com {c.query_pattern} frustrating")
            c.score_data_quality = 8 if c.source_type in {"api", "open_data_portal"} else 6
            c.score_search_demand = 6 + min(3, c.demand_signal_count // 8)
            c.score_competition_gap = 5 + (2 if diversity > 6 else 1)
            c.score_monetization_clarity = 7
            c.score_build_feasibility = 8
            c.score_defensibility = 5 + min(3, c.pain_signal_count // 10)
            c.composite = round(
                (
                    c.score_data_quality
                    + c.score_search_demand
                    + c.score_competition_gap
                    + c.score_monetization_clarity
                    + c.score_build_feasibility
                    + c.score_defensibility
                )
                / 6,
                2,
            )

            c.status = "survived"
            if c.composite >= 7.0:
                c.verdict = "BUILD"
            elif c.composite >= 5.0:
                c.verdict = "BACKLOG"
            else:
                c.verdict = "KILL"

    return candidates


def write_outputs(output_dir: Path, candidates: list[Candidate]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    pipeline = {
        "run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "framework_version": "v2",
        "candidates": [asdict(c) for c in candidates],
    }
    (output_dir / "pipeline.json").write_text(json.dumps(pipeline, indent=2))

    survivors = [c for c in candidates if c.status == "survived"]
    lines = [
        "# Opportunity Pipeline Report",
        "",
        f"Run date (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
        f"Total candidates: {len(candidates)}",
        f"Survivors after Phase 2: {len(survivors)}",
        "",
        "## Ranked Opportunities",
        "",
    ]

    ranked = sorted(survivors, key=lambda c: c.composite, reverse=True)
    for i, c in enumerate(ranked, 1):
        lines.extend(
            [
                f"### {i}. {c.name}",
                f"- Verdict: **{c.verdict}**",
                f"- Composite: **{c.composite}**",
                f"- Data source: {c.data_source}",
                f"- Query pattern: `{c.query_pattern}`",
                f"- Demand signals: {c.demand_signal_count}",
                f"- Pain signals: {c.pain_signal_count}",
                f"- Competition signal: {c.competition_signal}",
                f"- Monetization: {c.monetization_model}",
                "",
            ]
        )

    killed = [c for c in candidates if c.status == "killed"]
    lines.extend(["## Killed Candidates", ""])
    for c in killed:
        lines.append(f"- {c.name}: {c.kill_reason}")

    (output_dir / "pipeline-report.md").write_text("\n".join(lines) + "\n")

    for c in ranked:
        if c.verdict == "BUILD":
            slug = re.sub(r"[^a-z0-9]+", "-", c.name.lower()).strip("-")
            doc = [
                f"# Build Skeleton: {c.name}",
                "",
                "## MVP Scope (2-4 weeks)",
                "- Dataset ingestion cron",
                "- Entity detail pages + index pages",
                "- Search + filter UI",
                "- Basic ad/affiliate placements",
                "",
                "## Data Pipeline",
                f"- Ingest from: {c.data_source}",
                "- Normalize schema to D1 tables",
                "- Generate static-friendly page caches in KV",
                "- Publish sitemap shards",
                "",
                "## Monetization",
                f"- Model: {c.monetization_model}",
                "- Add premium alerting as upsell",
                "",
            ]
            (output_dir / f"build-spec-{slug}.md").write_text("\n".join(doc))


def generate_phase1_candidates(leads: list[dict]) -> list[Candidate]:
    ny_liquor = pick_lead(leads, "liquor authority active licenses")
    tx_insurance = pick_lead(leads, "insurance company appointments")

    return [
        Candidate(
            name="FDA Adverse Event Lookup",
            source_type="api",
            data_source="https://api.fda.gov/drug/event.json?limit=1",
            source_detail="openFDA drug/device adverse event endpoints",
            query_pattern="[drug name] adverse event reports",
            example_queries=[
                "Ozempic adverse event reports",
                "metformin side effect report database",
                "medical device adverse event lookup",
            ],
            monetization_model="Ads + affiliate links to telehealth/pharmacy comparison",
        ),
        Candidate(
            name="CPSC Recall Intelligence",
            source_type="api",
            data_source="https://www.saferproducts.gov/RestWebServices/Recall?format=json&RecallDateStart=2026-01-01",
            source_detail="CPSC recall feed + category indexing",
            query_pattern="[product] recall status",
            example_queries=[
                "space heater recall status",
                "stroller recall lookup",
                "kitchen appliance recall list",
            ],
            monetization_model="Ads + retailer affiliate replacements",
        ),
        Candidate(
            name="NY Liquor License Monitor",
            source_type="open_data_portal",
            data_source=(ny_liquor or {}).get("data_url", "https://data.ny.gov"),
            source_detail=(ny_liquor or {}).get("title", "NY open data liquor licenses"),
            query_pattern="[bar name] liquor license status",
            example_queries=[
                "Brooklyn bar liquor license status",
                "New York SLA active license lookup",
                "restaurant liquor license pending NY",
            ],
            monetization_model="Lead gen for legal/compliance consultants",
        ),
        Candidate(
            name="Texas Insurance Appointment Finder",
            source_type="open_data_portal",
            data_source=(tx_insurance or {}).get("data_url", "https://data.texas.gov"),
            source_detail=(tx_insurance or {}).get("title", "TX insurance appointment dataset"),
            query_pattern="[agent name] insurance appointment texas",
            example_queries=[
                "Texas insurance agent appointment lookup",
                "is adjuster licensed in Texas",
                "insurance company appointment active Texas",
            ],
            monetization_model="Lead gen for compliance SaaS + directories",
        ),
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run full opportunity workflow")
    parser.add_argument("--state-dir", default="./state")
    parser.add_argument("--output-dir", default="./output")
    parser.add_argument("--lookback-days", type=int, default=30)
    args = parser.parse_args()

    state_dir = Path(args.state_dir)
    output_dir = Path(args.output_dir)

    run_phase0(state_dir, output_dir, args.lookback_days)
    leads = load_watchlist(output_dir)
    candidates = generate_phase1_candidates(leads)
    evaluated = evaluate_candidates(candidates)
    write_outputs(output_dir, evaluated)


if __name__ == "__main__":
    main()
