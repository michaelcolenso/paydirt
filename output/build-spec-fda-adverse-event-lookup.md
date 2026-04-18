# Build Skeleton: FDA Adverse Event Lookup

## MVP Scope (2-4 weeks)
- Dataset ingestion cron
- Entity detail pages + index pages
- Search + filter UI
- Basic ad/affiliate placements

## Data Pipeline
- Ingest from: https://api.fda.gov/drug/event.json?limit=1
- Normalize schema to D1 tables
- Generate static-friendly page caches in KV
- Publish sitemap shards

## Monetization
- Model: Ads + affiliate links to telehealth/pharmacy comparison
- Add premium alerting as upsell
