#!/bin/zsh
# QQ NT macOS 密钥提取（普通身份运行，不要 sudo！）
# QQ 需以你的用户身份运行才能访问正确的数据目录
# 用法: zsh <本脚本路径>
# 产出: 本目录下 db_key.txt（敏感，勿外传；已在 .gitignore 中）
QQMAC="$(cd "$(dirname "$0")" && pwd)"
export QQMAC_DIR="$QQMAC"

: > "$QQMAC/hook.log"
pkill -x QQ 2>/dev/null && { echo "[*] 已退出 QQ"; sleep 2; } || true

lldb -b /Applications/QQ.app/Contents/MacOS/QQ \
  -o "command script import $QQMAC/getkey_helper.py" \
  -o "process launch -s" \
  -o "qqwait" 2>&1 | tee "$QQMAC/key_result.txt"

if grep -q "KEY_RAW=" "$QQMAC/key_result.txt" || [ -s "$QQMAC/db_key.txt" ]; then
  echo "[ok] 密钥已保存到 $QQMAC/db_key.txt"
  exit 0
fi
echo "[!] 未捕获密钥，见 $QQMAC/key_result.txt"
exit 1
