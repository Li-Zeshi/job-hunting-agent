"""Fetch job listings from web search (DuckDuckGo)."""

import json
import re

import warnings
warnings.filterwarnings("ignore", message="This package.*renamed to `ddgs`")

from duckduckgo_search import DDGS
from job_agent import config as cfg
from job_agent.state import RawJob


SEARCH_QUERIES = [
    "{keywords} vacature {location}",
    "{keywords} job {location}",
    "vacature {keywords} {location}",
]


SKIP_DOMAINS = [
    "wikipedia.org", "w3schools.com", "youtube.com", "instagram.com",
    "facebook.com", "tutorial", "compiler", "online-python.com",
    "programiz.com", "realpython.com", "geeksforgeeks.org",
]

SKIP_TITLE_KW = ["login", "sign in", "register", "create account",
                 "forgot password", "reset password"]


def _extract_company(title: str, body: str) -> str:
    # Pattern: "Something at Company Name"
    at_match = re.search(r"\bat\b\s+([A-Z][A-Za-z0-9\s&.]+)", title)
    if at_match:
        company = at_match.group(1).strip()
        company = re.split(r"[-–—|,]", company)[0].strip()
        if company:
            return company
    return ""


def _search_ddg(query: str, max_results: int = 10) -> list[RawJob]:
    """Search DuckDuckGo and return job-like results."""
    jobs: list[RawJob] = []
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, region="nl-nl", max_results=max_results))
    except Exception:
        return []

    for r in results:
        title = r.get("title", "")
        body = r.get("body", "")
        url = r.get("href", "")

        if not title or not url:
            continue
        # Skip non-job pages
        if any(d in url for d in SKIP_DOMAINS):
            continue
        if any(k in title.lower() for k in SKIP_TITLE_KW):
            continue

        company = _extract_company(title, body)

        jobs.append(RawJob(
            title=title,
            company=company,
            summary=body[:500],
            url=url,
            source="web",
        ))

    return jobs


def _load_cache() -> set[str]:
    if not cfg.JOBS_CACHE_PATH.exists():
        return set()
    return set(json.loads(cfg.JOBS_CACHE_PATH.read_text()))


def _save_cache(urls: set[str]) -> None:
    cfg.JOBS_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    cfg.JOBS_CACHE_PATH.write_text(json.dumps(list(urls), ensure_ascii=False))


def scanner_node(state) -> dict:
    """LangGraph node: search for jobs via web search."""
    keywords = state.get("search_keywords", "software engineer")
    location = state.get("search_location", cfg.DEFAULT_LOCATION)
    seen_urls = _load_cache()

    print(f"\n{'='*60}")
    print(f"🔍 Scanner: \"{keywords}\" in {location}")
    print(f"{'='*60}")

    all_jobs: list[RawJob] = []

    for query_template in SEARCH_QUERIES:
        query = query_template.format(keywords=keywords, location=location)
        jobs = _search_ddg(query, max_results=8)
        if jobs:
            all_jobs.extend(jobs)

    if not all_jobs:
        print("  ⚠ No jobs found via web search.")
        print("  💡 Add jobs manually via: python main.py manual")
        return {"raw_jobs": []}

    # Deduplicate
    seen: set[str] = set()
    unique: list[RawJob] = []
    for job in all_jobs:
        key = f"{job.title.lower()}|{job.url}"
        if key not in seen and job.url not in seen_urls:
            seen.add(key)
            unique.append(job)

    new_jobs = unique[:cfg.MAX_JOBS_PER_RUN]
    print(f"  ✓ Found {len(new_jobs)} jobs")

    for j in new_jobs:
        print(f"    • {j.title[:60]} @ {j.company or '?'}")

    # Cache URLs
    seen_urls.update(j.url for j in new_jobs)
    _save_cache(seen_urls)

    # Remove already-applied
    apps = []
    if cfg.APPLICATIONS_PATH.exists():
        apps = json.loads(cfg.APPLICATIONS_PATH.read_text())
    applied_urls = {a.get("job", {}).get("raw", {}).get("url", "") for a in apps}
    new_jobs = [j for j in new_jobs if j.url not in applied_urls]

    return {"raw_jobs": new_jobs, "current_job_index": 0}
