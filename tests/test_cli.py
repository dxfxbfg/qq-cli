"""CLI 端到端测试：退出码、JSON 契约、错误路径（临时夹具库）。"""

import contextlib
import io
import json
import os
import tempfile
import unittest

from _boot import fixtures

from qqcli import cli, config


def run(argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        code = cli.main(argv)
    return code, buf.getvalue()


class TestCliHappyPath(unittest.TestCase):
    def test_version(self):
        code, out = run(["version"])
        self.assertEqual(code, 0)
        self.assertIn("qqcli", out)

    def test_doctor(self):
        code, out = run(["doctor"])
        self.assertEqual(code, 0)
        self.assertIn("nt_msg.db", out)

    def test_sessions_text(self):
        code, out = run(["sessions", "-n", "10"])
        self.assertEqual(code, 0)
        self.assertIn("测试群", out)

    def test_sessions_json_schema(self):
        code, out = run(["--json", "sessions", "-n", "10"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertIsInstance(data, list)
        self.assertTrue(all({"id", "name", "type", "count"} <= set(d) for d in data))

    def test_history(self):
        code, out = run(["history", str(fixtures.GROUP)])
        self.assertEqual(code, 0)
        self.assertIn("我:", out)
        self.assertNotIn("1970", out)

    def test_history_json_segments(self):
        code, out = run(["--json", "history", str(fixtures.GROUP), "-n", "1", "--segments"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertIn("messages", data)
        self.assertIn("segments", data["messages"][0])

    def test_search(self):
        code, out = run(["search", "考试"])
        self.assertEqual(code, 0)
        self.assertIn("考试", out)

    def test_contacts_and_members(self):
        self.assertEqual(run(["contacts", "--kind", "group"])[0], 0)
        self.assertEqual(run(["groups"])[0], 0)
        self.assertEqual(run(["friends"])[0], 0)
        code, out = run(["members", str(fixtures.GROUP)])
        self.assertEqual(code, 0)
        self.assertIn("小明", out)

    def test_export_jsonl(self):
        code, out = run(["export", str(fixtures.GROUP), "-f", "jsonl"])
        self.assertEqual(code, 0)
        for line in out.strip().splitlines():
            json.loads(line)

    def test_new_peek(self):
        code, out = run(["new", "--peek", "-n", "5"])
        self.assertEqual(code, 0)


class TestCliErrors(unittest.TestCase):
    def test_unknown_target_exit_1(self):
        code, out = run(["history", "根本不存在xyz"])
        self.assertEqual(code, 1)
        self.assertIn("无法解析", out)

    def test_bad_date_exit_1(self):
        code, _ = run(["history", str(fixtures.GROUP), "--since", "2026/01/01"])
        self.assertEqual(code, 1)

    def test_usage_error_exit_1(self):
        code, _ = run(["history"])
        self.assertEqual(code, 1)

    def test_missing_db_exit_3(self):
        old = config.PLAIN
        config.PLAIN = tempfile.mkdtemp(prefix="qqcli-empty-")
        try:
            code, out = run(["sessions"])
            self.assertEqual(code, 3)
        finally:
            config.PLAIN = old


if __name__ == "__main__":
    unittest.main()
