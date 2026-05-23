"""LangGraph workflow for the job-hunting agent."""

from pathlib import Path

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from job_agent import config as cfg
from job_agent.state import JobAgentState
from job_agent.nodes.scanner import scanner_node
from job_agent.nodes.analyzer import analyzer_node
from job_agent.nodes.matcher import matcher_node
from job_agent.nodes.retriever import retriever_node
from job_agent.nodes.tailor import tailor_node
from job_agent.nodes.writer import writer_node
from job_agent.nodes.reviewer import reviewer_node
from job_agent.nodes.reporter import reporter_node

RESUME_CACHE: dict[str, str] = {}


def _load_resume() -> str:
    if "resume" in RESUME_CACHE:
        return RESUME_CACHE["resume"]
    path = Path(cfg.RESUME_PATH)
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8")
    RESUME_CACHE["resume"] = text
    return text


def _route_after_matcher(state: JobAgentState) -> str:
    jobs = state.get("filtered_jobs", [])
    if not jobs:
        return "no_jobs"
    return "has_jobs"


def _route_after_review(state: JobAgentState) -> str:
    status = state.get("review_status", "rejected")
    return "modified" if status == "modified" else "done"


def _route_to_next_job(state: JobAgentState) -> str:
    jobs = state.get("filtered_jobs", [])
    idx = state.get("current_job_index", 0)
    if idx < len(jobs):
        return "next_job"
    return "all_done"


def _prepare_current_job(state: JobAgentState) -> dict:
    jobs = state.get("filtered_jobs", [])
    idx = state.get("current_job_index", 0)
    if idx < len(jobs):
        return {"current_job": jobs[idx], "current_job_index": idx + 1}
    return {"current_job": None}


def build_graph() -> CompiledStateGraph:
    """Build and compile the LangGraph workflow."""
    builder = StateGraph(JobAgentState)

    builder.add_node("scanner", scanner_node)
    builder.add_node("analyzer", analyzer_node)
    builder.add_node("matcher", matcher_node)
    builder.add_node("prepare_job", _prepare_current_job)
    builder.add_node("retriever", retriever_node)
    builder.add_node("tailor", tailor_node)
    builder.add_node("writer", writer_node)
    builder.add_node("reviewer", reviewer_node)
    builder.add_node("reporter", reporter_node)

    # ── Edges ──
    builder.add_edge(START, "scanner")
    builder.add_edge("scanner", "analyzer")
    builder.add_edge("analyzer", "matcher")

    builder.add_conditional_edges(
        "matcher",
        _route_after_matcher,
        {"has_jobs": "prepare_job", "no_jobs": END},
    )

    builder.add_edge("prepare_job", "retriever")
    builder.add_edge("retriever", "tailor")
    builder.add_edge("tailor", "writer")
    builder.add_edge("writer", "reviewer")

    builder.add_conditional_edges(
        "reviewer",
        _route_after_review,
        {"modified": "writer", "done": "reporter"},
    )

    builder.add_conditional_edges(
        "reporter",
        _route_to_next_job,
        {"next_job": "prepare_job", "all_done": END},
    )

    checkpointer = MemorySaver()
    graph = builder.compile(
        checkpointer=checkpointer,
        interrupt_before=["reviewer"],
    )
    return graph


def get_initial_state(keywords: str, location: str = cfg.DEFAULT_LOCATION) -> dict:
    """Create initial state for a workflow run."""
    return {
        "search_keywords": keywords,
        "search_location": location,
        "raw_jobs": [],
        "filtered_jobs": [],
        "skipped_jobs": [],
        "current_job_index": 0,
        "current_job": None,
        "resume_text": _load_resume(),
        "tailored_resume": "",
        "bq_stories": [],
        "matched_stories": [],
        "cover_letter": "",
        "review_status": None,
        "review_feedback": "",
        "today_applications": [],
    }
