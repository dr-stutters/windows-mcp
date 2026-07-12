"""Active Directory Certificate Services tools.

Install a CA and pull its certificate so ISE (or anything) can trust it, list
templates, and sign a CSR. The CA cert export pairs directly with the ISE MCP's
ise_import_trusted_cert, and CSR signing pairs with ise_generate_csr -> import.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..client import WindowsClient
from . import dumps

_L = WindowsClient.ps_literal


def register(mcp: FastMCP, client: WindowsClient) -> None:
    @mcp.tool()
    async def win_adcs_ca_info() -> str:
        """Get the local Certification Authority's name and config (certutil)."""
        return dumps(await client.run_cmd("certutil -cainfo"))

    @mcp.tool()
    async def win_install_adcs_ca(ca_type: str = "EnterpriseRootCA",
                                  common_name: str | None = None,
                                  key_length: int = 2048,
                                  valid_years: int = 5) -> str:
        """Install and configure an AD CS Certification Authority.

        Run win_install_feature('ADCS-Cert-Authority') first. For an Enterprise CA
        the account must be an Enterprise Admin and the box domain-joined.

        Args:
            ca_type: 'EnterpriseRootCA' (default), 'StandaloneRootCA', etc.
            common_name: the CA common name (defaults to the host name).
            key_length: CA key length (default 2048).
            valid_years: root CA validity in years (default 5).
        """
        cn = f"-CACommonName {_L(common_name)} " if common_name else ""
        return dumps(await client.run_ps(
            "Import-Module ADCSDeployment; "
            f"Install-AdcsCertificationAuthority -CAType {ca_type} {cn}"
            f"-KeyLength {key_length} -HashAlgorithmName SHA256 "
            f"-ValidityPeriod Years -ValidityPeriodUnits {valid_years} "
            "-Force -Confirm:$false; 'CA installed'"))

    @mcp.tool()
    async def win_get_ca_certificate() -> str:
        """Export the CA's own certificate as PEM.

        Feed the returned PEM straight into the ISE MCP's ise_import_trusted_cert
        so ISE trusts certs this CA issues (EAP-TLS, pxGrid, portals). Reads the
        cert from the machine store (matched to the configured CA name)."""
        return dumps(await client.run_ps(
            "$name = (Get-ItemProperty "
            "'HKLM:\\SYSTEM\\CurrentControlSet\\Services\\CertSvc\\Configuration' "
            "-Name Active -ErrorAction SilentlyContinue).Active; "
            "$ca = Get-ChildItem Cert:\\LocalMachine\\CA, Cert:\\LocalMachine\\Root | "
            "Where-Object { $_.Subject -match ('CN=' + [regex]::Escape($name)) } | "
            "Sort-Object NotAfter -Descending | Select-Object -First 1; "
            "if (-not $ca) { throw 'CA certificate not found in the machine store' }; "
            "\"-----BEGIN CERTIFICATE-----`n\" + "
            "[System.Convert]::ToBase64String($ca.RawData, 'InsertLineBreaks') + "
            "\"`n-----END CERTIFICATE-----\""))

    @mcp.tool()
    async def win_list_ca_templates() -> str:
        """List certificate templates the CA can issue."""
        return dumps(await client.run_ps_json(
            "certutil -CATemplates 2>$null | ForEach-Object { $_.Trim() } | "
            "Where-Object { $_ }"))

    @mcp.tool()
    async def win_sign_csr(csr_pem: str, template: str = "WebServer") -> str:
        """Submit a PEM CSR to the CA and return the issued certificate (PEM).

        Pairs with the ISE MCP: ise_generate_csr -> win_sign_csr -> import/bind on
        ISE. Requires the CA to auto-issue for `template` (or manual approval).

        Args:
            csr_pem: the certificate signing request in PEM.
            template: certificate template name (default 'WebServer').
        """
        return dumps(await client.run_ps(
            "$req = [System.IO.Path]::GetTempFileName() + '.req'; "
            "$cer = [System.IO.Path]::GetTempFileName() + '.cer'; "
            f"Set-Content -Path $req -Value @'\n{csr_pem}\n'@ -Encoding ascii; "
            f"certreq -submit -attrib {_L('CertificateTemplate:' + template)} $req $cer | Out-Null; "
            "$out = Get-Content -Path $cer -Raw; "
            "Remove-Item $req,$cer -Force -ErrorAction SilentlyContinue; $out"))
