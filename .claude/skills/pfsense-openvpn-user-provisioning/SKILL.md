---
name: pfsense-openvpn-user-provisioning
description: >
  Use this skill when the user wants to create, provision, or add OpenVPN user
  accounts on a pfSense firewall — with or without static IPs, with or without a
  named server, whether the request says "VPN users", "OpenVPN accounts",
  "provision test.contract* users", or any similar phrasing. Triggers on:
  creating/provisioning/adding OpenVPN users, bulk VPN account setup,
  "create N VPN users with static IPs", "add OpenVPN accounts on LAB-VPN /
  ADMIN-VPN", "provision users on the 10.0.6.0/24 openvpn server". Fire eagerly —
  if the request is about getting people onto a pfSense-managed OpenVPN, this skill
  applies.
---

# pfSense OpenVPN User Provisioning

End-to-end provisioning of OpenVPN users on a live pfSense box via the
`mcp__pfsense__*` MCP tools. Creates, per user: a certificate signed by a
human-chosen CA + a pfSense user linked to that cert + (optionally) a Client
Specific Override for a static IP. Applies the VPN config at the end so CSOs
take effect.

---

## 1. When This Fires

- "create 6 new VPN users on LAB-VPN with static IPs 10.0.6.107–10.0.6.112"
- "provision test.contract01 to test.contract05 on the 10.0.6.0/24 openvpn server"
- "create VPN users foo, bar, baz on LAB-VPN, no static IPs"
- "add these OpenVPN accounts: alice / bob / carol on ADMIN-VPN, password <password>"
- Any phrasing involving creating/adding/provisioning accounts on a pfSense VPN.

---

## 2. Inputs to Extract

### 2a. Usernames
Accept explicit lists (`foo, bar, baz`) or range patterns.

Range patterns:
- `test.proxmox04–06` → `test.proxmox04`, `test.proxmox05`, `test.proxmox06`
- `user1–user5` → expand numeric suffix across the range
- Always pad numeric suffix to match the given digits (04 not 4).

