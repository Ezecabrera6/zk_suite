"""Corte del unboxing M999 (toma 2026-11-18 00-35-59, 16:59, grabada sin guion).
Se arma por renglones de analysis/tx_pausas_toma.txt (número de renglón = línea del archivo, desde 1).
Criterio (18/11/2026): natural, divertido y humano. Los gatos y los chistes QUEDAN; se sacan solo las retomas,
las alucinaciones de Whisper («¡Gracias!», «¡SUSCRIBETE!») y los silencios largos.
Cada tramo: (renglón_desde, renglón_hasta, opciones). Dentro de un tramo, los huecos entre frases de más de HUECO s
se acortan a HUECO (salvo «huecos»: n, que deja hasta n s, para lo que pasa en cuadro sin hablar: gatos, ASMR, clics).
KEEP sale como (etiqueta, desde_s, hasta_s, cámara) para bordes_edl.py y chequeo_tramos.py de la plantilla."""
import re, pathlib
import os
TX = pathlib.Path(os.environ.get("ZK_PROYECTO", ".")) / "12_project" / "analysis" / "tx_pausas_toma.txt"   # salida de edl/tx_por_pausas.py
L = [None]
for l in TX.read_text(encoding="utf-8").splitlines():
    m = re.match(r"(\d+):([\d.]+)-(\d+):([\d.]+)\s*(.*)", l)
    L.append((int(m[1]) * 60 + float(m[2]), int(m[3]) * 60 + float(m[4]), m[5].strip()))
PAD_A, PAD_B, HUECO = 0.15, 0.25, 0.9

