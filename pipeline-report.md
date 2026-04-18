# Opportunity Discovery Pipeline Report

Run date: 2026-04-18

## Phase 0
- Loaded `watchlist_leads.json` and `watchlist_report.md` from scanner output.

## Ranked Opportunities
### 1. DeviceIncidentScout — BUILD (Composite 7.83)
- Data source: openFDA Device Adverse Events API (https://api.fda.gov/device/event.json)
- Phase 2: data_status=200, search_positive=3/3
- Revenue scenarios (bear/base/bull): $60.0 / $700.0 / $4500.0
- Months to $1K/mo (base assumption): 1.4
- Scores: data=8, demand=7, gap=9, monetization=8, build=8, defensibility=7

### 2. OSHAInspectionLookup — BUILD (Composite 7.83)
- Data source: OSHA Enforcement Data Catalog (https://enforcedata.dol.gov/views/data_catalogs.php)
- Phase 2: data_status=200, search_positive=3/3
- Revenue scenarios (bear/base/bull): $90.0 / $800.0 / $5500.0
- Months to $1K/mo (base assumption): 1.2
- Scores: data=8, demand=7, gap=9, monetization=8, build=8, defensibility=7

### 3. NursingHomeGrade — BUILD (Composite 7.67)
- Data source: CMS Nursing Home Care Compare datasets (https://data.cms.gov/provider-data/dataset/4pq5-n9py)
- Phase 2: data_status=200, search_positive=3/3
- Revenue scenarios (bear/base/bull): $90.0 / $800.0 / $5500.0
- Months to $1K/mo (base assumption): 1.2
- Scores: data=8, demand=7, gap=9, monetization=8, build=8, defensibility=6

## Build Specs Generated

- build-spec-deviceincidentscout.md
- build-spec-oshainspectionlookup.md
- build-spec-nursinghomegrade.md

## Killed in Phase 2

- None