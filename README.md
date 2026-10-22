# windows-mcp

MCP server for **Windows Server** — Active Directory, DNS, DHCP, and AD
Certificate Services — driven over **WinRM / PowerShell remoting** ([pypsrp](https://github.com/jborean93/pypsrp)).
Python 3.11+, [uv](https://docs.astral.sh/uv/), FastMCP.

> **Disclaimer.** This is not an official Microsoft product or repository, and it isn't supported or
> endorsed by Microsoft. It's a personal project by [@dr-stutters](https://github.com/dr-stutters),
> for lab and learning use only: don't point it at production systems. It's provided as is, with no
> warranty. Microsoft, Windows Server and Active Directory are trademarks of the Microsoft group of
> companies.

Sibling to [`cml-mcp`](../CML_MCP) and the other suite MCPs ([`firepower-mcp`](../Firepower_MCP),
[`ise-mcp`](../ISE_MCP), [`splunk-mcp`](../Splunk_MCP), [`wlc-mcp`](../WLC_MCP),
[`catalyst-center-mcp`](../catalyst-center-mcp)); wired into the CML MCP project as the
`windows` server, where the **windows-engineer** agent drives its `mcp__windows__*` tools.

## What it does

Everything runs PowerShell (or `cmd`) on the server over WinRM. **37 tools** in
five groups, plus escape hatches:

- **general** — `win_run_powershell` / `win_run_powershell_json` / `win_run_command`
  (escape hatches), `win_system_info`, features (`win_list_features`,
  `win_install_feature`), services, `win_rename_computer`, `win_reboot`
- **AD DS** — `win_ad_domain_info`, `win_promote_to_dc` (Install-ADDSForest),
  users (list/get/create/set-password/delete), groups (list/create/add-member),
  OUs, computers
- **DNS** — zones, records (list/add A/add CNAME/remove)
- **DHCP** — scopes (list/create), leases, reservations
- **AD CS** — `win_adcs_ca_info`, `win_install_adcs_ca`, `win_get_ca_certificate`
  (PEM export), `win_list_ca_templates`, `win_sign_csr`

## In the suite — the identity / PKI / DNS root

Windows is the enterprise identity, PKI, and DNS backing for the rest of the stack. In the
[cml-mcp](https://github.com/dr-stutters/cml-mcp) suite these edges are built and validated
end-to-end (see the [suite integration map](https://github.com/dr-stutters/cml-mcp#suite-integration-map)):

- **AD as an external identity source** — build the domain + users/groups here, then join
  **ISE** ([ise-mcp](https://github.com/dr-stutters/ise-mcp), `ise_list_active_directory`) *and*
  create an AD **realm on FMC** ([firepower-mcp](https://github.com/dr-stutters/firepower-mcp))
  so the FTD can match rules on AD users/groups (passive identity).
- **PKI — one CA (MitchcloudCA) for the whole suite** — `win_get_ca_certificate` +
  `win_sign_csr` issue enterprise-trusted certs for **ISE** (EAP-TLS/system certs via
  `ise_generate_csr` → `win_sign_csr` → `ise_import_trusted_cert`), the **FMC pxGrid client
  cert** (needs a `clientAuth` EKU — temporarily add it to the WebServer template), and switch
  **TACACS-over-TLS** identity certs.
- **DNS** — resolvable names fix ISE's "non-resolvable CN" CSR requirement *and* let FMC reach
  the ISE pxGrid **FQDN**; A/CNAME records added via `win_add_dns_a_record` / `win_add_dns_cname`.
- **DHCP** — addresses for the endpoints in the auth flow.
- **Windows → Splunk** ([splunk-mcp](https://github.com/dr-stutters/splunk-mcp)) — AD/security
  events into the SIEM via the Splunk Add-on for Microsoft Windows.

> Gotcha worth knowing: `certreq.exe` **hangs over WinRM** — issue certs via the CA **COM
> `ICertRequest`** interface instead (`New-Object -ComObject CertificateAuthority.Request`).

## Prerequisite: enable WinRM

WinRM must be enabled on the server before this can reach it. Once, in an elevated
PowerShell (console/RDP, or via an answer file / GPO):

```powershell
Enable-PSRemoting -Force
```

HTTP (5985) with NTLM auth is fine for a lab (message-level encrypted). HTTPS
(5986) needs a WinRM listener cert.

## Install

```bash
git clone https://github.com/dr-stutters/windows-mcp
cd windows-mcp && uv sync
```

## Configure

Copy `.env.example` to `.env` (gitignored) and set:

> **Suite users:** these values can instead live in a shared `../.env` one level above the repos, read by every companion MCP — precedence: process env > this repo's `.env` > the shared `../.env`. See the [cml-mcp](https://github.com/dr-stutters/cml-mcp) hub.

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

## How to use this

Run standalone (stdio): `uv run windows-mcp` — or register it in any MCP client:

```json
{ "mcpServers": { "windows": { "command": "uv",
    "args": ["run", "--directory", "/path/to/windows-mcp", "windows-mcp"] } } }
```

It's built to be driven by an AI agent. In the
[cml-mcp](https://github.com/dr-stutters/cml-mcp) lab suite it's wired in as the
`windows` server, owned by the **windows-engineer** agent (tool prefix
`mcp__windows__*`) — AD/DNS/DHCP/PKI work in lab requests fans out to it
automatically as the identity backing for ISE. Standalone, just describe what
you want:

> "Promote this box to a DC for mitchcloud.lab, then create an OU and ten users."

> "Stand up an enterprise CA and give me its cert as PEM."

> "Sign this CSR with the WebServer template."

See **[EXAMPLE_PROMPT.md](EXAMPLE_PROMPT.md)** for a full end-to-end scenario plus
focused per-area prompts (AD DS, DNS, DHCP, AD CS / PKI-for-ISE).

Start with `win_system_info` to confirm WinRM answers; `win_run_powershell` is
the escape hatch when no dedicated tool fits.

## Test

```bash
uv run pytest                              # unit tests - no Windows box needed
uv run python tests/smoke_test.py          # read-only live check (needs WinRM up)
uv run python tests/integration_test.py    # full live pass (creates + removes objects)
```

The unit tests fake the PowerShell layer, so they verify the generated PowerShell,
JSON parsing and quoting with no live box (`ruff` + `pytest` run in CI on every
push). The integration suite has passed 34/34 functional tools against a live
domain controller.

## Notes & roadmap

- **Live-built + integrated:** the `mitchcloud.lab` domain — DC, DNS, a DHCP scope,
  and an AD CS enterprise CA — was stood up and is operated entirely through these
  tools. The full **ISE↔AD↔CA** flow is validated end-to-end: ISE joined to the
  domain, **PEAP-MSCHAPv2** against AD, and **EAP-TLS** with a `win_sign_csr`-issued
  client cert (both 802.1X methods passing through a cat9000v to ISE).
- **Rename the box first.** Run `win_rename_computer('AD01')` (reboots) *before*
  promoting to a DC — renaming a domain controller afterward is far more involved.
- `win_promote_to_dc` and role installs **reboot** the server — WinRM drops;
  reconnect and re-check (`win_ad_domain_info`) once it's back. While a box is
  mid-promotion/pre-reboot, neither the local nor domain Administrator can
  WinRM-auth — let it reboot, then log in as `DOMAIN\Administrator`.
- Enterprise AD CS operations need the account to be an Enterprise/Domain Admin.
- **Cert templates set the EKU + subject source.** `win_sign_csr` targets the
  host's default CA automatically (`certreq -config`). `WebServer` = serverAuth and
  honours the CSR subject; `User` = clientAuth but builds the subject from the
  enrolling account. A per-user clientAuth cert (EAP-TLS as a chosen user) needs a
  custom "supply in the request" + Client Authentication template — no stock one
  does both.
- Roadmap: computer domain-join automation, GPO helpers, Kerberos-auth verified
  end to end, and a bundled supply-in-request clientAuth template.

## Security notes

`.env` is gitignored — never commit credentials. The tools run arbitrary
PowerShell as the configured account: use a dedicated admin, not a shared one.
NTLM over HTTP (5985) is message-level encrypted and fine for a lab; production
should use HTTPS (5986) with a listener cert or Kerberos.
