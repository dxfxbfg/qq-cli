# qqcli — macOS 本机 QQ 记录读取（Agent 技能 / CLI）

给 **AI Agent** 用的本机 QQ 信息获取能力：读取 macOS 版 QQ NT 的本地数据库
（`nt_qq_<hash>/nt_db/nt_msg.db`，SQLCipher），解密为明文 SQLite 后即可搜索、
统计、导出聊天记录。可作为 agent skill 直接调用，也能当普通 CLI 用。

对标 [2233admin/qqcli-rs](https://github.com/2233admin/qqcli-rs)（Windows），本仓库是 macOS/Python 适配。

## 定位与前提

**仅支持 macOS**（QQ NT 桌面版）。不做跨平台适配——抓密钥依赖 macOS 的 lldb 与
SIP 调试开关，Windows 走不通。

**不限制 QQ 版本**：

- 正文解析走 protobuf 保序扫描，不依赖版本相关的元素字段号
- 时间戳 / 发送者 / 群号等字段 ID 跨 NT 版本长期稳定
- SQLCipher 参数（page_size / kdf_iter / HMAC）QQ NT 长期不变，默认值即可用；
  若某版本改动，用 `kdf_hook.py` 抓取后写回 `config.json` 的 `cipher`，无需改代码

**前置条件**：

1. macOS（Apple Silicon / Intel 均可），已安装 QQ NT 桌面版并至少登录运行过一次
2. `brew install sqlcipher`
3. **提取密钥需临时关闭 macOS SIP 的调试保护（Debugging Restrictions）**——抓密钥靠 lldb
   对 QQ 进程下断点，SIP 开着会被拒绝。恢复模式（Apple Silicon 长按电源键；Intel 按 ⌘R）
   执行 `csrutil enable --without debug`（保留其余 SIP 保护），或 `csrutil disable`；
   提取完成可再开回。
4. Python 3.9+（零第三方依赖）

> 密钥解出、明文库导出之后，日常查询不再需要关闭 SIP 或跑 lldb。

## 安装与入口

- 入口：`~/.local/bin/qq`（软链 → `~/.agents/bin/qq` → `python -m qqcli`）
- 源码根目录即 Python 包根：`qqcli/` 为包，`tests/` 为回归测试
- 零第三方依赖（标准库 + `sqlcipher` CLI）

推荐用 pip 安装（由 `pyproject.toml` 生成 `qq` 命令，免手配 PYTHONPATH）：

```bash
pip install -e .        # 或 pipx install .
qq version
```

也可不安装，直接用启动器或模块方式运行：

```bash
QQ="$HOME/.local/bin/qq"                 # 软链 -> python -m qqcli
PYTHONPATH=. python3 -m qqcli sessions   # 在仓库根目录直接跑包
```

> 注意：`~/.local/bin` 常不在会话 PATH，脚本里请用 `~/.local/bin/qq`（或绝对路径）。

## 作为 Agent 技能使用

本仓库目录本身就是一个合法的 agent 技能目录——根目录的 `SKILL.md` 即技能说明
（命令速查、字段语义、SQL 片段、踩坑清单），全部用 `$HOME`/相对路径书写，无机器相关信息。

- 要让 agent 识别，把本目录（或其软链）放到技能目录下，例如
  `~/.workbuddy/skills/qq-cli`、`~/.claude/skills/qq-cli`；
- 只共享文档时，单独分发 `SKILL.md` 也行。

## 命令

```bash
qq sync                            # 重新解密导出明文库（QQ 运行中也可）
qq init                            # 发现账号目录、查看数据库状态
qq sessions [-n 20] [--kind group|c2c|all]         # 会话列表
qq history <目标> [-n N] [--offset N] [--since D] [--until D] [--msg-type T]
qq search <关键词> [-c 会话] [-n N] [--since D] [--until D]
qq contacts [--kind all|friend|group] [-q 关键词] [-n N]
qq groups / qq friends             # contacts 的快捷方式
qq members <群号> [-n N]            # 群成员
qq new [-n N] [--peek]             # 自上次检查以来的新消息
qq export <目标> [-o 文件] [-f markdown|txt|json|jsonl] [--since D] [--until D]
qq doctor                          # 环境诊断
qq version
```

全局 `--json` 输出机器可读结果。`<目标>` 支持 群号 / QQ 号 / uid（`u_` 开头）/ 名称模糊匹配。

### 退出码（agent 契约）

| 码 | 含义 |
|----|------|
| 0 | 成功 |
| 1 | 一般错误（参数 / 无法解析目标 / 日期格式） |
| 2 | 需要授权（解密） |
| 3 | 环境未就绪（明文库缺失，需先 `qq sync`） |

## 架构

```
qqcli/
  config.py     路径与配置（支持 QQCLI_HOME / QQCLI_PLAIN_DIR 覆盖）
  schema.py     nt_msg/group_info/profile_info 的字段 ID 常量（跨 NT 版本稳定）
  names.py      uid / QQ / 群号 -> 显示名 解析 + self_uid 推断
  segment.py    [40800] protobuf -> OneBot 风格分段（text/image/at/file/...）
  db.py         只读查询：会话/历史/搜索/联系人/成员/新消息
  formatting.py 人类可读输出（东亚宽度对齐、日期分隔、方向标注）
  decrypt.py    SQLCipher 解密（仅 init/sync）
  cli.py        argparse 子命令 + --json + 退出码
```

分层原则：`db` 只出数据类，`formatting` 只做排版，`segment` 只做解析，互不越界。

## 列语义（nt_msg.db 字段 ID，跨 NT 版本稳定）

| 列 | 含义 |
|----|------|
| `[40050]` | 时间戳（秒） |
| `[40020]` | 发送者 uid —— **判断本人靠它**（== self_uid） |
| `[40090]` | 发送者群名片（群消息约 40% 为空，需回退 `group_member3`） |
| `[40021]` | 群表里是群号；c2c 表里是对方 uid |
| `[40030]` | 群号（群表）/ 对方 QQ 号（c2c） |
| `[40009]` | 常量标志，**不是**"本人发送"，勿据此判方向 |
| `[40800]` | 正文 protobuf blob |

> 明文库存在解密残留的 `[40050]=0` 占位行；所有查询已内建过滤。

## 测试

```bash
./tests/run_tests.sh          # 单元 + 集成（真实库存在时自动跑）
```

- 单元：protobuf 分段、噪声/富文本处理、名称解析、排版对齐、查询层（临时夹具库）
- 集成：对真实明文库跑全量子命令，校验退出码/JSON 契约/无 1970 脏行

## 密钥与隐私

- **passphrase / db_key 只存本机，绝不入库**：`~/.qqmac/config.json`、`passphrase.txt`、
  `db_key.txt` 均已列入 `.gitignore`。首次使用需在本机跑 `extract_key.sh` 自行提取，
  本仓库不含任何密钥。
- 只读本地数据；导出文件含隐私，放用户指定位置
- key 失效或换 QQ 版本 → 重跑 `extract_key.sh`（需 lldb + 关闭 SIP 调试保护，见「前置条件」）

## 发布前检查

提交/发布前跑一次安全自查，确认没有把个人路径或密钥带上：

```bash
./scripts/check_publish_safe.sh
```

无输出即通过（脚本会列出所有疑似泄露项）。

## 密钥提取链（一次性）

- `find_key_func.py` / `precise_locate.py`：静态定位 `nt_sqlite3_key_v2`
- `getkey_helper.py` + lldb spawn：自动抓 key
- `kdf_hook.py`：断点 `PKCS5_PBKDF2_HMAC` 抓真正的 SQLCipher passphrase

## 许可证

[MIT](LICENSE)。设计参考 [2233admin/qqcli-rs](https://github.com/2233admin/qqcli-rs)（MIT）。
