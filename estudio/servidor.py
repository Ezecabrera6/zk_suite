"""Servidor del estudio: la página para editar un video desde los crudos.

uso: python estudio/servidor.py [--puerto 8780]   →   http://127.0.0.1:8780/
Variables: ZK_GRABACIONES (carpeta de OBS, solo se lee), ZK_VIDEOS (donde se crean los proyectos), ZK_ASSETS.
Solo librería estándar. Escucha en 127.0.0.1 y rechaza pedidos con otro Host u Origin. Un proceso pesado a la vez
(transcribir, renderizar); las ediciones son instantáneas y cada una guarda una versión."""
import json, pathlib, re, sys, threading, time, traceback, urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import motor

AQUI = pathlib.Path(__file__).resolve().parent
PUERTO = int(sys.argv[sys.argv.index("--puerto") + 1]) if "--puerto" in sys.argv else 8780
TRABAJO = {"slug": None, "que": None, "desde": None, "log": "", "error": None}
CANDADO = threading.Lock()
TIPOS = {".html": "text/html; charset=utf-8", ".mp4": "video/mp4", ".json": "application/json", ".js": "text/javascript",
         ".css": "text/css", ".png": "image/png"}


def en_fondo(slug, que, fn):
    """Corre un proceso pesado en un hilo; si ya hay uno, avisa en vez de encolar."""
    if not CANDADO.acquire(blocking=False):
        raise ValueError(f"ya hay un proceso corriendo: {TRABAJO['que']} de {TRABAJO['slug']}")
    TRABAJO.update(slug=slug, que=que, desde=time.time(), log="", error=None)
    def correr():
        try:
            fn(lambda m: TRABAJO.update(log=str(m)))
            TRABAJO["log"] = "listo"
        except Exception as e:
            TRABAJO["error"] = str(e)[-800:]; traceback.print_exc()
        finally:
            TRABAJO.update(que=None); CANDADO.release()
    threading.Thread(target=correr, daemon=True).start()


