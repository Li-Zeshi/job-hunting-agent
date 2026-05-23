"""Record applications and generate daily report."""

import json
from datetime import datetime

from rich.console import Console
from rich.table import Table
from job_agent import config as cfg
from job_agent.state import ApplicationRecord

console = Console()


def _load_applications() -> list[dict]:
    if not cfg.APPLICATIONS_PATH.exists():
        return []
    return json.loads(cfg.APPLICATIONS_PATH.read_text())


def _save_application(record: ApplicationRecord) -> None:
    apps = _load_applications()
    apps.append(record.model_dump())
    cfg.APPLICATIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    cfg.APPLICATIONS_PATH.write_text(json.dumps(apps, ensure_ascii=False, indent=2))


def reporter_node(state) -> dict:
    """LangGraph node: record result and print status."""
    current_job = state.get("current_job")
    review_status = state.get("review_status", "rejected")
    today_apps = state.get("today_applications", [])

    if not current_job:
        # No job to record — this can happen when all were skipped
        # The node still runs as a pass-through
        print(f"  📊 No job to record (end of processing)")
        return {"today_applications": today_apps}

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    record = ApplicationRecord(
        job=current_job,
        tailored_resume=state.get("tailored_resume", ""),
        cover_letter=state.get("cover_letter", ""),
        matched_stories=state.get("matched_stories", []),
        review_status=review_status,
        review_feedback=state.get("review_feedback", ""),
        timestamp=now,
    )

    _save_application(record)
    today_apps.append(record)

    if review_status == "approved":
        console.print(f"[bold green]  ✓ SUBMITTED: {current_job.raw.title} @ {current_job.raw.company}[/]")
    else:
        console.print(f"[dim]  - {review_status.upper()}: {current_job.raw.title} @ {current_job.raw.company}[/]")

    return {"today_applications": today_apps}


def print_daily_report() -> None:
    """Print a standalone daily summary."""
    apps = _load_applications()
    if not apps:
        console.print("[yellow]No applications recorded yet.[/]")
        return

    today_str = datetime.now().strftime("%Y-%m-%d")
    today_apps = [a for a in apps if a.get("timestamp", "").startswith(today_str)]

    table = Table(title=f"📊 Daily Report — {today_str}")
    table.add_column("Status", style="bold")
    table.add_column("Company", style="cyan")
    table.add_column("Role")
    table.add_column("Match")
    table.add_column("Time")

    for a in (today_apps or apps[-20:]):
        job = a.get("job", {})
        raw = job.get("raw", {})
        status = a.get("review_status", "?")
        status_style = {
            "approved": "[green]✓ Approved[/]",
            "rejected": "[dim]⏭ Skipped[/]",
            "modified": "[yellow]↻ Edited[/]",
        }.get(status, status)
        table.add_row(
            status_style,
            raw.get("company", "-"),
            raw.get("title", "-"),
            f'{job.get("match_score", "-")}/100',
            a.get("timestamp", "")[-5:],
        )

    console.print(table)
    approved = sum(1 for a in (today_apps or apps) if a.get("review_status") == "approved")
    total = len(today_apps or apps)
    console.print(f"\n[bold]Summary:[/] {approved}/{total} approved today  |  {len(apps)} total applications")
