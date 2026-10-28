"""Where ytmine keeps its state, and the knobs that shape a download."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final

_APP_NAME: Final = "ytmine"

_FORMAT_BEST: Final = "bv*+ba/b"

_NAME_TEMPLATE: Final = "%(uploader)s/%(title)s [%(id)s].%(ext)s"


def _config_root() -> Path:
    """Resolve the config directory, honouring ``XDG_CONFIG_HOME``."""
    override = os.environ.get("YTMINE_CONFIG_DIR")
    if override:
        return Path(override).expanduser()
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg).expanduser() / _APP_NAME
    return Path.home() / ".config" / _APP_NAME


def default_out_dir() -> Path:
    """The default destination: ``~/Downloads/ytmine``."""
    return Path.home() / "Downloads" / _APP_NAME


@dataclass(frozen=True, slots=True)
class Settings:
    """Filesystem locations ytmine reads and writes."""

    config_dir: Path
    out_dir: Path

    @classmethod
    def discover(cls) -> Settings:
        """Build the settings from the environment."""
        return cls(config_dir=_config_root(), out_dir=default_out_dir())

    @property
    def client_secrets(self) -> Path:
        """Path of the Google OAuth 'Desktop app' client JSON."""
        return self.config_dir / "client_secrets.json"

    @property
    def token(self) -> Path:
        """Path of the cached OAuth token."""
        return self.config_dir / "token.json"


@dataclass(frozen=True, slots=True)
class DownloadOptions:
    """Everything the yt-dlp invocation needs beyond the target."""

    out_dir: Path
    format: str = _FORMAT_BEST
    container: str = "mp4"
    name_template: str = _NAME_TEMPLATE
    skip_downloaded: bool = True
    embed_metadata: bool = True
