"""Windows Server MCP server entry point (WinRM / PowerShell remoting)."""

from __future__ import annotations

import argparse
import logging

from mcp.server.fastmcp import FastMCP

from .client import WindowsClient
from .config import load_settings
from .tools import register_all

# pypsrp logs WinRM runspace open/close at INFO on stderr - quiet the noise.
logging.getLogger("pypsrp").setLevel(logging.WARNING)


def build_server() -> FastMCP:
    settings = load_settings()
    client = WindowsClient(settings)
    mcp = FastMCP(
        "windows",
        instructions=(
            "Tools for a Windows Server, driven over WinRM / PowerShell remoting "
            "(pypsrp). Manage Active Directory Domain Services (promote a DC, "
            "users/groups/OUs/computers), DNS (zones/records), DHCP (scopes/"
            "reservations/leases), and AD Certificate Services (install a CA, "
            "export its cert, sign CSRs). win_run_powershell / "
            "win_run_powershell_json / win_run_command are the escape hatches for "
            "anything else. Feature/role installs and promote-to-DC may reboot the "
            "server (WinRM drops - reconnect and re-check). Pairs with the ISE MCP: "
            "AD as an external identity source, and win_get_ca_certificate / "
            "win_sign_csr feed ISE's trusted-cert import + CSR flow for EAP-TLS."
        ),
    )
    register_all(mcp, client)
    return mcp


def main() -> None:
    parser = argparse.ArgumentParser(description="Windows Server MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="MCP transport (default: stdio)",
    )
    args = parser.parse_args()
    build_server().run(transport=args.transport)


if __name__ == "__main__":
    main()
