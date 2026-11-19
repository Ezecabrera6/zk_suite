"""CONTROL DE CALIDAD ANTES DE SUBIR UN BORRADOR (pedido del creador, 25/10/2026). Se corre sobre el render FINAL.
Si encuentra un solo problema, sale con código 1 y el video NO se sube hasta corregirlo y volver a correrlo.

Revisa:
1. Frase por frase (cada tramo de voz entre pausas se transcribe solo, sin contexto: así Whisper no se saltea nada):
   - muletillas de toma: «vamos de nuevo», «vámonos», «repito», «mamá», «la puta», «uno, dos, tres», claquetas («B13», «round 2 en off 4»…);
   - arranques cortados: una frase que es el comienzo de la siguiente («este round lo ganó el…» + «este round lo ganó el A16»);
   - frases colgadas: terminan en «…» o en palabra que no cierra («el», «de», «que», «y», «a», «con», «para»…);
   - palabras o sonidos sueltos (tramos de 1 palabra que no son un título como «Round 1»).
2. Técnica: cuadros negros, loudness integrado (−14 ± 1 LUFS) y true peak (≤ −1 dBTP).
uso: python control_borrador.py VIDEO_FINAL.mp4 [informe.txt]"""
import os, glob, sys, re, subprocess, tempfile, wave
import numpy as np
for d in glob.glob(os.path.expandvars(r"%APPDATA%\Python\Python312\site-packages\nvidia\*\bin")):
    os.add_dll_directory(d); os.environ["PATH"] = d + os.pathsep + os.environ["PATH"]
from faster_whisper import WhisperModel

src = sys.argv[1]; out = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(src)[0] + "_CONTROL.txt"
MULETILLAS = re.compile(r"vamos de nuevo|empe[cz]amos de nuevo|empiezo de nuevo|\bde nuevo\b|\botra vez\b|vamos a (?:ver|de nuevo)|\bv[aá]monos\b|\brepito\b|\bmam[aá]\b|la puta|la concha|"
                        r"uno,? dos,? tres|\bB\d+\b|en off|\bclaqueta|estoy hablando|por qu[eé] (?:hablo|me cuesta)|\bdios\b", re.I)
COLGADAS = {"el", "la", "los", "las", "de", "del", "que", "y", "a", "con", "para", "por", "un", "una", "en", "es", "se", "lo", "al", "mi", "tu", "su"}
TITULOS = re.compile(r"^(round \d|ronda \d|cap[ií]tulo|\d+\.?)$", re.I)
ALUCINACIONES = {"gracias", "ok", "va", "subtítulos realizados por la comunidad de amara.org", "música"}

def norm(s): return re.sub(r"[^\wáéíóúñü ]", "", s.lower()).strip()
def mmss(t): return f"{int(t // 60)}:{t % 60:05.2f}"

# ---- 1. voz por tramos
wav = os.path.join(tempfile.gettempdir(), "ctrl.wav")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-map", "0:a:0", "-ac", "1", "-ar", "16000", wav], check=True)
w = wave.open(wav); sr = w.getframerate(); x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
dur = len(x) / sr
hop = int(sr * 0.02); rms = 20 * np.log10(np.sqrt(np.convolve(x ** 2, np.ones(hop) / hop, "same")[::hop] + 1e-12))
v = rms > -38
runs, cur = [], None
for f, on in enumerate(v):
    t = f * 0.02
    if on:
        if cur is None: cur = [t, t]
        elif t - cur[1] > 0.30: runs.append(cur); cur = [t, t]
        else: cur[1] = t
if cur: runs.append(cur)
runs = [r for r in runs if r[1] - r[0] > 0.12 and r[0] < dur - 6.5]   # los últimos ~6 s son el outro (música)
m = WhisperModel("large-v3", device="cuda", compute_type="int8_float16")
frases = []
for a, b in runs:
    seg = x[int(max(0, a - 0.12) * sr):int((b + 0.22) * sr)]
    segs, _ = m.transcribe(seg, language="es", vad_filter=False, condition_on_previous_text=False, temperature=0.0)
    txt = " ".join(s.text.strip() for s in segs).strip()
    if txt: frases.append((a, b, txt))

