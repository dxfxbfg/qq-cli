"""nt_msg.db / group_info.db / profile_info.db 列号常量。

数字列名是 QQ NT 的字段 ID，跨 NT 版本长期稳定（本表在 macOS 版上实测校准；
与 Windows 版存在平台差异，读取时以实际库为准）。

要点：
  * [40009] 在实测库中是恒为常量的标志位（c2c 全 0 / group 全 1），
    **不能**用来判断是否本人发送；本人判定用 [40020] == self_uid。
  * 群消息 [40021] 存的是群号，不是发送者。
  * 群消息发送者昵称优先 [40090]，常为空，需回退 group_member3。
"""

# ── 通用 ──────────────────────────────────────────────
TS = "[40050]"          # Unix 时间戳（秒）
MSG_ID = "[40001]"      # 消息 ID
CONTENT = "[40800]"     # 正文 protobuf blob
FLAG = "[40009]"        # 常量标志（勿用于方向判定）

# ── 消息表（group_msg_table / c2c_msg_table 通用）──────
SENDER_UID = "[40020]"  # 发送者 uid（u_ 前缀）
SENDER_CARD = "[40090]" # 发送者群名片/昵称（群消息常有 ~40% 为空）
PEER = "[40021]"        # 群表: 群号;  c2c 表: 对方 uid
CHAT = "[40030]"        # 群表: 群号;  c2c 表: 对方 QQ 号

# ── group_info.db ────────────────────────────────────
GROUP_ID = "[60001]"
GROUP_NAME = "[60007]"
GROUP_MEMBER_COUNT = "[60009]"
MEMBER_UID = "[1000]"
MEMBER_CARD = "[64003]"
MEMBER_NICK = "[20002]"
MEMBER_QQ = "[1002]"

# ── profile_info.db ──────────────────────────────────
PROFILE_QQ = "[1002]"
PROFILE_NICK = "[20002]"
BUDDY_UID = "[1000]"
BUDDY_QQ = "[1002]"

# ── nt_msg.db uid 映射 ───────────────────────────────
UIDMAP_UID = "[48902]"
UIDMAP_QQ = "[1002]"
UIDMAP_NAME = "[48912]"

# 表名
T_GROUP_MSG = "group_msg_table"
T_C2C_MSG = "c2c_msg_table"
T_UIDMAP = "nt_uid_mapping_table"
T_GROUP_LIST = "group_list"
T_GROUP_MEMBER = "group_member3"
T_PROFILE = "profile_info_v6"
T_BUDDY = "buddy_list"
