"""Visor de previews: un navegador que siempre tiene la última preview y deja ver las anteriores, con comentarios
atados a la versión y el botón «Enviar a corregir».
Sirve la carpeta del video y esta página; /lista devuelve las previews de la más nueva a la más vieja y POST /enviar
guarda los comentarios en <video>/12_project/visor_correcciones/<versión>_<fecha>.json (la sesión de Claude que edita
vigila esa carpeta o la consola, y corrige).
uso: python servidor.py <carpeta del video> [--patron "*_v*_360p.mp4"] [--puerto 8773]   →   http://127.0.0.1:8773/visor/
Range para saltar dentro del mp4 y sin caché en las páginas."""
import json, pathlib, re, sys, time, urllib.parse
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

def opt(k, d): return sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
RAIZ = pathlib.Path(sys.argv[1]).resolve()                    # carpeta del video (01_main, 11_exports, 12_project…)
PREV = RAIZ / "11_exports" / "previews"
CORR = RAIZ / "12_project" / "visor_correcciones"
PATRON, PUERTO = opt("--patron", "*_v*_360p.mp4"), int(opt("--puerto", "8773"))
AQUI = pathlib.Path(__file__).resolve().parent


class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(RAIZ), **k)

    def log_message(self, *a):
        pass

    def end_headers(self):
        if self.path.split("?")[0].endswith((".html", ".json", "/")):
            self.send_header("Cache-Control", "no-store, must-revalidate")
        super().end_headers()

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

    def translate_path(self, path):
        # /visor/… sale de esta carpeta de la suite; todo lo demás, de la carpeta del video
        p = path.split("?")[0]
        if p.startswith("/visor/"):
            nombre = p[len("/visor/"):] or "index.html"
            if not re.fullmatch(r"[\w-]+\.(html|json)", nombre):        # solo las páginas de esta carpeta, sin rutas
                return str(AQUI / "_no_existe_")
            return str(AQUI / nombre)
        return super().translate_path(path)

    def do_GET(self):
        if self.path.split("?")[0] == "/lista":
            vs = sorted(PREV.glob(PATRON), key=lambda p: p.name, reverse=True)
            # solo las terminadas: una que se está escribiendo cambia de tamaño entre dos miradas
            vs = [p for p in vs if time.time() - p.stat().st_mtime > 3]
            data = json.dumps([{"nombre": (re.search(r"v\d+", p.stem) or [p.stem])[0], "url": f"/11_exports/previews/{p.name}",
                                "hora": time.strftime("%H:%M", time.localtime(p.stat().st_mtime)),
                                "mb": round(p.stat().st_size / 1e6, 1)} for p in vs]).encode("utf-8")
            self.send_response(200); self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(data); return
        super().do_GET()

    def do_POST(self):
        # «Enviar a corregir»: guarda los comentarios y avisa por consola a la sesión de Claude que lo vigila
        if self.path != "/enviar":
            self.send_error(404); return
        try:
            d = json.loads(self.rfile.read(max(0, min(int(self.headers.get("Content-Length", 0) or 0), 5_000_000))).decode("utf-8"))
            assert isinstance(d, dict) and isinstance(d.get("comentarios"), list) and d["comentarios"]
        except (ValueError, AssertionError):
            self.send_error(400, "comentarios inválidos"); return
        CORR.mkdir(exist_ok=True)
        ver = re.sub(r"[^\w+.-]", "_", str(d.get("version", "v")))[:40].strip(".") or "v"   # el nombre no puede salir de la carpeta
        f = CORR / f"{ver}_{time.strftime('%Y%m%d_%H%M%S')}.json"
        f.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        print("ENVIADO", f, flush=True)
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def send_head(self):
        # Chrome salta dentro de un mp4 pidiendo pedazos («Range: bytes=a-b»); sin esto vuelve siempre al segundo 0
        rng = self.headers.get("Range")
        path = self.translate_path(self.path)
        if not rng or not pathlib.Path(path).is_file():
            return super().send_head()
        size = pathlib.Path(path).stat().st_size
        try:
            s_a, s_b = rng.split("=", 1)[1].split(",")[0].strip().split("-")
            if s_a == "":
                a, b = max(0, size - int(s_b)), size - 1
            else:
                a = int(s_a); b = min(int(s_b), size - 1) if s_b else size - 1
        except ValueError:
            self.send_error(400, "Range inválido"); return None
        if a >= size or a > b:
            self.send_error(416); return None
        f = open(path, "rb"); f.seek(a)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Range", f"bytes {a}-{b}/{size}")
        self.send_header("Content-Length", str(b - a + 1))
        self.end_headers()
        self._resto = b - a + 1
        return f

    def copyfile(self, src, dst):
        n = getattr(self, "_resto", None)
        if n is None:
            return super().copyfile(src, dst)
        self._resto = None
        try:
            while n > 0:
                buf = src.read(min(1 << 20, n))
                if not buf: break
                dst.write(buf); n -= len(buf)
        except (ConnectionResetError, BrokenPipeError):
            pass


if __name__ == "__main__":
    print(f"Visor en http://127.0.0.1:{PUERTO}/visor/")
    ThreadingHTTPServer.allow_reuse_address = False   # en Windows SO_REUSEADDR deja que otro proceso tome el mismo puerto
    ThreadingHTTPServer(("127.0.0.1", PUERTO), H).serve_forever()   # solo local: no se expone a la red

