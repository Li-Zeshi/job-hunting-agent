#!/usr/bin/env python3
"""Job-Hunting Agent CLI — automated job matching and application drafting."""

import sys
import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.prompt import Prompt

from job_agent import config as cfg
from job_agent.nodes.reporter import print_daily_report
from job_agent.utils.visadb import build_index, load_stories_from_dir
from job_agent.workflow import build_graph, get_initial_state
from job_agent.state import RawJob

load_dotenv()

app = typer.Typer(rich_markup_mode="rich")
manual_app = typer.Typer(help="Manually add and manage jobs")
app.add_typer(manual_app, name="manual")

console = Console()


# ══════════════════════════════════════════════════════════════
#  Commands
# ══════════════════════════════════════════════════════════════

@app.command()
def run(
    keywords: str = typer.Argument("software engineer", help="Job search keywords"),
    location: str = typer.Argument(cfg.DEFAULT_LOCATION, help="Job location"),
):
    """Run full workflow: scan → analyze → match → tailor → cover letter → review."""
    _ensure_data()
    _ensure_index()

    graph = build_graph()
    initial_state = get_initial_state(keywords, location)
    config = {"configurable": {"thread_id": "job-hunting-run"}}

    console.print(f"\n🚀 [bold]Starting:[/] \"{keywords}\" in {location}")
    console.print(f"📄 Resume: {cfg.RESUME_PATH}")
    console.print(f"📚 BQ Stories: {cfg.BQ_STORIES_DIR}\n")

    # First pass → stops before reviewer nodes
    for _event in graph.stream(initial_state, config):
        pass

    # Process each job through human review
    state = graph.get_state(config)
    while state.next:
        if "reviewer" in state.next:
            job = state.values.get("current_job")
            if not job:
                break

            decision = _prompt_review(state.values)

            if decision["status"] == "approved":
                graph.update_state(config, {"review_status": "approved", "review_feedback": ""})
            elif decision["status"] == "modified":
                graph.update_state(config, {"review_status": "modified", "review_feedback": decision.get("feedback", "")})
            else:
                graph.update_state(config, {"review_status": "rejected", "review_feedback": decision.get("feedback", "skipped")})

            for _event in graph.stream(None, config):
                pass

            if decision["status"] == "quit":
                console.print("[yellow]Quitting.[/]")
                break

            state = graph.get_state(config)
        else:
            break

    # Summary
    final = graph.get_state(config).values
    apps = final.get("today_applications", [])
    approved = sum(1 for a in apps if a.review_status == "approved")
    console.print(f"\n[bold green]✓ Done![/] {len(apps)} processed, {approved} approved.")
    print_daily_report()


@app.command()
def process(
    title: str = typer.Option(..., "--title", "-t", help="Job title"),
    company: str = typer.Option("", "--company", "-c", help="Company name"),
    url: str = typer.Option("", "--url", "-u", help="Job URL"),
    description: str = typer.Option("", "--description", "-d", help="Job description / JD text"),
):
    """Process a single job directly (no scraping)."""
    _ensure_data()
    _ensure_index()

    # If no description provided via CLI, prompt to paste or read from stdin
    if not description:
        console.print("[yellow]Paste the job description below (Ctrl+D when done):[/]")
        description = sys.stdin.read().strip()

    job = RawJob(title=title, company=company, url=url, source="manual")
    run_single_job_workflow(job, description)


@manual_app.command("add")
def manual_add(
    title: str = typer.Option(..., "--title", "-t", help="Job title"),
    company: str = typer.Option("", "--company", "-c", help="Company name"),
    url: str = typer.Option("", "--url", "-u", help="Job URL"),
    description: str = typer.Option("", "--description", "-d", help="Job description"),
):
    """Add and process a job manually."""
    process.callback(title=title, company=company, url=url, description=description)


@app.command()
def report():
    """View today's application report."""
    print_daily_report()


@app.command()
def scan(
    keywords: str = typer.Argument("software engineer", help="Job search keywords"),
    location: str = typer.Argument(cfg.DEFAULT_LOCATION, help="Job location"),
):
    """Scan for jobs only (no application processing)."""
    from job_agent.nodes.scanner import scanner_node

    state = get_initial_state(keywords, location)
    result = scanner_node(state)
    jobs = result.get("raw_jobs", [])

    console.print(f"\n[bold]Found {len(jobs)} potential leads:[/]\n")
    for i, job in enumerate(jobs, 1):
        console.print(f"  {i:2d}. [cyan]{job.title}[/] @ [green]{job.company or '?'}[/]")
        console.print(f"      {job.url}")
    if jobs:
        console.print(f"\n💡 Run [bold]python main.py run \"{keywords}\"[/] for full workflow")
    else:
        console.print("\n💡 Add a job manually: python main.py manual add --title ... --description ...")


