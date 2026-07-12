"""General Windows tools: raw PowerShell/cmd, system info, features, services."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..client import WindowsClient
from . import dumps

_L = WindowsClient.ps_literal


def register(mcp: FastMCP, client: WindowsClient) -> None:
    @mcp.tool()
    async def win_run_powershell(script: str) -> str:
        """Run an arbitrary PowerShell script on the Windows Server and return its
        text output. The escape hatch for anything without a dedicated tool."""
        return dumps(await client.run_ps(script))

    @mcp.tool()
    async def win_run_powershell_json(script: str, depth: int = 4) -> str:
        """Run PowerShell and return its output as JSON (piped through
        ConvertTo-Json). Use for cmdlets that emit objects."""
        return dumps(await client.run_ps_json(script, depth=depth))

    @mcp.tool()
    async def win_run_command(command: str) -> str:
        """Run a cmd.exe command; returns {stdout, stderr, rc}."""
        return dumps(await client.run_cmd(command))

    @mcp.tool()
    async def win_system_info() -> str:
        """OS version, hostname, domain/workgroup, and uptime."""
        return dumps(await client.run_ps_json(
            "Get-CimInstance Win32_OperatingSystem | "
            "Select-Object CSName, Caption, Version, "
            "@{n='Domain';e={(Get-CimInstance Win32_ComputerSystem).Domain}}, "
            "@{n='PartOfDomain';e={(Get-CimInstance Win32_ComputerSystem).PartOfDomain}}, "
            "LastBootUpTime"))

    @mcp.tool()
    async def win_list_features(installed_only: bool = True) -> str:
        """List Windows Server features/roles.

        Args:
            installed_only: only show installed features (default true).
        """
        flt = "| Where-Object InstallState -eq 'Installed' " if installed_only else ""
        return dumps(await client.run_ps_json(
            f"Get-WindowsFeature {flt}| Select-Object Name, DisplayName, InstallState"))

    @mcp.tool()
    async def win_install_feature(name: str, include_management_tools: bool = True) -> str:
        """Install a Windows Server feature/role (e.g. 'AD-Domain-Services',
        'DNS', 'DHCP', 'ADCS-Cert-Authority'). May require a reboot."""
        mgmt = " -IncludeManagementTools" if include_management_tools else ""
        return dumps(await client.run_ps_json(
            f"Install-WindowsFeature -Name {_L(name)}{mgmt} | "
            "Select-Object Success, RestartNeeded, ExitCode, "
            "@{n='FeaturesInstalled';e={$_.FeatureResult.Name}}"))

    @mcp.tool()
    async def win_get_service(name: str) -> str:
        """Get a Windows service's status by name."""
        return dumps(await client.run_ps_json(
            f"Get-Service -Name {_L(name)} | "
            "Select-Object Name, DisplayName, Status, StartType"))

    @mcp.tool()
    async def win_restart_service(name: str) -> str:
        """Restart a Windows service by name."""
        return dumps(await client.run_ps(
            f"Restart-Service -Name {_L(name)} -Force; "
            f"(Get-Service -Name {_L(name)}).Status"))

    @mcp.tool()
    async def win_reboot() -> str:
        """Reboot the Windows Server (WinRM drops until it comes back up)."""
        return dumps(await client.run_ps("Restart-Computer -Force; 'reboot issued'"))
