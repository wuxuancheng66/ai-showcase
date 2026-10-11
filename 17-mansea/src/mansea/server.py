"""本地网页服务：只监听 127.0.0.1，不对外暴露。

    GET /                -> site/index.html
    GET /api/search?q=   -> JSON 检索结果
    GET /api/doc?id=     -> 单篇全文
    GET /api/stats       -> 语料统计
"""

from __future__ import annotations

import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from .engine import Engine

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
}


def make_handler(data_dir: str):
    eng = Engine(data_dir)
    print(f"[server] 已加载索引：{len(eng)} 篇文档", flush=True)

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(SITE), **kw)

        def log_message(self, fmt, *args):  # 安静一点
            pass

        def _json(self, obj, code=200):
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            u = urlparse(self.path)
            if u.path.startswith("/api/"):
                qs = parse_qs(u.query)
                try:
                    if u.path == "/api/search":
                        q = (qs.get("q") or [""])[0].strip()
                        k = int((qs.get("k") or ["20"])[0])
                        if not q:
                            return self._json({"query": q, "results": [], "total": len(eng)})
                        res = eng.search(q, k, with_html=True)
                        return self._json({"query": q, "results": res, "total": len(eng)})
                    if u.path == "/api/doc":
                        did = int((qs.get("id") or ["-1"])[0])
                        d = eng.doc(did)
                        if d is None:
                            return self._json({"error": "not found"}, 404)
                        return self._json(d)
                    if u.path == "/api/stats":
                        secs: dict[str, int] = {}
                        for m in eng.bm.docs:
                            secs[m.get("section", "?")] = secs.get(m.get("section", "?"), 0) + 1
                        return self._json(
                            {
                                "docs": len(eng),
                                "terms": len(eng.bm.postings),
                                "sections": secs,
                            }
                        )
                except Exception as e:  # noqa: BLE001
                    return self._json({"error": f"{type(e).__name__}: {e}"}, 500)
                return self._json({"error": "unknown api"}, 404)

            # 解析查询参数与 URL 编码后，限制静态资源始终位于站点目录内。
            root = SITE.resolve()
            decoded_path = unquote(u.path)
            if "\x00" in decoded_path:
                return self._json({"error": "invalid path"}, 400)
            fpath = (root / decoded_path.lstrip("/")).resolve()
            if not fpath.is_relative_to(root):
                return self._json({"error": "forbidden"}, 403)
            if not fpath.exists() or fpath.is_dir():
                fpath = root / "index.html"
            body = fpath.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", MIME.get(fpath.suffix, "application/octet-stream"))
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def run_server(port: int = 8733, data_dir: str = "") -> int:
    data_dir = data_dir or str(ROOT / "data")
    handler = make_handler(data_dir)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    print(f"[server] http://127.0.0.1:{port}/  (Ctrl-C 退出)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[server] 已停止")
    finally:
        httpd.server_close()
    return 0
