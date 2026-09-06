from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from . import store
from .ats.check import check_pdf
from .config import DEFAULT_PROFILE, OUT_DIR
from .models.tailored import TailoredBullet, TailoredResume
from .pipeline import elicit
from .pipeline.cover_letter import write_cover_letter
from .pipeline.parse_jd import parse_jd
from .pipeline.tailor import TailorConfig, tailor
from .render import docx as docx_render
from .render import pdf as pdf_render

app = typer.Typer(
    add_completion=False,
    help="Tailor a resume to a job description without inventing anything.",
    no_args_is_help=True,
)
console = Console()




def _interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _walk_gaps(resume, job, prof, profile_path: Path, out: Path) -> None:
    """Ask about each unevidenced requirement. Never writes a claim the user didn't make."""
    prompts = elicit.prompts_for(prof, job, resume.gaps)
    if not prompts:
        return

    console.print(
        f"\n[bold]{len(prompts)} thing(s) this job asks for that your profile doesn't evidence.[/]"
    )
    console.print("[dim]Answering adds them to your master profile, so you're asked once.[/]\n")

    resolved: set[str] = set()
    profile_changed = False

    for p in prompts:
        console.print(f"[bold yellow]›[/] {p.gap.requirement}")

        if not typer.confirm("  Have you actually worked on something matching this?",
                             default=False):
            if p.adjacent and typer.confirm(
                "  Anything adjacent worth reframing toward it?", default=False
            ):
                _offer_reframe(resume, p, job, prof)
            else:
                console.print("  [dim]left as a gap — nothing added[/]\n")
            continue

        console.print("  [dim]Tell me about it. Facts only — this becomes a bullet verbatim.[/]")
        answers = {
            key: typer.prompt(f"  {question}", default="", show_default=False)
            for key, question in elicit.ANSWER_FIELDS
        }

        with console.status("  Writing it up..."):
            bullet, flags = elicit.compose_from_answers(answers, p.gap.requirement, job, prof)

        if bullet is None:
            console.print("  [dim]nothing to work with — skipped[/]\n")
            continue

        console.print(f"\n  [green]{bullet.text}[/]")
        for f in flags:
            console.print(f"  [red]! {f}[/]  [dim](not in what you told me)[/]")

        if not typer.confirm("  Is that accurate?", default=True):
            console.print("  [dim]discarded[/]\n")
            continue

        exp = _pick_role(prof)
        elicit.add_to_profile(prof, bullet, exp.id if exp else None)
        profile_changed = True
        _attach(resume, bullet, exp)
        resolved.add(p.gap.requirement)
        console.print("  [green]added[/]\n")

    if profile_changed:
        store.save_profile(prof, profile_path)
        console.print(f"[dim]Master profile updated: {profile_path}[/]")
    elicit.resolved_gaps(resume, resolved)


def _offer_reframe(resume, prompt, job, prof) -> None:
    source = prompt.adjacent[0]
    console.print(f"  [dim]closest thing you've written:[/] {source.text[:90]}")
    with console.status("  Reframing..."):
        text, rationale, _ = elicit.reframe(source, prompt.gap.requirement, job, prof)

    if text.strip() == source.text.strip():
        console.print(f"  [dim]{rationale}[/]\n")
        return

    console.print(f"  [green]{text}[/]\n  [dim]{rationale}[/]")
    if not typer.confirm("  Use this wording?", default=False):
        console.print("  [dim]kept as written[/]\n")
        return

    for tb in resume.bullets():
        if tb.source_id == source.id:
            tb.text, tb.rationale, tb.locked = text, rationale, True
            console.print("  [green]updated[/]\n")
            return
    console.print("  [dim]that bullet isn't on this resume — left alone[/]\n")


def _pick_role(prof):
    if not prof.experience:
        return None
    console.print("  [dim]Which role was this under?[/]")
    for i, e in enumerate(prof.experience, 1):
        console.print(f"    [dim]{i}[/] {e.title}, {e.company}")
    choice = typer.prompt("  Number", default="1")
    try:
        return prof.experience[int(choice) - 1]
    except (ValueError, IndexError):
        return prof.experience[0]


def _attach(resume, bullet, exp) -> None:
    """Put a newly-authored bullet onto this resume, under the right role."""
    tb = TailoredBullet(
        source_id=bullet.id, text=bullet.text, original=bullet.text,
        score=1.0, rationale="you wrote this just now", locked=True,
    )
    for te in resume.experience:
        if exp is not None and te.source_id == exp.id:
            te.bullets.insert(0, tb)
            return
    if resume.experience:
        resume.experience[0].bullets.insert(0, tb)


def _read_jd(source: str) -> str:
    if source == "-":
        return sys.stdin.read()
    p = Path(source)
    if p.exists():
        return p.read_text(encoding="utf-8")
    return source  # treat as a pasted JD


