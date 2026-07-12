"""Smoke test: drive the Windows MCP tool layer against a live Windows Server.

Read-only. Requires a .env (WINRM_HOST/WINRM_USERNAME/WINRM_PASSWORD) pointing at
a reachable box with WinRM enabled (`Enable-PSRemoting -Force`).
Run: `uv run python tests/smoke_test.py`
"""

from __future__ import annotations

import asyncio

from windows_mcp.server import build_server


async def call(mcp, tool, /, **args) -> str:
    result = await mcp.call_tool(tool, args)
    if isinstance(result, tuple):
        result = result[0]
    return "\n".join(getattr(b, "text", str(b)) for b in result)


async def main() -> None:
    mcp = build_server()
    tools = {t.name for t in await mcp.list_tools()}
    assert {"win_run_powershell", "win_system_info", "win_ad_domain_info",
            "win_get_ca_certificate", "win_add_dns_a_record"} <= tools, "core tools missing"
    print(f"[ok] server built, {len(tools)} tools registered")

    try:
        info = await call(mcp, "win_system_info")
        print(f"[ok] win_system_info -> {info[:200].splitlines()}")
    except Exception as e:
        print(f"[skip] win_system_info -> WinRM unreachable/not enabled: {str(e)[:120]}")
        print("       (run `Enable-PSRemoting -Force` on the server and check the .env)")
        return

    feats = await call(mcp, "win_list_features")
    print(f"[ok] win_list_features -> {feats[:120].splitlines()[0]}")
    print("\nSMOKE TEST PASSED")


if __name__ == "__main__":
    asyncio.run(main())
