"""Rich rendering for verdicts and download outcomes."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, assert_never

from rich.console import Console
from rich.table import Table

from ytmine.download import Broken, DownloadOutcome, Planned, Saved, Unchanged
from ytmine.gate import Allowed, Refused, Verdict

_COLUMNS: Final = ("video", "estado", "base", "detalhe")


@dataclass(frozen=True, slots=True)
class _Row:
    """A download outcome flattened into display columns."""

    title: str
    status: str
    basis: str
    detail: str


def render_verdict(verdict: Verdict) -> str:
    """One-line verdict for a single video, with the reason attached."""
    match verdict:
        case Allowed(video=video, basis=basis):
            return f"[green]permitido[/green]  {video.title}  ({basis.value})"
        case Refused(video=video, why=why):
            return f"[red]bloqueado[/red]  {video.title}  ({why})"
        case unreachable:
            assert_never(unreachable)


def render_outcome(outcome: DownloadOutcome) -> str:
    """One-line outcome for a single video."""
    row = outcome_row(outcome)
    return f"{row.status}  {row.title}  ({row.basis}) {row.detail}"


def summary(console: Console, outcomes: Sequence[DownloadOutcome]) -> None:
    """Print the whole batch as one table."""
    table = Table(title="Resultado")
    for column in _COLUMNS:
        table.add_column(column)
    for outcome in outcomes:
        row = outcome_row(outcome)
        table.add_row(row.title, row.status, row.basis, row.detail)
    console.print(table)


def outcome_row(outcome: DownloadOutcome) -> _Row:
    """Flatten any outcome variant into its display columns."""
    match outcome:
        case Planned(video=video, basis=basis):
            return _Row(video.title, "simulado", basis.value, "--dry-run")
        case Saved(video=video, basis=basis, paths=paths):
            detail = ", ".join(path.name for path in paths) or "nenhum arquivo"
            return _Row(video.title, "baixado", basis.value, detail)
        case Unchanged(video=video):
            return _Row(video.title, "ja baixado", "", "no arquivo de historico")
        case Broken(video=video, status=status):
            return _Row(video.title, "falhou", "", f"yt-dlp status {status}")
        case Refused(video=video, why=why):
            return _Row(video.title, "bloqueado", "", why)
        case unreachable:
            assert_never(unreachable)
