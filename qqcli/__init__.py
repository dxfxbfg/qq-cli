"""qqcli — 本机 QQ NT 聊天记录查询 CLI（macOS）。

分层：
    config   路径与配置（明文库、self_uid）
    schema   nt_msg.db / group_info.db / profile_info.db 的列号常量
    names    uid / QQ / 群号 -> 显示名 解析
    segment  [40800] protobuf 正文 -> OneBot 风格分段
    db       只读查询：会话 / 历史 / 搜索 / 联系人 / 成员 / 未读
    formatting  人类可读输出与 JSON 序列化
    decrypt  仅用于 qq init / qq sync 的 SQLCipher 解密
    cli      argparse 子命令与退出码
"""

__version__ = "2.0.0"