def proyecto_completo(slug):
    d = motor.dir_proyecto(slug); an = d / "12_project" / "analysis"
    prev = sorted((d / "11_exports").glob("*/*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    return {"cfg": motor.cargar(slug), "edicion": motor.leer_edicion(slug),
            "estado": motor.leer_json(d / "12_project" / "estado.json", {"pasos": {}}),
            "frases": motor.leer_json(an / "frases.json", []), "silencios": motor.leer_json(an / "silencios.json", {}),
            "proxy": f"/m/{slug}/10_work/proxies/edicion.mp4" if (d / "10_work/proxies/edicion.mp4").exists() else None,
            "renders": [{"nombre": p.name, "url": f"/m/{slug}/{p.relative_to(d).as_posix()}", "hora": time.strftime("%d/%m %H:%M", time.localtime(p.stat().st_mtime))} for p in prev[:20]],
            "ultimo_render": motor.leer_json(d / "12_project" / "ultimo_render.json"),
            "versiones": [{"version": v["version"], "nota": v.get("nota"), "hora": v.get("hora")} for v in
                          (motor.leer_json(f) for f in sorted((d / "12_project" / "ediciones").glob("v*.json"))[-40:])]}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def parse_request(self):
        # solo 127.0.0.1/localhost (corta el DNS rebinding) y, si viene Origin, que sea local (corta el CSRF)
        if not super().parse_request():
            return False
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
        origen = self.headers.get("Origin")
        if host not in ("127.0.0.1", "localhost") or (origen and urllib.parse.urlparse(origen).hostname not in ("127.0.0.1", "localhost")):
            self.send_error(403, "solo local"); return False
        return True

    def _json(self, d, code=200):
        b = json.dumps(d, ensure_ascii=False).encode("utf-8")
        self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b))); self.send_header("Cache-Control", "no-store"); self.end_headers()
        self.wfile.write(b)

    def _archivo(self, f):
        if not f.is_file():
            return self.send_error(404)
        size = f.stat().st_size; a, b = 0, size - 1
        rng = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers.get("Range", "") or "")
        if rng and (rng[1] or rng[2]):
            a, b = (int(rng[1]), min(int(rng[2] or size - 1), size - 1)) if rng[1] else (max(0, size - int(rng[2])), size - 1)
            if a > b: return self.send_error(416)
            self.send_response(206); self.send_header("Content-Range", f"bytes {a}-{b}/{size}")
        else:
            self.send_response(200)
        self.send_header("Content-Type", TIPOS.get(f.suffix.lower(), "application/octet-stream"))
        self.send_header("Accept-Ranges", "bytes"); self.send_header("Content-Length", str(b - a + 1))
        self.send_header("Cache-Control", "no-store" if f.suffix == ".html" else "no-cache"); self.end_headers()
        try:
            with open(f, "rb") as fh:
                fh.seek(a); n = b - a + 1
                while n > 0:
                    buf = fh.read(min(1 << 20, n))
                    if not buf: break
                    self.wfile.write(buf); n -= len(buf)
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
            pass

    def do_GET(self):
        ruta = urllib.parse.unquote(urllib.parse.urlparse(self.path).path)
        try:
            if ruta in ("/", "/index.html"):
                return self._archivo(AQUI / "ui" / "index.html")
            if ruta == "/api/tomas":
                return self._json(motor.listar_tomas())
            if ruta.startswith("/api/toma/"):
                return self._json(motor.info_toma(ruta[len("/api/toma/"):]))
            if ruta == "/api/proyectos":
                return self._json(motor.listar_proyectos())
            if ruta == "/api/trabajo":
                return self._json(TRABAJO | {"segundos": round(time.time() - TRABAJO["desde"]) if TRABAJO["desde"] else 0})
            m = re.fullmatch(r"/api/p/([^/]+)", ruta)
            if m:
                return self._json(proyecto_completo(m[1]))
            m = re.fullmatch(r"/m/([^/]+)/(.+)", ruta)      # archivos del proyecto (proxy, renders), nunca fuera de su carpeta
            if m:
                if "\\" in m[2] or ":" in m[2] or m[2].startswith("/"):   # nada de rutas UNC ni de disco (Windows las abriría antes de mirar)
                    return self.send_error(403)
                d = motor.dir_proyecto(m[1]).resolve(); f = (d / m[2]).resolve()
                if d not in f.parents: return self.send_error(403)
                return self._archivo(f)
            self.send_error(404)
        except ValueError as e:
            self._json({"error": str(e)}, 400)

    def do_POST(self):
        ruta = urllib.parse.urlparse(self.path).path
        try:
            n = int(self.headers.get("Content-Length", 0) or 0)
            if not 0 <= n <= 1_000_000: raise ValueError("tamaño de pedido inválido")
            d = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            if not isinstance(d, dict): raise ValueError("se esperaba un objeto JSON")
            if ruta == "/api/crear":
                cfg = motor.crear(str(d.get("slug", "")), str(d.get("toma", "")), int(d.get("pista_voz", 0)),
                                  {str(k): str(v) for k, v in (d.get("roles") or {}).items()}, [str(x) for x in d.get("girar") or []])
                en_fondo(cfg["slug"], "procesar", lambda log: motor.procesar(cfg["slug"]))
                return self._json({"ok": True, "slug": cfg["slug"]})
            m = re.fullmatch(r"/api/p/([^/]+)/(op|procesar|render)", ruta)
            if not m: return self.send_error(404)
            slug, accion = m[1], m[2]; motor.cargar(slug)
            if accion == "op":
                return self._json({"ok": True, "edicion": motor.operar(slug, d)})
            if accion == "procesar":
                desde = d.get("desde") if d.get("desde") in motor.PASOS else None
                en_fondo(slug, "procesar", lambda log: motor.procesar(slug, desde))
                return self._json({"ok": True})
            calidad = "1080" if d.get("calidad") == "1080" else "360"
            en_fondo(slug, f"render {calidad}p", lambda log: motor.render(slug, calidad, log))
            return self._json({"ok": True})
        except (ValueError, KeyError, StopIteration, TypeError, AttributeError) as e:
            self._json({"error": str(e) or "pedido inválido"}, 400)


if __name__ == "__main__":
    print(f"Estudio en http://127.0.0.1:{PUERTO}/   ·   grabaciones: {motor.GRABACIONES}   ·   proyectos: {motor.VIDEOS}")
    ThreadingHTTPServer.allow_reuse_address = False   # en Windows SO_REUSEADDR deja que otro proceso tome el mismo puerto
    ThreadingHTTPServer(("127.0.0.1", PUERTO), H).serve_forever()
