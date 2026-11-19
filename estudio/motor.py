"""Motor del estudio: de los crudos de OBS a un video editado.

Un proyecto es una carpeta del video (ZK_VIDEOS/<slug>) con:
  12_project/estudio.json        de dónde salen las cámaras y la voz (los crudos se leen donde están, no se copian)
  12_project/edicion.json        la edición actual; cada cambio guarda una versión en 12_project/ediciones/vNNN.json
  12_project/analysis/           frases.json (transcripción frase por frase con palabras), silencios.json, voz16k.wav
  10_work/proxies/               edicion.mp4 (programa 360p + voz) para editar en el navegador
  10_work/audio/voz_c.wav        la voz con la cadena C
  11_exports/previews|final/     los renders

Todo el tiempo de la edición está en SEGUNDOS DE LA TOMA: las cámaras de OBS están sincronizadas, así que un corte
vale para todas. La edición es: cortes (silencio, manual, retoma) que se prenden y apagan, textos (lower third) y
cámaras forzadas por tramo. El render arma los planos con la cámara según lo que se dice (docs/REGLAS.md)."""
import copy, hashlib, json, math, os, pathlib, re, subprocess, sys, tempfile, threading, time, wave
import numpy as np

SUITE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SUITE / "graficos"))
VIDEOS = pathlib.Path(os.environ.get("ZK_VIDEOS", SUITE / "proyectos")).resolve()
GRABACIONES = pathlib.Path(os.environ.get("ZK_GRABACIONES", SUITE / "grabaciones")).resolve()
ASSETS = pathlib.Path(os.environ.get("ZK_ASSETS", SUITE / "assets"))
FPS, SR = 30, 48000
SLUG_OK = re.compile(r"[a-z0-9][a-z0-9_-]{0,39}")


# ------------------------------------------------------------------ utilidades
def run(a, **k):
    r = subprocess.run(a, capture_output=True, **k)
    if r.returncode:
        raise RuntimeError((r.stderr.decode("utf-8", "replace") if isinstance(r.stderr, bytes) else r.stderr)[-1500:])
    return r


def probe(f):
    return json.loads(run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=index,codec_type,channels",
                           "-of", "json", str(f)], text=True).stdout)


def leer_json(f, defecto=None):
    try:
        return json.loads(pathlib.Path(f).read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return defecto


def guardar_json(f, d):
    f = pathlib.Path(f); f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp"); tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8"); tmp.replace(f)


_ENC = None
def encoder():
    """h264_nvenc si la placa lo acepta de verdad (prueba de 1 cuadro); si no, libx264."""
    global _ENC
    if _ENC is None:
        r = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=s=256x144:d=0.1", "-frames:v", "1",
                            "-c:v", "h264_nvenc", "-f", "null", "-"], capture_output=True)
        _ENC = ["-c:v", "h264_nvenc", "-preset", "p4", "-cq"] if r.returncode == 0 else ["-c:v", "libx264", "-preset", "veryfast", "-crf"]
    return _ENC


def dir_proyecto(slug):
    if not SLUG_OK.fullmatch(slug or ""):
        raise ValueError("nombre de proyecto inválido (minúsculas, números, - y _)")
    return VIDEOS / slug


# ------------------------------------------------------------------ crudos de OBS
def listar_tomas():
    """Tomas de OBS en ZK_GRABACIONES: «<fecha hora>.mp4» (programa) y sus ISO «<fecha hora> CAM-<nombre>.mp4»."""
    out = []
    if not GRABACIONES.is_dir():
        return out
    for f in sorted(GRABACIONES.glob("*.mp4"), reverse=True):
        if " CAM-" in f.stem:
            continue
        cams = {g.stem.split(" CAM-", 1)[1]: g.name for g in GRABACIONES.glob(f"{f.stem} CAM-*.mp4")}
        out.append({"toma": f.stem, "programa": f.name, "camaras": cams, "mb": round(f.stat().st_size / 1e6)})
    return out


def info_toma(toma):
    t = next((x for x in listar_tomas() if x["toma"] == toma), None)
    if not t:
        raise ValueError("no existe esa toma en la carpeta de grabaciones")
    p = probe(GRABACIONES / t["programa"])
    t["duracion"] = float(p["format"]["duration"])
    t["pistas"] = [k for k, s in enumerate(s for s in p["streams"] if s["codec_type"] == "audio")]
    return t


