"""The yt-dlp invocation: argv is a pure function of the options."""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest

from ytmine.backend import FetchRequest, build_command, read_paths
from ytmine.config import DownloadOptions
from ytmine.models import VideoId

_VIDEO_ID: Final = "dQw4w9WgXcQ"
_SCRATCH: Final = Path("/tmp/scratch/paths.txt")
_ARCHIVE: Final = ".ytmine-archive"
_TEMPLATE: Final = "%(uploader)s/%(title)s [%(id)s].%(ext)s"


def _request(out_dir: Path, skip_downloaded: bool = True) -> FetchRequest:
    """A fetch request for one video, with the archive behaviour set explicitly."""
    return FetchRequest(
        video_id=VideoId(_VIDEO_ID),
        options=DownloadOptions(out_dir=out_dir, skip_downloaded=skip_downloaded),
    )


class Test_build_command:
    """Given a fetch request, when the argv is built, then it targets one video."""

    def test_targets_the_requested_video_only(self, tmp_path: Path) -> None:
        command = build_command(_request(tmp_path), _SCRATCH)

        assert command[1] == f"https://www.youtube.com/watch?v={_VIDEO_ID}"

    @pytest.mark.parametrize(
        "flag",
        [
            "--no-playlist",
            "--format",
            "--merge-output-format",
            "--output",
            "--print-to-file",
        ],
    )
    def test_carries_the_mandatory_flags(self, tmp_path: Path, flag: str) -> None:
        command = build_command(_request(tmp_path), _SCRATCH)

        assert flag in command

    def test_points_the_output_template_at_the_destination(
        self, tmp_path: Path
    ) -> None:
        out_dir = tmp_path / "out"

        command = build_command(_request(out_dir), _SCRATCH)

        index = command.index("--output")
        assert command[index + 1] == str(out_dir / _TEMPLATE)

    def test_records_the_archive_hit_file_when_skipping_enabled(
        self, tmp_path: Path
    ) -> None:
        out_dir = tmp_path / "out"

        command = build_command(_request(out_dir), _SCRATCH)

        index = command.index("--download-archive")
        assert command[index + 1] == str(out_dir / _ARCHIVE)

    def test_drops_the_archive_flag_when_forced(self, tmp_path: Path) -> None:
        command = build_command(_request(tmp_path, skip_downloaded=False), _SCRATCH)

        assert "--download-archive" not in command

    def test_writes_the_printed_paths_to_its_own_scratch_file(
        self, tmp_path: Path
    ) -> None:
        command = build_command(_request(tmp_path), _SCRATCH)

        index = command.index("--print-to-file")
        assert command[index + 1] == "after_move:filepath"
        assert command[index + 2] == str(_SCRATCH)


class Testread_paths:
    """Given a yt-dlp paths file, when it is read, then only real paths survive."""

    def test_returns_one_path_per_written_line(self, tmp_path: Path) -> None:
        paths_file = tmp_path / "paths.txt"
        paths_file.write_text(
            f"{tmp_path}/a.mp4\n{tmp_path}/b.m4a\n{tmp_path}/c.mp4\n", encoding="utf-8"
        )

        assert read_paths(paths_file) == (
            tmp_path / "a.mp4",
            tmp_path / "b.m4a",
            tmp_path / "c.mp4",
        )

    def test_ignores_blank_lines(self, tmp_path: Path) -> None:
        paths_file = tmp_path / "paths.txt"
        paths_file.write_text(f"{tmp_path}/a.mp4\n\n   \n", encoding="utf-8")

        assert read_paths(paths_file) == (tmp_path / "a.mp4",)

    def test_returns_nothing_when_the_file_is_missing(self, tmp_path: Path) -> None:
        assert read_paths(tmp_path / "absent.txt") == ()
