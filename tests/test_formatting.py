"""formatting 单元测试：东亚宽度对齐与截断。"""

import unittest

from _boot import fixtures  # noqa: F401

from qqcli import db
from qqcli import formatting as F


class TestWidth(unittest.TestCase):
    def test_width_cjk(self):
        self.assertEqual(F.width("abc"), 3)
        self.assertEqual(F.width("中文"), 4)
        self.assertEqual(F.width("中a"), 3)

    def test_truncate_by_width(self):
        s = "一二三四五六"
        out = F.truncate(s, 6)
        self.assertLessEqual(F.width(out), 6)
        self.assertTrue(out.endswith("…"))

    def test_pad(self):
        self.assertEqual(F.pad("中", 4), "中  ")
        self.assertEqual(F.pad("中", 4, "right"), "  中")


class TestTable(unittest.TestCase):
    def test_columns_align_exact(self):
        txt = F.table(["名", "值"], [["a", "1"], ["bb", "2"]])
        self.assertEqual(txt.splitlines(), ["名  值", "a   1", "bb  2"])

    def test_cjk_and_ascii_align_exact(self):
        txt = F.table(["名称", "值"], [["中文", "1"], ["ab", "22"]])
        self.assertEqual(txt.splitlines(), ["名称  值", "中文  1", "ab    22"])


class TestRenders(unittest.TestCase):
    def test_render_sessions_empty(self):
        self.assertEqual(F.render_sessions([]), "(无会话)")

    def test_render_messages_date_separator(self):
        msgs = [
            db.Message("1", 1780000000, "2026-05-29 10:00:00", "u_A", "小明", False, "hi"),
            db.Message("2", 1780000100, "2026-05-30 10:00:00", "u_ME", "我", True, "yo"),
        ]
        out = F.render_messages(msgs)
        self.assertIn("2026-05-29", out)
        self.assertIn("2026-05-30", out)
        self.assertIn("我: yo", out)

    def test_render_contacts_grouped(self):
        cs = [db.Contact("1", "群A", "group", 3), db.Contact("2", "好友B", "friend")]
        out = F.render_contacts(cs)
        self.assertIn("群聊", out)
        self.assertIn("好友", out)


if __name__ == "__main__":
    unittest.main()
