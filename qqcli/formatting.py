"""人类可读输出。所有排版在这里，查询层不掺格式。

宽度按东亚字符（全角）计 2 列，保证中文表格对齐。
"""

import unicodedata

BAR = "─"


def width(s):
    w = 0
    for ch in s:
        w += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return w


def truncate(s, max_w):
    if width(s) <= max_w:
        return s
    out, w = "", 0
    for ch in s:
        cw = 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
        if w + cw > max_w - 1:
            break
        out += ch
        w += cw
    return out + "…"


def pad(s, target, align="left"):
    gap = max(0, target - width(s))
    if align == "right":
        return " " * gap + s
    return s + " " * gap


def table(headers, rows, aligns=None, max_widths=None):
    cols = len(headers)
    aligns = aligns or ["left"] * cols
    max_widths = max_widths or [0] * cols
    cells = []
    for r in rows:
        cells.append([truncate(str(c), max_widths[i]) if max_widths[i] else str(c)
                      for i, c in enumerate(r)])
    w = [width(headers[i]) for i in range(cols)]
    for r in cells:
        for i in range(cols):
            w[i] = max(w[i], width(r[i]))
    lines = ["  ".join(pad(headers[i], w[i], aligns[i]) for i in range(cols)).rstrip()]
    for r in cells:
        lines.append("  ".join(pad(r[i], w[i], aligns[i]) for i in range(cols)).rstrip())
    return "\n".join(lines)


# ── 会话 ──────────────────────────────────────────────
def render_sessions(sessions):
    if not sessions:
        return "(无会话)"
    rows = []
    for s in sessions:
        rows.append(["群" if s.kind == "group" else "私", s.name, s.chat_id,
                     str(s.count), s.last_time, truncate(s.last_content.replace("\n", " "), 40)])
    return table(["类型", "名称", "会话 ID", "条数", "最后消息", "预览"],
                 rows, aligns=["left", "left", "left", "right", "left", "left"],
                 max_widths=[0, 28, 0, 0, 0, 40])


# ── 消息 ──────────────────────────────────────────────
def render_messages(messages, show_date=True, show_sender=True, indent="  "):
    if not messages:
        return "(无消息)"
    lines = []
    cur_day = None
    for m in messages:
        day = m.time_str[:10]
        if show_date and day != cur_day:
            lines.append("")
            lines.append("%s %s %s" % (BAR * 2, day, BAR * 40))
            cur_day = day
        hms = m.time_str[11:19] if len(m.time_str) >= 19 else m.time_str
        if show_sender:
            who = "我" if m.is_mine else m.sender_name
            lines.append("[%s] %s%s: %s" % (hms, indent, who,
                                            m.content.replace("\n", "\n" + indent)))
        else:
            lines.append("[%s] %s" % (hms, m.content))
    return "\n".join(lines).lstrip("\n")


def render_search(messages):
    if not messages:
        return "(无结果)"
    lines = []
    for m in messages:
        kind = "群" if m.chat_kind == "group" else "私"
        who = "我" if m.is_mine else m.sender_name
        text = m.content.replace("\n", " ")
        lines.append("[%s] %s %s  %s: %s" % (
            m.time_str[:16], kind, truncate(m.chat_name, 22), truncate(who, 16),
            truncate(text, 100)))
    return "\n".join(lines)


# ── 联系人 / 成员 ─────────────────────────────────────
def render_contacts(contacts):
    groups = [c for c in contacts if c.kind == "group"]
    friends = [c for c in contacts if c.kind == "friend"]
    lines = []
    if groups:
        lines.append("=== 群聊 (%d) ===" % len(groups))
        lines.append(table(["群号", "群名", "成员"],
                           [[c.contact_id, c.name, c.extra or ""] for c in groups],
                           aligns=["left", "left", "right"], max_widths=[0, 32, 0]))
        lines.append("")
    if friends:
        lines.append("=== 好友 (%d) ===" % len(friends))
        lines.append(table(["QQ", "昵称"], [[c.contact_id, c.name] for c in friends],
                           max_widths=[0, 32]))
    return "\n".join(lines) if lines else "(无联系人)"


def render_members(members, group_id, group_name=""):
    head = "=== 群 %s %s 成员 (%d) ===" % (group_id, group_name, len(members))
    if not members:
        return head + "\n(无成员数据)"
    return head + "\n" + table(
        ["uid", "群名片/昵称", "QQ"],
        [[m.uid, m.name, m.qq] for m in members],
        max_widths=[0, 28, 0])