@app.command()
def run(
    jd: Annotated[str, typer.Argument(help="Path to a JD file, a pasted JD, or '-' for stdin")],
    profile: Annotated[Path, typer.Option("--profile", "-p")] = DEFAULT_PROFILE,
    pages: Annotated[
        int | None,
        typer.Option(help="Cap the page count. Off by default — a 2-page resume is fine."),
    ] = None,
    cover: Annotated[
        bool | None,
        typer.Option("--cover/--no-cover", help="Write a cover letter. Asks if not given."),
    ] = None,
    fill: Annotated[
        bool, typer.Option(help="Ask about gaps before writing anything")
    ] = True,
    docx: Annotated[bool, typer.Option(help="Also write .docx versions")] = False,
    strict: Annotated[bool, typer.Option(help="Reject rewrites that add unverifiable claims")] = True,
    out: Annotated[Path, typer.Option(help="Output root")] = OUT_DIR,
):
    """Parse a JD, tailor the resume, render PDF, and self-check it as an ATS would."""
    raw = _read_jd(jd)
    prof = store.load_profile(profile)

    with console.status("Parsing job description..."):
        job = parse_jd(raw)
    store.save_job(job, out)
    console.print(f"[bold]{job.role or '?'}[/] at [bold]{job.company or '?'}[/] "
                  f"({job.seniority}) · {len(job.must_haves())} must-haves · "
                  f"{len(job.keywords)} keywords")

    with console.status("Scoring and rewriting bullets..."):
        resume = tailor(prof, job, TailorConfig(strict_guard=strict))

    # Ask about anything the job wants that the profile can't evidence — before
    # rendering, so answers land on this resume rather than the next one.
    if fill and _interactive():
        _walk_gaps(resume, job, prof, profile, out)

    with console.status("Rendering..."):
        fit = pdf_render.render_resume_pdf(resume, max_pages=pages)

    d = store.app_dir(job.id, out)
    pdf_render.write(d / "resume.pdf", fit.pdf)
    store.save_resume(resume, out)

    report = check_pdf(fit.pdf, resume, job)
    (d / "ats.txt").write_text(report.text, encoding="utf-8")

    if docx:
        docx_render.resume_docx(resume, d / "resume.docx")

    if cover is None:
        cover = typer.confirm("\nWrite a cover letter too?", default=True) if _interactive() \
            else False

    if cover:
        with console.status("Writing cover letter..."):
            letter = write_cover_letter(resume, job, prof)
        store.save_cover_letter(letter, out)
        pdf_render.write(
            d / "cover_letter.pdf",
            pdf_render.render_cover_letter_pdf(letter, prof.contact),
        )
        if docx:
            docx_render.cover_letter_docx(letter, d / "cover_letter.docx")

    record = store.load_application(job.id, out)
    record.company, record.role = job.company, job.role
    record.resume_pages = report.pages
    record.keyword_coverage = round(report.keyword_coverage, 3)
    store.save_application(record, out)

    _report(resume, report, fit)
    console.print(f"\n[dim]Files:[/] {d}")
    console.print(f"[dim]Edit[/] {d / 'resume.json'} [dim]then[/] recast render {job.id}")


@app.command("import")
def import_resume(
    file: Annotated[Path, typer.Argument(help="A PDF, .docx, or plain-text resume")],
    profile: Annotated[Path, typer.Option("--profile", "-p")] = DEFAULT_PROFILE,
    force: Annotated[bool, typer.Option(help="Overwrite an existing profile")] = False,
):
    """Turn an existing resume into your master profile.

    Everything downstream is checked against this file, so the parse is verified
    against the source text and anything that could not be traced back is shown to
    you before it is saved.
    """
    from .ingest import accept, extract, parse_resume

    if profile.exists() and not force:
        if not _interactive():
            console.print(f"[yellow]{profile} exists. Pass --force to overwrite.[/]")
            raise typer.Exit(1)
        if not typer.confirm(f"{profile} exists. Overwrite it?", default=False):
            raise typer.Exit()

    try:
        upload = accept(file.read_bytes(), file.name)
    except Exception as exc:  # RejectedUpload carries a user-facing message
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1) from exc

    with console.status(f"Reading {upload.kind}..."):
        doc = extract(upload.data, upload.filename)
    console.print(f"[dim]{len(doc.text)} characters from {doc.pages} page(s)[/]")
    for w in doc.warnings:
        console.print(f"  [yellow]![/] {w}")

    with console.status("Structuring..."):
        result = parse_resume(doc)

    prof = result.profile
    prof.origin, prof.source_filename = "upload", upload.filename
    prof.parse_confidence = result.confidence

    console.print(
        f"\n[bold]{prof.contact.name or '(no name found)'}[/] · "
        f"{len(prof.experience)} role(s) · {len(prof.all_bullets())} bullet(s) · "
        f"confidence [bold]{result.confidence:.0%}[/]"
    )
    for e in prof.experience:
        console.print(f"  {e.title}, {e.company}  [dim]{e.start} – {e.end or 'Present'} · "
                      f"{len(e.bullets)} bullets[/]")

    for w in result.warnings:
        console.print(f"  [yellow]![/] {w}")
    if result.unverified:
        console.print("\n[bold red]Not found in the original document:[/]")
        for text in result.unverified[:5]:
            console.print(f"  [red]•[/] {text[:100]}")

    if result.needs_review and _interactive():
        if not typer.confirm("\nSave anyway?", default=not result.unverified):
            console.print("[dim]Not saved.[/]")
            raise typer.Exit()

    store.save_profile(prof, profile)
    console.print(f"\n[green]Saved[/] {profile}")
    console.print(f"[dim]Review it, then:[/] recast run <job.txt> --profile {profile}")


