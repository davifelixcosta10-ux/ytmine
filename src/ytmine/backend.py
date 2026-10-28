"""The yt-dlp backend.

YouTube exposes no media-download endpoint, so the bytes come from yt-dlp — but
only after the API has already confirmed the video is Creative Commons or the
user's own upload. The rights decision never reaches this module.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import anyio

from ytmine.config import DownloadOptions
from ytmine.errors import BackendUnavailableError
from ytmine.models import VideoId

_BINARY: Final = "yt-dlp"
_SKIPPED_EXIT: Final = 101
_ARCHIVE_NAME: Final = ".ytmine-archive"
_WATCH_URL: Final = "https://www.youtube.com/watch?v="


@dataclass(frozen=True, slots=True)
class FetchRequest:
    """Everything one backend invocation needs."""

    video_id: VideoId
    options: DownloadOptions


@dataclass(frozen=True, slots=True)
class Fetched:
    """The files yt-dlp produced."""

    video_id: VideoId
    paths: tuple[Path, ...]


@dataclass(frozen=True, slots=True)
class Skipped:
    """Already in the download archive, nothing to do."""

    video_id: VideoId


@dataclass(frozen=True, slots=True)
class Failed:
    """yt-dlp exited with a status that is neither success nor skip."""

    video_id: VideoId
    status: int


type FetchResult = Fetched | Skipped | Failed


async def fetch(request: FetchRequest) -> FetchResult:
    """Run yt-dlp for one video and report what it produced."""
    if shutil.which(_BINARY) is None:
        raise BackendUnavailableError(command=_BINARY)
    with tempfile.TemporaryDirectory(prefix="ytmine-") as scratch:
        paths_file = Path(scratch) / "paths.txt"
        command = build_command(request, paths_file)
        status = await anyio.to_thread.run_sync(lambda: subprocess.call(command))  # noqa: S603
        if status == 0:
            return Fetched(video_id=request.video_id, paths=read_paths(paths_file))
        if status == _SKIPPED_EXIT:
            return Skipped(video_id=request.video_id)
        return Failed(video_id=request.video_id, status=status)


def build_command(request: FetchRequest, paths_file: Path) -> list[str]:
    """Assemble the yt-dlp argv for one video."""
    options = request.options
    command = [
        _BINARY,
        f"{_WATCH_URL}{request.video_id}",
        "--no-playlist",
        "--format",
        options.format,
        "--merge-output-format",
        options.container,
        "--output",
        str(options.out_dir / options.name_template),
        "--print-to-file",
        "after_move:filepath",
        str(paths_file),
    ]
    if options.embed_metadata:
        command.append("--embed-metadata")
    if options.skip_downloaded:
        command.extend(["--download-archive", str(options.out_dir / _ARCHIVE_NAME)])
    return command


def read_paths(paths_file: Path) -> tuple[Path, ...]:
    """Read the final filepaths yt-dlp printed for this download."""
    if not paths_file.is_file():
        return ()
    lines = paths_file.read_text(encoding="utf-8").splitlines()
    return tuple(Path(line.strip()) for line in lines if line.strip())
