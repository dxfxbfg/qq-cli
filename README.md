# qq-cli

简体中文 · [English](README.en.md)

读取 macOS 版 QQ NT 的本地聊天数据库（`nt_qq_<hash>/nt_db/nt_msg.db`，SQLCipher），
解密成明文 SQLite 后做搜索、统计和导出。既能当普通命令行工具用，也能装进 AI Agent 的
技能目录。Windows 上有功能更全的 [2233admin/qqcli-rs](https://github.com/2233admin/qqcli-rs)，
这里是 macOS 的 Python 实现。

本项目只处理使用者本人设备上、本人账号的数据。查询只读本地文件，不联网、不接管登录，不影响
QQ 正常使用。详见文末免责声明。

## 使用前提

只支持 macOS 和 QQ NT 桌面版，不做跨平台适配。抓密钥要靠 macOS 的 lldb 和 SIP 调试开关，
Windows 上走不通。

需要先装好 sqlcipher（`brew install sqlcipher`），QQ NT 至少登录运行过一次，Python 3.9 以上，
没有第三方依赖。

抓密钥的步骤要临时关掉 macOS SIP 的调试保护（Debugging Restrictions）。原理是对 QQ 进程下
lldb 断点，SIP 开着会被系统拒绝。恢复模式（Apple Silicon 长按电源键，Intel 按 ⌘R）里执行
`csrutil enable --without debug`，这样只放开调试、其余保护还在；也可以直接 `csrutil disable`。
抓完可以再开回来。密钥解出、明文库导出之后，日常查询既不需要关 SIP，也不用再跑 lldb。

不绑定 QQ 版本。正文按 protobuf 保序扫描，不依赖版本相关的元素字段号；时间戳、发送者、群号
这些字段 ID 跨 NT 版本一直没有变动。SQLCipher 参数（page_size / kdf_iter / HMAC）QQ NT
长期沿用同一套，默认值直接可用；如果哪个版本改了，用 `kdf_hook.py` 抓出来写进 `config.json`
的 `cipher` 字段，不用改代码。

## 和其他方案的区别

NapCat 这类机器人框架需要常驻一个专门的 QQ 账号，登录冲突和风控风险由那个账号承担。本项目
不接管登录，也不和 QQ 服务器通信。

查询全部发生在本地文件上。数据库以只读方式打开（`mode=ro`），代码里没有任何网络请求，唯一的
外部调用是本地 `sqlcipher` 命令。QQ 该怎么用还怎么用，也不用额外准备一个账号。

首次提取密钥是唯一会碰 QQ 进程的步骤：退出 QQ，用 lldb 重新拉起它抓 passphrase。做过这一次，
之后查询不需要 QQ 在场。

命令行、`--json`、固定退出码本来就是给程序调用的接口。`qq sync` 在 QQ 运行中实测 1 秒内完成，
导出先写临时文件，校验通过才原子替换，失败不会破坏已有的明文库。Agent 每次查询前 sync 一次，
读到的就是当下最新的记录，不用提前导出，也不用让 QQ 退出。

## 演示

下面的输出来自合成数据，示例项目组、阿澈、小满都是虚构的，不是真实聊天记录。

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

## 安装

推荐用 pip 装，`pyproject.toml` 会生成 `qq` 命令，不用自己配 PYTHONPATH：

```bash
pip install -e .        # 或 pipx install .
qq version
```

不想装也行，用启动器或直接跑包：

```bash
QQ="$HOME/.local/bin/qq"                 # 软链 -> python -m qqcli
PYTHONPATH=. python3 -m qqcli sessions   # 在仓库根目录直接跑
```

仓库根目录就是 Python 包根：`qqcli/` 是包，`tests/` 是回归测试。`~/.local/bin` 往往不在
会话的 PATH 里，脚本里写 `~/.local/bin/qq` 或绝对路径。

## 当 agent skill 用

这个仓库目录本身就是一个合法的技能目录，根目录的 `SKILL.md` 是技能说明，里面是命令速查、
字段语义、SQL 片段和踩坑清单，全部用 `$HOME` 和相对路径写，不含任何机器相关信息。

要让 Agent 认出来，把本目录（或它的软链）放进技能目录，例如 `~/.workbuddy/skills/qq-cli`
或 `~/.claude/skills/qq-cli`。只分享文档的话，单独发 `SKILL.md` 也可以。

## 命令

```bash
qq sync                            # 重新解密导出明文库（QQ 运行中也可，实测 1 秒内）
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

`--json` 是全局参数，加上就输出机器可读结果。`<目标>` 可以是群号、QQ 号、uid（`u_` 开头）
或名称的一部分。

退出码固定四个，方便 Agent 判断：

| 码 | 含义 |
|----|------|
| 0 | 成功 |
| 1 | 一般错误（参数不对、目标解析不了、日期格式错） |
| 2 | 需要授权（解密） |
| 3 | 环境未就绪（明文库缺失，先跑 `qq sync`） |

## 代码结构

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

分层比较严：`db` 只出数据类，`formatting` 只管排版，`segment` 只做解析，互相不越界。

## 字段语义

nt_msg.db 用的是数字列名，下面是几个关键字段。这些 ID 跨 NT 版本稳定。

| 列 | 含义 |
|----|------|
| `[40050]` | 时间戳（秒） |
| `[40020]` | 发送者 uid，判断是不是本人就看它（和 self_uid 比较） |
| `[40090]` | 发送者群名片，群消息里约 40% 为空，需回退 `group_member3` |
| `[40021]` | 群表里是群号，c2c 表里是对方 uid |
| `[40030]` | 群号（群表）或对方 QQ 号（c2c 表） |
| `[40009]` | 常量标志，与是否本人发送无关，不要拿它判方向 |
| `[40800]` | 正文 protobuf blob |

明文库里有解密残留的 `[40050]=0` 占位行，查询已经内建过滤。

## 测试

```bash
./tests/run_tests.sh          # 单元 + 集成（真实库存在时自动跑）
```

单元部分覆盖 protobuf 分段、噪声与富文本处理、名称解析、排版对齐、查询层，用临时建的夹具库；
集成部分对真实明文库跑一遍全部子命令，校验退出码、JSON 契约，以及输出里没有 1970 的脏行。

## 密钥与隐私

passphrase 和 db_key 只留在本机，绝不入库。`~/.qqmac/config.json`、`passphrase.txt`、
`db_key.txt` 都在 `.gitignore` 里。首次使用要在本机跑 `extract_key.sh` 自己提取，仓库里不含
任何密钥。

程序只读本地数据，导出的文件含隐私，放在自己指定的位置。key 失效或者换了 QQ 版本，重跑
`extract_key.sh`，同样需要 lldb 和关闭 SIP 调试保护。

## 发布前自查

提交或发布前跑一次，确认没把个人路径和密钥带进去：

```bash
./scripts/check_publish_safe.sh
```

没有输出就是通过，有疑似项脚本会逐条列出来。

## 密钥提取

三个脚本配合使用，只需跑一次：

- `find_key_func.py` / `precise_locate.py`：静态定位 `nt_sqlite3_key_v2`
- `getkey_helper.py` + lldb spawn：自动抓 key
- `kdf_hook.py`：断点 `PKCS5_PBKDF2_HMAC` 抓真正的 SQLCipher passphrase

## 免责声明

本工具只用于读取使用者本人设备上、本人账号的 QQ 聊天记录，不得用于获取、监控或分析他人的数据。

本项目是非官方项目，与腾讯公司没有关联，也未获其授权或认可，QQ 及相关商标归腾讯所有。

使用本工具须遵守所在地的法律法规和 QQ 用户协议。导出的聊天记录包含他人隐私，受《个人信息
保护法》等法规约束，转发或公开前请自行确认合法性。因使用本工具产生的合规与法律责任由使用者承担。

提取密钥需要临时关闭 macOS 的 SIP 调试保护，这段时间系统防护会下降，请在可信环境中操作，
用完及时恢复。全部处理都在本地完成，没有网络上传也没有遥测，导出文件由使用者自行保管。

软件依 MIT 协议按现状提供，不附带任何明示或默示担保。

## 许可证

[MIT](LICENSE)。设计参考 [2233admin/qqcli-rs](https://github.com/2233admin/qqcli-rs)（MIT）。
