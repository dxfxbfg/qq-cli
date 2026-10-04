"""只读查询层：会话 / 历史 / 搜索 / 联系人 / 成员 / 未读 / 新消息。

对外返回数据类（Session / Message / Contact / Member），不掺任何输出格式。
"""

import json
import os
import sqlite3
import time
from dataclasses import dataclass, field

from . import schema as S
from . import segment as SG
from .config import PLAIN, ensure_plain, plain_path
from .errors import QqcliError
from .names import NameResolver

STATE_PATH = os.path.join(os.path.dirname(PLAIN), "state.json")

TYPE_LABELS = {
    "text": "文本", "image": "图片", "record": "语音", "file": "文件",
    "face": "表情", "at": "@", "reply": "回复", "forward": "转发",
}


# ── 数据类 ────────────────────────────────────────────
@dataclass
class Session:
    chat_id: str
    name: str
    kind: str            # group / c2c
    count: int
    last_ts: int
    last_time: str
    last_content: str = ""

    def to_dict(self):
        return {
            "id": self.chat_id, "name": self.name, "type": self.kind,
            "count": self.count, "last_ts": self.last_ts,
            "last_time": self.last_time, "last": self.last_content,
        }


@dataclass
class Message:
    msg_id: str
    ts: int
    time_str: str
    sender_uid: str
    sender_name: str
    is_mine: bool
    content: str
    segments: list = field(default_factory=list)
    chat_id: str = ""
    chat_name: str = ""
    chat_kind: str = ""
    msg_type: str = "文本"

    def to_dict(self, with_segments=False):
        d = {
            "id": self.msg_id, "ts": self.ts, "time": self.time_str,
            "sender_uid": self.sender_uid, "sender": "我" if self.is_mine else self.sender_name,
            "is_mine": self.is_mine, "chat_id": self.chat_id,
            "chat_name": self.chat_name, "chat_type": self.chat_kind,
            "type": self.msg_type, "content": self.content,
        }
        if with_segments:
            d["segments"] = [s.to_dict() for s in self.segments]
        return d


@dataclass
class Contact:
    contact_id: str
    name: str
    kind: str            # friend / group
    extra: int = 0

    def to_dict(self):
        return {"id": self.contact_id, "name": self.name, "type": self.kind, "extra": self.extra}


@dataclass
class Member:
    uid: str
    name: str
    qq: str = ""

    def to_dict(self):
        return {"uid": self.uid, "name": self.name, "qq": self.qq}


# ── 连接与工具 ────────────────────────────────────────
def connect(name="nt_msg.db"):
    path = ensure_plain(name)
    return sqlite3.connect("file:%s?mode=ro" % path, uri=True)


def _fmt(ts):
    if not ts:
        return "未知"
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))


def _day(ts):
    return time.strftime("%Y-%m-%d", time.localtime(ts)) if ts else "未知"


def _parse_date(s, end=False):
    """'YYYY-MM-DD' -> epoch 秒。end=True 时取当日 23:59:59。"""
    try:
        t = time.strptime(s, "%Y-%m-%d")
    except ValueError:
        raise QqcliError("日期格式应为 YYYY-MM-DD: %s" % s)
    base = int(time.mktime((t.tm_year, t.tm_mon, t.tm_mday, 0, 0, 0, 0, 0, -1)))
    return base + (86399 if end else 0)


