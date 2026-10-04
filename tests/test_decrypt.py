"""decrypt 单元测试：SQLCipher 参数生成与版本无关的覆盖机制。"""

import unittest

from _boot import fixtures  # noqa: F401  (确保包路径/环境就绪)

from qqcli import decrypt


class TestBuildPragmas(unittest.TestCase):
    def test_defaults_match_qq_nt(self):
        p = decrypt.build_pragmas()
        self.assertIn("cipher_page_size=4096", p)
        self.assertIn("kdf_iter=4000", p)
        self.assertIn("cipher_hmac_algorithm=HMAC_SHA1;", p)
        self.assertIn("cipher_default_kdf_algorithm=PBKDF2_HMAC_SHA512;", p)

    def test_override_for_other_versions(self):
        p = decrypt.build_pragmas({"page_size": 1024, "kdf_iter": 64000,
                                   "hmac": "HMAC_SHA512"})
        self.assertIn("cipher_page_size=1024", p)
        self.assertIn("kdf_iter=64000", p)
        self.assertIn("cipher_hmac_algorithm=HMAC_SHA512;", p)

    def test_unknown_keys_ignored(self):
        p = decrypt.build_pragmas({"bogus": 1})
        self.assertIn("cipher_page_size=4096", p)

    def test_blank_override_keeps_default(self):
        p = decrypt.build_pragmas({"kdf_iter": None, "page_size": ""})
        self.assertIn("kdf_iter=4000", p)
        self.assertIn("cipher_page_size=4096", p)

    def test_pragma_is_well_formed(self):
        p = decrypt.build_pragmas()
        self.assertTrue(p.rstrip().endswith(";"))


if __name__ == "__main__":
    unittest.main()
