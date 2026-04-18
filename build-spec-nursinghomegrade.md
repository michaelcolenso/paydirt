# Build Spec: NursingHomeGrade

Generated: 2026-04-18

## MVP (2-4 weeks)
- Ingest source data into D1 nightly.
- Generate entity pages and summary index pages.
- Add simple on-site search and alert signup capture.

## Data pipeline
1. HTTP ingestion jobs
2. Transform and normalize schema
3. Persist to D1 + KV cached page payloads
4. Serve static-first pages via Worker routes

## Initial page plan
- Entity detail pages
- Query-intent landing pages
- City/state/category aggregations