# ── 目标解析 ──────────────────────────────────────────
def resolve_target(target, resolver):
    """目标 -> (kind, table, col, value, name)。"""
    names = resolver
    if target.startswith("u_"):
        con = connect()
        try:
            row = con.execute(
                "SELECT %s, count(*) FROM %s WHERE %s=? GROUP BY %s" % (
                    S.CHAT, S.T_C2C_MSG, S.SENDER_UID, S.CHAT), (target,)).fetchone()
        finally:
            con.close()
        qq = row[0] if row and row[0] else None
        name = names.resolve(target) or target
        if qq:
            return ("c2c", S.T_C2C_MSG, S.CHAT, str(qq), name)
        return ("c2c", S.T_C2C_MSG, S.PEER, target, name)

    if target.isdigit():
        con = connect()
        try:
            g = con.execute("SELECT count(*) FROM %s WHERE %s=? AND %s>0" % (
                S.T_GROUP_MSG, S.CHAT, S.TS), (target,)).fetchone()[0]
            c = con.execute("SELECT count(*) FROM %s WHERE %s=? AND %s>0" % (
                S.T_C2C_MSG, S.CHAT, S.TS), (target,)).fetchone()[0]
        finally:
            con.close()
        if g and not c:
            return ("group", S.T_GROUP_MSG, S.CHAT, target, names.group_name(target) or target)
        if c and not g:
            return ("c2c", S.T_C2C_MSG, S.CHAT, target, names.name_for_qq(target) or target)
        if g:
            return ("group", S.T_GROUP_MSG, S.CHAT, target, names.group_name(target) or target)
        return ("c2c", S.T_C2C_MSG, S.CHAT, target, names.name_for_qq(target) or target)

    # 名称模糊匹配：群名优先，其次好友昵称/群名片
    hit = None
    for gid, gname in names._by_group.items():
        if target in gname:
            hit = gid
            break
    if hit:
        return resolve_target(hit, resolver)
    for uid, nm in names._by_uid.items():
        if target in nm:
            return resolve_target(uid, resolver)
    for qq, nm in names._by_qq.items():
        if target in nm:
            return resolve_target(qq, resolver)
    raise QqcliError("无法解析目标: %s" % target,
                     hint="用 qq contacts / qq groups 查看可用名称")


# ── 消息装配 ──────────────────────────────────────────
def _build_message(row, kind, resolver, self_uid, chat_name=""):
    msg_id, ts, uid, card, peer, chat, blob = row
    segs = SG.parse_blob(blob)
    inline = SG.render_inline(segs, resolve=resolver.resolve)
    mine = bool(self_uid) and str(uid or "") == self_uid
    if mine:
        sender = "我"
    else:
        sender = (card
                  or resolver.name_for_uid(uid)
                  or resolver.name_for_qq(peer)
                  or (str(uid) if uid else "?"))
    primary = next((TYPE_LABELS[s.kind] for s in segs if s.kind in TYPE_LABELS), "文本")
    return Message(
        msg_id=str(msg_id or ""), ts=ts or 0, time_str=_fmt(ts),
        sender_uid=str(uid or ""), sender_name=sender, is_mine=mine,
        content=inline, segments=segs, chat_id=str(chat or ""),
        chat_name=chat_name, chat_kind=kind, msg_type=primary,
    )


def _where(table, col, val, since=None, until=None):
    w = ["%s = '%s'" % (col, val), "%s > 0" % S.TS]
    if since:
        w.append("%s >= %d" % (S.TS, _parse_date(since)))
    if until:
        w.append("%s <= %d" % (S.TS, _parse_date(until, end=True)))
    return " AND ".join(w)


def _fetch(table, col, val, since=None, until=None, limit=None, offset=0):
    con = connect()
    try:
        sel = ("SELECT %s, %s, %s, %s, %s, %s, %s FROM %s WHERE %s " % (
            S.MSG_ID, S.TS, S.SENDER_UID, S.SENDER_CARD, S.PEER, S.CHAT,
            S.CONTENT, table, _where(table, col, val, since, until)))
        if limit is not None:
            rows = con.execute(sel + "ORDER BY %s DESC LIMIT ? OFFSET ?" % S.TS,
                               (limit, offset)).fetchall()
            rows.reverse()
        else:
            rows = con.execute(sel + "ORDER BY %s ASC" % S.TS).fetchall()
        return rows
    finally:
        con.close()


