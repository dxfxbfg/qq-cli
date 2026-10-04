---
name: qq-cli
description: 查询本机 QQ 聊天记录（macOS，解密库就绪后）。当用户问起 QQ 聊天内容、某人在 QQ 里说过什么、聊天记录搜索/统计/导出时使用。
user_invocable: true
agent_created: true
---

# QQ 聊天记录查询（macOS）

读取本机 QQ NT（macOS 桌面版）的本地数据库，解密为明文 SQLite 后可查询、统计、导出。
实现为 Python 包 `qqcli`（仓库根目录下的 `qqcli/`），入口 `qq`。

**仅 macOS；不限 QQ 版本**：正文按 protobuf 保序扫描，不依赖版本相关的元素字段号；
时间戳 / 发送者 / 群号等字段 ID 跨 NT 版本长期稳定。

## 前置（一次性）

1. `brew install sqlcipher`
2. 抓密钥：跑仓库的 `extract_key.sh`。需用 lldb 对 QQ 进程下断点，因此必须**临时关闭
   macOS SIP 的调试保护**——恢复模式执行 `csrutil enable --without debug`（保留其余保护）
   或 `csrutil disable`，抓完可再开回。
3. 导出明文库：`qq sync`。

> 密钥解出、明文库导出之后，日常查询不再需要关闭 SIP 或跑 lldb。
> 若某 QQ 版本改了 SQLCipher 参数，用 `kdf_hook.py` 抓取后写回 `config.json` 的 `cipher`。

## 调用方式

`qq` 可能不在 PATH（`~/.local/bin` 常未加入），一律用绝对路径：

```bash
QQ="$HOME/.local/bin/qq"      # 入口：python -m qqcli
$QQ sessions
```

未安装入口时可直接跑包（在仓库根目录）：

```bash
PYTHONPATH=. python3 -m qqcli sessions
```

数据要最新：先 `$QQ sync`（QQ 运行中也行，重新解密覆盖明文缓存，实测 1 秒内，可反复调用）。

## 命令

```bash
$QQ sessions [-n 20] [--kind group|c2c|all]      # 会话列表（活跃降序）
$QQ history <目标> [-n N] [--offset N] [--since YYYY-MM-DD] [--until ...] [--msg-type 文本|图片|...]
$QQ search "关键词" [-c 会话] [-n N] [--since] [--until]
$QQ contacts [--kind all|friend|group] [-q 关键词] [-n N]
$QQ groups / $QQ friends                          # contacts 快捷方式
$QQ members <群号> [-n N]                          # 群成员
$QQ new [-n N] [--peek]                           # 自上次检查以来的新消息
$QQ export <目标> [-o 文件] [-f markdown|txt|json|jsonl] [--since] [--until]
$QQ doctor                                        # 环境诊断
$QQ version
```

- 全局加 `--json` 得机器可读输出（会话/消息/联系人/成员均为稳定字段）
- `<目标>`：群号 / QQ号 / uid（`u_` 开头）/ 名称模糊
- `history` 不带 `-n`：全部（时间正序）；带 `-n N`：**最近 N 条**（仍正序）

退出码：`0` 成功，`1` 一般错误/无法解析目标，`2` 需授权，`3` 环境未就绪（需 `qq sync`）。

## 数据位置与结构

明文库目录：`$HOME/.qqmac/plain/`（`nt_msg.db` / `group_info.db` / `profile_info.db`）

列语义（QQ NT 字段 ID，跨 NT 版本稳定）：

| 列 | 含义 |
|----|------|
| `[40050]` | 时间戳（秒） |
| `[40020]` | 发送者 uid —— **判断本人靠它**（== self_uid） |
| `[40090]` | 发送者群名片（常空，回退 `group_member3`） |
| `[40021]` | 群表里是群号；c2c 表里是对方 uid |
| `[40030]` | 群号（群表）/ 对方 QQ 号（c2c） |
| `[40009]` | 常量标志，**不是**"本人发送"，勿据此判方向 |
| `[40800]` | 正文 protobuf blob |
| 群名 | `group_list` `[60001]`=群号 `[60007]`=群名 |
| 群成员 | `group_member3` `[1000]`=uid `[64003]`=群名片 `[20002]`=昵称 `[1002]`=QQ `[60001]`=群号 |
| 好友 | `profile_info_v6` `[1002]`=QQ `[20002]`=昵称 |