def rol_sugerido(nombre):
    n = nombre.lower()
    return "producto" if any(k in n for k in ("cenital", "top", "mesa", "producto")) else "cara"


def crear(slug, toma, pista_voz, roles=None, girar=None):
    """Crea la carpeta del video y estudio.json. roles: {nombre_cam: "cara"|"producto"}; girar: [nombre_cam]."""
    d = dir_proyecto(slug)
    if (d / "12_project" / "estudio.json").exists():
        raise ValueError("ya existe un proyecto con ese nombre")
    t = info_toma(toma)
    if int(pista_voz) not in t["pistas"]:
        raise ValueError("esa pista de audio no existe en la toma")
    fuentes = {"programa": {"archivo": str(GRABACIONES / t["programa"]), "rol": "neutro", "girar": False}}
    for nom, arch in t["camaras"].items():
        rol = (roles or {}).get(nom) or rol_sugerido(nom)
        fuentes[nom] = {"archivo": str(GRABACIONES / arch), "rol": rol if rol in ("cara", "producto", "neutro") else "cara",
                        "girar": nom in (girar or [])}
    for sub in ("01_main", "10_work/proxies", "10_work/audio", "11_exports/previews", "11_exports/final", "12_project/analysis"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    guardar_json(d / "12_project" / "estudio.json", {"slug": slug, "toma": toma, "creado": time.strftime("%d/%m/%Y %H:%M"),
                                                     "duracion": t["duracion"], "pista_voz": int(pista_voz), "fuentes": fuentes})
    guardar_edicion(slug, {"cortes": [], "textos": [], "camaras": []}, "proyecto nuevo")
    return cargar(slug)


def cargar(slug):
    d = dir_proyecto(slug)
    cfg = leer_json(d / "12_project" / "estudio.json")
    if not cfg:
        raise ValueError("no existe el proyecto")
    return cfg


def listar_proyectos():
    if not VIDEOS.is_dir():
        return []
    return [leer_json(f) | {"estado": leer_json(f.parent / "estado.json", {})}
            for f in sorted(VIDEOS.glob("*/12_project/estudio.json"))]


# ------------------------------------------------------------------ estado de los procesos
def estado(slug, **cambios):
    f = dir_proyecto(slug) / "12_project" / "estado.json"
    e = leer_json(f, {"pasos": {}})
    for k, v in cambios.items():
        if k == "paso":
            e["pasos"][v[0]] = {"estado": v[1], "detalle": v[2] if len(v) > 2 else "", "hora": time.strftime("%H:%M:%S")}
        else:
            e[k] = v
    guardar_json(f, e)
    return e


PASOS = ["voz", "proxies", "transcripcion", "silencios"]


def procesar(slug, desde=None):
    """Corre los pasos que faltan (o todos desde «desde»). Cada paso deja su archivo: si se corta, retoma."""
    cfg = cargar(slug); d = dir_proyecto(slug)
    hechos = {"voz": (d / "10_work/audio/voz_c.wav").exists() and (d / "12_project/analysis/voz16k.wav").exists(),
              "proxies": (d / "10_work/proxies/edicion.mp4").exists(),
              "transcripcion": (d / "12_project/analysis/frases.json").exists(),
              "silencios": (d / "12_project/analysis/silencios.json").exists()}
    if desde in PASOS:
        for p in PASOS[PASOS.index(desde):]:
            hechos[p] = False
    for p in PASOS:
        if hechos[p]:
            estado(slug, paso=(p, "listo")); continue
        estado(slug, paso=(p, "corriendo"))
        try:
            det = {"voz": paso_voz, "proxies": paso_proxies, "transcripcion": paso_transcripcion, "silencios": paso_silencios}[p](slug, cfg)
            estado(slug, paso=(p, "listo", det or ""))
        except Exception as e:
            estado(slug, paso=(p, "error", str(e)[-600:])); raise
    if not leer_edicion(slug)["cortes"]:          # primera vez: los silencios largos ya salen cortados
        operar(slug, {"op": "silencios"})


def paso_voz(slug, cfg):
    d = dir_proyecto(slug)
    run([sys.executable, str(SUITE / "audio" / "voz_cadena_c.py"), cfg["fuentes"]["programa"]["archivo"], str(cfg["pista_voz"]),
         str(d / "10_work/audio/voz_c.wav"), str(d / "12_project/analysis")])
    return "cadena C"


def paso_proxies(slug, cfg):
    """edicion.mp4: el programa en 640x360 (GOP de medio segundo para saltar rápido) con la voz limpia."""
    d = dir_proyecto(slug); out = d / "10_work/proxies/edicion.mp4"; tmp = out.with_name("edicion_tmp.mp4")
    vf = "scale=640:360,fps=30" + (",hflip,vflip" if cfg["fuentes"]["programa"].get("girar") else "")
    run(["ffmpeg", "-v", "error", "-y", "-i", cfg["fuentes"]["programa"]["archivo"], "-i", str(d / "10_work/audio/voz_c.wav"),
         "-map", "0:v", "-map", "1:a", "-vf", vf, *encoder(), "30", "-g", "15", "-c:a", "aac", "-b:a", "128k",
         "-movflags", "+faststart", "-shortest", str(tmp)])
    tmp.replace(out)
    return "640x360"


def _voz16k(slug):
    w = wave.open(str(dir_proyecto(slug) / "12_project/analysis/voz16k.wav")); sr = w.getframerate()
    return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768, sr


def tramos_de_voz(x, sr, hueco=0.35, umbral=None):
    """Tramos con voz (por energía cada 20 ms). El umbral sale de la propia toma: 30 dB debajo de lo más fuerte."""
    hop = int(sr * 0.02); rms = 20 * np.log10(np.sqrt(np.convolve(x ** 2, np.ones(hop) / hop, "same")[::hop] + 1e-12))
    umbral = float(np.percentile(rms[rms > -90], 95) - 30) if umbral is None else umbral
    runs, cur = [], None
    for f, on in enumerate(rms > umbral):
        t = f * 0.02
        if on:
            if cur is None: cur = [t, t]
            elif t - cur[1] > hueco: runs.append(cur); cur = [t, t]
            else: cur[1] = t
    if cur: runs.append(cur)
    return [r for r in runs if r[1] - r[0] > 0.12], umbral


def _whisper():
    import glob
    for dd in glob.glob(os.path.expandvars(r"%APPDATA%\Python\Python312\site-packages\nvidia\*\bin")):
        os.add_dll_directory(dd); os.environ["PATH"] = dd + os.pathsep + os.environ["PATH"]
    from faster_whisper import WhisperModel
    modelo = os.environ.get("ZK_WHISPER", "large-v3")
    try:
        return WhisperModel(modelo, device="cuda", compute_type="int8_float16"), "GPU"
    except Exception:
        return WhisperModel(modelo, device="cpu", compute_type="int8"), "CPU"


def paso_transcripcion(slug, cfg):
    """Frase por frase (cada tramo de voz solo, sin contexto: no se pierden las retomas) y con la hora de cada palabra."""
    x, sr = _voz16k(slug)
    runs, _ = tramos_de_voz(x, sr)
    m, dev = _whisper(); frases = []
    for i, (a, b) in enumerate(runs):
        a0 = max(0, a - 0.15)
        segs, _ = m.transcribe(x[int(a0 * sr):int((b + 0.25) * sr)], language="es", vad_filter=False,
                               condition_on_previous_text=False, temperature=0.0, word_timestamps=True)
        pal = [{"w": w.word.strip(), "s": round(a0 + w.start, 2), "e": round(a0 + w.end, 2)} for s in segs for w in (s.words or []) if w.word.strip()]
        if pal:
            frases.append({"a": round(a, 2), "b": round(b, 2), "txt": " ".join(p["w"] for p in pal), "palabras": pal})
        if i % 10 == 0:
            estado(slug, paso=("transcripcion", "corriendo", f"{i}/{len(runs)} frases ({dev})"))
    guardar_json(dir_proyecto(slug) / "12_project/analysis/frases.json", frases)
    return f"{len(frases)} frases ({dev})"


def paso_silencios(slug, cfg):
    x, sr = _voz16k(slug)
    runs, umbral = tramos_de_voz(x, sr, hueco=0.25)
    dur = len(x) / sr
    huecos = [(0.0, runs[0][0])] if runs else [(0.0, dur)]
    huecos += [(runs[k][1], runs[k + 1][0]) for k in range(len(runs) - 1)] + ([(runs[-1][1], dur)] if runs else [])
    guardar_json(dir_proyecto(slug) / "12_project/analysis/silencios.json",
                 {"umbral_db": round(umbral, 1), "huecos": [[round(a, 2), round(b, 2)] for a, b in huecos if b - a > 0.3]})
    return f"{len(huecos)} huecos"


# ------------------------------------------------------------------ la edición (versionada)
def leer_edicion(slug):
    return leer_json(dir_proyecto(slug) / "12_project" / "edicion.json")


def guardar_edicion(slug, ed, nota):
    d = dir_proyecto(slug) / "12_project"
    vs = sorted(int(f.stem[1:]) for f in (d / "ediciones").glob("v*.json")) if (d / "ediciones").exists() else []
    ed = copy.deepcopy(ed); ed["version"] = (vs[-1] + 1) if vs else 1; ed["nota"] = nota; ed["hora"] = time.strftime("%d/%m %H:%M:%S")
    guardar_json(d / "ediciones" / f"v{ed['version']:03d}.json", ed)
    guardar_json(d / "edicion.json", ed)
    return ed


def restar(rangos, a, b):
    """Rangos [x, y] menos [a, b]."""
    out = []
    for x, y in rangos:
        if y <= a or x >= b: out.append([x, y]); continue
        if x < a: out.append([x, a])
        if y > b: out.append([b, y])
    return out


def nuevo_id(ed, pre):
    nums = [int(m[1]) for c in ed["cortes"] + ed["textos"] if (m := re.fullmatch(pre + r"(\d+)", str(c.get("id", ""))))]
    return f"{pre}{max(nums + [0]) + 1:03d}"


EDITANDO = threading.Lock()          # una operación a la vez: dos no pueden calcular el mismo número de versión


def operar(slug, o):
    """Aplica una operación de edición y guarda una versión nueva. Valida todo lo que llega del navegador."""
    with EDITANDO:
        return _operar(slug, o)


def _num(v, lo, hi):
    x = float(v)
    if not math.isfinite(x): raise ValueError("número inválido")
    return min(max(x, lo), hi)


def _operar(slug, o):
    ed = leer_edicion(slug); cfg = cargar(slug); dur = float(cfg["duracion"])
    op = o.get("op"); base = ed.pop("base", None)       # «base»: de qué versión partió el último deshacer
    num = lambda k, lo=0.0, hi=dur: _num(o[k], lo, hi)
    if op == "silencios":            # reemplaza los cortes de silencio: deja «antes» s de aire al final de la frase y «despues» antes de la siguiente
        minimo, antes, despues = _num(o.get("minimo", 0.9), 0.3, 10), _num(o.get("antes", 0.25), 0, 1), _num(o.get("despues", 0.15), 0, 1)
        sil = leer_json(dir_proyecto(slug) / "12_project/analysis/silencios.json", {"huecos": []})["huecos"]
        ed["cortes"] = [c for c in ed["cortes"] if c["tipo"] != "silencio"]
        for a, b in sil:
            a2, b2 = a + (antes if a > 0 else 0), b - (despues if b < dur - 0.05 else 0)
            if b - a >= minimo and b2 - a2 >= 0.05:
                ed["cortes"].append({"id": nuevo_id(ed, "c"), "tipo": "silencio", "a": round(a2, 2), "b": round(b2, 2), "activo": True})
        nota = f"silencios de más de {minimo:g} s"
    elif op == "cortar":
        a, b = sorted((num("a"), num("b")))
        if b - a < 0.05: raise ValueError("el tramo es muy corto")
        ed["cortes"].append({"id": nuevo_id(ed, "c"), "tipo": "manual", "a": round(a, 2), "b": round(b, 2), "activo": True,
                             "txt": str(o.get("txt", ""))[:200]})
        nota = f"cortado {a:.1f}–{b:.1f} s"
    elif op == "restaurar":          # vuelve a meter [a, b]: recorta todos los cortes que lo pisan
        a, b = sorted((num("a"), num("b"))); nuevos = []
        for c in ed["cortes"]:
            if not c["activo"] or c["b"] <= a or c["a"] >= b: nuevos.append(c); continue
            for k, (x, y) in enumerate(restar([[c["a"], c["b"]]], a, b)):
                if y - x >= 0.05:
                    nuevos.append(c | {"a": x, "b": y, "id": c["id"] if k == 0 else nuevo_id({"cortes": ed["cortes"] + nuevos, "textos": []}, "c")})
        ed["cortes"] = nuevos; nota = f"restaurado {a:.1f}–{b:.1f} s"
    elif op == "alternar":           # prende o apaga un corte
        c = next(c for c in ed["cortes"] if c["id"] == o.get("id")); c["activo"] = not c["activo"]
        nota = f"{'activado' if c['activo'] else 'desactivado'} {c['id']}"
    elif op == "texto":
        tid = o.get("id") if re.fullmatch(r"t\d+", str(o.get("id", ""))) else nuevo_id(ed, "t")
        t = {"id": tid, "t": round(num("t"), 2), "dur": round(num("dur", 1.0, 8.0), 2),
             "rotulo": str(o.get("rotulo", ""))[:40], "dato": str(o.get("dato", ""))[:70]}
        if not t["dato"].strip(): raise ValueError("el texto está vacío")
        ed["textos"] = [x for x in ed["textos"] if x["id"] != t["id"]] + [t]; ed["textos"].sort(key=lambda x: x["t"])
        nota = f"texto «{t['dato']}»"
    elif op == "borrar_texto":
        ed["textos"] = [x for x in ed["textos"] if x["id"] != o.get("id")]; nota = f"borrado texto {o.get('id')}"
    elif op == "camara":             # fuerza un rol de cámara en [a, b]; «auto» lo devuelve a la elección automática
        a, b = sorted((num("a"), num("b"))); rol = o.get("rol")
        if rol not in ("cara", "producto", "neutro", "auto"): raise ValueError("rol de cámara inválido")
        cams = []
        for c in ed["camaras"]:
            cams += [{"a": x, "b": y, "rol": c["rol"]} for x, y in restar([[c["a"], c["b"]]], a, b)]
        if rol != "auto": cams.append({"a": round(a, 2), "b": round(b, 2), "rol": rol})
        ed["camaras"] = sorted(cams, key=lambda c: c["a"]); nota = f"cámara {rol} {a:.1f}–{b:.1f} s"
    elif op == "deshacer":
        # Ctrl+Z seguidos van cada vez más atrás: se parte de la versión a la que volvió el deshacer anterior
        v = int(o.get("version") or (base or ed["version"]) - 1)
        prev = leer_json(dir_proyecto(slug) / "12_project" / "ediciones" / f"v{v:03d}.json")
        if not prev: raise ValueError("no hay versión anterior")
        ed = prev; ed["base"] = v; nota = f"vuelta a la v{v:03d}"
    else:
        raise ValueError("operación desconocida")
    return guardar_edicion(slug, ed, nota)


def tramos(ed, dur, minimo=0.35):
    """Lo que queda de la toma: todo menos los cortes activos. Tramos de menos de «minimo» s se ven como parpadeo: afuera."""
    keep = [[0.0, dur]]
    for c in ed["cortes"]:
        if c["activo"]:
            keep = restar(keep, c["a"], c["b"])
    return [k for k in keep if k[1] - k[0] >= minimo]


# ------------------------------------------------------------------ render
PROD = re.compile(r"\bmir[aeé]n?\b|\bac[aá]\b|\bah[ií]\b|\besto\b|\bpueden ver|\bse ve\b|\btiene\b|\btrae\b|\bcaja|\bbolsa|\bbase\b|\bcable|"
                  r"\bbot[oó]n|\bsensor|\bluces|\bconect|\benchuf|\babr[ií]|\bmanual|\bpesa\b|\bgramos|\bagarra|\bprendido|\bp[aá]gina|\bprueba", re.I)
CARA = re.compile(r"suscr[ií]b|\blike\b|coment|publicidad|promoci[oó]n|\bno s[eé]\b|\bche\b|vergüenza|me pregunto|\bcaro\b|car[ií]simo|"
                  r"\bojal[aá]|ganas|opini[oó]n|\bcreo\b|\bpienso\b|recomiendo|\bvale la pena", re.I)
ENCUADRES = {"producto": [("producto", 1.0), ("producto", 1.35)], "cara": [("cara", 1.0), ("cara", 1.3)], "neutro": [("neutro", 1.0), ("neutro", 1.2)]}


def planos(cfg, ed, frases):
    """Cada tramo se parte en planos de 1,6–3,2 s que arrancan en el inicio de una frase (o cada ~2,3 s). El rol sale de lo
    que se dice en el plano: mostrar → producto, hablar a cámara → cara, nada claro → neutro. Nunca dos planos iguales."""
    roles = {f["rol"]: k for k, f in cfg["fuentes"].items()}
    roles.setdefault("neutro", "programa")
    inicios = [f["a"] - 0.1 for f in frases]
    dicho = lambda a, b: " ".join(p["w"] for f in frases for p in f["palabras"] if p["s"] < b and p["e"] > a)
    forzado = lambda a, b: next((c["rol"] for c in ed["camaras"] if c["a"] < b and c["b"] > a), None)
    out, t, ult, cuenta = [], 0.0, None, {k: 0 for k in ENCUADRES}
    for a, b in tramos(ed, float(cfg["duracion"])):
        cs = [a]
        while b - cs[-1] > 3.2:
            c = [x for x in inicios if 1.6 <= x - cs[-1] <= 3.2 and b - x >= 1.6]
            cs.append(min(c, key=lambda x: abs(x - cs[-1] - 2.3)) if c else cs[-1] + max(1.6, min(2.3, (b - cs[-1]) / 2)))
        if len(cs) > 1 and b - cs[-1] < 1.0: cs.pop()          # sin planos de parpadeo al final del tramo
        cs.append(b)
        for s0, s1 in zip(cs, cs[1:]):
            rol = forzado(s0, s1)
            if rol is None:
                txt = dicho(s0, s1); tp, tf = bool(PROD.search(txt)), bool(CARA.search(txt))
                rol = "cara" if tf and not tp else "producto" if tp else ("cara", "neutro")[len(out) % 2]
            if rol not in roles: rol = "neutro"
            enc = ENCUADRES[rol][cuenta[rol] % 2]
            if (roles[rol], enc[1]) == ult: cuenta[rol] += 1; enc = ENCUADRES[rol][cuenta[rol] % 2]
            cuenta[rol] += 1; ult = (roles[rol], enc[1])
            out.append({"fuente": roles[rol], "rol": rol, "zoom": enc[1], "s": round(s0, 3), "d": round(s1 - s0, 3), "t": round(t, 3)})
            t += s1 - s0
    return out


def a_edicion(pl, s):
    """Segundo de la toma → segundo del video editado (None si quedó cortado)."""
    for p in pl:
        if p["s"] <= s < p["s"] + p["d"]:
            return p["t"] + s - p["s"]
    return None


def render(slug, calidad="360", log=print):
    cfg, ed = cargar(slug), leer_edicion(slug); d = dir_proyecto(slug)
    frases = leer_json(d / "12_project/analysis/frases.json", [])
    W, H = (1920, 1080) if calidad == "1080" else (640, 360)
    pl = planos(cfg, ed, frases)
    if not pl: raise ValueError("no queda nada sin cortar")
    cache = d / "10_work" / "estudio" / f"planos_{H}"; cache.mkdir(parents=True, exist_ok=True)
    work = pathlib.Path(tempfile.mkdtemp(prefix="estudio_", dir=d / "10_work" / "estudio"))
    # 1) cada plano, cacheado por hash: si cambia un corte, solo se rehacen los planos que cambiaron
    archivos = []
    for i, p in enumerate(pl):
        f = cfg["fuentes"][p["fuente"]]; fr = round((p["t"] + p["d"]) * FPS) - round(p["t"] * FPS)
        z = p["zoom"]; cw, ch = int(W / z) // 2 * 2, int(H / z) // 2 * 2
        vf = f"scale={W}:{H}" + (",hflip,vflip" if f.get("girar") else "") + (f",crop={cw}:{ch}:{(W - cw) // 2}:{int((H - ch) * 0.4)},scale={W}:{H}" if z > 1 else "")
        key = hashlib.md5(f"{f['archivo']}|{p['s']}|{fr}|{vf}|{encoder()}".encode()).hexdigest()[:16]
        out = cache / f"{key}.mp4"
        if not out.exists():
            run(["ffmpeg", "-v", "error", "-y", "-ss", f"{p['s']:.3f}", "-i", f["archivo"], "-frames:v", str(fr), "-an",
                 "-vf", vf + f",fps={FPS},format=yuv420p", *encoder(), "21" if H > 360 else "27", "-g", "60", "-r", str(FPS), str(out)])
        archivos.append(out)
        if i % 10 == 0: log(f"planos {i}/{len(pl)}")
    (work / "lista.txt").write_text("".join(f"file '{a.as_posix()}'\n" for a in archivos), encoding="utf-8")
    base = work / "base.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(work / "lista.txt"), "-c", "copy", str(base)])
    total = pl[-1]["t"] + pl[-1]["d"]
    # 2) audio: la voz de cada tramo con fundidos cortos, respiraciones −8 dB entre frases, y −14 LUFS
    habla = [(f["a"] - 0.05, f["b"] + 0.35) for f in frases]
    voz = np.frombuffer(run(["ffmpeg", "-v", "error", "-i", str(d / "10_work/audio/voz_c.wav"), "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"]).stdout, np.float32)
    mix = np.zeros(int(total * SR) + SR, np.float32); n = int(0.012 * SR)
    for a, b in tramos(ed, float(cfg["duracion"])):
        x = voz[int(a * SR):int(b * SR)].copy()
        g = np.full(len(x), 0.4, np.float32)
        for h0, h1 in habla:
            if h1 > a and h0 < b: g[max(0, int((h0 - a) * SR)):max(0, int((h1 - a) * SR))] = 1.0
        k = int(0.03 * SR); x *= np.convolve(g, np.ones(k) / k, "same").astype(np.float32)
        if len(x) > 2 * n: x[:n] *= np.linspace(0, 1, n); x[-n:] *= np.linspace(1, 0, n)
        en = a_edicion(pl, a + 1e-3) or 0.0; i = int(round(en * SR)); j = min(len(mix), i + len(x)); mix[i:j] += x[:j - i]
    crudo = work / "voz.wav"
    run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-", str(crudo)], input=mix.tobytes())
    def lufs(f):
        st = run(["ffmpeg", "-hide_banner", "-i", str(f), "-af", "ebur128", "-f", "null", "-"], text=True).stderr
        return float(re.search(r"I:\s+(-?[\d.]+) LUFS", st[st.rfind("Summary:"):]).group(1))
    li = lufs(crudo); gan = -14 - li + 1.3; mezcla = work / "mezcla.wav"
    for _ in range(3):               # ganancia + limitador con sobremuestreo (el AAC sube los picos); el limitador come nivel: se repite
        run(["ffmpeg", "-v", "error", "-y", "-i", str(crudo), "-af", f"volume={gan:.2f}dB,aresample=192000,alimiter=limit=0.76:attack=1:release=50:level=false,aresample={SR}", str(mezcla)])
        falta = -14 - lufs(mezcla)
        if abs(falta) < 0.4: break
        gan += falta
    # 3) textos: el lower third oficial, anclado al segundo de la toma donde se dice el dato
    from lower_third import lower_third
    ins, fc, last, m = [], [], "[0:v]", 0
    for k, tx in enumerate(ed["textos"]):
        en = a_edicion(pl, tx["t"])
        if en is None: continue
        png = work / f"t{k}.png"; lower_third(1920, 1080, tx["rotulo"], tx["dato"]).resize((W, H)).save(png)
        ins += ["-loop", "1", "-framerate", str(FPS), "-t", f"{tx['dur']:.2f}", "-itsoffset", f"{en:.3f}", "-i", str(png)]
        m += 1
        fc.append(f"[{m}:v]format=rgba,fade=t=in:st={en:.3f}:d=0.15:alpha=1,fade=t=out:st={en + tx['dur'] - 0.15:.3f}:d=0.15:alpha=1[g{k}];"
                  f"{last}[g{k}]overlay=0:0:eof_action=pass[v{k}]"); last = f"[v{k}]"
    carpeta = "final" if calidad == "1080" else "previews"
    salida = d / "11_exports" / carpeta / f"{slug}_v{ed['version']:03d}_{H}p.mp4"
    vid = (["-filter_complex", ";".join(fc), "-map", last, *encoder(), "21" if H > 360 else "27"] if fc else ["-map", "0:v", "-c:v", "copy"])
    run(["ffmpeg", "-v", "error", "-y", "-i", str(base), *ins, "-i", str(mezcla), *vid, "-map", f"{m + 1}:a",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", str(salida)])
    cuerpo = [p["d"] for p in pl]; por_min = {}
    for p in pl: por_min[int(p["t"] // 60)] = por_min.get(int(p["t"] // 60), 0) + 1
    rep = {"salida": salida.name, "version": ed["version"], "duracion_s": round(total, 1), "planos": len(pl),
           "plano_promedio_s": round(float(np.mean(cuerpo)), 2), "plano_mas_largo_s": round(max(cuerpo), 2),
           "cortes_por_minuto": por_min, "lufs_antes": li}
    guardar_json(d / "12_project" / "ultimo_render.json", rep)
    for f in work.glob("*"): f.unlink()
    work.rmdir()
    return rep
