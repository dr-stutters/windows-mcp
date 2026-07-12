"""ISE-free unit tests for the Windows MCP.

No live Windows box needed: the client's PowerShell layer is faked, so these test
the generated PowerShell, JSON parsing, quoting and config. Run: `uv run pytest`.
"""

from __future__ import annotations

import asyncio

import pytest
from mcp.server.fastmcp import FastMCP

from windows_mcp.client import WindowsClient
from windows_mcp.config import Settings, load_settings
from windows_mcp.tools import register_all


def run(coro):
    return asyncio.run(coro)


class FakeClient:
    """Records scripts instead of talking to WinRM; returns canned data."""

    def __init__(self, ps="ok", ps_json=None, cmd=None):
        self.calls: list[tuple[str, str]] = []
        self._ps, self._ps_json = ps, ps_json if ps_json is not None else {"ok": True}
        self._cmd = cmd or {"stdout": "", "stderr": "", "rc": 0}

    async def run_ps(self, script):
        self.calls.append(("ps", script))
        return self._ps

    async def run_ps_json(self, script, depth=4):
        self.calls.append(("json", script))
        return self._ps_json

    async def run_cmd(self, command):
        self.calls.append(("cmd", command))
        return self._cmd

    ps_literal = staticmethod(WindowsClient.ps_literal)


def _mcp(fake):
    mcp = FastMCP("windows")
    register_all(mcp, fake)
    return mcp


async def _call(mcp, tool, **args):
    res = await mcp.call_tool(tool, args)
    if isinstance(res, tuple):
        res = res[0]
    return "\n".join(getattr(b, "text", str(b)) for b in res)


# --------------------------------------------------------------------------
# ps_literal quoting
# --------------------------------------------------------------------------
def test_ps_literal_wraps_and_escapes():
    assert WindowsClient.ps_literal("lab.local") == "'lab.local'"
    assert WindowsClient.ps_literal("O'Brien") == "'O''Brien'"


# --------------------------------------------------------------------------
# run_ps_json wrapping + parsing (mock run_ps)
# --------------------------------------------------------------------------
def _client(ps_output: str) -> WindowsClient:
    c = WindowsClient(Settings("h", "u", "p", "ntlm", False, 5985, False, 30))

    async def fake_run_ps(script):
        fake_run_ps.script = script
        return ps_output

    c.run_ps = fake_run_ps  # type: ignore[method-assign]
    return c


def test_run_ps_json_parses_object():
    c = _client('{"Name":"DC1"}')
    assert run(c.run_ps_json("Get-ADDomain")) == {"Name": "DC1"}
    assert "ConvertTo-Json" in c.run_ps.script  # wrapping applied


def test_run_ps_json_parses_array():
    c = _client('[{"Name":"a"},{"Name":"b"}]')
    assert run(c.run_ps_json("Get-ADUser")) == [{"Name": "a"}, {"Name": "b"}]


def test_run_ps_json_empty_is_none():
    assert run(_client("").run_ps_json("Get-Nothing")) is None


def test_run_ps_json_non_json_returned_raw():
    assert run(_client("plain text").run_ps_json("x")) == "plain text"


# --------------------------------------------------------------------------
# tools generate the right PowerShell (FakeClient captures the script)
# --------------------------------------------------------------------------
def test_create_ad_user_script():
    fake = FakeClient()
    run(_call(_mcp(fake), "win_create_ad_user", sam_account_name="jdoe",
              password="P@ss'w0rd", user_principal_name="jdoe@lab.local"))
    _, script = fake.calls[-1]
    assert "New-ADUser" in script
    assert "-SamAccountName 'jdoe'" in script
    assert "ConvertTo-SecureString 'P@ss''w0rd'" in script  # escaped quote
    assert "-UserPrincipalName 'jdoe@lab.local'" in script


def test_install_feature_script():
    fake = FakeClient()
    run(_call(_mcp(fake), "win_install_feature", name="AD-Domain-Services"))
    _, script = fake.calls[-1]
    assert "Install-WindowsFeature -Name 'AD-Domain-Services'" in script
    assert "-IncludeManagementTools" in script


def test_add_dns_a_record_script():
    fake = FakeClient()
    run(_call(_mcp(fake), "win_add_dns_a_record", zone="lab.local", name="ise",
              ip="10.0.0.30", create_ptr=True))
    _, script = fake.calls[-1]
    assert "Add-DnsServerResourceRecordA" in script
    assert "-ZoneName 'lab.local'" in script and "-Name 'ise'" in script
    assert "-IPv4Address '10.0.0.30'" in script and "-CreatePtr" in script


def test_get_ca_certificate_script():
    fake = FakeClient(ps="-----BEGIN CERTIFICATE-----\nMII...\n-----END CERTIFICATE-----")
    out = run(_call(_mcp(fake), "win_get_ca_certificate"))
    _, script = fake.calls[-1]
    assert "Cert:\\LocalMachine" in script and "ToBase64String" in script
    assert "BEGIN CERTIFICATE" in out


def test_rename_computer_script():
    fake = FakeClient()
    run(_call(_mcp(fake), "win_rename_computer", new_name="AD01"))
    _, script = fake.calls[-1]
    assert "Rename-Computer -NewName 'AD01'" in script and "-Restart" in script


def test_promote_to_dc_script():
    fake = FakeClient()
    run(_call(_mcp(fake), "win_promote_to_dc", domain_name="lab.local",
              safe_mode_password="Str0ng!Pass"))
    _, script = fake.calls[-1]
    assert "Install-ADDSForest" in script
    assert "-DomainName 'lab.local'" in script
    assert "ConvertTo-SecureString 'Str0ng!Pass'" in script


def test_create_dhcp_scope_script():
    fake = FakeClient()
    run(_call(_mcp(fake), "win_create_dhcp_scope", name="LAN",
              start_range="10.0.0.100", end_range="10.0.0.200"))
    _, script = fake.calls[-1]
    assert "Add-DhcpServerv4Scope" in script and "-State Active" in script


# --------------------------------------------------------------------------
# config loading
# --------------------------------------------------------------------------
def test_load_settings_defaults(monkeypatch):
    monkeypatch.setattr("windows_mcp.config.load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("WINRM_HOST", "10.0.0.50")
    monkeypatch.setenv("WINRM_USERNAME", "Administrator")
    monkeypatch.setenv("WINRM_PASSWORD", "pw")
    monkeypatch.delenv("WINRM_SSL", raising=False)
    monkeypatch.delenv("WINRM_PORT", raising=False)
    s = load_settings()
    assert s.host == "10.0.0.50" and s.port == 5985 and s.ssl is False and s.auth == "ntlm"


def test_load_settings_ssl_default_port(monkeypatch):
    monkeypatch.setattr("windows_mcp.config.load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("WINRM_HOST", "10.0.0.50")
    monkeypatch.setenv("WINRM_USERNAME", "Administrator")
    monkeypatch.setenv("WINRM_PASSWORD", "pw")
    monkeypatch.setenv("WINRM_SSL", "true")
    monkeypatch.delenv("WINRM_PORT", raising=False)
    s = load_settings()
    assert s.ssl is True and s.port == 5986


def test_load_settings_missing_host_raises(monkeypatch):
    monkeypatch.setattr("windows_mcp.config.load_dotenv", lambda *a, **k: None)
    monkeypatch.delenv("WINRM_HOST", raising=False)
    with pytest.raises(RuntimeError):
        load_settings()
