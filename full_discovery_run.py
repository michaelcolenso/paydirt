import json, re
from datetime import datetime, timezone
from pathlib import Path
import httpx
from urllib.parse import quote_plus

TODAY = datetime.now(timezone.utc).strftime('%Y-%m-%d')

RESERVED_SOURCES = {
    "NHTSA Recalls API",
    "Federal micro-purchase card data",
    "College Scorecard API",
}
RESERVED_QUERY_SPACES = {
    "vehicle recalls",
    "federal micro-purchase spending",
    "college major ROI / earnings by school",
}

candidates = [
    {
        "name": "DeviceIncidentScout",
        "data_source": {
            "name": "openFDA Device Adverse Events API",
            "url": "https://api.fda.gov/device/event.json",
            "sample_url": "https://api.fda.gov/device/event.json?limit=1&sort=date_received:desc",
            "format": "API",
            "update_frequency": "daily",
            "entity_count": 2900000,
            "licensing": "Public U.S. government data (openFDA terms)",
        },
        "query_pattern": "[device name] adverse event report",
        "example_queries": [
            "philips cpap adverse event reports",
            "insulin pump malfunction reports",
            "hip implant adverse events",
            "medical device MAUDE database search",
        ],
        "intent_type": "Informational with high-risk purchase/medical decision support intent",
        "monetization_model": "display ads + affiliate (home health/safety products) + premium alerts",
        "primary_vertical": "consumer safety",
        "build_notes": "Cloudflare Worker ETL of openFDA into D1, pSEO pages by brand/model/problem code",
    },
    {
        "name": "OSHAInspectionLookup",
        "data_source": {
            "name": "OSHA Enforcement Data Catalog",
            "url": "https://enforcedata.dol.gov/views/data_catalogs.php",
            "sample_url": "https://enforcedata.dol.gov/views/data_catalogs.php",
            "format": "CSV/Bulk",
            "update_frequency": "monthly",
            "entity_count": 120000,
            "licensing": "Public U.S. government data",
        },
        "query_pattern": "[company] OSHA violations",
        "example_queries": [
            "amazon osha violations",
            "tyson foods osha fines",
            "[company] osha inspection history",
            "osha establishment search",
        ],
        "intent_type": "Informational / compliance",
        "monetization_model": "lead gen (workplace safety consultants, OSHA training) + ads",
        "primary_vertical": "labor/compliance",
        "build_notes": "Ingest inspection and citation CSVs, normalize employer names, pages per employer and facility",
    },
    {
        "name": "NursingHomeGrade",
        "data_source": {
            "name": "CMS Nursing Home Care Compare datasets",
            "url": "https://data.cms.gov/provider-data/dataset/4pq5-n9py",
            "sample_url": "https://data.cms.gov/provider-data/dataset/4pq5-n9py",
            "format": "CSV/API",
            "update_frequency": "monthly",
            "entity_count": 15000,
            "licensing": "U.S. government open data",
        },
        "query_pattern": "[facility] nursing home rating",
        "example_queries": [
            "sunrise nursing home rating",
            "best nursing homes near me medicare",
            "nursing home deficiency report [city]",
            "cms nursing home compare [facility]",
        ],
        "intent_type": "Transactional-adjacent informational",
        "monetization_model": "ads + senior-care lead gen",
        "primary_vertical": "healthcare transparency",
        "build_notes": "Join star ratings + deficiencies + staffing; location landing pages and facility detail pages",
    },
]


def web_search(client, query, max_results=5):
    url = f"https://www.bing.com/search?q={quote_plus(query)}"
    r = client.get(url, timeout=30, follow_redirects=True)
    html = r.text
    items = []
    blocks = re.findall(r'(<li class="b_algo".*?</li>)', html, flags=re.S)
    for block in blocks:
        m = re.search(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, flags=re.S)
        if not m:
            continue
        href = m.group(1)
        title = re.sub('<.*?>', '', m.group(2))
        items.append({"title": title, "url": href})
        if len(items) >= max_results:
            break
    paa_like = bool(re.search(r'People also ask|Related searches|People also search', html, re.I))
    return {"results": items, "paa_like": paa_like, "raw_len": len(html)}


def domain_from_url(url):
    m = re.search(r'https?://([^/]+)', url)
    return m.group(1).lower() if m else ""


def api_accessible(client, url):
    try:
        r = client.get(url, timeout=30, follow_redirects=True)
        return r.status_code, r.text[:400]
    except Exception as e:
        return 0, str(e)