@app.command()
def baseline(
    profile: Annotated[Path, typer.Option("--profile", "-p")] = DEFAULT_PROFILE,
    pages: Annotated[int | None, typer.Option()] = None,
    out: Annotated[Path, typer.Option()] = OUT_DIR,
):
    """Render your master profile as-is. No JD, no model calls, no API key needed."""
    from .pipeline.tailor import baseline as build_baseline

    resume = build_baseline(store.load_profile(profile))
    fit = pdf_render.render_resume_pdf(resume, max_pages=pages)
    d = store.app_dir("baseline", out)
    pdf_render.write(d / "resume.pdf", fit.pdf)
    store.save_resume(resume, out)
    report = check_pdf(fit.pdf, resume)
    (d / "ats.txt").write_text(report.text, encoding="utf-8")
    _report(resume, report, fit)
    console.print(f"\n[dim]Files:[/] {d}")


@app.command()
def render(
    job_id: Annotated[str, typer.Argument(help="Job id, i.e. the folder name under out/")],
    pages: Annotated[int | None, typer.Option()] = None,
    docx: Annotated[bool, typer.Option()] = False,
    out: Annotated[Path, typer.Option()] = OUT_DIR,
):
    """Re-render from an edited resume.json. No model calls, no cost, instant."""
    resume = store.load_resume(job_id, out)
    job = store.load_job(job_id, out)
    fit = pdf_render.render_resume_pdf(resume, max_pages=pages)

    d = store.app_dir(job_id, out)
    pdf_render.write(d / "resume.pdf", fit.pdf)
    store.save_resume(resume, out)
    report = check_pdf(fit.pdf, resume, job)
    (d / "ats.txt").write_text(report.text, encoding="utf-8")
    if docx:
        docx_render.resume_docx(resume, d / "resume.docx")

    _report(resume, report, fit)


@app.command()
def fill(
    job_id: Annotated[str, typer.Argument()],
    profile: Annotated[Path, typer.Option("--profile", "-p")] = DEFAULT_PROFILE,
    out: Annotated[Path, typer.Option()] = OUT_DIR,
):
    """Work through this job's gaps by answering questions, then re-render.

    For each thing the job wants that your profile can't evidence, you get asked
    whether you've actually done it. If yes, your answers become a bullet and are
    saved to your master profile. If no, you can reframe adjacent real work — or
    leave the gap alone.
    """
    resume = store.load_resume(job_id, out)
    job = store.load_job(job_id, out)
    prof = store.load_profile(profile)

    if not _interactive():
        console.print("[yellow]This needs a terminal — it's a conversation.[/]")
        raise typer.Exit(1)

    _walk_gaps(resume, job, prof, profile, out)

    fit = pdf_render.render_resume_pdf(resume)
    d = store.app_dir(job_id, out)
    pdf_render.write(d / "resume.pdf", fit.pdf)
    store.save_resume(resume, out)
    report = check_pdf(fit.pdf, resume, job)
    (d / "ats.txt").write_text(report.text, encoding="utf-8")
    _report(resume, report, fit)


@app.command()
def ats(
    job_id: Annotated[str, typer.Argument()],
    show_text: Annotated[bool, typer.Option("--text", help="Print the extracted text")] = False,
    out: Annotated[Path, typer.Option()] = OUT_DIR,
):
    """Show what an ATS actually reads from the generated PDF."""
    d = store.app_dir(job_id, out)
    pdf = (d / "resume.pdf").read_bytes()
    resume = store.load_resume(job_id, out)
    job = store.load_job(job_id, out)
    report = check_pdf(pdf, resume, job)
    _report(resume, report, None)
    if show_text:
        console.print("\n[bold]Extracted text[/]\n")
        console.print(report.text)