# ── 会话 ──────────────────────────────────────────────
def sessions(resolver, limit=20, kind="all"):
    con = connect()
    try:
        rows = con.execute(
            "SELECT %s, count(*), max(%s) FROM %s WHERE %s!=0 AND %s>0 "
            "GROUP BY %s UNION ALL "
            "SELECT %s, count(*), max(%s) FROM %s WHERE %s!=0 AND %s>0 "
            "GROUP BY %s ORDER BY 3 DESC" % (
                S.CHAT, S.TS, S.T_GROUP_MSG, S.CHAT, S.TS, S.CHAT,
                S.CHAT, S.TS, S.T_C2C_MSG, S.CHAT, S.TS, S.CHAT)
        ).fetchall()
    finally:
        con.close()

    out = []
    for chat_id, cnt, last_ts in rows:
        gname = resolver.group_name(chat_id)
        is_group = bool(gname) or _is_group_chat(str(chat_id))
        kind_ = "group" if is_group else "c2c"
        if kind != "all" and kind_ != kind:
            continue
        name = gname if is_group else (resolver.name_for_qq(chat_id) or str(chat_id))
        out.append(Session(str(chat_id), name, kind_, cnt, last_ts or 0,
                           _fmt(last_ts), _last_preview(str(chat_id), is_group, resolver)))
        if len(out) >= limit:
            break
    return out


def _is_group_chat(chat_id):
    con = connect()
    try:
        g = con.execute("SELECT count(*) FROM %s WHERE %s=? AND %s>0" % (
            S.T_GROUP_MSG, S.CHAT, S.TS), (chat_id,)).fetchone()[0]
        return g > 0
    finally:
        con.close()


def _last_preview(chat_id, is_group, resolver):
    table = S.T_GROUP_MSG if is_group else S.T_C2C_MSG
    con = connect()
    try:
        row = con.execute(
            "SELECT %s FROM %s WHERE %s=? AND %s>0 ORDER BY %s DESC LIMIT 1" % (
                S.CONTENT, table, S.CHAT, S.TS, S.TS), (chat_id,)).fetchone()
    finally:
        con.close()
    if not row:
        return ""
    return SG.render_inline(row[0], resolve=resolver.resolve)


# ── 历史 ──────────────────────────────────────────────
def history(resolver, target, limit=None, offset=0, since=None, until=None, msg_type=None):
    kind, table, col, val, name = resolve_target(target, resolver)
    self_uid = resolver.self_uid()
    if msg_type:
        rows = _fetch(table, col, val, since, until, None, 0)
        msgs = [_build_message(r, kind, resolver, self_uid, name) for r in rows]
        msgs = [m for m in msgs if m.msg_type == msg_type]
        if limit is not None:
            end = max(0, len(msgs) - offset)
            start = max(0, end - limit)
            msgs = msgs[start:end]
    else:
        rows = _fetch(table, col, val, since, until, limit, offset)
        msgs = [_build_message(r, kind, resolver, self_uid, name) for r in rows]
    return msgs, name, kind


# ── 搜索 ──────────────────────────────────────────────
def search(resolver, keyword, chat=None, limit=20, since=None, until=None):
    kh = keyword.encode("utf-8").hex().upper()
    self_uid = resolver.self_uid()
    chat_filter = None
    if chat:
        _, ctable, ccol, cval, _ = resolve_target(chat, resolver)
        chat_filter = (ctable, ccol, cval)

    out = []
    for kind, table in (("c2c", S.T_C2C_MSG), ("group", S.T_GROUP_MSG)):
        if chat_filter and chat_filter[0] != table:
            continue
        con = connect()
        try:
            w = ["%s>0" % S.TS, "hex(%s) LIKE '%%%s%%'" % (S.CONTENT, kh)]
            if chat_filter:
                w.append("%s = '%s'" % (chat_filter[1], chat_filter[2]))
            if since:
                w.append("%s >= %d" % (S.TS, _parse_date(since)))
            if until:
                w.append("%s <= %d" % (S.TS, _parse_date(until, end=True)))
            rows = con.execute(
                ("SELECT %s, %s, %s, %s, %s, %s, %s FROM %s WHERE %s "
                 "ORDER BY %s DESC LIMIT ?") % (
                    S.MSG_ID, S.TS, S.SENDER_UID, S.SENDER_CARD, S.PEER, S.CHAT,
                    S.CONTENT, table, " AND ".join(w), S.TS),
                (max(limit * 5, 100),)).fetchall()
        finally:
            con.close()

        chat_name = ""
        for r in rows:
            m = _build_message(r, kind, resolver, self_uid, chat_name)
            if keyword not in m.content:
                continue
            if kind == "group":
                m.chat_name = resolver.group_name(m.chat_id) or m.chat_id
            else:
                m.chat_name = resolver.name_for_qq(m.chat_id) or m.chat_id
            out.append(m)

    out.sort(key=lambda m: m.ts, reverse=True)
    return out[:limit]