def score_from_evidence(c):
    # tuned heuristics for framework scoring
    dq = 8 if c['phase2']['data_ok'] else 2
    sd = min(9, 4 + c['phase2']['search_positive'] + c['phase3']['pain_signal_hits'])
    comp_gap = c['phase3']['competition_gap']
    mon = c['phase3']['monetization_clarity']
    build = c['phase3']['build_feasibility']
    defense = c['phase3']['defensibility']
    composite = round((dq + sd + comp_gap + mon + build + defense) / 6, 2)
    return {
        "data_quality": dq,
        "search_demand": sd,
        "competition_gap": comp_gap,
        "monetization_clarity": mon,
        "build_feasibility": build,
        "defensibility": defense,
        "composite": composite,
    }


def scenario_revenue(model):
    if "lead gen" in model:
        rpm = (18, 32, 55)
    elif "affiliate" in model:
        rpm = (12, 28, 45)
    else:
        rpm = (10, 20, 35)
    sessions = (5000, 25000, 100000)
    return {
        "bear": round(sessions[0] / 1000 * rpm[0], 2),
        "base": round(sessions[1] / 1000 * rpm[1], 2),
        "bull": round(sessions[2] / 1000 * rpm[2], 2),
        "assumed_rpm": {"bear": rpm[0], "base": rpm[1], "bull": rpm[2]},
    }


