"""BQ story retrieval — OpenAI embeddings with keyword fallback."""

import json
import math
import re
from pathlib import Path

import numpy as np
from openai import OpenAI

from job_agent import config as cfg
from job_agent.state import BQStory

INDEX_PATH = cfg.DATA_DIR / "bq_index.json"


def _get_client():
    try:
        return OpenAI()
    except Exception:
        return None


def _embed(text: str, client: OpenAI) -> list[float] | None:
    try:
        resp = client.embeddings.create(input=text, model="text-embedding-3-small")
        return resp.data[0].embedding
    except Exception:
        return None


def _cosine_sim(a: list[float], b: list[float]) -> float:
    arr_a, arr_b = np.array(a), np.array(b)
    if np.linalg.norm(arr_a) == 0 or np.linalg.norm(arr_b) == 0:
        return 0.0
    return float(np.dot(arr_a, arr_b) / (np.linalg.norm(arr_a) * np.linalg.norm(arr_b)))


def _keyword_search(query: str, entries: list[dict]) -> list[tuple[int, float]]:
    """Fallback: rank entries by keyword overlap with query."""
    query_words = set(re.findall(r"\w+", query.lower()))
    scored: list[tuple[int, float]] = []
    for i, e in enumerate(entries):
        text = (e["title"] + " " + e["content"]).lower()
        matches = sum(1 for w in query_words if w in text)
        if matches > 0:
            score = matches / math.sqrt(len(query_words))
            scored.append((i, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def build_index(stories: list[BQStory]) -> None:
    """Embed stories and save to JSON index."""
    client = _get_client()
    entries = []

    for s in stories:
        if not s.content.strip():
            continue

        emb = None
        if client:
            emb = _embed(s.content, client)

        entries.append({
            "title": s.title,
            "content": s.content,
            "competencies": s.competencies,
            "embedding": emb,  # None if embedding failed — will use keyword fallback
        })

    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(json.dumps(entries, ensure_ascii=False))
    method = "vector + keyword" if any(e["embedding"] for e in entries) else "keyword-only"
    print(f"  ✓ Indexed {len(entries)} BQ stories ({method}) → {INDEX_PATH.name}")


def search_stories(query: str, k: int = 3) -> list[BQStory]:
    """Find top-K relevant BQ stories. Uses embeddings when available, keyword fallback otherwise."""
    if not INDEX_PATH.exists():
        return []

    entries = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    if not entries:
        return []

    # Try vector search first
    client = _get_client()
    if client and entries[0].get("embedding"):
        q_emb = _embed(query, client)
        if q_emb:
            scored: list[tuple[int, float]] = []
            for i, e in enumerate(entries):
                if e["embedding"]:
                    sim = _cosine_sim(q_emb, e["embedding"])
                    scored.append((i, sim))
            scored.sort(key=lambda x: x[1], reverse=True)
            top = scored[:k]
        else:
            top = _keyword_search(query, entries)[:k]
    else:
        top = _keyword_search(query, entries)[:k]

    results = []
    for idx, score in top:
        e = entries[idx]
        results.append(BQStory(
            title=e["title"],
            content=e["content"],
            competencies=e.get("competencies", []),
            relevance_score=round(score, 3),
        ))
    return results


def load_stories_from_dir() -> list[BQStory]:
    """Load BQ stories from markdown files."""
    stories_dir = Path(cfg.BQ_STORIES_DIR)
    if not stories_dir.exists():
        return []

    stories = []
    for md_file in sorted(stories_dir.glob("*.md")):
        content = md_file.read_text(encoding="utf-8").strip()
        if not content:
            continue
        title = md_file.stem
        lines = content.split("\n")
        first_line = lines[0].strip().lstrip("# ")
        if first_line:
            title = first_line
        stories.append(BQStory(title=title, content=content))
    return stories
