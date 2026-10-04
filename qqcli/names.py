"""uid / QQ 号 / 群号 -> 显示名 解析。

数据源与优先级：
    群名片  group_info.db.group_member3 [1000]->[64003]
    昵称    group_member3 [1000]->[20002] / profile_info_v6 [1002]->[20002]
    uid映射 nt_msg.db.nt_uid_mapping_table [48902]->[48912]（名字列常为空）
    uid->QQ c2c 表 [40020]->[40030] 反查（成员表未覆盖时兜底）

本人 uid（self_uid）优先读 config，其次用 c2c 中出现最多不同会话的 uid 推断。
"""

import os
import sqlite3

from . import schema as S
from .config import load_config, plain_path, save_config

_MISSING = object()


def _connect(path):
    if not os.path.exists(path):
        return None
    try:
        return sqlite3.connect("file:%s?mode=ro" % path, uri=True)
    except sqlite3.Error:
        return None


class NameResolver:
    """一次性加载映射表，之后纯内存查。任何数据源缺失都不致命。"""

    def __init__(self, nt_msg=None, group_info=None, profile_info=None, self_uid=None):
        self.nt_msg = nt_msg or plain_path("nt_msg.db")
        self.group_info = group_info or plain_path("group_info.db")
        self.profile_info = profile_info or plain_path("profile_info.db")
        self._by_uid = {}
        self._by_qq = {}
        self._by_group = {}
        self._member_count = {}
        self._uid_to_qq = {}
        self._self_uid = self_uid
        self._load()

    # ── 加载 ──────────────────────────────────────────
    def _load(self):
        self._load_profile()
        self._load_groups()
        self._load_members()
        self._load_uidmap_and_c2c()

    def _rows(self, path, sql):
        con = _connect(path)
        if con is None:
            return []
        try:
            return list(con.execute(sql))
        except sqlite3.Error:
            return []
        finally:
            con.close()

    def _load_profile(self):
        for qq, nick in self._rows(
                self.profile_info,
                "SELECT %s, %s FROM %s WHERE %s!=''" % (
                    S.PROFILE_QQ, S.PROFILE_NICK, S.T_PROFILE, S.PROFILE_NICK)):
            if qq is not None and nick:
                self._by_qq.setdefault(str(qq), str(nick))
        for uid, qq in self._rows(
                self.profile_info,
                "SELECT %s, %s FROM %s" % (S.BUDDY_UID, S.BUDDY_QQ, S.T_BUDDY)):
            if uid and qq:
                self._uid_to_qq.setdefault(str(uid), str(qq))

    def _load_groups(self):
        for gid, gname, cnt in self._rows(
                self.group_info,
                "SELECT %s, %s, %s FROM %s" % (
                    S.GROUP_ID, S.GROUP_NAME, S.GROUP_MEMBER_COUNT, S.T_GROUP_LIST)):
            if gid is None:
                continue
            if gname:
                self._by_group[str(gid)] = str(gname)
            if cnt:
                self._member_count[str(gid)] = cnt

    def _load_members(self):
        for uid, card, nick, qq in self._rows(
                self.group_info,
                "SELECT %s, %s, %s, %s FROM %s" % (
                    S.MEMBER_UID, S.MEMBER_CARD, S.MEMBER_NICK, S.MEMBER_QQ,
                    S.T_GROUP_MEMBER)):
            if not uid:
                continue
            uid = str(uid)
            if card:
                self._by_uid.setdefault(uid, str(card))
            if nick:
                self._by_uid.setdefault(uid, str(nick))
            if qq:
                self._uid_to_qq.setdefault(uid, str(qq))
        # 群成员数兜底：group_list [60009] 常为空，用成员表计数
        for gid, cnt in self._rows(
                self.group_info,
                "SELECT %s, count(*) FROM %s GROUP BY %s" % (
                    S.GROUP_ID, S.T_GROUP_MEMBER, S.GROUP_ID)):
            if gid is not None:
                self._member_count.setdefault(str(gid), cnt)

    def _load_uidmap_and_c2c(self):
        for uid, qq, name in self._rows(
                self.nt_msg,
                "SELECT %s, %s, %s FROM %s" % (
                    S.UIDMAP_UID, S.UIDMAP_QQ, S.UIDMAP_NAME, S.T_UIDMAP)):
            if not uid:
                continue
            uid = str(uid)
            if name:
                self._by_uid.setdefault(uid, str(name))
            if qq:
                self._uid_to_qq.setdefault(uid, str(qq))
        # c2c 反查：私聊里 uid<->对方 QQ，用于成员表未覆盖的会话
        for uid, qq in self._rows(
                self.nt_msg,
                "SELECT DISTINCT %s, %s FROM %s WHERE %s>0 AND %s!=0 AND %s!=''" % (
                    S.SENDER_UID, S.CHAT, S.T_C2C_MSG, S.TS, S.CHAT, S.SENDER_UID)):
            if uid and qq:
                self._uid_to_qq.setdefault(str(uid), str(qq))
        # uid -> QQ -> 昵称 最后一跳
        for uid, qq in self._uid_to_qq.items():
            nick = self._by_qq.get(str(qq))
            if nick:
                self._by_uid.setdefault(uid, nick)

    # ── 查询 ──────────────────────────────────────────
    def name_for_uid(self, uid):
        if not uid:
            return None
        return self._by_uid.get(str(uid))

    def name_for_qq(self, qq):
        if not qq:
            return None
        return self._by_qq.get(str(qq))

    def group_name(self, gid):
        if not gid:
            return None
        return self._by_group.get(str(gid))

    def member_count(self, gid):
        return self._member_count.get(str(gid))

    def resolve(self, raw):
        """uid / QQ 号 / 群号，尽力解出显示名。"""
        if raw is None:
            return None
        raw = str(raw)
        return (self.name_for_uid(raw)
                or self.name_for_qq(raw)
                or self.group_name(raw)
                or self.name_for_uid(self._uid_to_qq.get(raw)))

    # ── 本人 uid ──────────────────────────────────────
    def self_uid(self):
        if self._self_uid:
            return self._self_uid
        cfg = load_config()
        if cfg.get("self_uid"):
            self._self_uid = cfg["self_uid"]
            return self._self_uid
        rows = self._rows(
            self.nt_msg,
            "SELECT %s, count(DISTINCT %s) p FROM %s "
            "WHERE %s>0 AND %s!='' GROUP BY %s "
            "ORDER BY p DESC, count(*) DESC LIMIT 1" % (
                S.SENDER_UID, S.CHAT, S.T_C2C_MSG, S.TS, S.SENDER_UID, S.SENDER_UID))
        if rows and rows[0][0]:
            self._self_uid = str(rows[0][0])
            cfg["self_uid"] = self._self_uid
            try:
                save_config(cfg)
            except OSError:
                pass
        return self._self_uid