@app.command()
def ingest():
    """(Re)build BQ story vector index."""
    stories = load_stories_from_dir()
    if not stories:
        console.print(f"[yellow]No .md files in {cfg.BQ_STORIES_DIR}[/]")
        console.print("Place your BQ stories as .md files there, then run this command.")
        return

    console.print(f"📚 Building index for {len(stories)} BQ stories...")
    build_index(stories)
    console.print("[green]✓ Done![/]")
    for s in stories:
        console.print(f"  • [cyan]{s.title}[/] — {s.content[:70].replace(chr(10),' ')}...")


# ══════════════════════════════════════════════════════════════
#  Workflow runner for a single job
# ══════════════════════════════════════════════════════════════

def run_single_job_workflow(job: RawJob, description: str):
    """Run the analysis→matching→tailoring→cover→review pipeline for one job."""
    job.summary = description  # Use description as the JD

    from job_agent.workflow import build_graph, get_initial_state

    initial = get_initial_state("", cfg.DEFAULT_LOCATION)
    initial["raw_jobs"] = [job]
    initial["resume_text"] = _load_resume()

    graph = build_graph()

    # We skip scanner and directly route to analyzer then per-job pipeline.
    # Build a simpler sub-graph: [analyzer → matcher → prepare_job → retriever → tailor → writer → reviewer → reporter]
    from langgraph.graph import StateGraph, START, END
    from job_agent.state import JobAgentState
    from job_agent.nodes.analyzer import analyzer_node
    from job_agent.nodes.matcher import matcher_node
    from job_agent.nodes.retriever import retriever_node
    from job_agent.nodes.tailor import tailor_node
    from job_agent.nodes.writer import writer_node
    from job_agent.nodes.reviewer import reviewer_node
    from job_agent.nodes.reporter import reporter_node
    from job_agent.workflow import _prepare_current_job, _route_after_matcher, _route_after_review, _route_to_next_job

    builder = StateGraph(JobAgentState)
    builder.add_node("analyzer", analyzer_node)
    builder.add_node("matcher", matcher_node)
    builder.add_node("prepare_job", _prepare_current_job)
    builder.add_node("retriever", retriever_node)
    builder.add_node("tailor", tailor_node)
    builder.add_node("writer", writer_node)
    builder.add_node("reviewer", reviewer_node)
    builder.add_node("reporter", reporter_node)

    builder.add_edge(START, "analyzer")
    builder.add_edge("analyzer", "matcher")
    builder.add_conditional_edges("matcher", _route_after_matcher, {"has_jobs": "prepare_job", "no_jobs": END})
    builder.add_edge("prepare_job", "retriever")
    builder.add_edge("retriever", "tailor")
    builder.add_edge("tailor", "writer")
    builder.add_edge("writer", "reviewer")
    builder.add_conditional_edges("reviewer", _route_after_review, {"modified": "writer", "done": "reporter"})
    builder.add_conditional_edges("reporter", _route_to_next_job, {"next_job": "prepare_job", "all_done": END})

    from langgraph.checkpoint.memory import MemorySaver
    graph = builder.compile(checkpointer=MemorySaver(), interrupt_before=["reviewer"])

    config = {"configurable": {"thread_id": "manual-job"}}

    for _event in graph.stream(initial, config):
        pass

    state = graph.get_state(config)
    while state.next:
        if "reviewer" in state.next:
            decision = _prompt_review(state.values)
            if decision["status"] == "approved":
                graph.update_state(config, {"review_status": "approved", "review_feedback": ""})
            elif decision["status"] == "modified":
                graph.update_state(config, {"review_status": "modified", "review_feedback": decision.get("feedback", "")})
            else:
                graph.update_state(config, {"review_status": "rejected", "review_feedback": decision.get("feedback", "skipped")})

            for _event in graph.stream(None, config):
                pass

            if decision["status"] == "quit":
                break
            state = graph.get_state(config)
        else:
            break

    print_daily_report()


# ══════════════════════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════════════════════

