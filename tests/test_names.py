"""names 单元测试：uid/QQ/群号 解析 与 self_uid 推断。"""

import unittest

from _boot import fixtures

from qqcli.names import NameResolver


class TestResolver(unittest.TestCase):
    def setUp(self):
        self.r = NameResolver()

    def test_group_card_preferred(self):
        self.assertEqual(self.r.name_for_uid("u_A"), "小明")   # 群名片优先

    def test_nick_fallback(self):
        self.assertEqual(self.r.name_for_uid("u_B"), "小红")   # 无名片取昵称

    def test_qq_nick(self):
        self.assertEqual(self.r.name_for_qq(fixtures.PEER_QQ), "阿蓝")

    def test_group_name(self):
        self.assertEqual(self.r.group_name(fixtures.GROUP), "测试群")

    def test_member_count_from_members(self):
        self.assertEqual(self.r.member_count(fixtures.GROUP), 3)

    def test_resolve_mixed(self):
        self.assertEqual(self.r.resolve("u_A"), "小明")
        self.assertEqual(self.r.resolve(str(fixtures.PEER_QQ)), "阿蓝")
        self.assertEqual(self.r.resolve(str(fixtures.GROUP)), "测试群")

    def test_self_uid_inferred(self):
        self.assertEqual(self.r.self_uid(), fixtures.SELF)

    def test_missing_paths_do_not_crash(self):
        r = NameResolver(nt_msg="/nonexistent.db", group_info="/nonexistent.db",
                         profile_info="/nonexistent.db", self_uid=None)
        self.assertIsNone(r.name_for_uid("u_A"))
        self.assertIsNone(r.group_name("1001"))
        r.self_uid()   # 不抛异常即可（可能回落到 config 缓存）


if __name__ == "__main__":
    unittest.main()
