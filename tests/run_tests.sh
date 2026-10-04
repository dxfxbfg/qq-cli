#!/bin/zsh
# 全套回归测试：单元 + 集成（真实库存在时）
set -e
DIR="$(cd "$(dirname "$0")/.." && pwd)"
PY="${QQCLI_PY:-python3}"
export PYTHONPATH="$DIR:$DIR/tests"
exec "$PY" -m unittest discover -s "$DIR/tests" -t "$DIR/tests" "$@"
