"""命令行入口：argparse 子命令 + 全局 --json + 稳定退出码。"""

import argparse
import json
import os
import platform
import sys

from . import __version__, db, decrypt, formatting as F
from .config import CONFIG_PATH, PLAIN, find_sqlcipher
from .errors import EXIT_ERROR, QqcliError
from .names import NameResolver


# ── 输出辅助 ──────────────────────────────────────────
def emit_json(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def resolver_for(args):
    return NameResolver()


# ── 子命令 ────────────────────────────────────────────
def cmd_sessions(args):
    r = resolver_for(args)
    got = db.sessions(r, limit=args.limit, kind=args.kind)
    if args.json:
        emit_json([s.to_dict() for s in got])
    else:
        print(F.render_sessions(got))
    return 0


def cmd_history(args):
    r = resolver_for(args)
    msgs, name, kind = db.history(
        r, args.target, limit=args.limit, offset=args.offset,
        since=args.since, until=args.until, msg_type=args.msg_type)
    if args.json:
        emit_json({"chat": name, "type": kind,
                   "messages": [m.to_dict(args.segments) for m in msgs]})
    else:
        if not args.quiet:
            print("=== %s (%s) 共 %d 条 ===" % (name, kind, len(msgs)))
        print(F.render_messages(msgs))
    return 0


def cmd_search(args):
    r = resolver_for(args)
    msgs = db.search(r, args.keyword, chat=args.chat, limit=args.limit,
                     since=args.since, until=args.until)
    if args.json:
        emit_json([m.to_dict() for m in msgs])
    else:
        print(F.render_search(msgs))
        print("\n共 %d 条" % len(msgs))
    return 0


def _contacts(args, kind):
    r = resolver_for(args)
    got = db.contacts(r, kind=kind, query=args.query, limit=args.limit)
    if args.json:
        emit_json([c.to_dict() for c in got])
    else:
        print(F.render_contacts(got))
    return 0


def cmd_contacts(args):
    return _contacts(args, args.kind)


def cmd_groups(args):
    return _contacts(args, "group")


def cmd_friends(args):
    return _contacts(args, "friend")


def cmd_members(args):
    r = resolver_for(args)
    got, gid = db.members(r, args.group, limit=args.limit)
    gname = r.group_name(gid) or ""
    if args.json:
        emit_json({"group_id": gid, "group_name": gname,
                   "members": [m.to_dict() for m in got]})
    else:
        print(F.render_members(got, gid, gname))
    return 0


def cmd_new(args):
    r = resolver_for(args)
    msgs, since = db.new_messages(r, limit=args.limit, advance=not args.peek)
    if args.json:
        emit_json({"since_ts": since, "messages": [m.to_dict() for m in msgs]})
    else:
        if not msgs:
            print("(无新消息)")
        else:
            print(F.render_messages(msgs))
    return 0


def cmd_export(args):
    r = resolver_for(args)
    msgs, name, kind = db.history(
        r, args.target, limit=args.limit, since=args.since, until=args.until)
    fmt = args.format.lower()
    if fmt in ("md", "markdown"):
        text = _export_markdown(name, msgs)
    elif fmt == "txt":
        text = F.render_messages(msgs, indent="")
    elif fmt in ("json",):
        text = json.dumps({"chat": name, "type": kind,
                           "messages": [m.to_dict(args.segments) for m in msgs]},
                          ensure_ascii=False, indent=2)
    elif fmt in ("jsonl", "ndjson"):
        text = "\n".join(json.dumps(m.to_dict(args.segments), ensure_ascii=False) for m in msgs)
    else:
        raise QqcliError("未知导出格式: %s" % args.format,
                         hint="可选 markdown/txt/json/jsonl")
    if args.output:
        with open(args.output, "w") as f:
            f.write(text if text.endswith("\n") else text + "\n")
        print("[ok] %d 条消息 -> %s" % (len(msgs), args.output))
    else:
        print(text)
    return 0


def _export_markdown(name, msgs):
    lines = ["# 与 %s 的聊天记录" % name, "",
             "> 共 %d 条消息" % len(msgs), ""]
    cur_day = None
    for m in msgs:
        day = m.time_str[:10]
        if day != cur_day:
            lines += ["", "## %s" % day, ""]
            cur_day = day
        who = "我" if m.is_mine else m.sender_name
        lines.append("- `%s` **%s**: %s" % (m.time_str[11:19], who,
                                            m.content.replace("\n", " ")))
    return "\n".join(lines)


def cmd_doctor(args):
    rep = {
        "version": __version__,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "plain_dir": PLAIN,
        "plain_exists": os.path.isdir(PLAIN),
        "config": CONFIG_PATH,
        "config_exists": os.path.exists(CONFIG_PATH),
        "sqlcipher": find_sqlcipher(),
        "databases": [],
    }
    for name in ("nt_msg.db", "group_info.db", "profile_info.db", "recent_contact.db"):
        p = os.path.join(PLAIN, name)
        rep["databases"].append({
            "name": name, "exists": os.path.exists(p),
            "size": os.path.getsize(p) if os.path.exists(p) else 0,
        })
    try:
        r = NameResolver()
        rep["self_uid"] = r.self_uid()
        rep["known_names"] = {"uid": len(r._by_uid), "qq": len(r._by_qq),
                              "groups": len(r._by_group)}
    except QqcliError as e:
        rep["self_uid"] = None
        rep["note"] = str(e)
    if args.json:
        emit_json(rep)
    else:
        print("qqcli %s  (python %s)" % (rep["version"], rep["python"]))
        print("明文库目录 : %s  %s" % (rep["plain_dir"],
                                       "存在" if rep["plain_exists"] else "缺失"))
        print("配置       : %s  %s" % (rep["config"],
                                       "存在" if rep["config_exists"] else "缺失"))
        print("sqlcipher  : %s" % (rep["sqlcipher"] or "未找到 (brew install sqlcipher)"))
        print("本人 uid   : %s" % rep.get("self_uid"))
        print("已加载名称 : %s" % rep.get("known_names"))
        print("数据库:")
        for d in rep["databases"]:
            print("  %-18s %s %s" % (d["name"],
                                     "ok" if d["exists"] else "--",
                                     "%.1f MB" % (d["size"] / 1e6) if d["exists"] else ""))
    return 0


def cmd_version(args):
    rep = {"version": __version__, "python": sys.version.split()[0],
           "platform": platform.platform(), "name": "qqcli"}
    if args.json:
        emit_json(rep)
    else:
        print("qqcli %s" % __version__)
    return 0


def cmd_sync(args):
    from .config import load_config
    cfg = load_config()
    passphrase = cfg.get("passphrase") or _read_passphrase()
    acct, out = decrypt.sync(passphrase, account=args.account)
    cfg["passphrase"] = passphrase
    cfg["account_dir"] = acct
    from .config import save_config
    save_config(cfg)
    if args.json:
        emit_json({"account": acct,
                   "synced": [{"db": d, "path": p, "size": s} for d, p, s in out]})
    else:
        for d, p, s in out:
            print("[ok] %-18s -> %s (%.1f MB)" % (d, p, s / 1e6))
        print("[done] %d 个库已同步" % len(out))
    return 0


def _read_passphrase():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cand = os.path.join(base, "passphrase.txt")
    if os.path.exists(cand):
        with open(cand) as f:
            return f.read().strip()
    return None


def cmd_init(args):
    acct, info = decrypt.account_db_state(account=args.account)
    if args.json:
        emit_json({"account": acct,
                   "databases": [{"db": d, "exists": e, "size": s} for d, e, s in info]})
    else:
        print("[*] 账号目录: %s" % acct)
        for d, e, s in info:
            print("  %-18s %s %s" % (d, "ok" if e else "--",
                                     "%.1f MB" % (s / 1e6) if e else ""))
        print("[*] 解密导出请运行: qq sync")
    return 0


# ── argparse ──────────────────────────────────────────
class _Parser(argparse.ArgumentParser):
    """用法错误退出码统一为 1，把退出码 2 留给「需授权」。"""

    def error(self, message):
        self.print_usage(sys.stderr)
        print("[!] %s" % message, file=sys.stderr)
        raise SystemExit(EXIT_ERROR)


def build_parser():
    p = _Parser(
        prog="qq", description="本机 QQ 聊天记录查询 CLI（macOS）",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--json", action="store_true", help="以 JSON 输出")
    p.add_argument("--version", action="version", version="qqcli %s" % __version__)
    sub = p.add_subparsers(dest="command")

    sp = sub.add_parser("sessions", help="会话列表")
    sp.add_argument("-n", "--limit", type=int, default=20)
    sp.add_argument("--kind", choices=["all", "group", "c2c"], default="all")
    sp.set_defaults(func=cmd_sessions)

    sp = sub.add_parser("history", help="查看会话历史")
    sp.add_argument("target", help="群号/QQ号/uid/名称")
    sp.add_argument("-n", "--limit", type=int, default=None)
    sp.add_argument("--offset", type=int, default=0)
    sp.add_argument("--since", help="起始 YYYY-MM-DD")
    sp.add_argument("--until", help="结束 YYYY-MM-DD")
    sp.add_argument("--msg-type", dest="msg_type",
                    choices=["文本", "图片", "语音", "文件", "表情", "@", "回复", "转发"])
    sp.add_argument("--segments", action="store_true", help="JSON 中带分段")
    sp.add_argument("-q", "--quiet", action="store_true")
    sp.set_defaults(func=cmd_history)

    sp = sub.add_parser("search", help="搜索消息")
    sp.add_argument("keyword")
    sp.add_argument("-c", "--chat", help="限定会话")
    sp.add_argument("-n", "--limit", type=int, default=20)
    sp.add_argument("--since")
    sp.add_argument("--until")
    sp.set_defaults(func=cmd_search)

    sp = sub.add_parser("contacts", help="联系人（好友/群）")
    sp.add_argument("--kind", choices=["all", "friend", "group"], default="all")
    sp.add_argument("-q", "--query")
    sp.add_argument("-n", "--limit", type=int, default=50)
    sp.set_defaults(func=cmd_contacts)

    sp = sub.add_parser("groups", help="群列表")
    sp.add_argument("-q", "--query")
    sp.add_argument("-n", "--limit", type=int, default=200)
    sp.set_defaults(func=cmd_groups)

    sp = sub.add_parser("friends", help="好友列表")
    sp.add_argument("-q", "--query")
    sp.add_argument("-n", "--limit", type=int, default=200)
    sp.set_defaults(func=cmd_friends)

    sp = sub.add_parser("members", help="群成员")
    sp.add_argument("group")
    sp.add_argument("-n", "--limit", type=int, default=0)
    sp.set_defaults(func=cmd_members)

    sp = sub.add_parser("new", help="自上次检查以来的新消息")
    sp.add_argument("-n", "--limit", type=int, default=200)
    sp.add_argument("--peek", action="store_true", help="不推进检查点")
    sp.set_defaults(func=cmd_new)

    sp = sub.add_parser("export", help="导出会话")
    sp.add_argument("target")
    sp.add_argument("-o", "--output")
    sp.add_argument("-f", "--format", default="markdown",
                    choices=["markdown", "md", "txt", "json", "jsonl"])
    sp.add_argument("-n", "--limit", type=int, default=None)
    sp.add_argument("--since")
    sp.add_argument("--until")
    sp.add_argument("--segments", action="store_true")
    sp.set_defaults(func=cmd_export)

    sp = sub.add_parser("doctor", help="环境诊断")
    sp.set_defaults(func=cmd_doctor)

    sp = sub.add_parser("version", help="版本信息")
    sp.set_defaults(func=cmd_version)

    sp = sub.add_parser("init", help="发现账号并查看数据库状态")
    sp.add_argument("--account")
    sp.set_defaults(func=cmd_init)

    sp = sub.add_parser("sync", help="重新解密导出明文库")
    sp.add_argument("--account")
    sp.set_defaults(func=cmd_sync)

    return p


def main(argv=None):
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:                      # --help / --version / 用法错误
        return int(e.code) if e.code is not None else EXIT_ERROR
    if not getattr(args, "command", None):
        parser.print_help()
        return 0
    try:
        return args.func(args)
    except QqcliError as e:
        if getattr(args, "json", False):
            print(json.dumps({"error": str(e), "hint": e.hint,
                              "exit_code": e.exit_code}, ensure_ascii=False))
        else:
            print("[!] %s" % e)
            if e.hint:
                print("    %s" % e.hint)
        return e.exit_code
    except BrokenPipeError:
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as e:  # noqa: BLE001 — 顶层兜底，保证退出码稳定
        if getattr(args, "json", False):
            print(json.dumps({"error": str(e), "exit_code": EXIT_ERROR},
                             ensure_ascii=False))
        else:
            print("[!] 内部错误: %s" % e)
        return EXIT_ERROR
