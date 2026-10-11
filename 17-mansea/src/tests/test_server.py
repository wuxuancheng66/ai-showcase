"""静态文件服务的可观察边界：正常资源可读，越界路径不可读。"""
import http.client
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from mansea import server


class EmptyEngine:
    def __init__(self, _data):
        pass

    def __len__(self):
        return 0


class StaticBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.site = root / "site"
        self.site.mkdir()
        (self.site / "index.html").write_text("home")
        (self.site / "guide.html").write_text("guide")
        (root / "outside.txt").write_text("outside-sentinel")
        (self.site / "escape.txt").symlink_to(root / "outside.txt")
        self.site_patch = patch.object(server, "SITE", self.site)
        self.engine_patch = patch.object(server, "Engine", EmptyEngine)
        self.site_patch.start()
        self.engine_patch.start()
        self.http = ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler("unused"))
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join()
        self.engine_patch.stop()
        self.site_patch.stop()
        self.tmp.cleanup()

    def request(self, path):
        conn = http.client.HTTPConnection("127.0.0.1", self.http.server_port)
        try:
            conn.request("GET", path)
            response = conn.getresponse()
            return response.status, response.read().decode()
        finally:
            conn.close()

    def test_static_resource_with_query_string(self):
        self.assertEqual(self.request("/guide.html?v=1"), (200, "guide"))

    def test_url_encoded_filename(self):
        self.assertEqual(self.request("/gu%69de.html"), (200, "guide"))

    def test_parent_path_is_denied(self):
        for path in ("/../outside.txt", "/%2e%2e/outside.txt", "/%2e%2e%2foutside.txt", "/escape.txt"):
            with self.subTest(path=path):
                status, body = self.request(path)
                self.assertEqual(status, 403)
                self.assertNotIn("outside-sentinel", body)

    def test_invalid_path_is_rejected(self):
        self.assertEqual(self.request("/%00")[0], 400)

    def test_unknown_route_retains_home_fallback(self):
        self.assertEqual(self.request("/missing"), (200, "home"))


if __name__ == "__main__":
    unittest.main()
