#!/usr/bin/env bash
# 发布前安全自查：确认仓库里没有个人路径 / 密钥 / 聊天数据库。
# 用法：./scripts/check_publish_safe.sh
# 退出码：0 = 无阻塞项（可能有 warn）；1 = 存在必须处理的泄露风险。
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1
fail=0

say() { printf '%s\n' "$*"; }
blocker() { say "[blocker] $*"; fail=1; }
warn() { say "[warn]    $*"; }

say "== 发布前安全自查：$ROOT =="

# 1) 密钥类文件：不得被 git 跟踪
SECRETS="passphrase.txt db_key.txt config.json"
for f in $SECRETS; do
  [ -e "$f" ] || continue
  if [ -d .git ]; then
    if git ls-files --error-unmatch "$f" >/dev/null 2>&1; then
      blocker "$f 已被 git 跟踪，必须 git rm --cached 并从历史中清除"
    elif ! git check-ignore -q "$f"; then
      blocker "$f 存在且未被 .gitignore 覆盖，有被提交风险"
    fi
  else
    warn "$f 存在于工作区（尚未初始化 git，提交前务必确认 .gitignore 生效）"
  fi
done

# 2) 个人绝对路径（用户名/家目录）
hits=$(grep -rInE '/(Users|home)/[A-Za-z0-9._-]+' \
        --exclude-dir=.git --exclude-dir=__pycache__ . 2>/dev/null \
        | grep -v 'scripts/check_publish_safe.sh' || true)
if [ -n "$hits" ]; then
  blocker "检测到个人绝对路径："
  say "$hits"
fi

# 3) 聊天数据库 / 明文库产物
hits=$(find . -type f \( -name '*.db' -o -name '*.sqlite' -o -name '*.sqlite3' \) \
        -not -path './.git/*' 2>/dev/null || true)
if [ -n "$hits" ]; then
  blocker "检测到数据库文件："
  say "$hits"
fi

# 4) 密钥提取过程的残留产物
hits=$(find . -maxdepth 2 -type f \
        \( -name 'key_result*' -o -name 'hook.log' -o -name 'va_cache.txt' \
           -o -name 'kdf_calls.txt' -o -name 'kdf_attach.txt' \) \
        -not -path './.git/*' 2>/dev/null || true)
if [ -n "$hits" ]; then
  blocker "检测到密钥提取残留："
  say "$hits"
fi

# 5) 疑似真实账号标识（人工复核；测试夹具为合成值，已排除 tests/）
hits=$(grep -rInE 'nt_qq_[0-9a-f]{8,}|u_[A-Za-z0-9_-]{18,}' \
        --exclude-dir=.git --exclude-dir=__pycache__ --exclude-dir=tests . 2>/dev/null || true)
if [ -n "$hits" ]; then
  warn "疑似真实账号标识，请人工确认："
  say "$hits"
fi

if [ "$fail" -eq 0 ]; then
  say "== 通过：未发现阻塞项 =="
else
  say "== 未通过：请先处理上面的 [blocker] =="
fi
exit "$fail"
