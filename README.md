# windows-mcp

MCP server for **Windows Server** — Active Directory, DNS, DHCP, and AD
Certificate Services — driven over **WinRM / PowerShell remoting** ([pypsrp](https://github.com/jborean93/pypsrp)).
Python 3.11+, [uv](https://docs.astral.sh/uv/), FastMCP.

Sibling to [`cml-mcp`](../CML_MCP), [`firepower-mcp`](../Firepower_MCP) and
[`ise-mcp`](../ISE_MCP); wired into the CML MCP project as the `windows` server,
where the **windows-engineer** agent drives its `mcp__windows__*` tools.

## What it does

Everything runs PowerShell (or `cmd`) on the server over WinRM. **36 tools** in
five groups, plus escape hatches:

- **general** — `win_run_powershell` / `win_run_powershell_json` / `win_run_command`
  (escape hatches), `win_system_info`, features (`win_list_features`,
  `win_install_feature`), services, `win_reboot`
- **AD DS** — `win_ad_domain_info`, `win_promote_to_dc` (Install-ADDSForest),
  users (list/get/create/set-password/delete), groups (list/create/add-member),
  OUs, computers
- **DNS** — zones, records (list/add A/add CNAME/remove)
- **DHCP** — scopes (list/create), leases, reservations
- **AD CS** — `win_adcs_ca_info`, `win_install_adcs_ca`, `win_get_ca_certificate`
  (PEM export), `win_list_ca_templates`, `win_sign_csr`

## Pairs with the ISE MCP

This is the piece that unblocks the deeper ISE scenarios:

- **AD as an external identity source** — build the domain + users here, then join
  ISE to AD (`ise_list_active_directory`).
- **PKI / EAP-TLS** — `win_get_ca_certificate` → `ise_import_trusted_cert`, and
  `ise_generate_csr` → `win_sign_csr` → import/bind on ISE.
- **DNS** — resolvable names fix ISE's "non-resolvable CN" CSR requirement.
- **DHCP** — addresses for the endpoints in the auth flow.

## Prerequisite: enable WinRM

WinRM must be enabled on the server before this can reach it. Once, in an elevated
PowerShell (console/RDP, or via an answer file / GPO):

```powershell
Enable-PSRemoting -Force
```

HTTP (5985) with NTLM auth is fine for a lab (message-level encrypted). HTTPS
(5986) needs a WinRM listener cert.

## Configuration

Copy `.env.example` to `.env` (gitignored) and set:

```ini
WINRM_HOST=192.0.2.50
WINRM_USERNAME=Administrator
WINRM_PASSWORD=changeme
WINRM_AUTH=ntlm            # ntlm | kerberos | credssp | basic
WINRM_SSL=false            # true -> port 5986 (needs a listener cert)
WINRM_PORT=5985
WINRM_CERT_VALIDATION=false
WINRM_TIMEOUT=120          # seconds (AD/CA installs are slow)
```

## Run & test

```bash
uv run windows-mcp                    # stdio transport (for MCP clients)
uv run pytest                         # unit tests - no Windows box needed
uv run python tests/smoke_test.py     # read-only live check (needs WinRM up)
```

The unit tests fake the PowerShell layer, so they verify the generated PowerShell,
JSON parsing and quoting with no live box (`ruff` + `pytest` run in CI on every
push).

## Notes & roadmap

- `win_promote_to_dc` and role installs **reboot** the server — WinRM drops;
  reconnect and re-check (`win_ad_domain_info`) once it's back.
- Enterprise AD CS operations need the account to be an Enterprise/Domain Admin.
- Roadmap: computer domain-join automation, GPO helpers, Kerberos-auth verified
  end to end, and a full ISE↔AD↔CA integration test.
