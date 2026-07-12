"""WinRM / PowerShell-remoting client for Windows Server.

Wraps pypsrp's synchronous Client in asyncio.to_thread so the MCP tool layer
stays async. Everything runs PowerShell (or cmd) remotely over WinRM:
  - run_ps(script)      -> stdout text (raises WinRMError on a PS error stream)
  - run_ps_json(script) -> the script's output piped through ConvertTo-Json,
                           parsed to a dict/list (None when empty)
  - run_cmd(command)    -> {"stdout", "stderr", "rc"}

Auth is typically NTLM with a username/password (works from Linux without a
cert); Kerberos/CredSSP/basic are also supported via WINRM_AUTH.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from pypsrp.client import Client

from .config import Settings


class WinRMError(Exception):
    """A remote PowerShell/command call failed (error stream or non-zero rc)."""


class WindowsClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def _client(self) -> Client:
        s = self.settings
        return Client(
            s.host, username=s.username, password=s.password, ssl=s.ssl,
            port=s.port, auth=s.auth, cert_validation=s.cert_validation,
            connection_timeout=s.timeout)

    # ------------------------------------------------------------------
    # PowerShell
    # ------------------------------------------------------------------
    def _run_ps_sync(self, script: str) -> str:
        output, streams, had_errors = self._client().execute_ps(script)
        if had_errors:
            detail = "; ".join(
                str(getattr(e, "message", e)) for e in (streams.error or []))
            raise WinRMError(detail or "PowerShell reported an error")
        return output or ""

    async def run_ps(self, script: str) -> str:
        """Run a PowerShell script; return its text output."""
        return await asyncio.to_thread(self._run_ps_sync, script)

    async def run_ps_json(self, script: str, depth: int = 4) -> Any:
        """Run a PowerShell script, pipe its output through ConvertTo-Json, and
        parse the result to a dict/list (or None if there was no output)."""
        wrapped = (
            "$ErrorActionPreference='Stop';\n"
            f"$McpResult = @({script});\n"
            f"if ($McpResult.Count -eq 1) {{ $McpResult = $McpResult[0] }}\n"
            f"$McpResult | ConvertTo-Json -Depth {depth} -Compress"
        )
        out = (await self.run_ps(wrapped)).strip()
        if not out:
            return None
        try:
            return json.loads(out)
        except json.JSONDecodeError:
            return out

    # ------------------------------------------------------------------
    # cmd.exe
    # ------------------------------------------------------------------
    def _run_cmd_sync(self, command: str) -> dict:
        stdout, stderr, rc = self._client().execute_cmd(command)
        return {"stdout": stdout, "stderr": stderr, "rc": rc}

    async def run_cmd(self, command: str) -> dict:
        """Run a cmd.exe command; return {stdout, stderr, rc}."""
        result = await asyncio.to_thread(self._run_cmd_sync, command)
        if result["rc"] != 0 and result["stderr"]:
            raise WinRMError(f"rc={result['rc']}: {result['stderr'].strip()[:400]}")
        return result

    @staticmethod
    def ps_literal(value: str) -> str:
        """Quote a string as a PowerShell single-quoted literal (escapes ')."""
        return "'" + str(value).replace("'", "''") + "'"
