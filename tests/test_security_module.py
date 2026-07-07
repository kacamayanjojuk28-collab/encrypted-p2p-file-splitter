from pathlib import Path

import pytest

from src.security_module import (
    SecurityConfig,
    is_path_inside_base,
    is_ui_auth_configured,
    resolve_safe_path,
    sanitize_filename,
    validate_file_size,
)


def test_allowed_path_is_accepted(tmp_path: Path) -> None:
    allowed = tmp_path / "workspace"
    allowed.mkdir()
    target = allowed / "file.bin"
    target.write_bytes(b"ok")

    assert resolve_safe_path(target, (allowed,), allow_absolute_paths=True) == target.resolve()


def test_path_traversal_is_rejected(tmp_path: Path) -> None:
    allowed = tmp_path / "workspace"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()

    with pytest.raises(ValueError, match="outside allowed"):
        resolve_safe_path(allowed / ".." / "outside", (allowed,), allow_absolute_paths=True)


def test_absolute_path_rejected_when_disabled(tmp_path: Path) -> None:
    absolute_path = tmp_path / "file.bin"

    with pytest.raises(ValueError, match="Absolute paths are not allowed"):
        resolve_safe_path(absolute_path, (tmp_path,), allow_absolute_paths=False)


def test_file_size_limit_rejects_large_file(tmp_path: Path) -> None:
    file_path = tmp_path / "large.bin"
    file_path.write_bytes(b"x" * 1025)

    with pytest.raises(ValueError, match="File size exceeds"):
        validate_file_size(file_path, max_size_mb=0)


def test_sanitize_filename_removes_dangerous_characters() -> None:
    assert sanitize_filename("../bad name?.bin") == "bad_name_.bin"


def test_path_outside_allowed_base_is_rejected(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    target = outside / "file.bin"
    target.write_bytes(b"x")

    assert not is_path_inside_base(target, allowed)
    with pytest.raises(ValueError, match="outside allowed"):
        resolve_safe_path(target, (allowed,), allow_absolute_paths=True)


def test_missing_auth_env_is_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_USERNAME", raising=False)
    monkeypatch.delenv("APP_PASSWORD", raising=False)

    assert is_ui_auth_configured() is False


def test_security_config_defaults_are_safe() -> None:
    config = SecurityConfig()

    assert config.max_upload_size_mb == 100
    assert config.allow_absolute_paths is False
    assert config.bind_host == "127.0.0.1"
