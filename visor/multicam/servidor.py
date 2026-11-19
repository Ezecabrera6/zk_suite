"""Visor multicámara: editor de corte con las 3 cámaras (cenital, cara, programa) y la salida, más la preview en vivo.
Sirve la carpeta del video y guarda el corte en <video>/12_project/edl_multicam.json (copia de seguridad antes de pisar).
POST /plan corre el render con --plan para rearmar la preview en vivo sin renderizar.
uso: python servidor.py <carpeta del video> [--render ruta/al/render.py] [--puerto 8771]
     →   http://127.0.0.1:8771/visor/          (preview en vivo: /visor/preview.html)
"""
import json, pathlib, re, shutil, sys, time, urllib.parse
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

def opt(k, d): return sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
RAIZ = pathlib.Path(sys.argv[1]).resolve()                    # carpeta del video
RENDER = pathlib.Path(opt("--render", str(RAIZ / "12_project" / "render.py"))).resolve()
PUERTO = int(opt("--puerto", "8771"))
AQUI = pathlib.Path(__file__).resolve().parent
EDL = RAIZ / "12_project" / "edl_multicam.json"
COPIAS = RAIZ / "12_project" / "analysis" / "edl_copias"


class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(RAIZ), **k)

    def log_message(self, *a):  # silencio: los pedidos de video por rangos llenan la consola
        pass

    def end_headers(self):
        # al recargar se veía la versión vieja: las páginas y los planes nunca se guardan en caché
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
        # /visor/… sale de esta carpeta de la suite (plan.json lo escribe el render en <video>/12_project/visor/)
        p = path.split("?")[0]
        if p.startswith("/visor/"):
            nombre = p[len("/visor/"):] or "index.html"
            if not re.fullmatch(r"[\w-]+\.(html|json)", nombre):        # solo las páginas de esta carpeta, sin rutas
                return str(AQUI / "_no_existe_")
            return str(RAIZ / "12_project" / "visor" / nombre) if nombre == "plan.json" else str(AQUI / nombre)
        return super().translate_path(path)

    def do_GET(self):
        if self.path.split("?")[0] == "/edl":
            data = EDL.read_bytes() if EDL.exists() else b'{"segmentos": []}'
            self.send_response(200); self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(data); return
        super().do_GET()

    def send_head(self):
        # Chrome salta dentro de un mp4 pidiendo pedazos («Range: bytes=a-b»); sin esto vuelve siempre al segundo 0
        rng = self.headers.get("Range")
        path = self.translate_path(self.path)
        if not rng or not pathlib.Path(path).is_file():
            return super().send_head()
        size = pathlib.Path(path).stat().st_size
        try:
            s_a, s_b = rng.split("=", 1)[1].split(",")[0].strip().split("-")
            if s_a == "":                       # «bytes=-N»: los últimos N
                a, b = max(0, size - int(s_b)), size - 1
            else:                               # «bytes=a-» o «bytes=a-b»
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
        except (ConnectionResetError, BrokenPipeError):  # Chrome corta pedidos de video a la mitad todo el tiempo
            pass

    def do_POST(self):
        if self.path == "/plan":   # «Actualizar» de la preview: rearma el plan con el corte actual (≈10 s, sin renderizar)
            import subprocess, os
            r = subprocess.run([sys.executable, str(RENDER), "v=preview", "--plan"], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", cwd=str(RAIZ), env={**os.environ, "ZK_PROYECTO": str(RAIZ)})
            ok = r.returncode == 0
            self.send_response(200 if ok else 500); self.send_header("Content-Type", "application/json"); self.end_headers()
            self.wfile.write(json.dumps({"ok": ok, "salida": (r.stdout + r.stderr)[-1500:]}).encode("utf-8")); return
        if self.path != "/edl":
            self.send_error(404); return
        n = max(0, min(int(self.headers.get("Content-Length", 0) or 0), 5_000_000))
        try:
            d = json.loads(self.rfile.read(n).decode("utf-8"))
            assert isinstance(d, dict) and isinstance(d.get("segmentos"), list)
        except Exception as e:  # validación en la entrada: nunca pisar el corte con algo roto
            self.send_error(400, str(e)); return
        COPIAS.mkdir(parents=True, exist_ok=True)
        if EDL.exists():  # copia antes de pisar, para poder volver atrás
            shutil.copy2(EDL, COPIAS / time.strftime("edl_%Y%m%d_%H%M%S.json"))
        EDL.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(b'{"ok": true}')


if __name__ == "__main__":
    print(f"Visor en http://127.0.0.1:{PUERTO}/visor/")
    ThreadingHTTPServer.allow_reuse_address = False   # en Windows SO_REUSEADDR deja que otro proceso tome el mismo puerto
    ThreadingHTTPServer(("127.0.0.1", PUERTO), H).serve_forever()   # solo local