# ── 联系人 ────────────────────────────────────────────
def contacts(resolver, kind="all", query=None, limit=50):
    out = []
    if kind in ("all", "group"):
        for gid, gname in sorted(resolver._by_group.items(), key=lambda x: str(x[1])):
            if query and query not in gname:
                continue
            out.append(Contact(gid, gname, "group", resolver.member_count(gid) or 0))
            if len(out) >= limit:
                break
    if kind in ("all", "friend"):
        con = None
        try:
            con = connect("profile_info.db")
            uid2qq = dict(con.execute(
                "SELECT %s, %s FROM %s" % (S.BUDDY_UID, S.BUDDY_QQ, S.T_BUDDY)))
        except sqlite3.Error:
            uid2qq = {}
        finally:
            if con:
                con.close()
        for uid, qq in uid2qq.items():
            nm = resolver.name_for_uid(uid) or resolver.name_for_qq(qq) or str(qq)
            if query and query not in nm:
                continue
            out.append(Contact(str(qq), nm, "friend"))
            if len(out) >= limit:
                break
    return out


def members(resolver, group, limit=0):
    gid = group
    if not str(group).isdigit():
        gname = resolver.group_name(group)
        if not gname:
            for g, n in resolver._by_group.items():
                if group in n:
                    gid = g
                    break
        else:
            gid = group
    con = connect("group_info.db")
    try:
        rows = con.execute(
            "SELECT %s, %s, %s, %s FROM %s WHERE %s=? ORDER BY %s" % (
                S.MEMBER_UID, S.MEMBER_CARD, S.MEMBER_NICK, S.MEMBER_QQ,
                S.T_GROUP_MEMBER, S.GROUP_ID, S.MEMBER_NICK), (str(gid),)).fetchall()
    finally:
        con.close()
    out = []
    for uid, card, nick, qq in rows:
        nm = (card or nick or resolver.name_for_uid(uid)
              or resolver.name_for_qq(qq) or str(uid))
        out.append(Member(str(uid), nm, str(qq or "")))
        if limit and len(out) >= limit:
            break
    return out, str(gid)


# ── 新消息（自上次检查）────────────────────────────────
def _load_state():
    if not os.path.exists(STATE_PATH):
        return {}
    try:
        with open(STATE_PATH) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_state(state):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, ensure_ascii=False)


def new_messages(resolver, limit=200, advance=True):
    state = _load_state()
    since_ts = int(state.get("last_check_ts", 0))
    con = connect()
    try:
        rows = con.execute(
            "SELECT %s, %s, %s, %s, %s, %s, %s FROM %s WHERE %s>? AND %s!=0 "
            "ORDER BY %s ASC LIMIT ?" % (
                S.MSG_ID, S.TS, S.SENDER_UID, S.SENDER_CARD, S.PEER, S.CHAT,
                S.CONTENT, S.T_GROUP_MSG, S.TS, S.CHAT, S.TS),
            (since_ts, limit)).fetchall()
    finally:
        con.close()
    self_uid = resolver.self_uid()
    msgs = []
    for r in rows:
        m = _build_message(r, "group", resolver, self_uid)
        m.chat_name = resolver.group_name(m.chat_id) or m.chat_id
        msgs.append(m)
    if advance:
        state["last_check_ts"] = int(time.time())
        _save_state(state)
    return msgs, since_ts