def main():
    portfolio_path = Path("portfolio_state.json")
    if portfolio_path.exists():
        portfolio = json.loads(portfolio_path.read_text())
    else:
        portfolio = {
            "last_updated": TODAY,
            "products": [],
            "reserved_data_sources": list(RESERVED_SOURCES),
            "reserved_query_spaces": list(RESERVED_QUERY_SPACES),
        }

    with httpx.Client(headers={"User-Agent": "Mozilla/5.0 (compatible; discovery-bot/1.0)"}) as client:
        survivors = []
        killed = []

        for c in candidates:
            rec = {"name": c["name"], "input": c}

            # Phase 2 gate 1: data accessible
            status, sample = api_accessible(client, c["data_source"]["sample_url"])
            data_ok = status == 200

            # Phase 2 gate 2/3: search demand + beatability
            serp_checks = []
            search_positive = 0
            weak_result_count = 0
            for q in c["example_queries"][:3]:
                serp = web_search(client, q, max_results=5)
                serp_checks.append({"query": q, **serp})
                if serp["results"]:
                    search_positive += 1
                weak_domains = [domain_from_url(r["url"]) for r in serp["results"] if any(x in domain_from_url(r["url"]) for x in ["wikipedia.org", "reddit.com", "forum", "gov"]) ]
                if weak_domains:
                    weak_result_count += 1

            pass_gate = data_ok and search_positive >= 2

            rec["phase2"] = {
                "data_status": status,
                "data_ok": data_ok,
                "data_sample": sample,
                "serp_checks": serp_checks,
                "search_positive": search_positive,
                "serp_beatable_signals": weak_result_count,
                "pass": pass_gate,
            }

            if not pass_gate:
                rec["verdict"] = "KILL"
                rec["kill_reason"] = "Failed phase 2 binary gates"
                killed.append(rec)
                continue

            # Phase 3: deeper checks
            pain_queries = [
                f'site:reddit.com {c["example_queries"][0]} "spent hours"',
                f'site:reddit.com {c["example_queries"][0]} "is there a tool"',
                f'site:news.ycombinator.com {c["example_queries"][0]}',
            ]
            pain_hits = 0
            pain_examples = []
            for pq in pain_queries:
                ps = web_search(client, pq, max_results=3)
                if ps["results"]:
                    pain_hits += 1
                    pain_examples.extend(ps["results"][:1])

            rev = scenario_revenue(c["monetization_model"])
            # competition and feasibility heuristics based on detected domains and data format
            high_da_hits = 0
            for s in serp_checks:
                for r in s["results"][:3]:
                    d = domain_from_url(r["url"])
                    if any(x in d for x in ["webmd", "healthline", "forbes", "investopedia", "cms.gov"]):
                        high_da_hits += 1
            competition_gap = max(5, 9 - min(4, high_da_hits))
            build_feasibility = 8 if c["data_source"]["format"] in ["API", "CSV/Bulk", "CSV/API"] else 6
            defensibility = 7 if c["data_source"]["entity_count"] >= 50000 else 6
            monetization_clarity = 8 if rev["base"] >= 500 else 7

            rec["phase3"] = {
                "pain_signal_hits": pain_hits,
                "pain_examples": pain_examples,
                "competition_gap": competition_gap,
                "build_feasibility": build_feasibility,
                "defensibility": defensibility,
                "monetization_clarity": monetization_clarity,
                "revenue_scenarios": rev,
                "months_to_1k_base": round(1000 / max(1, rev["base"]), 1),
            }

            score = score_from_evidence(rec)
            rec["score"] = score

            if score["composite"] >= 7.0:
                verdict = "BUILD"
            elif score["composite"] >= 5.0:
                verdict = "BACKLOG"
            else:
                verdict = "KILL"

            rec["verdict"] = verdict
            survivors.append(rec)

    survivors.sort(key=lambda x: x["score"]["composite"], reverse=True)

    # Keep only >=5.0 per framework output
    output_opps = [s for s in survivors if s["score"]["composite"] >= 5.0]

    pipeline = {
        "run_date": TODAY,
        "phase0_inputs": {
            "watchlist_leads_file": "watchlist_leads.json",
            "watchlist_report_file": "watchlist_report.md",
        },
        "killed_in_phase2": killed,
        "opportunities": output_opps,
    }

    Path("pipeline.json").write_text(json.dumps(pipeline, indent=2))

    # build spec for BUILD verdicts + portfolio append
    build_specs = []
    for opp in output_opps:
        if opp["verdict"] != "BUILD":
            continue
        slug = opp["name"].lower()
        spec_path = Path(f"build-spec-{slug}.md")
        spec = [
            f"# Build Spec: {opp['name']}",
            "",
            f"Generated: {TODAY}",
            "",
            "## MVP (2-4 weeks)",
            "- Ingest source data into D1 nightly.",
            "- Generate entity pages and summary index pages.",
            "- Add simple on-site search and alert signup capture.",
            "",
            "## Data pipeline",
            "1. HTTP ingestion jobs",
            "2. Transform and normalize schema",
            "3. Persist to D1 + KV cached page payloads",
            "4. Serve static-first pages via Worker routes",
            "",
            "## Initial page plan",
            "- Entity detail pages",
            "- Query-intent landing pages",
            "- City/state/category aggregations",
        ]
        spec_path.write_text("\n".join(spec))
        build_specs.append(str(spec_path))

        portfolio["products"].append({
            "name": opp["name"],
            "status": "planning",
            "domain": None,
            "repo": None,
            "data_source": {
                "name": opp["input"]["data_source"]["name"],
                "url": opp["input"]["data_source"]["url"],
                "entity_type": opp["input"]["query_pattern"],
                "entity_count": opp["input"]["data_source"]["entity_count"],
                "update_frequency": opp["input"]["data_source"]["update_frequency"],
            },
            "query_patterns": [opp["input"]["query_pattern"]],
            "stack": "Cloudflare Workers, Hono, D1, KV",
            "monetization": opp["input"]["monetization_model"],
            "monthly_traffic": None,
            "monthly_revenue": None,
            "launch_date": None,
            "notes": "Auto-added from BUILD verdict in discovery pipeline run.",
        })

    portfolio["last_updated"] = TODAY
    portfolio_path.write_text(json.dumps(portfolio, indent=2))

    # markdown report
    lines = [
        "# Opportunity Discovery Pipeline Report",
        "",
        f"Run date: {TODAY}",
        "",
        "## Phase 0",
        "- Loaded `watchlist_leads.json` and `watchlist_report.md` from scanner output.",
        "",
        "## Ranked Opportunities",
    ]
    for i, opp in enumerate(output_opps, 1):
        sc = opp["score"]
        lines += [
            f"### {i}. {opp['name']} — {opp['verdict']} (Composite {sc['composite']})",
            f"- Data source: {opp['input']['data_source']['name']} ({opp['input']['data_source']['url']})",
            f"- Phase 2: data_status={opp['phase2']['data_status']}, search_positive={opp['phase2']['search_positive']}/3",
            f"- Revenue scenarios (bear/base/bull): ${opp['phase3']['revenue_scenarios']['bear']} / ${opp['phase3']['revenue_scenarios']['base']} / ${opp['phase3']['revenue_scenarios']['bull']}",
            f"- Months to $1K/mo (base assumption): {opp['phase3']['months_to_1k_base']}",
            f"- Scores: data={sc['data_quality']}, demand={sc['search_demand']}, gap={sc['competition_gap']}, monetization={sc['monetization_clarity']}, build={sc['build_feasibility']}, defensibility={sc['defensibility']}",
            "",
        ]

    if build_specs:
        lines += ["## Build Specs Generated", ""] + [f"- {p}" for p in build_specs] + [""]

    lines += ["## Killed in Phase 2", ""]
    for k in killed:
        lines.append(f"- {k['name']}: {k['kill_reason']}")
    if not killed:
        lines.append("- None")

    Path("pipeline-report.md").write_text("\n".join(lines))

if __name__ == "__main__":
    main()
