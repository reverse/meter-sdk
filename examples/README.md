# Meter SDK Examples

Example scripts demonstrating Meter's web scraping and API extraction capabilities.

## Setup

1. Install the Meter SDK:

```bash
pip install meter-sdk
```

2. Set your API key:

```bash
export METER_API_KEY=sk_live_...
```

Get your API key at [meter.sh](https://meter.sh/login).

## Examples

### Ashby Job Board Scraper

Scrapes job listings from multiple top startups (OpenAI, Anthropic, Sierra, Ramp, Notion, Figma) that use Ashby-powered job boards.

```bash
python ashby_job_scraper.py
```

This example demonstrates Meter's key feature: **generate a strategy once, run it everywhere**.

Since all Ashby job boards use the same underlying API structure, we generate a single strategy and reuse it across multiple companies - no need to regenerate for each one.

For a full walkthrough, see the blog post: [I scraped every top startup's jobs to find the best matches](https://meter.sh/blog/scraping-ashby-job-boards)

## Learn More

- [Meter Documentation](https://docs.meter.sh)
- [Python SDK Reference](https://docs.meter.sh/api-reference/python)
- [Get Support](mailto:mckinnon@meter.sh)