self_uid 由 c2c 中出现最多不同会话的 uid 推断，缓存在 `$HOME/.qqmac/config.json`。
正文解析（`qqcli/segment.py`）：protobuf 保序扫描 -> OneBot 风格分段
（text/image/record/file/face/at/reply），自动去重、过滤图片/CDN 噪声、
解析 `<gtip>/<qq>/<nor>` 富文本、剥离 `gchatpic_new` 等资源路径。

## 细粒度查询（直连 sqlite3）

复杂需求（时间段统计、发言排行）直接写 SQL。两条硬规则：

- **必须带 `[40050] > 0`**：明文库有解密残留的 ts=0 占位行，否则命中并显示成 1970 空行
- `ATTACH` 不展开 `~`：用 shell 展开后的绝对路径（下面的 `"$HOME/..."`）

```bash
sqlite3 "$HOME/.qqmac/plain/nt_msg.db" "
  SELECT datetime([40050],'unixepoch','localtime') t, [40020], [40090], hex([40800])
  FROM group_msg_table WHERE [40030]='群号' AND [40050]>0
  ORDER BY [40050] DESC LIMIT 20;"
```

```sql
-- 发言排行（排除本人 uid）
SELECT [40020], count(*) c FROM group_msg_table
WHERE [40030]='群号' AND [40050]>0 AND [40020]!='本人uid'
GROUP BY [40020] ORDER BY c DESC LIMIT 20;

-- 跨库 JOIN 群名
ATTACH '$HOME/.qqmac/plain/group_info.db' AS g;
SELECT g.group_list.[60007], count(*) FROM group_msg_table m
JOIN g.group_list ON m.[40030]=g.group_list.[60001]
WHERE m.[40050]>0 GROUP BY 1 ORDER BY 2 DESC;
```

提取单条正文（在仓库根目录执行）：

```bash
python3 -c "import qqcli.segment as S; print(S.render_inline(bytes.fromhex('...')))"
```

## 坑

- `~/.local/bin` 常不在 PATH：用 `"$HOME/.local/bin/qq"` 或绝对路径
- 明文库 ts=0 占位行：自定义 SQL 必带 `[40050] > 0`
- `[40009]` 恒为常量，**不能**判本人；本人判定用 `[40020] == self_uid`
- 群消息 `[40090]` 常为空：回退查 `group_member3`（CLI 已自动处理）
- `[40021]` 在群表里是群号，别当发送者
- 正文 protobuf 常存两份、夹带图片 ID / CDN 链接：CLI 已去重并过滤
- 少量群不在 `group_list`（新群/已退群），显示 `?`

## 维护与隐私

- **使用边界**：仅用于读取用户**本人**设备上**本人**账号的数据，不得用于他人数据；详见仓库
  README 的「免责声明」（非官方、合规责任在用户、关闭 SIP 有安全代价）。
- 回归测试（仓库根目录）：`./tests/run_tests.sh`（单元 + 对真实库的集成）
- 隐私：查询结果仅向用户本人展示；导出文件含隐私，放用户指定位置
- 密钥：`$HOME/.qqmac/config.json` 与仓库 `passphrase.txt` / `db_key.txt`
  （均 0600，已在 `.gitignore` 中，勿外传、勿打印）
- 发布前跑 `./scripts/check_publish_safe.sh`，确认没有个人路径或密钥入库
- key 失效或换 QQ 版本：重跑 `extract_key.sh`（需 lldb + 关闭 SIP 调试保护，见「前置」）
