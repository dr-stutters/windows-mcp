"""Live full-tool integration pass for the Windows MCP (needs a real Windows DC).

Not collected by pytest (that's test_*.py); run it directly against a live box:
    uv run python tests/integration_test.py

Exercises every tool group through the built server's call_tool: read-only calls,
safe create->delete round-trips (AD user/group/OU, DNS A+CNAME, DHCP scope/
reservation), AD CS CSR signing, and idempotent-safe checks. The 4 destructive
one-time ops (promote_to_dc / install_adcs_ca / reboot / rename_computer) are
listed but NOT executed - they would disrupt a live DC. All test objects are torn
down at the end (including OU deletion-protection + the DHCP scope).
"""

from __future__ import annotations

import asyncio
import subprocess

from windows_mcp.server import build_server

s = build_server()
ZONE = "mitchcloud.lab"          # adjust to your domain
SID = "198.18.199.0"             # throwaway DHCP scope network
results: list[tuple[str, str, str]] = []


async def call(name: str, args: dict | None = None) -> str:
    res = await s.call_tool(name, args or {})
    payload = res[0] if isinstance(res, tuple) else res
    return "".join(getattr(c, "text", "") or "" for c in
                   (payload if isinstance(payload, (list, tuple)) else [payload]))


async def check(name: str, args=None, label=None) -> str:
    try:
        txt = await call(name, args)
        low = txt.lower()
        ok = not (txt.strip().startswith("Error") or '"error"' in low or "exception" in low[:200])
    except Exception as e:  # noqa: BLE001
        txt, ok = f"EXC: {e}", False
    results.append((label or name, "PASS" if ok else "FAIL", txt.replace("\n", " ")[:88]))
    return txt


async def main() -> None:
    # --- read-only ---
    for n, a in [
        ("win_system_info", {}), ("win_list_features", {}),
        ("win_get_service", {"name": "DNS"}),
        ("win_run_command", {"command": "whoami"}),
        ("win_run_powershell", {"script": "Get-Date"}),
        ("win_run_powershell_json", {"script": "Get-Service W32Time | Select-Object Status,Name"}),
        ("win_ad_domain_info", {}), ("win_list_ad_users", {}),
        ("win_get_ad_user", {"identity": "Administrator"}),
        ("win_list_ad_groups", {}), ("win_list_ad_ous", {}), ("win_list_ad_computers", {}),
        ("win_list_dns_zones", {}), ("win_get_dns_records", {"zone": ZONE}),
        ("win_list_dhcp_scopes", {}),
        ("win_adcs_ca_info", {}), ("win_get_ca_certificate", {}), ("win_list_ca_templates", {}),
    ]:
        await check(n, a)

    # --- AD user / group / OU round-trips ---
    U, G, OU = "mcptest_user", "MCPTEST_Group", "MCPTEST_OU"
    await check("win_create_ad_user", {"sam_account_name": U, "password": "P@ssw0rd-Mcp1!"})
    await check("win_set_ad_user_password", {"identity": U, "password": "P@ssw0rd-Mcp2!"})
    await check("win_get_ad_user", {"identity": U}, "win_get_ad_user (created)")
    await check("win_create_ad_group", {"name": G})
    await check("win_add_group_member", {"group": G, "member": U})
    await check("win_create_ad_ou", {"name": OU})

    # --- DNS round-trips (note: CNAME removal needs record_type="CNAME") ---
    await check("win_add_dns_a_record", {"zone": ZONE, "name": "mcptest-a", "ip": "198.18.134.199"})
    await check("win_add_dns_cname", {"zone": ZONE, "name": "mcptest-cn", "target": f"mcptest-a.{ZONE}"})
    await check("win_remove_dns_record", {"zone": ZONE, "name": "mcptest-a"}, "win_remove_dns_record (A)")
    await check("win_remove_dns_record", {"zone": ZONE, "name": "mcptest-cn", "record_type": "CNAME"},
                "win_remove_dns_record (CNAME)")

    # --- DHCP round-trips ---
    await check("win_create_dhcp_scope",
                {"name": "MCPTEST-Scope", "start_range": "198.18.199.10", "end_range": "198.18.199.20"})
    await check("win_list_dhcp_leases", {"scope_id": SID})
    await check("win_add_dhcp_reservation", {"scope_id": SID, "ip": "198.18.199.15", "mac": "AA-BB-CC-DD-EE-FF"})

    # --- AD CS: sign a throwaway CSR ---
    csr = subprocess.run(
        ["openssl", "req", "-new", "-newkey", "rsa:2048", "-nodes", "-keyout", "/dev/null",
         "-subj", "/CN=mcptest-cert.mitchcloud.lab"], capture_output=True, text=True).stdout
    if "BEGIN CERTIFICATE REQUEST" in csr:
        txt = await call("win_sign_csr", {"csr_pem": csr})
        results.append(("win_sign_csr", "PASS" if "BEGIN CERTIFICATE" in txt else "FAIL",
                        "cert ISSUED" if "BEGIN CERTIFICATE" in txt else txt[:80]))
    else:
        results.append(("win_sign_csr", "SKIP", "openssl CSR gen unavailable"))

    # --- idempotent-safe (already-present feature / benign service) ---
    await check("win_install_feature", {"name": "RSAT-AD-PowerShell"}, "win_install_feature (idempotent)")
    await check("win_restart_service", {"name": "W32Time"}, "win_restart_service (W32Time)")

    # --- teardown (handles OU deletion-protection + the DHCP scope) ---
    teardown = f"""
Remove-ADUser -Identity {U} -Confirm:$false -ErrorAction SilentlyContinue
Remove-ADGroup -Identity {G} -Confirm:$false -ErrorAction SilentlyContinue
$ou = Get-ADOrganizationalUnit -Filter "Name -eq '{OU}'"
if ($ou) {{ Set-ADOrganizationalUnit -Identity $ou -ProtectedFromAccidentalDeletion $false
           Remove-ADOrganizationalUnit -Identity $ou -Recursive -Confirm:$false }}
Remove-DhcpServerv4Scope -ScopeId {SID} -Force -ErrorAction SilentlyContinue
'cleaned'
"""
    await check("win_run_powershell", {"script": teardown}, "teardown")

    # --- destructive one-time ops: NOT executed against a live DC ---
    for n in ["win_install_adcs_ca", "win_promote_to_dc", "win_reboot", "win_rename_computer"]:
        results.append((n, "SKIP", "destructive on live DC - not executed"))

    p = sum(1 for _, st, _ in results if st == "PASS")
    f = sum(1 for _, st, _ in results if st == "FAIL")
    sk = sum(1 for _, st, _ in results if st == "SKIP")
    print(f"\n=== Windows MCP integration: {p} PASS / {f} FAIL / {sk} SKIP ===")
    for name, st, note in results:
        print(f"  {st:5} {name:34} {note}")
    if f:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
