"""Servidor local del LIVE PREVIEW (solo librería estándar de Python).

- Sirve la interfaz y los archivos del proyecto con soporte de Range (necesario para buscar en el video).
- /api/state se consulta cada segundo desde el navegador: si timeline_current.json cambió,
  la interfaz se recarga sola manteniendo la posición.
"""
from __future__ import annotations

import json
import mimetypes
import os
import threading
import urllib.parse
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .render import parse_vtt
from .timeline import (base_timeline_path, edited_duration, list_enhanced, list_versions, load_current,
                       removed_ranges)
from .util import ffprobe_json, load_json

UI_DIR = Path(__file__).parent / "ui"
mimetypes.add_type("video/mp4", ".mp4")
mimetypes.add_type("video/webm", ".webm")
mimetypes.add_type("text/vtt", ".vtt")


def make_handler(prj):
    dur_cache = {}
    render_lock = threading.Lock()

    def main_duration():
        src = prj.p(prj.source("main")["path"])
        k = str(src)
        if k not in dur_cache:
            dur_cache[k] = float(ffprobe_json(src)["format"]["duration"])
        return dur_cache[k]

    def media_url(rel):
        return "/media/" + urllib.parse.quote(str(rel).replace("\\", "/"))

    def ab_payload():
        """Datos del visor A/B: A = base de la editora, B = timeline_current (enhanced)."""
        srcs = {}
        for k, s in prj.cfg.get("sources", {}).items():
            use = s.get("proxy") if s.get("proxy") and prj.p(s["proxy"]).exists() else s["path"]
            srcs[k] = {"url": media_url(use), "kind": s.get("kind")}
        conform = load_json(prj.project_dir / "editorial_conform.json") or             load_json(prj.analysis_dir / "editorial_conform_draft.json", {}) or {}
        prev = []
        for p in list(prj.previews_dir.glob("*.mp4")) + list(prj.final_dir.glob("*.mp4")):
            prev.append({"name": p.name, "url": media_url(prj.rel(p)), "mtime": p.stat().st_mtime})
        for sub in ("review", "before_after", "visual_test"):
            d = prj.previews_dir / sub
            if d.exists():
                prev += [{"name": f"{sub}/{p.name}", "url": media_url(prj.rel(p)), "mtime": p.stat().st_mtime}
                         for p in d.glob("*.mp4")]
        prev.sort(key=lambda x: x["name"])
        return {"base": load_json(base_timeline_path(prj), {}), "current": load_current(prj) or {},
                "versions": list_enhanced(prj), "sources": srcs,
                "conform": conform.get("segments", []),
                "review": (load_json(prj.project_dir / "preedit_review.json", {}) or {}).get("findings", []),
                "previews": prev}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _json(self, obj, code=200):
            b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def _file(self, path: Path):
            if not path.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            size = path.stat().st_size
            ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
            rng = self.headers.get("Range")
            start, end = 0, size - 1
            if rng and rng.startswith("bytes="):
                a, _, b = rng[6:].split(",")[0].partition("-")
                if a:
                    start = int(a)
                    end = int(b) if b else size - 1
                else:
                    start = max(0, size - int(b))
                end = min(end, size - 1)
                self.send_response(HTTPStatus.PARTIAL_CONTENT)
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            else:
                self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", ctype)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(end - start + 1))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            try:
                with open(path, "rb") as f:
                    f.seek(start)
                    left = end - start + 1
                    while left > 0:
                        chunk = f.read(min(1 << 20, left))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        left -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def parse_request(self):
            # solo pedidos a 127.0.0.1/localhost (corta el DNS rebinding) y, en los POST, desde una página local (corta el CSRF)
            if not super().parse_request():
                return False
            host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
            origen = self.headers.get("Origin")
            if host not in ("127.0.0.1", "localhost") or (origen and urllib.parse.urlparse(origen).hostname not in ("127.0.0.1", "localhost")):
                self.send_error(403, "solo local")
                return False
            return True

        def do_POST(self):
            u = urllib.parse.urlparse(self.path)
            if u.path != "/api/render":
                return self.send_error(HTTPStatus.NOT_FOUND)
            q = urllib.parse.parse_qs(u.query)
            try:
                ef, et = float(q["from"][0]), float(q["to"][0])
            except (KeyError, ValueError):
                return self.send_error(HTTPStatus.BAD_REQUEST, "faltan from/to")
            from .render import render
            with render_lock:
                try:
                    r = render(prj, "preview", edit_from=max(0.0, ef), edit_to=et,
                               encoder=q.get("encoder", ["h264_nvenc"])[0], log=lambda *x: None)
                    r["url"] = media_url(r["output"])
                    return self._json(r)
                except BaseException as e:  # SystemExit incluido
                    return self._json({"status": "error", "error": str(e)}, 500)

        def do_GET(self):
            u = urllib.parse.urlparse(self.path)
            path = urllib.parse.unquote(u.path)
            if path in ("/", "/compare", "/compare.html"):
                return self._file(UI_DIR / "compare.html")
            if path in ("/live", "/index.html"):
                return self._file(UI_DIR / "index.html")
            if path in ("/ab", "/ab.html"):
                return self._file(UI_DIR / "ab.html")
            if path == "/api/ab":
                return self._json(ab_payload())
            if "\\" in path or ":" in path:          # nada de rutas UNC ni de disco (Windows las abriría antes de mirar)
                return self.send_error(HTTPStatus.FORBIDDEN)
            if path.startswith("/ui/"):
                target = (UI_DIR / path[4:]).resolve()
                if UI_DIR.resolve() not in target.parents:          # nada fuera de ui/
                    return self.send_error(HTTPStatus.FORBIDDEN)
                return self._file(target)
            if path == "/api/state":
                tlp = prj.timeline_current
                tl = load_json(tlp, {}) or {}
                prev = sorted(prj.previews_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True) \
                    if prj.previews_dir.exists() else []
                rv = prj.project_dir / "preedit_review.json"
                mt = max(tlp.stat().st_mtime if tlp.exists() else 0, rv.stat().st_mtime if rv.exists() else 0)
                return self._json({"version": tl.get("version"), "mtime": mt,
                                   "previews": [{"name": p.name, "url": "/media/" + prj.rel(p), "mtime": p.stat().st_mtime}
                                                for p in prev[:30]]})
            if path == "/api/timeline":
                tl = load_current(prj) or {}
                md = main_duration()
                srcs = {}
                for k, s in prj.cfg.get("sources", {}).items():
                    use = s.get("proxy") if s.get("proxy") and prj.p(s["proxy"]).exists() else s["path"]
                    srcs[k] = {**s, "url": "/media/" + urllib.parse.quote(use)}
                cues = []
                st = tl.get("subtitles", {})
                if st.get("file"):
                    cues = parse_vtt(prj.p(st["file"]))
                return self._json({"timeline": tl, "sources": srcs, "main_duration": md,
                                   "edited_duration": edited_duration(tl) if tl else 0,
                                   "removed": removed_ranges(tl, md) if tl else [], "cues": cues,
                                   "analysis": load_json(prj.analysis_dir / "edit_summary.json", {})})
            if path == "/api/versions":
                return self._json(list_versions(prj))
            if path.startswith("/media/"):
                rel = path[len("/media/"):]
                target = (prj.root / rel).resolve()
                if prj.root not in target.parents and target != prj.root:
                    return self.send_error(HTTPStatus.FORBIDDEN)
                return self._file(target)
            self.send_error(HTTPStatus.NOT_FOUND)

    return H


def serve(prj, port: int = 8765, open_browser: bool = True):
    ThreadingHTTPServer.allow_reuse_address = False   # en Windows SO_REUSEADDR deja que otro proceso tome el mismo puerto
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(prj))
    url = f"http://127.0.0.1:{port}/"
    print(f"[vedit] LIVE PREVIEW en {url}  (Ctrl+C para salir)")
    print(f"[vedit] Proyecto: {prj.root}")
    print("[vedit] La interfaz se actualiza sola cuando cambia 12_project/timeline_current.json")
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[vedit] cerrado")
