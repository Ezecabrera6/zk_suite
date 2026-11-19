"""Primer corte automático de una toma multicámara desde la transcripción pausa por pausa (edl/tx_por_pausas.py).
- Todo tramo de voz entra como segmento (tiempos de la toma; las tres cámaras están sincronizadas).
- Quedan «fuera» (no se borran, el visor los muestra tachados): retomas (frase muy parecida dicha después),
  muletillas sueltas, alucinaciones de Whisper sobre ruidos (tipeo) y, si se pide, una tanda de despedidas repetidas.
- Cámara sugerida: «cara» hasta --cara-hasta segundos (el gancho a cámara); después se alterna
  «programa» (cenital con recuadro) y «cenital» (cruda rotada, más cerca) para que haya cortes.
uso: python edl_auto.py <video>/12_project [--cara-hasta 52] [--chau 1250-1296] [--forzar]
     lee analysis/tx_pausas_toma.txt y escribe edl_multicam.json (solo si no existe, o con --forzar)
"""
import difflib, json, pathlib, re, sys

P = pathlib.Path(sys.argv[1])
def opt(k, d): return sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
CARA_HASTA = float(opt("--cara-hasta", "0"))
CHAU = tuple(map(float, opt("--chau", "-1--1").split("-", 1))) if "--chau" in sys.argv else None
TX = P / "analysis" / "tx_pausas_toma.txt"
OUT = P / "edl_multicam.json"
PAD_A, PAD_B, UNIR = 0.12, 0.22, 0.60   # aire antes/después de la voz y hueco máximo para unir frases seguidas

segs = []
for l in TX.read_text(encoding="utf-8").splitlines():
    m = re.match(r"(\d+):([\d.]+)-(\d+):([\d.]+)\s+(.*)", l)
    if m:
        a = int(m[1]) * 60 + float(m[2]); b = int(m[3]) * 60 + float(m[4])
        segs.append({"a": a, "b": b, "txt": m[5].strip()})

def norm(s):
    return re.sub(r"[^a-záéíóúñ0-9 ]", "", s.lower())

MULETILLA = re.compile(r"^(bueno|eh+|ehm+|ok|ah+|gracias|gracias por ver el video|bueno, gente|a ver|ahora|nada|bien|chau|bye)[.,!?… ]*$", re.I)
for k, s in enumerate(segs):
    t = s["txt"]; why = None
    if re.search(r"[^\x00-ɏ¿¡«»…–—’“”]", t):
        why = "Whisper inventó texto sobre el tipeo"
    elif MULETILLA.match(norm(t).strip() + "") or MULETILLA.match(t):
        why = "muletilla suelta"
    elif re.search(r"\bchau\b", t, re.I) and CHAU and CHAU[0] < s["a"] < CHAU[1]:
        why = "tanda de despedidas del final"
    else:  # retoma: la misma frase vuelve a aparecer dentro de los 90 s siguientes
        for o in segs[k + 1:]:
            if o["a"] - s["b"] > 90: break
            if len(norm(t)) > 12 and difflib.SequenceMatcher(None, norm(t), norm(o["txt"])).ratio() > 0.72:
                why = f"retoma (se repite en {int(o['a'] // 60)}:{o['a'] % 60:04.1f})"; break
    s["fuera"] = bool(why)
    if why: s["por_que"] = why

# unir frases seguidas que entran, para no tener mil segmentos de medio segundo
out = []
for s in segs:
    a, b = max(0, s["a"] - PAD_A), s["b"] + PAD_B
    if out and not s["fuera"] and not out[-1]["fuera"] and a - out[-1]["b"] < UNIR and (b - out[-1]["a"]) < 9:
        out[-1]["b"] = b; out[-1]["txt"] += " " + s["txt"]
    else:
        d = {"a": round(a, 2), "b": round(b, 2), "txt": s["txt"], "fuera": s["fuera"]}
        if s.get("por_que"): d["por_que"] = s["por_que"]
        out.append(d)

turno = 0
for s in out:
    s["a"], s["b"] = round(s["a"], 2), round(s["b"], 2)
    if s["a"] < CARA_HASTA:
        s["cam"] = "cara"
    else:
        s["cam"] = ("programa", "cenital")[turno % 2]; turno += 1 if not s["fuera"] else 0

if OUT.exists() and "--forzar" not in sys.argv:
    sys.exit(f"{OUT.name} ya existe (tiene las elecciones hechas a mano en el visor). Usá --forzar para pisarlo.")
dentro = [s for s in out if not s["fuera"]]
OUT.write_text(json.dumps({"version": "auto_v1", "segmentos": out}, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(out), "segmentos ·", len(dentro), "adentro ·", f"{sum(s['b'] - s['a'] for s in dentro) / 60:.1f} min de salida")
