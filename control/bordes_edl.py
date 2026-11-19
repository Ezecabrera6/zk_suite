"""Revisa los cortes del EDL antes de renderizar (pedido 25/10/2026: «están mal cortadas las palabras»).
uso: python bordes_edl.py <video>/12_project [salida_uniones.txt]

1. FINALES: el tramo tiene que terminar en silencio. Whisper adelanta las marcas 0,3–0,5 s y se comía
   «A16», «diferencia», «alrededor». Propone hasta dónde estirar.
2. INICIOS: el tramo no puede arrancar con la voz ya sonando (cola de la palabra anterior pegada, como
   «…gustar ‿ Hay una guerra»). Propone desde dónde arrancar.
3. UNIONES: escribe cada unión «…final del tramo | principio del siguiente», transcripta por separado,
   para LEERLA ENTERA antes de renderizar: cada frase tiene que tener sentido, sin cortes raros ni incómodos.
Un tramo cuenta como pegado solo si el SIGUIENTE en el EDL arranca donde termina él (orden de la fuente)."""
import os, sys, glob
import numpy as np
for d in glob.glob(os.path.expandvars(r"%APPDATA%\Python\Python312\site-packages\nvidia\*\bin")):
    os.add_dll_directory(d); os.environ["PATH"] = d + os.pathsep + os.environ["PATH"]
from faster_whisper import WhisperModel, decode_audio

proj = sys.argv[1]
salida = sys.argv[2] if len(sys.argv) > 2 else os.path.join(proj, "analysis", "uniones_edl.txt")
sys.path.insert(0, os.path.join(proj, "narrado"))
import edl_manual as E

x = decode_audio(os.path.join(proj, "analysis", "voz16k.wav")); sr = 16000
def db(t): r = x[int(max(t, 0) * sr):int((t + 0.03) * sr)]; return 20 * np.log10(np.sqrt((r ** 2).mean()) + 1e-9) if len(r) else -180
m = WhisperModel("large-v3", device="cuda", compute_type="int8_float16")
pad = np.zeros(sr // 2, dtype=np.float32)
def tx(a, b): return " ".join(s.text.strip() for s in m.transcribe(np.concatenate([pad, x[int(max(a, 0) * sr):int(b * sr)], pad]), language="es", condition_on_previous_text=False)[0]).strip()

import re
# pedido 25/10: «siempre que diga empezamos de nuevo es porque me equivoqué y regrabo»: lo de antes del marcador se descarta
RETOMA = re.compile(r"(?:vamos|empe[cz]amos|empiezo) de nuevo|\bde nuevo\b|\botra vez\b|vamos a ver|\bmam[aá]\b|\bv[aá]monos\b", re.I)
K = E.KEEP
malos, uniones = 0, []
for i, k in enumerate(K):
    a, b = k[1], k[2]
    # 0. toma descartada: el tramo termina justo antes de un marcador de retoma, o lo contiene
    despues, adentro = tx(b, b + 1.6), tx(a, b)   # solo lo pegado al corte: más lejos ya es otra frase
    if RETOMA.search(despues) and not (i + 1 < len(K) and abs(K[i + 1][1] - b) < 0.1):
        malos += 1; print(f"RETOMA placa {k[0]!s:>4}  {a:.2f}-{b:.2f} es la toma DESCARTADA: después viene «{despues}». Usar la toma siguiente")
    if RETOMA.search(adentro):
        malos += 1; print(f"RETOMA placa {k[0]!s:>4}  {a:.2f}-{b:.2f} tiene un marcador adentro: «{adentro}»")
    prev = K[i - 1] if i else None
    sig = K[i + 1] if i + 1 < len(K) else None
    pegado_sig = sig is not None and abs(sig[1] - b) < 0.1
    pegado_prev = prev is not None and abs(prev[2] - a) < 0.1
    # 1. final
    if not pegado_sig and max(db(t) for t in np.arange(b, b + 0.15, 0.03)) > -40:
        lim = min(b + 0.6, sig[1] - 0.05) if sig is not None and sig[1] > b else b + 0.6
        fin = next((t for t in np.arange(b, lim, 0.03) if db(t) < -50), None)
        malos += 1
        print(f"FIN    placa {k[0]!s:>4}  {a:.2f}-{b:.2f} sigue sonando: «{tx(max(a, b - 4), b)}»")
        print(f"        estirar a {fin:.2f}: «{tx(max(a, fin - 4), fin)}»" if fin else "        sin silencio cerca: revisar a mano")
    # 2. inicio
    if not pegado_prev and max(db(t) for t in np.arange(a - 0.12, a, 0.03)) > -40:
        ini = next((t for t in np.arange(a, a - 0.6, -0.03) if db(t) < -50), None)
        malos += 1
        print(f"INICIO placa {k[0]!s:>4}  {a:.2f}-{b:.2f} arranca con voz sonando: «{tx(a, min(b, a + 4))}»")
        print(f"        arrancar en {ini:.2f}: «{tx(ini, min(b, ini + 4))}»  (ojo: puede traer la cola de otra palabra)" if ini else "        palabra pegada a la anterior: buscar otra toma o cortar en otro lado")
    # 3. unión con el siguiente
    if sig is not None and not pegado_sig:
        uniones.append(f"[{i + 1:>2}→{i + 2:<2}] …{tx(max(a, b - 3.5), b)}  ||  {tx(sig[1], min(sig[2], sig[1] + 3.5))}…")

open(salida, "w", encoding="utf-8").write("UNIONES DEL EDL — leer cada una: ¿la frase tiene sentido? ¿hay un corte raro o incómodo?\n\n" + "\n".join(uniones) + "\n")
print(f"\n{len(uniones)} uniones escritas en {salida} (LEERLAS antes de renderizar)")
print(f"{malos} borde(s) para revisar" if malos else "Bordes OK: todos los tramos empiezan y terminan en silencio")
sys.exit(1 if malos else 0)
