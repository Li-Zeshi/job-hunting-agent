"""Human-in-the-loop review node using Rich terminal UI."""

from datetime import datetime, timezone

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.prompt import Prompt

console = Console()


def _build_review_panel(state) -> None:
    """Display full review of application materials."""
    job = state.get("current_job")
    if not job:
        return

    # ── Header ──
    header = Table.grid(padding=1)
    header.add_column(style="bold cyan", width=14)
    header.add_column(style="white")
    header.add_row("📋 Role", f"{job.raw.title}")
    header.add_row("🏢 Company", f"{job.raw.company}")
    header.add_row("📍 Location", f"{job.raw.location or 'Not specified'}")
    header.add_row("🎯 Match", f"{job.match_score}/100 — {job.match_reasoning}")
    visa_icon = "✅" if job.has_km_visa else "⚠️"
    header.add_row("🛂 KM Visa", f"{visa_icon} {job.visa_info or 'Detected from keywords' if job.has_km_visa else 'Not found'}")

    console.print(Panel(header, title="[bold]Application Review[/]", border_style="cyan"))

    # ── JD Requirements ──
    if job.requirements:
        req_table = Table.grid(padding=(0, 2))
        for i, req in enumerate(job.requirements[:8], 1):
            req_table.add_row(f"  {i}.", req)
        console.print(Panel(req_table, title="📋 Requirements", border_style="blue"))

    # ── Tailored Resume (changes summary) ──
    tailored = state.get("tailored_resume", "")
    if tailored:
        preview = tailored[:600] + ("..." if len(tailored) > 600 else "")
        console.print(Panel(preview, title="📄 Tailored Resume (preview)", border_style="green"))

    # ── BQ Stories Used ──
    stories = state.get("matched_stories", [])
    if stories:
        story_table = Table.grid(padding=(0, 2))
        for s in stories:
            story_table.add_row(f"  •", f"{s.title}  [dim](relevance: {s.relevance_score:.0%})[/dim]")
        console.print(Panel(story_table, title="📖 BQ Stories Used", border_style="yellow"))

    # ── Cover Letter ──
    letter = state.get("cover_letter", "")
    if letter:
        console.print(Panel(letter, title="💌 Cover Letter", border_style="magenta"))
        console.print(f"[dim]Word count: {len(letter.split())}[/dim]")

    console.print()


def reviewer_node(state) -> dict:
    """LangGraph node: present materials and get user decision."""
    _build_review_panel(state)

    while True:
        choice = Prompt.ask(
            "[bold]What would you like to do?[/]",
            default="a",
            choices=["a", "e", "s", "v", "q"],
            show_choices=False,
        )

        if choice == "a":  # Approve
            console.print("[bold green]✓ Approved! Application will be recorded.[/]")
            return {
                "review_status": "approved",
                "review_feedback": "",
            }

        elif choice == "e":  # Edit cover letter
            feedback = Prompt.ask("[bold yellow]What should I change?[/]")
            console.print("[yellow]↻ Regenerating cover letter with your feedback...[/]")
            return {
                "review_status": "modified",
                "review_feedback": feedback,
            }

        elif choice == "s":  # Skip
            console.print("[dim]⏭ Skipped.[/]")
            return {
                "review_status": "rejected",
                "review_feedback": "skipped",
            }

        elif choice == "v":  # View full JD
            job = state.get("current_job")
            if job:
                console.print(Panel(
                    job.raw.summary or "No full description available",
                    title="📋 Full Job Description",
                    border_style="blue",
                ))

        elif choice == "q":  # Quit early
            console.print("[dim]Quitting early — jobs not reviewed will be skipped.[/]")
            return {
                "review_status": "rejected",
                "review_feedback": "quit_early",
            }
