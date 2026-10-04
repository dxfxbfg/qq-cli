"""decrypt 单元测试：SQLCipher 参数生成、版本无关的覆盖机制、原子替换。"""

import os
import tempfile
import unittest

from _boot import fixtures  # noqa: F401  (确保包路径/环境就绪)

from qqcli import decrypt
from qqcli.config import find_sqlcipher
from qqcli.errors import QqcliError


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


@unittest.skipUnless(find_sqlcipher(), "sqlcipher 未安装，跳过解密相关测试")
class TestAtomicReplace(unittest.TestCase):
    """解密失败时必须保住旧明文库——Agent 会反复 sync，不能一次失败就毁库。"""

    def _fixture(self, d):
        src = os.path.join(d, "fake_encrypted.db")
        with open(src, "wb") as f:
            f.write(b"\x00" * 1024)          # 明文头
            f.write(os.urandom(2048))        # 垃圾密文
        dst = os.path.join(d, "plain.db")
        with open(dst, "wb") as f:
            f.write(b"OLD-PLAIN-DB")
        return src, dst

    def test_failure_keeps_existing_plain_db(self):
        with tempfile.TemporaryDirectory() as d:
            src, dst = self._fixture(d)
            with self.assertRaises(QqcliError):
                decrypt.decrypt_db(src, dst, "definitely-wrong-passphrase")
            with open(dst, "rb") as f:
                self.assertEqual(f.read(), b"OLD-PLAIN-DB")

    def test_failure_leaves_no_temp_files(self):
        with tempfile.TemporaryDirectory() as d:
            src, dst = self._fixture(d)
            with self.assertRaises(QqcliError):
                decrypt.decrypt_db(src, dst, "definitely-wrong-passphrase")
            leftovers = [n for n in os.listdir(d) if n.endswith((".tmp", ".new"))]
            self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
