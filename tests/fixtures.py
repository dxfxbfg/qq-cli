"""测试夹具：构造临时明文库与 protobuf blob。"""

import os
import sqlite3

from qqcli import schema as S


# ── protobuf 构造 ─────────────────────────────────────
def varint(n):
    out = b""
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out += bytes([b | 0x80])
        else:
            out += bytes([b])
            break
    return out


def pb_string(field, text):
    """wire-2 字段。"""
    payload = text.encode("utf-8") if isinstance(text, str) else text
    return varint(field << 3 | 2) + varint(len(payload)) + payload


def pb_nested(field, payload):
    return varint(field << 3 | 2) + varint(len(payload)) + payload


def blob_text(text, uid="u_ABCDEFGHIJKLMNOPQRST", extra=b""):
    """模拟一条正文：外层字段 40800 包裹 uid + 文本。"""
    inner = pb_string(40021, uid) + pb_string(47502, text) + extra
    return pb_nested(40800, inner)


# ── 临时库 ────────────────────────────────────────────
DDL = {
    "nt_msg.db": [
        """CREATE TABLE group_msg_table (
            [40001] INTEGER, [40009] INTEGER, [40020] TEXT, [40021] TEXT,
            [40030] INTEGER, [40050] INTEGER, [40090] TEXT, [40800] BLOB)""",
        """CREATE TABLE c2c_msg_table (
            [40001] INTEGER, [40009] INTEGER, [40020] TEXT, [40021] TEXT,
            [40030] INTEGER, [40050] INTEGER, [40090] TEXT, [40800] BLOB)""",
        """CREATE TABLE nt_uid_mapping_table (
            [48902] TEXT, [1002] INTEGER, [48912] TEXT)""",
    ],
    "group_info.db": [
        """CREATE TABLE group_list (
            [60001] INTEGER, [60007] TEXT, [60009] INTEGER)""",
        """CREATE TABLE group_member3 (
            [60001] INTEGER, [1000] TEXT, [64003] TEXT, [20002] TEXT, [1002] INTEGER)""",
    ],
    "profile_info.db": [
        """CREATE TABLE profile_info_v6 ([1002] INTEGER, [20002] TEXT)""",
        """CREATE TABLE buddy_list ([1000] TEXT, [1002] INTEGER)""",
    ],
}

SELF = "u_ME"
GROUP = 1001
PEER_QQ = 2002
DAY = 1780000000        # 固定基准时间戳


def build_plain(dirpath):
    """在 dirpath 下建三套明文库并写入样例数据，返回 dirpath。"""
    os.makedirs(dirpath, exist_ok=True)
    for name, ddls in DDL.items():
        path = os.path.join(dirpath, name)
        if os.path.exists(path):
            os.remove(path)
        con = sqlite3.connect(path)
        for d in ddls:
            con.execute(d)
        con.commit()
        con.close()

    pm = os.path.join(dirpath, "nt_msg.db")
    con = sqlite3.connect(pm)
    rows = [
        # msgid, flag, uid, peer/uid, chat, ts, card, blob
        (1, 1, SELF, str(GROUP), GROUP, DAY + 100, "", blob_text("我发的第一句", SELF)),
        (2, 1, "u_A", str(GROUP), GROUP, DAY + 200, "小明", blob_text("群里的回复")),
        (3, 1, "u_B", str(GROUP), GROUP, DAY + 300, "", blob_text("含关键词考试")),
        (4, 1, "u_A", str(GROUP), GROUP, 0, "", blob_text("ts=0 脏数据")),          # 应被过滤
        (5, 1, "u_X", str(GROUP), GROUP, DAY + 400, "", blob_text("重复正文")),
        (6, 1, "u_X", str(GROUP), GROUP, DAY + 401, "", blob_text("重复正文")),
    ]
    for r in rows:
        con.execute("INSERT INTO group_msg_table VALUES (?,?,?,?,?,?,?,?)", r)
    con.execute("INSERT INTO c2c_msg_table VALUES (?,?,?,?,?,?,?,?)",
                (10, 0, "u_LAN", "u_LAN", PEER_QQ, DAY + 150, "", blob_text("私聊内容")))
    con.execute("INSERT INTO c2c_msg_table VALUES (?,?,?,?,?,?,?,?)",
                (11, 0, SELF, SELF, PEER_QQ, DAY + 160, "", blob_text("我私聊回的")))
    # 让 SELF 出现在两个不同会话，作为 self_uid 推断依据（出现会话数最多）
    con.execute("INSERT INTO c2c_msg_table VALUES (?,?,?,?,?,?,?,?)",
                (12, 0, SELF, SELF, 3003, DAY + 170, "", blob_text("另一个私聊")))
    # self_uid 推断依据：SELF 出现在唯一会话里；再加一个更像本人的 uid 覆盖多会话
    con.execute("INSERT INTO nt_uid_mapping_table VALUES (?,?,?)", ("u_A", 3001, ""))
    con.commit()
    con.close()

    pg = os.path.join(dirpath, "group_info.db")
    con = sqlite3.connect(pg)
    con.execute("INSERT INTO group_list VALUES (?,?,?)", (GROUP, "测试群", None))
    for uid, card, nick, qq in [
            ("u_A", "小明", "小明昵称", 3001),
            ("u_B", "", "小红", 3002),
            ("u_ME", "本人", "", 9001)]:
        con.execute("INSERT INTO group_member3 VALUES (?,?,?,?,?)", (GROUP, uid, card, nick, qq))
    con.commit()
    con.close()

    pp = os.path.join(dirpath, "profile_info.db")
    con = sqlite3.connect(pp)
    con.execute("INSERT INTO profile_info_v6 VALUES (?,?)", (PEER_QQ, "阿蓝"))
    con.execute("INSERT INTO profile_info_v6 VALUES (?,?)", (3001, "小明昵称"))
    con.execute("INSERT INTO buddy_list VALUES (?,?)", ("u_LAN", PEER_QQ))
    con.commit()
    con.close()
    return dirpath