problemas = []
for i, (a, b, txt) in enumerate(frases):
    n = norm(txt); palabras = n.split()
    if n in ALUCINACIONES: continue
    if MULETILLAS.search(txt): problemas.append((a, "muletilla de toma", txt))
    if txt.rstrip().endswith(("...", "…")) or (palabras and palabras[-1] in COLGADAS):
        # en tramos largos Whisper corta con «…» aunque la frase siga: se repasan los últimos 6 s solos
        # y el final de frase que baja de volumen queda fuera del tramo: se estira hasta 1,5 s sin pisar el siguiente
        fin = min(b + 1.5, frases[i + 1][0] - 0.05) if i + 1 < len(frases) else b + 1.5
        cola = x[int(max(a, b - 6) * sr):int(max(fin, b + 0.22) * sr)]
        ct = " ".join(s.text.strip() for s in m.transcribe(cola, language="es", vad_filter=False, condition_on_previous_text=False, temperature=0.0)[0]).strip()
        cp = norm(ct).split()
        if ct.rstrip().endswith(("...", "…")) or not cp or cp[-1] in COLGADAS:
            problemas.append((a, "frase colgada / arranque cortado", txt + "  [final: " + ct + "]"))
    if len(palabras) == 1 and not TITULOS.match(n): problemas.append((a, "palabra o sonido suelto", txt))
    # autocorrección dentro de la frase: «tienen el mismo, prácticamente el mismo» (pedido 25/10)
    pares = list(zip(palabras, palabras[1:]))
    # una sola palabra en el medio: con dos ya son recursos o enumeraciones («vos no comprás unos…, vos comprás unos», «con el 520 y con el 720»)
    if any(pares[j] == pares[k] for j in range(len(pares)) for k in range(j + 2, min(j + 4, len(pares)))):
        problemas.append((a, "repetición dentro de la frase (autocorrección)", txt))
    if i + 1 < len(frases):
        sig = norm(frases[i + 1][2]).split()
        k = min(len(palabras), 4)
        if k >= 2 and sig[:k] == palabras[:k] and frases[i + 1][0] - b < 12:
            problemas.append((a, "frase repetida (retoma)", f"{txt}  →  {frases[i + 1][2]}"))

# ---- 2. técnica
r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", src, "-an", "-vf", "blackdetect=d=0.3:pix_th=0.05", "-f", "null", "-"], capture_output=True, text=True).stderr
for s0 in re.findall(r"black_start:([\d.]+)", r): problemas.append((float(s0), "cuadro negro", ""))
r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", src, "-vn", "-af", "ebur128=peak=true:framelog=quiet", "-f", "null", "-"], capture_output=True, text=True).stderr
summ = r[r.rfind("Summary:"):]; I = float(re.search(r"I:\s+(-?[\d.]+)", summ).group(1)); TP = float(re.search(r"Peak:\s+(-?[\d.]+)", summ).group(1))
if abs(I + 14) > 1: problemas.append((0, "loudness fuera de −14 ± 1 LUFS", f"{I} LUFS"))
if TP > -1: problemas.append((0, "true peak por encima de −1 dBTP", f"{TP} dBTP"))

with open(out, "w", encoding="utf-8") as fo:
    fo.write(f"CONTROL DE BORRADOR · {os.path.basename(src)}\nVeredicto: {'APROBADO' if not problemas else 'NO SE SUBE'} · {len(problemas)} problema(s) · {I} LUFS · TP {TP} dB\n\n")
    for t, tipo, txt in sorted(problemas): fo.write(f"  {mmss(t)}  {tipo}: {txt}\n")
    fo.write("\nTRANSCRIPCIÓN FRASE POR FRASE\n" + "".join(f"  {mmss(a)}  {txt}\n" for a, b, txt in frases))
print(open(out, encoding="utf-8").read().split("TRANSCRIPCIÓN")[0])
sys.exit(1 if problemas else 0)