### 2b. Static IPs (OPTIONAL)
- Explicit list: `10.0.6.107, 10.0.6.108, 10.0.6.109` — assign in order to usernames
- Range notation: `10.0.6.107–10.0.6.112` — expand and assign in order
- Omitted entirely → skip CSO for all users
- Mixed (some users have IPs, some don't) → ask the user to clarify before proceeding

### 2c. Target OpenVPN Server
Identify by either:
- Description substring: "LAB-VPN", "ADMIN-VPN"
- Tunnel-network subnet: "10.0.6.0/24"

Resolution: call `mcp__pfsense__search_openvpn_servers` and filter. If ambiguous
or no match found, present the list to the human and ask them to pick.

### 2d. Password
- If the request contains `pass:` or `password:` followed by a value, use that
  literal string for every user in the batch.
- Otherwise, auto-generate a unique 8-char password **per user** using:
  `.claude/skills/pfsense-openvpn-user-provisioning/scripts/gen_password.py`
  Call it as: `python3 <path>/gen_password.py <N>` where N is the number of
  users. It prints N space-separated passwords on stdout, one per user.
  Complexity guarantee: ≥1 lowercase, ≥1 uppercase, ≥1 digit, ≥1 special (`!@#$%^&*`).
- Report all passwords in the final table (see §6). Warn the human to record them.

---

## 3. Preflight

### 3a. CA Selection (always ask — never default)
1. Call `mcp__pfsense__search_certificate_authorities` to get the CA list.
2. Present the list (description + refid) to the human.
3. Ask which CA to sign the user certificates against.
4. Do not proceed until the human answers.

### 3b. Target Server Resolution
- Call `mcp__pfsense__search_openvpn_servers(sort_by='description')` — the default
  `sort_by='descr'` returns HTTP 400 on this pfSense build; always pass `'description'`.
- Match against the description substring or tunnel_network the human gave.
- If exactly one match: confirm with the human ("I'll use server '<description>'
  (vpnid: <id>) — proceed?") then continue.
- If zero or multiple matches: list them and ask the human to choose.
- Record the vpnid for use in CSO creation.

### 3c. Idempotency Scan
Before any write, call `mcp__pfsense__search_users` for each username.
- If a user exists: mark as `skipped: already exists` — do NOT create cert,
  do NOT update the user, do NOT create a CSO.
- Continue to the next username.

---

## 4. Provisioning Loop

**Process serially (one user at a time).** The pfSense API is sensitive to
concurrent writes — do not issue parallel MCP calls within a batch.

### 4a. Create User + Certificate

Use `mcp__pfsense__create_user_with_certificate`. In one call it generates a
certificate signed by the chosen CA, creates the user with that certificate
linked, and rolls back the certificate if user creation fails:
```
name         = <username>
password     = <per-user or batch password>
caref        = <caref chosen by human>
cert_descr   = <username>
dn_commonname = <username>
keytype      = "RSA"
keylen       = 2048
digest_alg   = "sha256"
lifetime     = 3650
descr        = <username>
```
If the call fails, record the failure (status: `failed`) and continue to the
next user. No manual cert linkage is needed. If the tool is missing from an
older MCP build, check `mcp__pfsense__get_api_capabilities` and upgrade the server.

### 4b. Client Specific Override (only if static IP assigned to this user)
Call `mcp__pfsense__manage_openvpn_cso` with:
```
action            = "create"
common_name       = <username>
server_id         = <vpnid>           # single integer — NOT server_list=[N]
custom_options    = "ifconfig-push <ip> 255.255.255.0"  # string — NOT a list
apply_immediately = True              # applies inline; no separate apply tool needed
```
All other fields: default / empty.

If the CSO call fails: note it in the report as a partial failure — do NOT
roll back the user/cert (the user account is still valid; the static IP simply
won't be pushed). Human can retry the CSO manually.

---

## 5. Apply

CSO changes are applied inline via `apply_immediately=True` on each
`manage_openvpn_cso` call (§4b). No separate apply tool is needed after the
loop — `mcp__pfsense__apply_openvpn_changes` does not exist in this MCP version.

If a CSO was created without `apply_immediately=True`, instruct the human to
click Save / Apply in pfSense WebUI → VPN → OpenVPN → Client Specific Overrides.
If no CSOs were created, skip this section.

---

## 6. Final Report

Print this block **after** all provisioning completes.

> ⚠️ **Save these passwords now.** Store them in your password manager or
> share them securely. Do not commit this chat to version control.

```
## Provisioning Report — <target OpenVPN server description>

CA used: <description> (refid: <caref>)

| username | user_id | cert_refid | cso_id | static_ip | password | status |
|---|---|---|---|---|---|---|
| alice | 42 | abc123 | 7 | 10.0.6.107 | <password> | created |
| bob | 43 | def456 | — | — | <password> | created-no-csc |
| carol | — | — | — | — | — | skipped: already exists |
```

Status legend:
- `created` — cert + user + CSO all succeeded
- `created-no-csc` — cert + user created; no static IP was provided for this user
- `skipped: already exists` — username found in pfSense before any writes
- `failed` — see Anomalies section below the table

Anomalies section: list any partial failures (e.g. cert created but user
creation failed and cert was rolled back; CSO failed after user was created;
apply step failed).

---

## 7. Common Pitfalls

**nextuid stale counter** — pfSense tracks the next available UID in config.
If you create users rapidly via API and the counter isn't incremented between
calls, two users may collide on the same UID. This manifests as a 409 or the
second user silently overwriting the first. Mitigation: process serially (§4)
and verify `user_id` in the response is unique before continuing.

**CSO apply is inline** — pass `apply_immediately=True` on each
`manage_openvpn_cso` call (§4b). There is no separate `apply_openvpn_changes`
tool in this MCP version; do not attempt to call one.

**Classifier block on destructive tools** — `mcp__pfsense__delete_certificate`
and other destructive tools are often blocked by auto-mode classifiers when
invoked inside subagents. If cleanup or rollback is needed and the tool is
refused, the human must pre-authorize it or delete manually via
System → Cert Manager → Certificates in the WebUI.

**Dangling certs on rollback failure** — if `create_user` fails and
`delete_certificate` also fails (e.g. a network timeout), the cert exists in
pfSense but is unlinked to any user. Note this explicitly in the report so the
human can clean up via System → Cert Manager → Certificates.

**Subnet mask in ifconfig-push** — pfSense's OpenVPN CSO `ifconfig-push`
directive requires the subnet mask in dotted-decimal, not CIDR. Always use
`ifconfig-push <ip> 255.255.255.0` (not `/24`).

**Tool availability varies by MCP version** — check the loaded tool list before
assuming `create_user_with_certificate` or any apply tool exists. Use
`mcp__pfsense__get_api_capabilities` if uncertain.

---

## 8. Cleanup / Rollback

Use this section when you need to undo a partially completed or failed batch.

**Object IDs are non-persistent array indices.** Every delete shifts the indices
of all subsequent objects. Never cache an ID across multiple deletes — always
re-query between each delete to get the current ID.

**Delete order: CSOs → users → certificates.** Certificates are last because
they are most sensitive to index shift and are hardest to recover if the wrong
one is deleted.

**Always serial, never parallel.** Do not issue multiple `delete_*` calls in the
same response turn. Issue one delete, wait for confirmation, then search again
before the next delete.

**Use stable lookups.** Prefer `mcp__pfsense__find_object_by_field` with
`refid` (for certs) or `common_name`/`name` (for CSOs/users) instead of
relying on a previously recorded numeric ID.

**Classifier-blocked deletes** — if `delete_certificate` is refused by the
auto-mode classifier, ask the human to authorize it explicitly or delete via
WebUI (System → Cert Manager → Certificates).
