"""The ytmine command line.

Every command funnels through the same three steps: resolve credentials, gate
the target's licence through the YouTube Data API, and only then hand the video
to the yt-dlp backend.

Each command carries its own options rather than a nested options struct: with
typer the signature is what `--help` prints, and folding flags into a struct
hides them from the user.
"""

from __future__ import annotations

import webbrowser
from pathlib import Path
from typing import Annotated, Final

import anyio
import typer
from rich.console import Console

from ytmine import auth as oauth
from ytmine.api import youtube_api
from ytmine.config import DownloadOptions, Settings
from ytmine.download import DownloadJob, read_channel_batch
from ytmine.errors import TokenMissingError, YtmineError
from ytmine.gate import judge
from ytmine.report import render_outcome, render_verdict, summary
from ytmine.token import Credentials, clock, load, save
from ytmine.videos import parse_video_ref

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)
console = Console()

_Url = Annotated[str, typer.Argument(help="Link do YouTube.")]
_Out = Annotated[Path | None, typer.Option("--out", help="Pasta de destino.")]
_Quality = Annotated[
    str, typer.Option("--quality", help="Formato do yt-dlp, ex. 'bestvideo+bestaudio'.")
]
_Parallel = Annotated[
    int, typer.Option("--parallel", min=1, max=8, help="Simultaneos.")
]
_DryRun = Annotated[bool, typer.Option("--dry-run", help="Nao baixa nada, so mostra.")]
_Force = Annotated[bool, typer.Option("--force", help="Ignora o arquivo de historico.")]
_Limit = Annotated[int, typer.Option("--limit", min=1, max=500, help="Quantos videos.")]

_DEFAULT_QUALITY: Final = "bv*+ba/b"


def main() -> None:
    """Console entry point: known errors become one line, not a traceback."""
    try:
        app()
    except YtmineError as error:
        Console(stderr=True).print(f"[red]erro[/red]  {error}")
        raise SystemExit(1) from None


@app.command()
def auth() -> None:
    """Autoriza o ytmine a ler seu canal. Precisa rodar uma vez so."""
    settings = Settings.discover()
    secrets_ = oauth.read_client_secrets(settings.client_secrets)
    url = oauth.authorization_url(secrets_, oauth.new_state())
    console.print("Abra esta URL e autorize:\n")
    console.print(url)
    _ = webbrowser.open(url)
    pasted = input("Cole a URL de redirecionamento (ou somente o codigo): ")
    credentials = anyio.run(
        oauth.exchange_code, oauth.extract_code(pasted), secrets_, clock()
    )
    save(settings.token, credentials)
    console.print(f"[green]ok[/green] token salvo em {settings.token}")


@app.command()
def check(url: _Url) -> None:
    """Mostra a licenca de um video e se o ytmine baixaria ele."""
    video_id = parse_video_ref(url)
    settings = Settings.discover()

    async def run() -> None:
        async with youtube_api(_credentials(settings)) as api:
            owned = await api.owned_channel_or_none()
            console.print(render_verdict(judge(await api.video(video_id), owned)))

    anyio.run(run)


# A typer command's signature *is* its `--help` output, so the flags stay as
# named parameters instead of being smuggled through an options struct.
@app.command()
def download(  # noqa: PLR0913, PLR0917
    urls: Annotated[list[str], typer.Argument(help="Links do YouTube.")],
    out: _Out = None,
    quality: _Quality = _DEFAULT_QUALITY,
    parallel: _Parallel = 1,
    dry_run: _DryRun = False,
    force: _Force = False,
) -> None:
    """Baixa um ou mais videos — so passa o que e seu ou Creative Commons."""
    settings = Settings.discover()
    options = _options(settings, out, quality, force)
    video_ids = [parse_video_ref(url) for url in urls]

    async def run() -> None:
        async with youtube_api(_credentials(settings)) as api:
            job = DownloadJob(
                api=api,
                owned=await api.owned_channel_or_none(),
                options=options,
                dry_run=dry_run,
            )
            for outcome in await job.many(video_ids, parallel):
                console.print(render_outcome(outcome))

    anyio.run(run)


@app.command()
def channel(  # noqa: PLR0913, PLR0917
    limit: _Limit = 50,
    out: _Out = None,
    quality: _Quality = _DEFAULT_QUALITY,
    parallel: _Parallel = 1,
    dry_run: _DryRun = False,
    force: _Force = False,
) -> None:
    """Baixa os videos do seu proprio canal, do mais recente ao mais antigo."""
    settings = Settings.discover()
    options = _options(settings, out, quality, force)

    async def run() -> None:
        async with youtube_api(_credentials(settings)) as api:
            batch = await read_channel_batch(api, limit)
            if not batch.video_ids:
                console.print(f"[yellow]nenhum video em[/yellow] {batch.channel.title}")
                return
            heading = (
                f"canal [bold]{batch.channel.title}[/bold]"
                f" — {len(batch.video_ids)} videos"
            )
            console.print(heading)
            job = DownloadJob(
                api=api, owned=batch.channel, options=options, dry_run=dry_run
            )
            summary(console, await job.many(batch.video_ids, parallel))

    anyio.run(run)


@app.command()
def paths() -> None:
    """Mostra onde o ytmine guarda segredos, token e downloads."""
    settings = Settings.discover()
    console.print(f"config    {settings.config_dir}")
    console.print(f"segredos  {settings.client_secrets}")
    console.print(f"token     {settings.token}")
    console.print(f"destino   {settings.out_dir}")


def _options(
    settings: Settings, out: Path | None, quality: str, force: bool
) -> DownloadOptions:
    """Resolve the shared flags into download options."""
    out_dir = settings.out_dir if out is None else out
    return DownloadOptions(out_dir=out_dir, format=quality, skip_downloaded=not force)


def _credentials(settings: Settings) -> Credentials:
    """Load the cached token, pointing at `ytmine auth` when it is absent."""
    stored = load(settings.token)
    if stored is None:
        raise TokenMissingError
    return stored
