"""Boundary tests: client-secrets parsing and code extraction."""

from __future__ import annotations

from pathlib import Path

import pytest

from ytmine.auth import ClientSecrets, extract_code, read_client_secrets
from ytmine.errors import AuthorizationError, ClientSecretsMissingError

_INSTALLED = (
    '{"installed":{"client_id":"the-client-id","client_secret":"the-secret-value"}}'
)
_WEB = '{"web":{"client_id":"the-client-id","client_secret":"the-secret-value"}}'


class Test_read_client_secrets:
    """Given a Google client JSON, when it is read, then the pair comes back."""

    def test_reads_an_installed_desktop_client(self, tmp_path: Path) -> None:
        path = tmp_path / "client_secrets.json"
        path.write_text(_INSTALLED, encoding="utf-8")

        secrets_ = read_client_secrets(path)

        assert secrets_ == ClientSecrets(
            client_id="the-client-id", client_secret="the-secret-value"
        )

    def test_reads_a_web_client(self, tmp_path: Path) -> None:
        path = tmp_path / "client_secrets.json"
        path.write_text(_WEB, encoding="utf-8")

        assert read_client_secrets(path).client_id == "the-client-id"

    def test_reports_a_missing_file_with_the_path(self, tmp_path: Path) -> None:
        path = tmp_path / "absent.json"

        with pytest.raises(ClientSecretsMissingError) as raised:
            read_client_secrets(path)

        assert str(path) in str(raised.value)

    def test_rejects_a_file_with_no_client_section(self, tmp_path: Path) -> None:
        path = tmp_path / "client_secrets.json"
        path.write_text('{"project_id":"x"}', encoding="utf-8")

        with pytest.raises(AuthorizationError):
            read_client_secrets(path)


class Test_extract_code:
    """Given what the user pasted, when it is extracted, then the code survives."""

    @pytest.mark.parametrize(
        "pasted",
        [
            "http://127.0.0.1:53123/?state=abc&code=4/0AbCdEf&scope=email",
            "http://127.0.0.1:53123/#code=4/0AbCdEf",
            "  http://127.0.0.1:53123/?code=4/0AbCdEf  ",
        ],
    )
    def test_pulls_the_code_out_of_a_redirect_url(self, pasted: str) -> None:
        assert extract_code(pasted) == "4/0AbCdEf"

    def test_passes_a_bare_code_through(self) -> None:
        assert extract_code("  4/0AbCdEf  ") == "4/0AbCdEf"

    def test_rejects_a_url_with_no_code(self) -> None:
        with pytest.raises(AuthorizationError):
            extract_code("http://127.0.0.1:53123/?error=access_denied")
