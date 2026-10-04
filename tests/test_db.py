"""db 单元测试：会话 / 历史 / 搜索 / 联系人 / 成员（用临时夹具库）。"""

import unittest

from _boot import fixtures

from qqcli import db
from qqcli.names import NameResolver


class TestQueries(unittest.TestCase):
    def setUp(self):
        self.r = NameResolver()

    def test_sessions_group_count_excludes_ts0(self):
        ss = db.sessions(self.r, limit=50)
        g = [s for s in ss if s.chat_id == str(fixtures.GROUP)]
        self.assertEqual(len(g), 1)
        self.assertEqual(g[0].kind, "group")
        self.assertEqual(g[0].count, 5)          # 6 行 - 1 行 ts=0
        self.assertEqual(g[0].name, "测试群")

    def test_sessions_kind_filter(self):
        ss = db.sessions(self.r, kind="c2c")
        self.assertTrue(all(s.kind == "c2c" for s in ss))

    def test_history_no_epoch_rows_and_mine(self):
        msgs, name, kind = db.history(self.r, str(fixtures.GROUP))
        self.assertTrue(all(m.time_str[:4] != "1970" for m in msgs))
        self.assertEqual(len(msgs), 5)
        self.assertEqual(kind, "group")
        self.assertTrue(msgs[0].is_mine)
        self.assertEqual(msgs[0].sender_name, "我")
        # 小明来自群名片，小红来自昵称
        self.assertIn("小明", [m.sender_name for m in msgs])
        self.assertIn("小红", [m.sender_name for m in msgs])

    def test_history_limit_returns_recent_ascending(self):
        msgs, _, _ = db.history(self.r, str(fixtures.GROUP), limit=2)
        self.assertEqual(len(msgs), 2)
        self.assertLess(msgs[0].ts, msgs[1].ts)                 # 正序
        self.assertEqual(msgs[-1].ts, fixtures.DAY + 401)        # 取到最近一条

    def test_history_msg_type_filter(self):
        msgs, _, _ = db.history(self.r, str(fixtures.GROUP), msg_type="文本")
        self.assertTrue(all(m.msg_type == "文本" for m in msgs))

    def test_history_by_name(self):
        msgs, name, _ = db.history(self.r, "测试群")
        self.assertEqual(name, "测试群")
        self.assertTrue(msgs)

    def test_search_hits_and_scope(self):
        hits = db.search(self.r, "考试")
        self.assertEqual(len(hits), 1)
        self.assertIn("考试", hits[0].content)
        self.assertEqual(hits[0].chat_name, "测试群")

    def test_search_chat_scope(self):
        self.assertEqual(db.search(self.r, "考试", chat=str(fixtures.GROUP)), db.search(self.r, "考试"))
        self.assertEqual(db.search(self.r, "考试", chat="2002"), [])

    def test_contacts(self):
        cs = db.contacts(self.r, kind="group")
        self.assertTrue(any(c.name == "测试群" for c in cs))
        fr = db.contacts(self.r, kind="friend")
        self.assertTrue(any(c.name == "阿蓝" for c in fr))

    def test_members(self):
        ms, gid = db.members(self.r, str(fixtures.GROUP))
        self.assertEqual(gid, str(fixtures.GROUP))
        names = [m.name for m in ms]
        self.assertIn("小明", names)
        self.assertIn("小红", names)

    def test_unknown_target_raises(self):
        from qqcli.errors import QqcliError
        with self.assertRaises(QqcliError):
            db.history(self.r, "根本不存在xyz")


if __name__ == "__main__":
    unittest.main()
