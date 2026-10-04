# qq-cli

[简体中文](README.md) · English

Reads the local chat database of QQ NT on macOS (`nt_qq_<hash>/nt_db/nt_msg.db`, SQLCipher),
decrypts it into plain SQLite, then searches, summarizes and exports. Runs as an ordinary CLI or
as a skill installed into an AI agent's skill directory. On Windows there is a more complete
[2233admin/qqcli-rs](https://github.com/2233admin/qqcli-rs); this repo is the macOS port in Python.

It only touches the data of the person running it, on their own machine and their own account.
Queries read local files only — no network, no login takeover, no effect on normal QQ use. See the
disclaimer at the end.

## Requirements

macOS and QQ NT desktop only — no cross-platform support. Key extraction relies on macOS lldb and
the SIP debug switch, so Windows is out of scope.

You need sqlcipher installed (`brew install sqlcipher`), QQ NT logged in and run at least once,
and Python 3.9 or newer. There are no third-party dependencies.

Extracting the key requires temporarily turning off the macOS SIP debug restriction
(Debugging Restrictions). The step sets lldb breakpoints inside the QQ process, which SIP refuses.
Boot into Recovery (hold the power button on Apple Silicon, ⌘R on Intel) and run
`csrutil enable --without debug` to lift only the debug restriction while leaving the rest of SIP
in place, or `csrutil disable`. You can turn it back on afterwards. Once the key is captured and
the plain database is exported, day-to-day queries need neither SIP disabled nor lldb running.

The tool is not tied to a QQ version. Message bodies are parsed with an order-preserving protobuf
scan that does not depend on version-specific element field numbers, and the timestamp / sender /
group-id field IDs have not changed across NT versions. The SQLCipher parameters (page_size /
kdf_iter / HMAC) have stayed the same for a long time and the defaults work as-is; if a future
version changes them, capture the values with `kdf_hook.py` and write them into the `cipher` field
of `config.json`. No code change needed.

## How this differs from other tools

Frameworks like NapCat take the bot route: they run a separate QQ account, usually headless, and
that account carries the login conflicts, risk-control and ban risk. This project does the opposite.
It takes over no login and never talks to QQ's servers.

During queries it does one thing: read the plain database copy on disk. Connections are read-only
(`mode=ro`), there is no network request anywhere in the code, and the only external call is the
local `sqlcipher` command. QQ keeps logging in, sending and receiving as usual, and no extra account
is needed.

The one step that does touch the QQ process is the initial key extraction: it quits QQ and
relaunches it under lldb to capture the passphrase. That happens once, and afterwards queries do not
need QQ running at all.

## Demo

The output below comes from synthetic data. The group and the names in it are made up, not real
chat records.

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

The CLI output is Chinese because it targets Chinese QQ users, so the block above is verbatim.
In the first table, `类型` is the type (`私` for c2c, `群` for group), `条数` the message count,
`最后消息` the last message time and `预览` a preview. In `history` and `search`, `我` means "me"
and `[图片]` stands for an image message.

## Install

Installing with pip is recommended: `pyproject.toml` generates the `qq` command, so there is no
PYTHONPATH to configure.

```bash
pip install -e .        # or: pipx install .
qq version
```

Running without installing also works:

```bash
QQ="$HOME/.local/bin/qq"                 # symlink -> python -m qqcli
PYTHONPATH=. python3 -m qqcli sessions   # run from the repo root
```

The repo root is the Python package root: `qqcli/` is the package, `tests/` the regression suite.
`~/.local/bin` is often missing from a session's PATH, so scripts should use `~/.local/bin/qq` or
an absolute path.

## As an agent skill

This repo directory is itself a valid skill directory. The `SKILL.md` at its root holds the command
reference, field semantics, SQL snippets and pitfalls, written entirely with `$HOME` and relative
paths, with no machine-specific information.

To make an agent pick it up, put this directory (or a symlink to it) under a skill directory such as
`~/.workbuddy/skills/qq-cli` or `~/.claude/skills/qq-cli`. To share only the documentation,
`SKILL.md` on its own is enough.

## Commands

```bash
qq sync                            # re-decrypt and export the plain databases (works while QQ runs)
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

`--json` is global and switches the output to machine-readable form. `<target>` accepts a group id,
a QQ number, a uid (`u_` prefix), or part of a name.

There are four exit codes, which agents can branch on:

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error (bad arguments, unresolvable target, bad date format) |
| 2 | Authorization required (decryption) |
| 3 | Environment not ready (plain database missing — run `qq sync` first) |

## Code structure

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

The layering is fairly strict: `db` yields data classes only, `formatting` handles presentation
only, `segment` handles parsing only, and none of them reach into each other.

## Field semantics

nt_msg.db uses numeric column names. These are the important ones, and the IDs are stable across
NT versions.

| Column | Meaning |
|--------|---------|
| `[40050]` | Unix timestamp (seconds) |
| `[40020]` | Sender uid — this is what "is it me" is based on (compared against self_uid) |
| `[40090]` | Sender's group card; empty for roughly 40% of group messages, falls back to `group_member3` |
| `[40021]` | Group id in the group table, peer uid in the c2c table |
| `[40030]` | Group id (group table) or peer QQ number (c2c table) |
| `[40009]` | A constant flag, unrelated to who sent the message — do not use it for direction |
| `[40800]` | Message body protobuf blob |

The plain database contains leftover `[40050]=0` placeholder rows from decryption; queries filter
them out already.

## Tests

```bash
./tests/run_tests.sh          # unit + integration (integration runs when a real DB exists)
```

The unit tests cover protobuf segmentation, noise and rich-text handling, name resolution, layout
alignment and the query layer, using temporary fixture databases. The integration tests run every
subcommand against the real plain database and check exit codes, the JSON contract, and that no
1970 junk rows show up in the output.

## Keys and privacy

The passphrase and db_key stay on the local machine and are never committed. `~/.qqmac/config.json`,
`passphrase.txt` and `db_key.txt` are all listed in `.gitignore`. First use requires running
`extract_key.sh` locally; the repo ships no keys.

The tool reads local data only. Exported files contain private information, so store them where you
choose. If the key breaks or you switch QQ versions, re-run `extract_key.sh` — again with lldb and
the SIP debug restriction off.

## Pre-publish check

Run this before committing or publishing to confirm no personal paths or keys slipped in:

```bash
./scripts/check_publish_safe.sh
```

No output means it passed; otherwise the script lists everything suspicious.

## Key extraction

Three scripts work together, for a one-time run:

- `find_key_func.py` / `precise_locate.py`: statically locate `nt_sqlite3_key_v2`
- `getkey_helper.py` + lldb spawn: capture the key automatically
- `kdf_hook.py`: breakpoint on `PKCS5_PBKDF2_HMAC` to capture the actual SQLCipher passphrase

## Disclaimer

This tool is for reading the QQ chat history of the person running it, on their own device and their
own account. It must not be used to obtain, monitor or analyze anyone else's data.

This is an unofficial project. It is not affiliated with or endorsed by Tencent, and QQ and related
marks belong to Tencent.

Use must comply with local law and QQ's terms of service. Exported chat history contains other
people's private information and is subject to privacy law; confirm legality before forwarding or
publishing it. Any compliance or legal consequences of use rest with the user.

Key extraction requires temporarily disabling the macOS SIP debug restriction, which lowers system
protection during that window — do it in a trusted environment and re-enable it afterwards. All
processing happens locally with no uploads and no telemetry; exported files are the user's to keep
safe.

The software is provided as is under the MIT license, with no warranty of any kind.

## License

[MIT](LICENSE). Design inspired by [2233admin/qqcli-rs](https://github.com/2233admin/qqcli-rs) (MIT).
