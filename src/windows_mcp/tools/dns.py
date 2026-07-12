"""DNS Server tools (PowerShell DnsServer module). Needs the DNS role."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..client import WindowsClient
from . import dumps

_L = WindowsClient.ps_literal


def register(mcp: FastMCP, client: WindowsClient) -> None:
    @mcp.tool()
    async def win_list_dns_zones() -> str:
        """List DNS zones on the server."""
        return dumps(await client.run_ps_json(
            "Get-DnsServerZone | Select-Object ZoneName, ZoneType, "
            "IsDsIntegrated, IsReverseLookupZone"))

    @mcp.tool()
    async def win_get_dns_records(zone: str, record_type: str | None = None) -> str:
        """List resource records in a DNS zone.

        Args:
            zone: the zone name, e.g. 'lab.local'.
            record_type: optional filter, e.g. 'A', 'CNAME', 'PTR'.
        """
        rt = f" -RRType {record_type}" if record_type else ""
        return dumps(await client.run_ps_json(
            f"Get-DnsServerResourceRecord -ZoneName {_L(zone)}{rt} | "
            "Select-Object HostName, RecordType, "
            "@{n='Data';e={$_.RecordData.IPv4Address.IPAddressToString + "
            "$_.RecordData.HostNameAlias + $_.RecordData.PtrDomainName}}"))

    @mcp.tool()
    async def win_add_dns_a_record(zone: str, name: str, ip: str,
                                   create_ptr: bool = False) -> str:
        """Add an A record to a zone.

        Args:
            zone: zone name, e.g. 'lab.local'.
            name: host label (e.g. 'ise' for ise.lab.local).
            ip: IPv4 address.
            create_ptr: also create the matching PTR record (default false).
        """
        ptr = " -CreatePtr" if create_ptr else ""
        return dumps(await client.run_ps(
            f"Add-DnsServerResourceRecordA -ZoneName {_L(zone)} -Name {_L(name)} "
            f"-IPv4Address {_L(ip)}{ptr}; 'A record added'"))

    @mcp.tool()
    async def win_add_dns_cname(zone: str, name: str, target: str) -> str:
        """Add a CNAME record (target must be an FQDN ending in '.')."""
        return dumps(await client.run_ps(
            f"Add-DnsServerResourceRecordCName -ZoneName {_L(zone)} -Name {_L(name)} "
            f"-HostNameAlias {_L(target)}; 'CNAME added'"))

    @mcp.tool()
    async def win_remove_dns_record(zone: str, name: str,
                                    record_type: str = "A") -> str:
        """Remove a resource record from a zone by name + type."""
        return dumps(await client.run_ps(
            f"Remove-DnsServerResourceRecord -ZoneName {_L(zone)} -Name {_L(name)} "
            f"-RRType {record_type} -Force; 'removed'"))
