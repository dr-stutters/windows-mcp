# Example prompts — Windows MCP

Copy any prompt below to an AI agent (Claude Code, Claude Desktop, …) with the
**`windows`** MCP server connected. Describe the outcome — the agent picks the
tools. Names in `code` show which tools each prompt exercises.

**Always start with:** *"Confirm WinRM answers and show me the system info."*
→ `win_system_info`. (WinRM must be enabled first: `Enable-PSRemoting -Force`.)

## One end-to-end scenario

> **"Rename this box to `AD01`, promote it to a domain controller for `mitchcloud.lab`,
> then create an OU `Lab Users` with ten users in it, stand up an enterprise CA, and
> give me the CA certificate as PEM so I can import it into ISE."**

Exercises: `win_rename_computer` (reboots) → `win_promote_to_dc` (reboots) →
`win_create_ad_ou` → `win_create_ad_user` ×10 → `win_install_adcs_ca` →
`win_get_ca_certificate`. *(Promote/role-installs reboot the box — WinRM drops;
the agent reconnects and re-checks with `win_ad_domain_info`.)*

## Focused tasks (one area each)

**AD DS — users & groups**
> "Create a group `Wi-Fi Users`, add jdoe and asmith to it, and show me the group
> membership."  *(`win_create_ad_group` / `win_add_group_member` / `win_list_ad_groups`)*

**DNS**
> "Add an A record `ise35.mitchcloud.lab → 198.18.134.35` and a CNAME `radius → ise35`."
> *(`win_add_dns_a_record` / `win_add_dns_cname`)*

**DHCP**
> "Create a DHCP scope 10.40.0.100–10.40.0.200 for the 10.40.0.0/24 subnet and reserve
> .50 for this MAC."  *(`win_create_dhcp_scope` / `win_add_dhcp_reservation`)*

**AD CS — PKI for ISE EAP-TLS**
> "Sign this CSR with the WebServer template and give me the issued cert."
> *(`win_sign_csr`)*  — pairs with `ise_generate_csr` on the ISE side.

**Escape hatch**
> "Run `Get-ADDomainController -Filter *` and give me the result as JSON."
> *(`win_run_powershell_json`)*

## Tips

- **Rename before promoting.** Renaming a box *after* it's a DC is far more involved —
  `win_rename_computer('AD01')` first, then `win_promote_to_dc`.
- **Reboots drop WinRM.** After a promote/role-install, wait for the box to come back
  and re-auth as `DOMAIN\Administrator`.
- **This backs the ISE MCP:** AD as an external identity source, the CA cert →
  `ise_import_trusted_cert`, and `ise_generate_csr` → `win_sign_csr` for EAP-TLS.
- `win_run_powershell` / `win_run_powershell_json` are the escape hatches for anything
  without a dedicated tool.
