"""集成回归测试：对真实明文库跑全量子命令。

真实库缺失时自动跳过。子进程运行时清空 QQCLI_* 环境变量，确保打到真实
~/.qqmac，而不是夹具库。
"""

import json
import os
import subprocess
import sys
import unittest

from _boot import REAL_DB, ROOT

PY = sys.executable


def real_env():
    env = dict(os.environ)
    for k in ("QQCLI_HOME", "QQCLI_PLAIN_DIR"):
        env.pop(k, None)
    env["PYTHONPATH"] = ROOT
    return env


def run_real(*args):
    p = subprocess.run([PY, "-m", "qqcli", *args], capture_output=True,
                       text=True, env=real_env(), timeout=120)
    return p.returncode, p.stdout, p.stderr


@unittest.skipUnless(os.path.exists(REAL_DB), "真实 QQ 明文库不存在，跳过集成测试")
class TestIntegration(unittest.TestCase):
    group_id = None

    @classmethod
    def setUpClass(cls):
        code, out, _ = run_real("--json", "sessions", "-n", "5")
        if code == 0:
            data = json.loads(out)
            groups = [d for d in data if d["type"] == "group"]
            cls.group_id = groups[0]["id"] if groups else (data[0]["id"] if data else None)

    def _need_group(self):
        if not self.group_id:
            self.skipTest("无可用群会话")

    def test_version_doctor(self):
        self.assertEqual(run_real("version")[0], 0)
        code, out, err = run_real("doctor")
        self.assertEqual(code, 0, err)

    def test_sessions_table_has_header(self):
        code, out, err = run_real("sessions", "-n", "5")
        self.assertEqual(code, 0, err)
        self.assertIn("类型", out)
        self.assertIn("会话 ID", out)

    def test_sessions_json_all_ts_positive(self):
        code, out, err = run_real("--json", "sessions", "-n", "10")
        self.assertEqual(code, 0, err)
        for d in json.loads(out):
            self.assertGreater(d["last_ts"], 0)
            self.assertIn(d["type"], ("group", "c2c"))

    def test_history_no_epoch(self):
        self._need_group()
        code, out, err = run_real("history", self.group_id, "-n", "10")
        self.assertEqual(code, 0, err)
        self.assertNotIn("1970-", out)

    def test_history_json_counts(self):
        self._need_group()
        code, out, err = run_real("--json", "history", self.group_id, "-n", "5")
        self.assertEqual(code, 0, err)
        data = json.loads(out)
        self.assertLessEqual(len(data["messages"]), 5)
        ts = [m["ts"] for m in data["messages"]]
        self.assertEqual(ts, sorted(ts))          # 时间正序

    def test_export_jsonl_parses(self):
        self._need_group()
        code, out, err = run_real("export", self.group_id, "-n", "5", "-f", "jsonl")
        self.assertEqual(code, 0, err)
        for line in out.strip().splitlines():
            json.loads(line)

    def test_search_common_word(self):
        code, out, err = run_real("search", "我", "-n", "5")
        self.assertEqual(code, 0, err)

    def test_contacts(self):
        self.assertEqual(run_real("contacts", "--kind", "group", "-n", "5")[0], 0)
        self.assertEqual(run_real("friends", "-n", "5")[0], 0)

    def test_bad_target_exit_code(self):
        code, _, _ = run_real("history", "根本不存在xyz")
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
