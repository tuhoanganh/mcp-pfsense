# pfsense-openvpn-user-provisioning

End-to-end OpenVPN user provisioning on pfSense via MCP — certificates, user accounts, and static-IP overrides in a single guided workflow.

## What it does

- Resolves the target OpenVPN server by description substring (e.g. `LAB-VPN`) or tunnel subnet (e.g. `10.0.6.0/24`).
- Asks which CA to sign against — never defaults — then generates a certificate per user (RSA 2048, SHA-256, 3650-day lifetime).
- Creates a pfSense user account with a per-user or batch password.
- Optionally creates a Client Specific Override (CSO) to push a static IP via `ifconfig-push`.
- Prints a final report table (username / user_id / cert_refid / cso_id / static_ip / password / status) and warns you to save passwords immediately.

## When it triggers

The skill fires eagerly on any OpenVPN user provisioning intent. Example prompts:

```
"create 6 new VPN users on LAB-VPN with static IPs 10.0.6.107–10.0.6.112"
"provision test.contract01 to test.contract05 on the 10.0.6.0/24 openvpn server"
"add OpenVPN accounts: alice / bob / carol on ADMIN-VPN, password <password>"
```

If the request is about getting users onto a pfSense-managed OpenVPN, this skill applies.

## Inputs

| Input | Required | Notes |
|---|---|---|
| Usernames | Yes | Explicit list (`foo, bar, baz`) or range (`test.proxmox04–06` → 04, 05, 06, zero-padded). |
| Target OpenVPN server | Yes | Description substring (`LAB-VPN`) or tunnel subnet (`10.0.6.0/24`). Ambiguous matches prompt you to choose. |
| Static IPs | No | Explicit list or range (`10.0.6.107–10.0.6.112`), assigned in order to usernames. All-or-none per batch — mixed assignment requires clarification. Omit to skip CSO for all users. |
| Password | No | Include `password: xxx` in the prompt to use one password for every user in the batch. Otherwise a unique 8-char password is auto-generated per user by `scripts/gen_password.py`. |
| CA | Asked at runtime | The skill lists all CAs from pfSense and asks which to use. It will not proceed until you answer. |

## Outputs

After provisioning completes, the skill prints a report table:

```
## Provisioning Report — LAB-VPN

CA used: SVTECH-CA (refid: abc123)

| username        | user_id | cert_refid | cso_id | static_ip     | password | status         |
|---|---|---|---|---|---|---|
| test.proxmox04  | 42      | abc123     | 7      | 10.0.6.107  | <password> | created        |
| test.proxmox05  | 43      | def456     | —      | —             | <password> | created-no-csc |
| test.proxmox06  | —       | —          | —      | —             | —        | skipped: already exists |
```

Status values: `created`, `created-no-csc` (no static IP requested), `skipped: already exists`, `failed` (see Anomalies section below the table).

> **Save these passwords now.** Store them in your password manager or share them via a secure channel. Do not commit the chat transcript to version control.

## Prerequisites

- pfSense MCP server connected in Claude Code (`mcp__pfsense__*` tools available).
- The following MCP tool families must be present: `search_openvpn_servers`, `search_certificate_authorities`, `create_user_with_certificate`, `manage_openvpn_cso`, `find_object_by_field`, `delete_certificate` / `delete_user` (for rollback).
- Python 3 on the machine running Claude Code (for `scripts/gen_password.py`).

## Certificate linkage

`create_user_with_certificate` generates the certificate, creates the user with the certificate linked, and rolls back the certificate if user creation fails, all in one call. No manual WebUI linkage step is needed.

## Safety notes

- **Serial only.** The pfSense API is sensitive to concurrent writes. The skill processes one user at a time. Do not run two invocations of this skill against the same pfSense simultaneously — concurrent batches can produce UID collisions or ID-shift races.
- **Destructive tools are often auto-mode-blocked.** `delete_certificate` and `delete_user` may be refused by auto-mode classifiers when invoked inside subagents. If rollback is needed and a tool is refused, authorize it explicitly or delete via the WebUI (System → Cert Manager → Certificates).
- **Object IDs are non-persistent array indices.** Every deletion shifts the indices of all subsequent objects. Always re-query between deletes — never reuse a cached numeric ID across multiple delete operations.
- **Dangling certs on rollback failure.** If `create_user` fails and `delete_certificate` also fails (e.g. network timeout), the cert exists in pfSense but is unlinked to any user. The skill reports this so you can clean up via System → Cert Manager → Certificates.

## Files in this skill

| File | Purpose |
|---|---|
| `SKILL.md` | The full workflow instructions that Claude follows. Read this for exact MCP call parameters, field names, rollback order, and all edge cases. |
| `scripts/gen_password.py` | Standalone Python 3 script. Prints N space-separated 8-char passwords (≥1 lowercase, uppercase, digit, special char each) to stdout. Call directly: `python3 scripts/gen_password.py <N>`. |

## See also

- [`SKILL.md`](./SKILL.md) — authoritative workflow reference (CA selection, provisioning loop, apply behavior, cleanup/rollback order, common pitfalls).
- Repo root — [`pfsense-mcp-server`](../../..) for MCP server setup, and connection configuration.