@app.command("list")
def list_apps(out: Annotated[Path, typer.Option()] = OUT_DIR):
    """List every application you've generated."""
    apps = store.list_applications(out)
    if not apps:
        console.print("[dim]No applications yet.[/]")
        raise typer.Exit()
    table = Table(box=None, pad_edge=False)
    for col in ("updated", "status", "company", "role", "coverage", "id"):
        table.add_column(col)
    for a in apps:
        cov = f"{a.keyword_coverage:.0%}" if a.keyword_coverage is not None else "-"
        table.add_row(a.updated, a.status, a.company or "-", a.role or "-", cov, a.job_id)
    console.print(table)


@app.command()
def status(
    job_id: Annotated[str, typer.Argument()],
    new_status: Annotated[str, typer.Argument(help="draft|applied|screening|interviewing|offer|rejected|withdrawn")],
    note: Annotated[str, typer.Option("--note", "-n")] = "",
    out: Annotated[Path, typer.Option()] = OUT_DIR,
):
    """Update an application's status."""
    record = store.load_application(job_id, out)
    record.status = new_status  # type: ignore[assignment]
    if note:
        record.notes.append(note)
    store.save_application(record, out)
    console.print(f"{job_id} -> [bold]{new_status}[/]")


@app.command()
def models():
    """List models your provider actually serves. Catalogs drift; this is the check."""
    from .config import settings
    from .llm.client import client

    console.print(f"[dim]{settings.base_url}[/]\n")
    for m in sorted(x.id for x in client().models.list().data):
        tags = [t for t, v in
                (("fast", settings.model_fast), ("smart", settings.model_smart),
                 ("prose", settings.model_prose)) if v == m]
        console.print(f"  {m}" + (f"  [green]<- {', '.join(tags)}[/]" if tags else ""))


@app.command()
def initdb():
    """Create the Postgres tables. Safe to re-run; needs DATABASE_URL set."""
    if not store.using_postgres():
        console.print("[yellow]DATABASE_URL is not set — nothing to do.[/]")
        console.print("[dim]Without it, recast stores applications as files under out/.[/]")
        raise typer.Exit(1)

    from .store.postgres import PgStore

    PgStore().init_schema()
    console.print("[green]Tables ready.[/]")

    profile_path = DEFAULT_PROFILE
    if profile_path.exists() and typer.confirm(
        f"Upload {profile_path.name} as your master profile?", default=True
    ):
        store.save_profile(store.FileStore(OUT_DIR).load_profile(profile_path), profile_path)
        console.print("[green]Profile uploaded.[/]")


@app.command()
def serve(
    host: str = "127.0.0.1",
    port: int = 8000,
    reload: bool = False,
):
    """Run the HTTP API (what the editor UI will talk to)."""
    import uvicorn

    uvicorn.run("recast.api.main:api", host=host, port=port, reload=reload)


def _report(resume: TailoredResume, report, fit) -> None:
    console.print()
    if fit:
        note = f"{fit.pages} page(s) at {fit.scale:g}x"
        if fit.trimmed:
            note += f", {fit.trimmed} bullet(s) trimmed to fit"
        console.print(f"[bold]Render[/]  {note}")

    console.print(f"[bold]ATS[/]     keyword coverage {report.keyword_coverage:.0%}"
                  f" · {len(report.missing_bullets)} bullet(s) lost in extraction")
    for w in report.warnings:
        console.print(f"  [yellow]![/] {w}")
    for b in report.missing_bullets[:3]:
        console.print(f"  [yellow]![/] not extractable: {b}")
    if report.keyword_misses:
        console.print(f"  [dim]missing keywords:[/] {', '.join(report.keyword_misses[:12])}")

    flagged = [b for b in resume.bullets() if b.flags]
    if flagged:
        console.print(f"\n[bold red]Guard[/]   {len(flagged)} bullet(s) flagged")
        for b in flagged[:5]:
            console.print(f"  [red]•[/] {b.flags[0]}")
            console.print(f"    [dim]{b.text[:90]}[/]")

    if resume.trimmed:
        console.print(f"\n[bold]Trimmed[/] {len(resume.trimmed)} bullet(s) — in resume.json under "
                      f"'trimmed', put any back and re-render")

    musts = [g for g in resume.gaps if g.kind == "must"]
    missing = [g for g in musts if g.confidence == "high"]
    unsure = [g for g in musts if g.confidence == "low"]
    if missing:
        console.print(f"\n[bold]Gaps[/]    {len(missing)} must-have(s) absent from your profile")
        for g in missing[:5]:
            console.print(f"  [yellow]•[/] {g.requirement[:100]}")
    if unsure:
        console.print(f"\n[bold]Check[/]   {len(unsure)} must-have(s) we could not confirm")
        for g in unsure[:5]:
            console.print(f"  [dim]?[/] {g.requirement[:100]}")

    console.print(f"\n[dim]{elicit.RESPONSIBILITY_NOTICE}[/]")


if __name__ == "__main__":
    app()