TRAMOS = [
    # ---- GANCHO (se reordena): el chiste de entrada, qué compró, lo malo adelantado y el «suscríbanse»
    "BLOOPER",   # pedido 18/11: «el clip del mouse cayéndose es como algo en blanco y negro al principio, un blooper» (con piiip)
    (1, 1, {"cam": "cara"}),   # pedido 18/11 (v006 0:00: sin el recuadro raro mientras habla   # pedido 18/11: en el chiste SIEMPRE su cara; la base prendida (7:35 de la toma en recuadro                                   # «como si fuera millonario… suscríbanse a la…» (queda entera)
    (2, 5, {"cam": "alterna", "prod": 59.0}),   # pedido 18/11 (v006 0:08: «cara sola y la caja» → cara a pantalla, alternada con la caja ya fuera de la bolsa (sin etiqueta)   # la caja con «KING ULTRA» en recuadro; «me compré un mouse bastante caro… Redragon… esto no es promoción»
    # (190, 191): adelanto de lo malo, SACADO. pedido 18/11 (v006: «este clip llega de la nada y es raro» (otra luz y otra postura). Lo malo queda en el cuerpo.
    (8, 8, {}),                                   # «no voy a quedar pobre si no se suscriben. Suscríbanse.»
    "LOGO",
    # ---- UNBOXING
    # PRIVACIDAD (18/11): en la etiqueta del envío se leen datos personales (nombre, código postal, número de envío).
    # Mientras la bolsa está en la mesa (hasta ~57 s de la toma) va su cara y la cenital solo en recuadro chico (ilegible).
    # pedido 18/11 (v005: «acá el unboxing en grande y mi cara chica». OJO: con la cenital grande la etiqueta se lee → falta tapar antes del final.
    # v006 0:39 «el cuadro está raro»: el zoom alternado cortaba la bolsa → plano abierto fijo.
    (10, 13, {"cam": "producto", "vis": "cenital", "pip": ("cara", None)}), (14, 18, {"huecos": 3.0, "cam": "producto", "vis": "cenital", "pip": ("cara", None)}),
    (19, 21, {}), (22, 25, {}), (26, 29, {}), (31, 31, {}),
    (35, 40, {"huecos": 1.5}), (41, 44, {"huecos": 1.5}),
    # ---- ACCESORIOS
    (46, 52, {}), (54, 60, {}), (61, 63, {}), (64, 66, {}), (67, 70, {}),
    (74, 77, {}), (79, 82, {}), (83, 86, {}),
    # ---- EL MOUSE
    (87, 87, {}), (88, 89, {}), (90, 95, {}),
    (97, 102, {"huecos": 4.0, "cam": "cara"}),    # el gato viene a saludar (está en la StreamCam)
    (103, 110, {}), (111, 114, {}), (115, 118, {}),
    (119, 124, {"huecos": 2.5}),   # «otro de los gatos quiere venir a saludar»
    (125, 132, {}), (133, 135, {}),
    (136, 139, {}),   # el gato jugando con la caja. v009 5:11/5:16: sin los ruidos sueltos ni cuando se acomoda (huecos normales)
    # ---- LA BASE DE CARGA
    (140, 145, {"huecos": 2.0}), (146, 149, {}),
    (150, 160, {"huecos": 1.5}), (161, 161, {}), (164, 165, {}),
    (166, 167, {}), (169, 176, {"huecos": 2.0}), (178, 178, {}), (179, 180, {}),
    (181, 186, {"huecos": 2.0}), (187, 194, {"huecos": 1.5}),
    (195, 196, {}), (198, 198, {}), (200, 200, {}),
    # ---- PROBÁNDOLO
    (201, 207, {}), (208, 214, {"huecos": 1.5}), (217, 217, {}), (219, 220, {}), (223, 225, {}),
    (228, 232, {}), (233, 235, {}), (237, 237, {}), (238, 242, {}), (244, 247, {}), (248, 250, {}),
    (252, 255, {}), (257, 261, {}),
    (266, 266, {}), (268, 269, {}), (271, 273, {}), (276, 281, {}),   # la página de prueba: «resultado regular»
    (283, 285, {}), (286, 287, {}),
    (291, 293, {"huecos": 1.5}), (294, 296, {}), (297, 297, {}), (299, 299, {}),
    (300, 304, {"huecos": 3.0}),                  # velocidad de clic: se escuchan los clics
    (305, 305, {}),
    # ---- CIERRE
    (307, 311, {}), (313, 314, {}),
    "OUTRO",
]
# Blooper de apertura (s de la toma, cenital en blanco y negro): el mouse se cae de la base a los 553,8 s → ahí el piiip.
# El insulto NO se censura: pedido 18/11 «no saques el insultoooo».
BLOOPER, BLOOPER_PIIP = (551.5, 554.6), 553.8
# Cámara por frase (renglón de la toma), pedida en el visor (v009, 18/11): cara / producto / ancho (cenital
# abierta para que entre todo lo que muestra) / alterna (cara y producto, para no quedar >2 s en lo mismo).
CAM = {44: "cara",                                    # 1:40 «reboleado todo»: su cara, después sigue la caja
       61: "ancho", 62: "ancho",                      # 2:23 el largo del cable
       79: "alterna", 80: "alterna", 81: "alterna",   # 2:52 mucho rato en lo mismo
       91: "cara",                                    # 3:17 «mirá, tenelo»: chiste a cámara
       107: "cara", 108: "cara", 109: "cara", 110: "cara",   # 3:57 dice datos sin mostrar nada
       150: "ancho", 151: "ancho",                    # 5:43 «che, está muy buena»: la base
       183: "ancho", 184: "ancho", 185: "ancho", 187: "ancho",   # 6:52 «¿se caerá?»: el mouse
       230: "ancho", 231: "ancho", 232: "ancho"}      # 8:31 muestra los botones
# Efectos sueltos (renglón, segundos desde que arranca la frase, archivo en gfx/sfx, duración): sin cartel.
SFX = [(91, 1.9, "cartoon_dazzle_birds_746.mp3", 1.8)]   # 3:17 le da el mouse a nadie: pajaritos de «está loco»
# Carteles: APAGADOS. pedido 18/11: «todos los carteles son muy hechos por IA» (también el Fn+F9) y rechazó las 5
# propuestas de 10_work/gfx/propuestas. Hasta que apruebe un estilo, el video sale sin carteles. La lista de la v009:
GRAF_V009 = [("m01_precio", 3), ("m03_no_publi", 59), ("m04_malo", 190), ("m21_sec_unboxing", 10), ("m02_nombre", 19),
        ("m05_dpi", 21), ("m22_sec_accesorios", 46), ("like", 52), ("m24_sec_la_base_de_carga", 74),
        ("m23_sec_el_mouse", 87), ("m06_peso", 90), ("m10_invitado", 99), ("m07_modos", 107), ("m08_ips", 111),
        ("m09_bateria", 117), ("m11_invitado2", 194), ("m25_sec_probándolo", 201), ("m12_botones", 230), ("m13_tarjeta_fizz", 234)]
