"""Configuration for the Windows MCP server, from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    host: str
    username: str
    password: str
    auth: str
    ssl: bool
    port: int
    cert_validation: bool
    timeout: int


def load_settings() -> Settings:
    """Build settings from WINRM_* environment variables.

    A local .env is honored - both next to this project and in the current
    working directory (so the server works standalone and when launched from a
    parent project like cml-mcp via `uv run --directory`).
    """
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    load_dotenv()  # also honor .env in the current working directory
    # shared secrets base for the whole MCP suite (../.env, one level above the
    # repos) - lowest precedence: process env > this repo's .env > shared. Skipped
    # silently if absent, so standalone clones are unaffected.
    load_dotenv(Path(__file__).resolve().parents[3] / ".env")

    host = os.environ.get("WINRM_HOST", "")
    if not host:
        raise RuntimeError(
            "WINRM_HOST is not set. Set WINRM_HOST (e.g. 192.0.2.50), "
            "WINRM_USERNAME and WINRM_PASSWORD in the environment or a .env file."
        )
    username = os.environ.get("WINRM_USERNAME", "")
    password = os.environ.get("WINRM_PASSWORD", "")
    if not username or not password:
        raise RuntimeError("WINRM_USERNAME and WINRM_PASSWORD must be set.")

    ssl = os.environ.get("WINRM_SSL", "false").strip().lower() in ("1", "true", "yes")
    port = int(os.environ.get("WINRM_PORT", "5986" if ssl else "5985"))
    auth = os.environ.get("WINRM_AUTH", "ntlm").strip().lower()
    cert_validation = os.environ.get(
        "WINRM_CERT_VALIDATION", "false").strip().lower() in ("1", "true", "yes")
    timeout = int(os.environ.get("WINRM_TIMEOUT", "120"))

    return Settings(host=host, username=username, password=password, auth=auth,
                    ssl=ssl, port=port, cert_validation=cert_validation, timeout=timeout)