def _ensure_data():
    """Prompt user if resume/BQ stories are missing."""
    if not cfg.RESUME_PATH.exists():
        console.print(f"[yellow]⚠ No resume at {cfg.RESUME_PATH}[/]")
        if Prompt.ask("Create a placeholder?", choices=["y", "n"], default="y") == "y":
            cfg.RESUME_PATH.parent.mkdir(parents=True, exist_ok=True)
            cfg.RESUME_PATH.write_text("# My Resume\n\n## Skills\n\n## Experience\n\n")
            console.print(f"  Created — edit {cfg.RESUME_PATH} with your info!")
        else:
            console.print("[red]Cannot proceed without a resume.[/]")
            raise typer.Exit(1)

    if not cfg.BQ_STORIES_DIR.exists() or not list(cfg.BQ_STORIES_DIR.glob("*.md")):
        console.print(f"[yellow]⚠ No BQ stories in {cfg.BQ_STORIES_DIR}[/]")
        if Prompt.ask("Create a sample story?", choices=["y", "n"], default="y") == "y":
            cfg.BQ_STORIES_DIR.mkdir(parents=True, exist_ok=True)
            (cfg.BQ_STORIES_DIR / "example-story.md").write_text(
                "# Example: Led a cross-team migration\n\n"
                "**Situation:** Legacy monolith was nearing limits.\n"
                "**Task:** Coordinate 3 teams for migration.\n"
                "**Action:** Set up syncs, shared roadmap, CI/CD pipelines.\n"
                "**Result:** Completed 2 weeks early, zero downtime.\n"
            )
            console.print("  Created example-story.md")
        else:
            console.print("[yellow]Continuing without BQ stories.[/]")


def _ensure_index():
    """Auto-index BQ stories if not indexed yet."""
    idx_path = cfg.DATA_DIR / "bq_index.json"
    if not idx_path.exists():
        stories = load_stories_from_dir()
        if stories:
            console.print("📚 Building BQ story index...")
            build_index(stories)


def _load_resume() -> str:
    if cfg.RESUME_PATH.exists():
        return cfg.RESUME_PATH.read_text()
    return ""


def _prompt_review(state_values: dict) -> dict:
    job = state_values.get("current_job")
    if not job:
        return {"status": "rejected", "feedback": "no_job"}

    console.print(f"\n[bold cyan]📋 {job.raw.title}[/] @ [bold green]{job.raw.company}[/]")
    console.print(f"   Match: [bold]{job.match_score}/100[/]", end="")
    console.print(f"   🛂 {'✅ KM Visa' if job.has_km_visa else '⚠️ No KM visa'}")

    letter = state_values.get("cover_letter", "")
    if letter:
        preview = letter[:500] + "..." if len(letter) > 500 else letter
        console.print(f"\n[bold]💌 Cover Letter:[/]\n{preview}\n")

    choice = Prompt.ask(
        "[bold]a[/]=Approve [bold]e[/]=Edit [bold]s[/]=Skip [bold]v[/]=View full [bold]q[/]=Quit",
        default="a", choices=["a", "e", "s", "v", "q"],
    )

    if choice == "a":
        return {"status": "approved"}
    elif choice == "e":
        feedback = Prompt.ask("[yellow]What should I change?[/]")
        return {"status": "modified", "feedback": feedback}
    elif choice == "s":
        return {"status": "rejected", "feedback": "skipped"}
    elif choice == "v":
        _show_full(state_values)
        return _prompt_review(state_values)
    elif choice == "q":
        return {"status": "quit", "feedback": "quit_early"}
    return {"status": "rejected", "feedback": "invalid_choice"}


def _show_full(state_values: dict) -> None:
    from rich.panel import Panel
    job = state_values.get("current_job")
    if not job:
        return

    console.print(Panel(job.raw.summary or "No JD", title="📋 Full Job Description"))

    tailored = state_values.get("tailored_resume", "")
    if tailored:
        console.print(Panel(tailored[:1500], title="📄 Tailored Resume"))

    letter = state_values.get("cover_letter", "")
    if letter:
        console.print(Panel(letter, title="💌 Cover Letter"))

    stories = state_values.get("matched_stories", [])
    if stories:
        console.print("[bold]📖 BQ Stories Used:[/]")
        for s in stories:
            console.print(f"  • [cyan]{s.title}[/] (relevance: {s.relevance_score:.0%})")


if __name__ == "__main__":
    app()
