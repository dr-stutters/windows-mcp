"""DHCP Server tools (PowerShell DhcpServer module). Needs the DHCP role."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..client import WindowsClient
from . import dumps

_L = WindowsClient.ps_literal


def register(mcp: FastMCP, client: WindowsClient) -> None:
    @mcp.tool()
    async def win_list_dhcp_scopes() -> str:
        """List IPv4 DHCP scopes."""
        return dumps(await client.run_ps_json(
            "Get-DhcpServerv4Scope | Select-Object ScopeId, Name, State, "
            "StartRange, EndRange, SubnetMask, LeaseDuration"))

    @mcp.tool()
    async def win_create_dhcp_scope(name: str, start_range: str, end_range: str,
                                    subnet_mask: str = "255.255.255.0") -> str:
        """Create and activate an IPv4 DHCP scope.

        Args:
            name: scope name.
            start_range: first address in the pool.
            end_range: last address in the pool.
            subnet_mask: the scope subnet mask (default /24).
        """
        return dumps(await client.run_ps(
            f"Add-DhcpServerv4Scope -Name {_L(name)} -StartRange {_L(start_range)} "
            f"-EndRange {_L(end_range)} -SubnetMask {_L(subnet_mask)} -State Active; "
            "'scope created'"))

    @mcp.tool()
    async def win_list_dhcp_leases(scope_id: str) -> str:
        """List active leases in a scope (scope_id = the scope's network address)."""
        return dumps(await client.run_ps_json(
            f"Get-DhcpServerv4Lease -ScopeId {_L(scope_id)} | "
            "Select-Object IPAddress, ClientId, HostName, AddressState, LeaseExpiryTime"))

    @mcp.tool()
    async def win_add_dhcp_reservation(scope_id: str, ip: str, mac: str,
                                       name: str | None = None) -> str:
        """Add a DHCP reservation binding an IP to a MAC.

        Args:
            scope_id: the scope network address.
            ip: reserved IP.
            mac: client MAC (hex, e.g. 'AABBCCDDEEFF' or 'aa-bb-cc-dd-ee-ff').
            name: optional reservation name.
        """
        nm = f" -Name {_L(name)}" if name else ""
        return dumps(await client.run_ps(
            f"Add-DhcpServerv4Reservation -ScopeId {_L(scope_id)} -IPAddress {_L(ip)} "
            f"-ClientId {_L(mac)}{nm}; 'reservation added'"))
