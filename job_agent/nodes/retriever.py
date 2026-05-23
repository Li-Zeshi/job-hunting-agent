"""Retrieve relevant BQ stories using RAG."""

from job_agent.utils.visadb import search_stories, load_stories_from_dir


def retriever_node(state) -> dict:
    """LangGraph node: find BQ stories relevant to the current job."""
    import json, re

    current_job = state.get("current_job")
    if not current_job:
        return {"matched_stories": []}

    # Build query from JD requirements
    parts = [
        current_job.raw.title,
        current_job.raw.company,
        *current_job.requirements[:5],
        *current_job.responsibilities[:5],
    ]
    query = " ".join(p for p in parts if p)
    print(f"  Searching BQ stories for: {current_job.raw.title} @ {current_job.raw.company}")

    stories = search_stories(query, k=3)
    if stories:
        for s in stories:
            print(f"    ✓ Matched: \"{s.title}\" (rel: {s.relevance_score:.2f})")
    else:
        print("  ⚠ No BQ stories found — check your bq_stories/ folder and run ingest-stories")

    return {"matched_stories": stories}
