# qq-cli — Local QQ Chat History Reader for macOS (Agent Skill / CLI)

[简体中文](README.md) · **English**

Local QQ data access built for **AI agents**: read the local database of QQ NT for macOS
(`nt_qq_<hash>/nt_db/nt_msg.db`, SQLCipher), decrypt it into plain SQLite, then search,
summarize and export chat history. Usable directly as an agent skill, or as an ordinary CLI.

Inspired by [2233admin/qqcli-rs](https://github.com/2233admin/qqcli-rs) (Windows); this repo is the macOS/Python port.

## Scope and prerequisites

> **For reading your own QQ data, on your own device, for your own account only** — never anyone
> else's. See the Disclaimer at the end.

**macOS only** (QQ NT desktop). No cross-platform support — key extraction relies on macOS
lldb and the SIP debug switch, neither of which exists on Windows.

**Not tied to a specific QQ version:**

- Message bodies are parsed with an order-preserving protobuf scan, not version-specific element field numbers
- Field IDs (timestamp / sender / group id) have been stable across NT versions
- SQLCipher parameters (page_size / kdf_iter / HMAC) are long-standing defaults; if a future
  version changes them, capture them with `kdf_hook.py` and write them into `config.json`
  under `cipher` — no code change needed

**Prerequisites:**

1. macOS (Apple Silicon or Intel), QQ NT desktop installed and logged in at least once
2. `brew install sqlcipher`
3. **Extracting the key requires temporarily disabling the macOS SIP debug restriction** —
   key capture sets lldb breakpoints inside the QQ process, which SIP blocks. Boot into
   Recovery (hold the power button on Apple Silicon; ⌘R on Intel) and run
   `csrutil enable --without debug` (keeps the rest of SIP intact) or `csrutil disable`.
   You can turn it back on afterwards.
4. Python 3.9+ (zero third-party dependencies)

> Once the key is captured and the plain database is exported, day-to-day queries no longer
> need SIP disabled or lldb running.

## Demo

The output below comes from **synthetic data** (the group and people shown are made up —
no real chat records):

```console
$ qq sessions -n 5
类型  名称        会话 ID  条数  最后消息             预览
私    老周        66001       1  2026-10-03 13:00:00  资料我已经发你邮箱了
私    晓风        77001       2  2026-10-03 12:55:00  好，八点我上线
群    示例项目组  88001       5  2026-10-03 12:50:00  我把文档放群文件了

$ qq history 88001 -n 5
=== 示例项目组 (group) 共 5 条 ===
── 2026-10-03 ────────────────────────────────────────
[12:10:00]   我: 我自己发的测试消息
[12:20:00]   阿澈: 下周的分享会改到周四晚上八点
[12:30:00]   小满: 收到，我把会议室也改一下
[12:40:00]   阿澈: [图片]
[12:50:00]   我: 我把文档放群文件了

$ qq search 分享会
[2026-10-03 12:20] 群 示例项目组  阿澈: 下周的分享会改到周四晚上八点

共 1 条
```

The CLI output itself is Chinese (it targets Chinese QQ users), so the block above is verbatim.
Column legend for the first table: `类型` = type (`私` c2c / `群` group), `条数` = message count,
`最后消息` = last message time, `预览` = preview. In `history`/`search`, `我` means "me" and
`[图片]` is the placeholder for an image message.

## Install and entry points

- Entry point: `~/.local/bin/qq` (symlink → `~/.agents/bin/qq` → `python -m qqcli`)
- The repo root is the Python package root: `qqcli/` is the package, `tests/` the regression suite
- Zero third-party dependencies (standard library + the `sqlcipher` CLI)

Recommended: install with pip so `pyproject.toml` generates the `qq` command (no manual PYTHONPATH):

```bash
pip install -e .        # or: pipx install .
qq version
```

Or run without installing:

```bash
QQ="$HOME/.local/bin/qq"                 # symlink -> python -m qqcli
PYTHONPATH=. python3 -m qqcli sessions   # run the package straight from the repo root
```

> Note: `~/.local/bin` is often missing from a session's PATH — use `~/.local/bin/qq` or an absolute path in scripts.

## Using it as an agent skill

This repo directory **is** a valid agent skill directory — the `SKILL.md` at its root is the
skill description (command reference, field semantics, SQL snippets, pitfalls), written entirely
with `$HOME`/relative paths and containing no machine-specific information.

- To make an agent pick it up, place this directory (or a symlink to it) under a skill directory,
  e.g. `~/.workbuddy/skills/qq-cli` or `~/.claude/skills/qq-cli`
- To share only the documentation, distributing `SKILL.md` alone works too

## Commands

```bash
qq sync                            # re-decrypt and export the plain databases (works while QQ is running)
qq init                            # discover account dirs, show database status
qq sessions [-n 20] [--kind group|c2c|all]         # session list
qq history <target> [-n N] [--offset N] [--since D] [--until D] [--msg-type T]
qq search <keyword> [-c chat] [-n N] [--since D] [--until D]
qq contacts [--kind all|friend|group] [-q query] [-n N]
qq groups / qq friends             # shortcuts for contacts
qq members <group-id> [-n N]       # group members
qq new [-n N] [--peek]             # messages since the last check
qq export <target> [-o file] [-f markdown|txt|json|jsonl] [--since D] [--until D]
qq doctor                          # environment diagnostics
qq version
```

`--json` (global) emits machine-readable output. `<target>` accepts a group id, a QQ number,
a uid (`u_` prefix), or a fuzzy name match.

### Exit codes (agent contract)

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error (bad arguments / unresolvable target / bad date format) |
| 2 | Authorization required (decryption) |
| 3 | Environment not ready (plain database missing — run `qq sync` first) |

## Architecture

```
qqcli/
  config.py     paths and config (QQCLI_HOME / QQCLI_PLAIN_DIR overrides)
  schema.py     field-ID constants for nt_msg/group_info/profile_info (stable across NT versions)
  names.py      uid / QQ / group-id -> display name, plus self_uid inference
  segment.py    [40800] protobuf -> OneBot-style segments (text/image/at/file/...)
  db.py         read-only queries: sessions / history / search / contacts / members / new
  formatting.py human-readable output (East-Asian width alignment, date separators, direction)
  decrypt.py    SQLCipher decryption (init/sync only)
  cli.py        argparse subcommands + --json + exit codes
```

Layering rule: `db` yields data classes only, `formatting` handles presentation only,
`segment` handles parsing only — no crossing.

## Column semantics (`nt_msg.db` field IDs, stable across NT versions)

| Column | Meaning |
|--------|---------|
| `[40050]` | Unix timestamp (seconds) |
| `[40020]` | Sender uid — **this is how "is it me" is determined** (== self_uid) |
| `[40090]` | Sender's group card (empty for ~40% of group messages; falls back to `group_member3`) |
| `[40021]` | Group id in the group table; peer uid in the c2c table |
| `[40030]` | Group id (group table) / peer QQ number (c2c table) |
| `[40009]` | A constant flag, **not** "sent by me" — do not use it to infer direction |
| `[40800]` | Message body protobuf blob |

> The plain database contains leftover `[40050]=0` placeholder rows from decryption;
> all queries filter them out automatically.

## Tests

```bash
./tests/run_tests.sh          # unit + integration (integration runs automatically when a real DB exists)
```

- Unit: protobuf segmentation, noise/rich-text handling, name resolution, layout alignment, query layer (temp fixture DBs)
- Integration: every subcommand against the real plain database — exit codes, JSON contract, no 1970 junk rows

## Keys and privacy

- **passphrase / db_key stay local and are never committed**: `~/.qqmac/config.json`,
  `passphrase.txt` and `db_key.txt` are all covered by `.gitignore`. First use requires running
  `extract_key.sh` on your own machine — this repo ships no keys.
- Read-only local access; exported files contain private data, so put them where you choose
- If the key breaks or you switch QQ versions → re-run `extract_key.sh` (needs lldb and the SIP debug restriction off, see Prerequisites)

## Pre-publish check

Run the safety check before committing or publishing, to confirm no personal paths or keys got included:

```bash
./scripts/check_publish_safe.sh
```

No output means it passed (the script lists anything suspicious).

## Key extraction chain (one-time)

- `find_key_func.py` / `precise_locate.py`: statically locate `nt_sqlite3_key_v2`
- `getkey_helper.py` + lldb spawn: capture the key automatically
- `kdf_hook.py`: breakpoint on `PKCS5_PBKDF2_HMAC` to capture the actual SQLCipher passphrase

## Disclaimer

- **Your own device and your own account only.** This tool reads **your own** QQ chat history from
  **your own** machine. Do not use it to obtain, monitor or analyze anyone else's data.
- **Unofficial.** Not affiliated with, authorized by, or endorsed by Tencent. QQ and related marks
  belong to Tencent.
- **You are responsible for compliance.** Use must comply with your local laws and QQ's terms of
  service. Do not use exported chat history to invade privacy, harass, defame or profit. Other
  people's messages are protected by privacy law (e.g. PIPL in China) — redistribute with care.
- **Disabling SIP has a security cost.** Key extraction requires temporarily disabling the macOS SIP
  debug restriction; your machine is less protected during that window. Do it in a trusted
  environment and re-enable it afterwards.
- **Nothing leaves your machine.** All processing is local — no uploads, no telemetry. Exported
  files are your responsibility to store.
- **Provided as is.** Released under MIT with no warranty of any kind; you bear the consequences of use.

## License

[MIT](LICENSE). Design inspired by [2233admin/qqcli-rs](https://github.com/2233admin/qqcli-rs) (MIT).