# Pendientes del visor que dependen del estilo: tarjeta del Fizz al nombrar el teclado (renglón 57, también tarjeta de
# YouTube en Studio), explicar «750 IPS» (renglón 111) y que «6 botones» entre cuando lo dice (renglón 230, ~1,6 s).
# pedido 18/11 aprobó el lower third en Consolas sin línea de color (10_work/gfx/gen_lt.py. Sin rótulos de sección ni «like».
# (id, renglón, segundos desde que arranca la frase hasta que dice el dato; estimados por la posición en el texto)
GRAF = [("lt_precio", 3, 1.5), ("lt_modelo", 19), ("lt_dpi", 21, 1.3), ("lt_fizz", 57, 2.5), ("lt_nopubli", 59, 1.5),
        ("lt_peso", 90), ("lt_invitado", 99), ("lt_modos", 107, 0.5), ("lt_ips", 111, 1.8), ("lt_hz", 112, 1.5),
        ("lt_bateria", 117, 0.5), ("lt_malo", 190), ("lt_gato", 194, 0.5),
        ("lt_bateria", 228, 2.0), ("lt_dpi", 228, 3.4), ("lt_botones", 230, 1.8),   # v009 8:26: cuando enumera, cartel por dato
        ("lt_fizz", 234, 1.0)]
# Gráficos: (id, renglón donde se dice). Entran 0,25 s después de que arranca esa frase en el corte.


# Bordes corregidos con bordes_edl.py (18/11): {borde viejo: borde nuevo}. Finales estirados hasta el silencio,
# inicios adelantados, y tramos dichos de corrido unidos con el siguiente (fin = inicio del que sigue).
AJ_FIN = {35.01: 35.22, 56.31: 57.69, 81.57: 81.69, 87.97: 88.30, 131.74: 132.04, 135.30: 135.75, 228.31: 230.41,
          323.21: 323.30, 376.41: 376.65, 484.47: 484.65, 514.33: 514.69, 519.53: 519.83, 562.29: 562.71,
          604.41: 604.77, 640.08: 640.35, 691.13: 691.16, 830.77: 830.95}
AJ_INI = {570.99: 570.60, 53.41: 52.90, 85.49: 85.34, 324.21: 324.15, 343.57: 343.30, 414.83: 414.30, 494.43: 494.28,
          596.83: 596.77, 829.01: 828.53, 925.67: 925.28}
def _aj(d, x): return next((v for k, v in d.items() if abs(k - x) < 0.03), x)


def piezas():
    """Lista de (desde, hasta, opciones) en segundos de la toma, con los huecos largos acortados."""
    out = []
    for t in TRAMOS:
        if isinstance(t, str): out.append(t); continue
        i, j, op = t; cap = op.get("huecos", HUECO); a = L[i][0] - PAD_A; partes = []
        for k in range(i, j + 1):
            if k > i and L[k][0] - L[k - 1][1] > cap:
                partes.append((a, L[k - 1][1] + min(PAD_B + cap / 2, L[k][0] - L[k - 1][1]) if cap > HUECO else L[k - 1][1] + PAD_B)); a = L[k][0] - PAD_A
        partes.append((a, L[j][1] + PAD_B))
        for n, (x, y) in enumerate(partes):
            out.append((_aj(AJ_INI, round(x, 2)), _aj(AJ_FIN, round(y, 2)), dict(op, primero=(n == 0), renglones=(i, j))))
    return out


KEEP = [(f"{p[2]['renglones'][0]}-{p[2]['renglones'][1]}", p[0], p[1], p[2].get("cam", "auto")) for p in piezas() if not isinstance(p, str)]

if __name__ == "__main__":
    tot = sum(b - a for _, a, b, _ in KEEP)
    print(len(KEEP), "tramos ·", f"{tot / 60:.1f} min de toma")
    for k in KEEP[:6]: print(k)
