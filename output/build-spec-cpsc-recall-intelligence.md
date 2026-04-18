# Build Skeleton: CPSC Recall Intelligence

## MVP Scope (2-4 weeks)
- Dataset ingestion cron
- Entity detail pages + index pages
- Search + filter UI
- Basic ad/affiliate placements

## Data Pipeline
- Ingest from: https://www.saferproducts.gov/RestWebServices/Recall?format=json&RecallDateStart=2026-01-01
- Normalize schema to D1 tables
- Generate static-friendly page caches in KV
- Publish sitemap shards

## Monetization
- Model: Ads + retailer affiliate replacements
- Add premium alerting as upsell
