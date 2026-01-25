#!/usr/bin/env python3
"""
Ashby Job Board Scraper

Scrapes job listings from multiple companies using Ashby-powered job boards.
Demonstrates Meter's key feature: generate a strategy once, run it everywhere.

Usage:
    export METER_API_KEY=sk_live_...
    python ashby_job_scraper.py
"""

from meter_sdk import MeterClient
import os
import sys

# Companies using Ashby for their job boards
ASHBY_COMPANIES = [
    "openai",
    "sierra",
    "anthropic",
    "ramp",
    "notion",
    "figma",
]


def main():
    api_key = os.getenv("METER_API_KEY")
    if not api_key:
        print("Error: METER_API_KEY environment variable not set")
        print("Get your API key at https://meter.sh")
        sys.exit(1)

    client = MeterClient(api_key=api_key)

    # Step 1: Generate a strategy using the first company as a template
    # force_api=True tells Meter to prioritize API extraction over HTML scraping
    print("Generating strategy for Ashby job boards...")
    strategy = client.generate_strategy(
        url=f"https://jobs.ashbyhq.com/{ASHBY_COMPANIES[0]}",
        description="Extract all job postings with title, department, location, and application URL",
        name="Ashby Job Board",
        force_api=True,
    )

    strategy_id = strategy["strategy_id"]
    print(f"Strategy ID: {strategy_id}\n")

    # Step 2: Collect jobs from all companies using the SAME strategy
    all_jobs = []

    for company in ASHBY_COMPANIES:
        print(f"Fetching {company.title()} jobs...")

        # Execute job with different URL - no need to regenerate strategy!
        job_result = client.execute_job(
            strategy_id=strategy_id, url=f"https://jobs.ashbyhq.com/{company}"
        )

        for job in job_result["results"]:
            job["company"] = company
            all_jobs.append(job)

        print(f"  Found {len(job_result['results'])} jobs")

    # Step 3: Display all jobs with application links
    print(f"\n{'='*60}")
    print(f"TOTAL: {len(all_jobs)} jobs across {len(ASHBY_COMPANIES)} companies")
    print(f"{'='*60}\n")

    for job in all_jobs:
        company = job.get("company", "unknown").upper()
        title = job.get("title", "Unknown Title")
        location = job.get("location", "Unknown Location")
        url = job.get("url", "")

        print(f"[{company}] {title} ({location})")
        if url:
            print(f"  Apply: {url}")
        print()


if __name__ == "__main__":
    main()
