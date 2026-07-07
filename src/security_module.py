from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_MAX_UPLOAD_SIZE_MB = 100


@dataclass(frozen=True)
class SecurityConfig:
    max_upload_size_mb: int = DEFAULT_MAX_UPLOAD_SIZE_MB
    allowed_input_dirs: tuple[Path, ...] = (Path("."),)
    allowed_workspace_dir: Path = Path("workspace")
    allowed_output_dir: Path = Path(".")
    allow_absolute_paths: bool = False
    bind_host: str = "127.0.0.1"


def load_security_config(config_path: Path | str | None = None) -> SecurityConfig:
    """Load optional security config with safe defaults."""
    path = Path(config_path) if config_path is not None else Path("security_config.json")
    raw_security: dict[str, Any] = {}
    base_dir = path.resolve().parent

    if path.exists():
        with path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        raw_security = dict(raw.get("security", raw))
    else:
        base_dir = Path.cwd().resolve()

    def resolve_dir(value: str | Path) -> Path:
        configured = Path(value)
        if configured.is_absolute():
            return configured.resolve()
        return (base_dir / configured).resolve()

    allowed_input_dirs = tuple(
        resolve_dir(value)
        for value in raw_security.get("allowed_input_dirs", ["."])
    )
    return SecurityConfig(
        max_upload_size_mb=int(
            raw_security.get("max_upload_size_mb", DEFAULT_MAX_UPLOAD_SIZE_MB)
        ),
        allowed_input_dirs=allowed_input_dirs,
        allowed_workspace_dir=resolve_dir(raw_security.get("allowed_workspace_dir", "workspace")),
        allowed_output_dir=resolve_dir(raw_security.get("allowed_output_dir", ".")),
        allow_absolute_paths=bool(raw_security.get("allow_absolute_paths", False)),
        bind_host=str(raw_security.get("bind_host", "127.0.0.1")),
    )


def is_path_inside_base(path: Path | str, base_dir: Path | str) -> bool:
    resolved_path = Path(path).resolve()
    resolved_base = Path(base_dir).resolve()
    try:
        resolved_path.relative_to(resolved_base)
        return True
    except ValueError:
        return False


def resolve_safe_path(
    user_path: Path | str,
    allowed_base_dirs: list[Path] | tuple[Path, ...],
    allow_absolute_paths: bool = False,
) -> Path:
    candidate = Path(user_path)
    if candidate.is_absolute() and not allow_absolute_paths:
        raise ValueError("Absolute paths are not allowed by security configuration.")

    resolved_candidate = candidate.resolve()
    resolved_bases = [Path(base).resolve() for base in allowed_base_dirs]
    if not any(is_path_inside_base(resolved_candidate, base) for base in resolved_bases):
        allowed = ", ".join(str(base) for base in resolved_bases)
        raise ValueError(f"Path is outside allowed directories: {allowed}")
    return resolved_candidate


def validate_input_file_path(path: Path | str, security_config: SecurityConfig) -> Path:
    resolved = resolve_safe_path(
        path,
        security_config.allowed_input_dirs,
        allow_absolute_paths=security_config.allow_absolute_paths,
    )
    if not resolved.exists():
        raise FileNotFoundError(f"Input file not found: {resolved}")
    validate_file_size(resolved, security_config.max_upload_size_mb)
    return resolved


def validate_workspace_path(path: Path | str, security_config: SecurityConfig) -> Path:
    return resolve_safe_path(
        path,
        (security_config.allowed_workspace_dir,),
        allow_absolute_paths=security_config.allow_absolute_paths,
    )


def validate_output_file_path(path: Path | str, security_config: SecurityConfig) -> Path:
    resolved = resolve_safe_path(
        path,
        (security_config.allowed_output_dir,),
        allow_absolute_paths=security_config.allow_absolute_paths,
    )
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved


def validate_file_size(path: Path | str, max_size_mb: int) -> None:
    limit_bytes = max_size_mb * 1024 * 1024
    file_size = Path(path).stat().st_size
    if file_size > limit_bytes:
        raise ValueError(f"File size exceeds the configured limit of {max_size_mb} MB.")


def sanitize_filename(filename: str) -> str:
    name = Path(filename).name
    sanitized = re.sub(r"[^A-Za-z0-9._-]", "_", name).strip("._")
    if not sanitized:
        raise ValueError("Filename is empty after sanitization.")
    return sanitized


def is_ui_auth_configured() -> bool:
    return bool(os.environ.get("APP_USERNAME") and os.environ.get("APP_PASSWORD"))


def verify_ui_credentials(username: str, password: str) -> bool:
    expected_username = os.environ.get("APP_USERNAME")
    expected_password = os.environ.get("APP_PASSWORD")
    if not expected_username or not expected_password:
        return False
    return username == expected_username and password == expected_password
