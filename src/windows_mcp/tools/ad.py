"""Active Directory Domain Services tools (PowerShell ActiveDirectory module).

The ActiveDirectory module is present once the box is a domain controller (or
RSAT-AD-PowerShell is installed). Use win_install_feature('AD-Domain-Services')
then win_promote_to_dc to build a new forest.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..client import WindowsClient
from . import dumps

_L = WindowsClient.ps_literal


def register(mcp: FastMCP, client: WindowsClient) -> None:
    @mcp.tool()
    async def win_ad_domain_info() -> str:
        """Get the AD domain (name, forest, DCs, functional levels). Requires this
        host to be a domain controller / have the AD module."""
        return dumps(await client.run_ps_json(
            "Get-ADDomain | Select-Object Name, DNSRoot, NetBIOSName, Forest, "
            "DomainMode, InfrastructureMaster, "
            "@{n='DomainControllers';e={$_.ReplicaDirectoryServers}}"))

    @mcp.tool()
    async def win_promote_to_dc(domain_name: str, safe_mode_password: str,
                                netbios_name: str | None = None,
                                install_dns: bool = True) -> str:
        """Promote this server to the first DC of a NEW forest (Install-ADDSForest).

        INVASIVE: installs AD DS + reboots the server, so WinRM drops - reconnect
        after the reboot and check win_ad_domain_info. Run
        win_install_feature('AD-Domain-Services') first.

        Args:
            domain_name: FQDN of the new domain, e.g. 'lab.local'.
            safe_mode_password: the Directory Services Restore Mode password.
            netbios_name: optional NetBIOS name (derived if omitted).
            install_dns: also install the DNS role (default true).
        """
        nb = f" -DomainNetbiosName {_L(netbios_name)}" if netbios_name else ""
        dns = "$true" if install_dns else "$false"
        return dumps(await client.run_ps(
            "Import-Module ADDSDeployment; "
            f"$pw = ConvertTo-SecureString {_L(safe_mode_password)} -AsPlainText -Force; "
            f"Install-ADDSForest -DomainName {_L(domain_name)}{nb} "
            f"-SafeModeAdministratorPassword $pw -InstallDns:{dns} "
            "-Force -NoRebootOnCompletion:$false -Confirm:$false"))

    # ---- users ----
    @mcp.tool()
    async def win_list_ad_users(filter: str = "*") -> str:
        """List AD users.

        Args:
            filter: AD filter, e.g. '*' (all) or "Name -like 'svc*'".
        """
        return dumps(await client.run_ps_json(
            f"Get-ADUser -Filter {_L(filter)} -Properties Enabled,EmailAddress | "
            "Select-Object Name, SamAccountName, UserPrincipalName, Enabled, DistinguishedName"))

    @mcp.tool()
    async def win_get_ad_user(identity: str) -> str:
        """Get one AD user by SamAccountName/DN/UPN, with group memberships."""
        return dumps(await client.run_ps_json(
            f"Get-ADUser -Identity {_L(identity)} -Properties * | "
            "Select-Object Name, SamAccountName, UserPrincipalName, Enabled, "
            "EmailAddress, DistinguishedName, "
            "@{n='MemberOf';e={$_.MemberOf}}"))

    @mcp.tool()
    async def win_create_ad_user(sam_account_name: str, password: str,
                                 name: str | None = None,
                                 user_principal_name: str | None = None,
                                 path: str | None = None,
                                 enabled: bool = True) -> str:
        """Create an AD user and return it.

        Args:
            sam_account_name: the logon name (pre-Windows-2000).
            password: initial password (must meet the domain policy).
            name: display name (defaults to sam_account_name).
            user_principal_name: UPN, e.g. 'user@lab.local'.
            path: target OU DN (defaults to the default Users container).
            enabled: whether the account is enabled (default true).
        """
        opts = [f"-SamAccountName {_L(sam_account_name)}",
                f"-Name {_L(name or sam_account_name)}",
                f"-AccountPassword (ConvertTo-SecureString {_L(password)} -AsPlainText -Force)",
                f"-Enabled ${'true' if enabled else 'false'}"]
        if user_principal_name:
            opts.append(f"-UserPrincipalName {_L(user_principal_name)}")
        if path:
            opts.append(f"-Path {_L(path)}")
        return dumps(await client.run_ps_json(
            f"New-ADUser {' '.join(opts)}; "
            f"Get-ADUser -Identity {_L(sam_account_name)} | "
            "Select-Object Name, SamAccountName, Enabled, DistinguishedName"))

    @mcp.tool()
    async def win_set_ad_user_password(identity: str, password: str,
                                       enable: bool = True) -> str:
        """Reset an AD user's password (and optionally enable the account)."""
        en = f"; Enable-ADAccount -Identity {_L(identity)}" if enable else ""
        return dumps(await client.run_ps(
            f"Set-ADAccountPassword -Identity {_L(identity)} -Reset "
            f"-NewPassword (ConvertTo-SecureString {_L(password)} -AsPlainText -Force)"
            f"{en}; 'password set'"))

    @mcp.tool()
    async def win_delete_ad_user(identity: str) -> str:
        """Delete an AD user by SamAccountName/DN."""
        return dumps(await client.run_ps(
            f"Remove-ADUser -Identity {_L(identity)} -Confirm:$false; 'deleted'"))

    # ---- groups ----
    @mcp.tool()
    async def win_list_ad_groups(filter: str = "*") -> str:
        """List AD groups (filter, e.g. '*' or "Name -like 'ISE*'")."""
        return dumps(await client.run_ps_json(
            f"Get-ADGroup -Filter {_L(filter)} | "
            "Select-Object Name, SamAccountName, GroupScope, GroupCategory, DistinguishedName"))

    @mcp.tool()
    async def win_create_ad_group(name: str, scope: str = "Global",
                                  category: str = "Security",
                                  path: str | None = None) -> str:
        """Create an AD group.

        Args:
            name: group name.
            scope: 'Global' (default), 'DomainLocal', or 'Universal'.
            category: 'Security' (default) or 'Distribution'.
            path: target OU DN (optional).
        """
        p = f" -Path {_L(path)}" if path else ""
        return dumps(await client.run_ps_json(
            f"New-ADGroup -Name {_L(name)} -GroupScope {scope} "
            f"-GroupCategory {category}{p}; "
            f"Get-ADGroup -Identity {_L(name)} | "
            "Select-Object Name, GroupScope, DistinguishedName"))

    @mcp.tool()
    async def win_add_group_member(group: str, member: str) -> str:
        """Add a member (user/group) to an AD group."""
        return dumps(await client.run_ps(
            f"Add-ADGroupMember -Identity {_L(group)} -Members {_L(member)}; 'added'"))

    # ---- OUs / computers ----
    @mcp.tool()
    async def win_list_ad_ous() -> str:
        """List organizational units."""
        return dumps(await client.run_ps_json(
            "Get-ADOrganizationalUnit -Filter * | "
            "Select-Object Name, DistinguishedName"))

    @mcp.tool()
    async def win_create_ad_ou(name: str, path: str | None = None) -> str:
        """Create an OU (path = parent DN; defaults to the domain root)."""
        p = f" -Path {_L(path)}" if path else ""
        return dumps(await client.run_ps(
            f"New-ADOrganizationalUnit -Name {_L(name)}{p}; 'created'"))

    @mcp.tool()
    async def win_list_ad_computers(filter: str = "*") -> str:
        """List AD computer accounts."""
        return dumps(await client.run_ps_json(
            f"Get-ADComputer -Filter {_L(filter)} -Properties OperatingSystem | "
            "Select-Object Name, DNSHostName, OperatingSystem, Enabled, DistinguishedName"))
