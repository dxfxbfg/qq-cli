"""segment 单元测试：protobuf 扫描 / 富文本 / 噪声过滤 / 媒体折叠。"""

import unittest

from _boot import fixtures  # noqa: F401  (注入环境)

from qqcli import segment as SG


class TestParseBlob(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(SG.parse_blob(b""), [])
        self.assertEqual(SG.parse_blob(None), [])

    def test_plain_text_roundtrip(self):
        blob = fixtures.blob_text("你好世界")
        segs = SG.parse_blob(blob)
        self.assertEqual([s.kind for s in segs], ["text"])
        self.assertEqual(SG.render_inline(blob), "你好世界")

    def test_uid_fragment_dropped(self):
        blob = fixtures.blob_text("hi", uid="u_ABCDEFGHIJ")
        self.assertEqual(SG.render_inline(blob), "hi")

    def test_hex_noise_dropped(self):
        blob = fixtures.pb_string(1, "DE56B0C5BE92351482D036E1C95AE5BE")
        self.assertEqual(SG.parse_blob(blob), [])

    def test_long_digits_dropped(self):
        blob = fixtures.pb_string(1, "7168896419021355869")
        self.assertEqual(SG.parse_blob(blob), [])

    def test_short_digits_kept(self):
        blob = fixtures.pb_string(1, "123456789")
        self.assertEqual(SG.render_inline(blob), "123456789")

    def test_cdn_url_becomes_image(self):
        url = "https://multimedia.nt.qq.com.cn/download?appid=1406&fileid=abc"
        blob = fixtures.pb_string(1, url)
        segs = SG.parse_blob(blob)
        self.assertEqual([s.kind for s in segs], ["image"])
        self.assertEqual(SG.render_inline(blob), "[图片]")
        self.assertEqual(len(SG.media_of(segs)), 1)

    def test_consecutive_images_collapse(self):
        blob = (fixtures.pb_string(1, "https://multimedia.nt.qq.com.cn/download?appid=1&fileid=a")
                + fixtures.pb_string(2, "https://multimedia.nt.qq.com.cn/download?appid=1&fileid=b"))
        self.assertEqual(SG.render_inline(blob), "[图片]")

    def test_jpg_filename_becomes_image(self):
        blob = fixtures.pb_string(1, "EDE5031F93DBE31F4711A87721DBE35D.jpg")
        self.assertEqual(SG.render_inline(blob), "[图片]")


class TestMarkup(unittest.TestCase):
    def test_gray_tip_at_and_text(self):
        s = '<gtip align="center"><qq uin="u_A" jp="3001"/><nor txt="你好"/></gtip>'
        blob = fixtures.pb_string(1, s)
        segs = SG.parse_blob(blob)
        kinds = [x.kind for x in segs]
        self.assertIn("at", kinds)
        self.assertIn("text", kinds)
        inline = SG.render_inline(
            blob, resolve=lambda k: "小明" if k == "u_A" else None)
        self.assertIn("@小明", inline)
        self.assertIn("你好", inline)

    def test_at_falls_back_to_qq(self):
        seg = SG.Segment("at", uid="u_Z", qq="3001")
        self.assertEqual(seg.inline(), "@3001")


class TestAssetStrip(unittest.TestCase):
    def test_gchatpic_path_removed(self):
        s = "欢迎新人{1ef060a6-41d6-41e4-bfae-7dc433902681}.jpg2395281898/gchatpic_new/1/2/198"
        self.assertNotIn("gchatpic_new", SG.strip_assets(s))
        self.assertIn("欢迎新人", SG.strip_assets(s))

    def test_embedded_asset_in_text_blob(self):
        s = "看这个 http://x/gchatpic_new/a/198 图"
        blob = fixtures.pb_string(1, s)
        inline = SG.render_inline(blob)
        self.assertNotIn("gchatpic_new", inline)
        self.assertIn("看这个", inline)


class TestDedup(unittest.TestCase):
    def test_repeated_fragment_dropped(self):
        blob = fixtures.pb_string(1, "重复正文") + fixtures.pb_string(2, "重复正文")
        self.assertEqual(SG.render_inline(blob), "重复正文")


if __name__ == "__main__":
    unittest.main()
