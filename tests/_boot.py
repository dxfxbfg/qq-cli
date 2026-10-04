"""测试引导：注入临时库环境，必须在 import qqcli 之前执行。"""

import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

_TMP = tempfile.mkdtemp(prefix="qqcli-test-")
os.environ["QQCLI_HOME"] = _TMP
os.environ["QQCLI_PLAIN_DIR"] = os.path.join(_TMP, "plain")

import fixtures  # noqa: E402

fixtures.build_plain(os.environ["QQCLI_PLAIN_DIR"])
PLAIN_DIR = os.environ["QQCLI_PLAIN_DIR"]
TMP_HOME = _TMP

# 真实库路径（供集成测试判断是否跳过）
REAL_DB = os.path.join(os.path.expanduser("~"), ".qqmac", "plain", "nt_msg.db")
