#!/usr/bin/env python3
"""
Reel: CÓMO LEER UN ELECTROCARDIOGRAMA (ECG) EN MENOS DE 3 MINUTOS (versión 2, corregida).

Estilo "monitor clínico": fondo oscuro, papel milimetrado, trazos neón,
tipografía Inter + JetBrains Mono. SIN VOZ: subtítulos karaoke + efectos
sobrios (bips de monitor, tics, confirmaciones) + música ambiental, listo
para narrar con ElevenLabs.

Las formas de onda de las 12 derivaciones se generan matemáticamente
(sumas de gaussianas) con proporciones realistas a 25 mm/s y 10 mm/mV.

Uso:
    python generar.py --modelo kokoro.onnx --voces voices.bin --out .
    python generar.py --voz-dir audios_elevenlabs --out .      # con tus audios reales
"""
import argparse
import glob
import importlib.util
import math
import os
import subprocess
import tempfile

import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw, ImageFont

AQUI = os.path.dirname(os.path.abspath(__file__))
_v2p = os.path.join(AQUI, "..", "sistema_inmune_v2", "generar.py")
_spec = importlib.util.spec_from_file_location("reel_v2", _v2p)
v2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v2)

W, H, FPS, SR = 1080, 1920, 30, v2.SR
LEAD, PAD, MIN_DUR = 0.25, 0.85, 5.0
NOMBRE = "reel_ecg_v2"

# ----------------------------------------------------------------------------
# ESTILO
# ----------------------------------------------------------------------------
FD = os.path.join(AQUI, "..", "ecg", "fonts")
F_BLACK = os.path.join(FD, "InterDisplay-Black.ttf")
F_BOLD = os.path.join(FD, "InterDisplay-Bold.ttf")
F_SEMI = os.path.join(FD, "Inter-SemiBold.ttf")
F_MED = os.path.join(FD, "Inter-Medium.ttf")
F_MONO = os.path.join(FD, "JetBrainsMono-Bold.ttf")
F_MONO_M = os.path.join(FD, "JetBrainsMono-Medium.ttf")

BG = (5, 11, 22)
PANEL = (11, 19, 33)
BORDE = (34, 54, 80)
BLANCO = (236, 243, 250)
GRIS = (128, 146, 168)
VERDE = (57, 255, 156)
CIAN = (64, 210, 255)
CORAL = (255, 79, 109)
AMBAR = (255, 192, 64)
VIOLETA = (170, 130, 255)
PAPEL_MIN = (44, 17, 28)
PAPEL_MAY = (92, 30, 50)
PAPEL_BG = (13, 9, 16)

_fc = {}


def F(path, size):
    k = (path, int(size))
    if k not in _fc:
        _fc[k] = ImageFont.truetype(path, max(4, int(size)))
    return _fc[k]


def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(x + (y - x) * t) for x, y in zip(a, b))


lerp, clamp01 = v2.lerp, v2.clamp01
ease_out_back, ease_in_out = v2.ease_out_back, v2.ease_in_out


def eo(t, t0, d=0.45):
    """Entrada con rebote (0 antes de t0)."""
    if t <= t0:
        return 0.0
    return ease_out_back((t - t0) / d)


def ei(t, t0, d=0.45):
    return ease_in_out((t - t0) / d) if t > t0 else 0.0


# ----------------------------------------------------------------------------
# GUION  (texto = subtítulos; voz = versión deletreada para la narración)
# ----------------------------------------------------------------------------
ESCENAS = [
    dict(id="intro", kicker="ELECTROCARDIOGRAMA", titulo="¿Solo ves garabatos?", acento=VERDE,
         texto="Seguramente has visto esto. Esto es un electrocardiograma. Y si tenías dudas, o si solo veías "
               "garabatos, hoy te enseño a leerlo en menos de 3 minutos.",
         voz="Seguramente has visto esto. Esto es un electrocardiograma. Y si tenías dudas, o si solo veías "
             "garabatos, hoy te enseño a leerlo en menos de tres minutos."),
    dict(id="papel", kicker="FUNDAMENTOS · 01", titulo="El papel del ECG", acento=CORAL,
         texto="Primero, el papel. Se registra a 25 mm/s. Cada cuadro pequeño mide 1 mm: equivale a 0.04 segundos "
               "en horizontal y a 0.1 mV en vertical. Un cuadro grande, de cinco pequeños, equivale a 0.20 segundos.",
         voz="Primero, el papel. Se registra a veinticinco milímetros por segundo. Cada cuadro pequeño mide un "
             "milímetro: equivale a cero punto cero cuatro segundos en horizontal, y a cero punto uno milivoltios "
             "en vertical. Un cuadro grande, de cinco pequeños, equivale a cero punto veinte segundos."),
    dict(id="ondas", kicker="FUNDAMENTOS · 02", titulo="Ondas del latido", acento=VERDE,
         texto="Cada latido tiene tres componentes: la onda P, que es la despolarización auricular; el complejo QRS, "
               "la despolarización ventricular; y la onda T, la repolarización ventricular.",
         voz="Cada latido tiene tres componentes: la onda pe, que es la despolarización auricular; el complejo "
             "cu erre ese, la despolarización ventricular; y la onda te, la repolarización ventricular."),
    dict(id="frontales", kicker="DERIVACIONES · 03", titulo="Plano frontal", acento=CIAN,
         texto="El ECG tiene 12 derivaciones. Seis son del plano frontal: las bipolares DI, DII y DIII, "
               "y las monopolares aumentadas aVR, aVL y aVF.",
         voz="El electrocardiograma tiene doce derivaciones. Seis son del plano frontal: las bipolares, de uno, "
             "de dos y de tres; y las monopolares aumentadas, a ve erre, a ve ele y a ve efe."),
    dict(id="precordiales", kicker="DERIVACIONES · 04", titulo="Precordiales", acento=AMBAR,
         texto="Las otras seis son las precordiales, de V1 a V6, en el plano horizontal. V1 y V2 van en el cuarto "
               "espacio intercostal, junto al esternón; V4, en el quinto espacio, en la línea medioclavicular; "
               "y V6, en la línea medioaxilar.",
         voz="Las otras seis son las precordiales, de ve uno a ve seis, en el plano horizontal. Ve uno y ve dos van "
             "en el cuarto espacio intercostal, junto al esternón; ve cuatro, en el quinto espacio, en la línea "
             "medioclavicular; y ve seis, en la línea medioaxilar."),
    dict(id="caras", kicker="DERIVACIONES · 05", titulo="Caras del corazón", acento=VIOLETA,
         texto="Cada grupo mira una cara del corazón: DII, DIII y aVF, la cara inferior; DI, aVL, V5 y V6, la lateral; "
               "V1 y V2, el septo; y V3 y V4, la cara anterior.",
         voz="Cada grupo mira una cara del corazón: de dos, de tres y a ve efe, la cara inferior; de uno, a ve ele, "
             "ve cinco y ve seis, la lateral; ve uno y ve dos, el septo; y ve tres y ve cuatro, la cara anterior."),
    dict(id="ritmo", kicker="PASO 1 DE 5", titulo="Ritmo", acento=VERDE, paso=1,
         texto="Paso 1: el ritmo. Es sinusal si cada QRS va precedido de una onda P, positiva en DII y negativa en aVR, "
               "y si los intervalos R-R son regulares.",
         voz="Paso uno: el ritmo. Es sinusal si cada cu erre ese va precedido de una onda pe, positiva en de dos y "
             "negativa en a ve erre, y si los intervalos erre erre son regulares."),
    dict(id="frecuencia", kicker="PASO 2 DE 5", titulo="Frecuencia", acento=CORAL, paso=2,
         texto="Paso 2: la frecuencia. Divide 300 entre el número de cuadros grandes que hay entre dos ondas R. "
               "Si hay 4, la frecuencia es de 75 lpm. Lo normal es entre 60 y 100.",
         voz="Paso dos: la frecuencia. Divide trescientos entre el número de cuadros grandes que hay entre dos ondas "
             "erre. Si hay cuatro, la frecuencia es de setenta y cinco latidos por minuto. Lo normal es entre "
             "sesenta y cien."),
    dict(id="eje", kicker="PASO 3 DE 5", titulo="Eje eléctrico", acento=CIAN, paso=3,
         texto="Paso 3: el eje eléctrico. Mira el QRS en DI y aVF: si ambos son positivos, el eje es normal. "
               "Si DI es negativo, hay desviación a la derecha; si aVF y DII son negativos, desviación a la izquierda.",
         voz="Paso tres: el eje eléctrico. Mira el cu erre ese en de uno y a ve efe: si ambos son positivos, el eje "
             "es normal. Si de uno es negativo, hay desviación a la derecha; si a ve efe y de dos son negativos, "
             "desviación a la izquierda."),
    dict(id="intervalos", kicker="PASO 4 DE 5", titulo="Intervalos", acento=AMBAR, paso=4,
         texto="Paso 4: los intervalos. El PR normal mide de 0.12 a 0.20 segundos, de 3 a 5 cuadros pequeños. "
               "El QRS, menos de 0.12 segundos. Y el QTc, menos de 440 ms en hombres y de 460 en mujeres.",
         voz="Paso cuatro: los intervalos. El pe erre normal mide de cero punto doce a cero punto veinte segundos, de "
             "tres a cinco cuadros pequeños. El cu erre ese, menos de cero punto doce segundos. Y el cu te corregido, "
             "menos de cuatrocientos cuarenta milisegundos en hombres y de cuatrocientos sesenta en mujeres."),
    dict(id="st", kicker="PASO 5 DE 5", titulo="Segmento ST y onda T", acento=CORAL, paso=5,
         texto="Paso 5: el segmento ST y la onda T. Compáralos con la línea isoeléctrica. Una elevación del ST en dos "
               "derivaciones contiguas sugiere un infarto agudo; una depresión o una T invertida, isquemia.",
         voz="Paso cinco: el segmento ese te y la onda te. Compáralos con la línea isoeléctrica. Una elevación del "
             "ese te en dos derivaciones contiguas sugiere un infarto agudo; una depresión o una onda te invertida, "
             "isquemia."),
    dict(id="resumen", kicker="RESUMEN", titulo="Los 5 pasos", acento=VERDE,
         texto="Recuerda los cinco pasos: ritmo, frecuencia, eje, intervalos y segmento ST. "
               "Siempre en el mismo orden, y no se te escapará nada.",
         voz="Recuerda los cinco pasos: ritmo, frecuencia, eje, intervalos y segmento ese te. "
             "Siempre en el mismo orden, y no se te escapará nada."),
    dict(id="outro", kicker="ECG EN MENOS DE 3 MINUTOS", titulo="¿Te sirvió?", acento=VERDE,
         texto="Guarda este video para tu próxima guardia. ¿Qué tema quieres que explique después? "
               "Déjalo en los comentarios y sígueme para más."),
]

# ----------------------------------------------------------------------------
# FORMAS DE ONDA
# ----------------------------------------------------------------------------
RR = 0.8  # 75 lpm

LEADS = {
    "I": dict(P=.10, Q=-.05, R=.80, S=-.10, T=.25),
    "II": dict(P=.15, Q=-.10, R=1.30, S=-.25, T=.35),
    "III": dict(P=.06, Q=-.08, R=.60, S=-.20, T=.12),
    "aVR": dict(P=-.10, Q=0, R=-.90, S=.10, T=-.25),
    "aVL": dict(P=.04, Q=-.05, R=.40, S=-.08, T=.10),
    "aVF": dict(P=.10, Q=-.08, R=.90, S=-.20, T=.22),
    "V1": dict(P=.08, Q=0, R=.25, S=-1.00, T=-.05),
    "V2": dict(P=.08, Q=0, R=.40, S=-1.10, T=.30),
    "V3": dict(P=.08, Q=0, R=.80, S=-.70, T=.35),
    "V4": dict(P=.10, Q=-.05, R=1.30, S=-.40, T=.40),
    "V5": dict(P=.10, Q=-.08, R=1.30, S=-.20, T=.35),
    "V6": dict(P=.10, Q=-.08, R=1.00, S=-.10, T=.30),
}


def latido(tau, P=.15, Q=-.10, R=1.3, S=-.25, T=.35, st=0.0):
    """Voltaje (mV) de un latido en el tiempo tau (s) desde su inicio."""
    g = lambda a, mu, s: a * np.exp(-0.5 * ((tau - mu) / s) ** 2)
    v = g(P, .10, .022) + g(Q, .212, .008) + g(R, .235, .0095) + g(S, .258, .009) + g(T, .47, .042)
    if st:
        sig = lambda x: 1 / (1 + np.exp(-x))
        v = v + st * sig((tau - .275) / .006) * sig((.50 - tau) / .03)
    return v


def ecg(t, lead="II", rr=RR, **kw):
    p = dict(LEADS[lead])
    p.update(kw)
    return latido(np.mod(t, rr), **p)


def puntos_traza(x0, y0, pps, ppmv, t0, t1, fn, n=None, rel=True):
    """Puntos (x, y) de fn entre t0 y t1. rel=True: x0 corresponde a t0; rel=False: x0 corresponde a t=0."""
    n = n or max(2, int((t1 - t0) * pps / 2))
    ts = np.linspace(t0, t1, n)
    vs = fn(ts)
    base = t0 if rel else 0.0
    return [(x0 + (tt - base) * pps, y0 - vv * ppmv) for tt, vv in zip(ts, vs)]


# ----------------------------------------------------------------------------
# PRIMITIVAS GRÁFICAS
# ----------------------------------------------------------------------------
def trazo(d, pts, col, w=4, glow=True):
    if len(pts) < 2:
        return
    if glow:
        d.line(pts, fill=mix(BG, col, 0.12), width=w * 5, joint="curve")
        d.line(pts, fill=mix(BG, col, 0.32), width=w * 2 + 2, joint="curve")
    d.line(pts, fill=col, width=w, joint="curve")


def cabeza(d, x, y, col, r=9):
    d.ellipse([x - r * 2.2, y - r * 2.2, x + r * 2.2, y + r * 2.2], fill=mix(BG, col, 0.25))
    d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255))


def tarjeta(d, box, borde=BORDE, fill=PANEL, r=28, w=2):
    d.rounded_rectangle(box, radius=r, fill=fill, outline=borde, width=w)


def papel(d, box, mm, r=24, borde=BORDE, origen=None):
    """Papel de ECG: cuadrícula de 1 mm y 5 mm dentro de box."""
    x0, y0, x1, y1 = box
    d.rounded_rectangle(box, radius=r, fill=PAPEL_BG)
    ox, oy = origen if origen else (x0, y0)
    k0 = int(math.floor((x0 - ox) / mm))
    k1 = int(math.ceil((x1 - ox) / mm))
    for k in range(k0, k1 + 1):
        x = ox + k * mm
        if x0 + 2 < x < x1 - 2:
            d.line([(x, y0 + 2), (x, y1 - 2)], fill=PAPEL_MAY if k % 5 == 0 else PAPEL_MIN, width=2 if k % 5 == 0 else 1)
    k0 = int(math.floor((y0 - oy) / mm))
    k1 = int(math.ceil((y1 - oy) / mm))
    for k in range(k0, k1 + 1):
        y = oy + k * mm
        if y0 + 2 < y < y1 - 2:
            d.line([(x0 + 2, y), (x1 - 2, y)], fill=PAPEL_MAY if k % 5 == 0 else PAPEL_MIN, width=2 if k % 5 == 0 else 1)
    d.rounded_rectangle(box, radius=r, outline=borde, width=2)


def pildora(d, x, y, txt, col, fuente, fill=None, anchor="mm", pad=(22, 12), texto_col=None, check=False):
    tw = d.textlength(txt, font=fuente)
    h = fuente.size
    extra = h * 1.4 if check else 0
    ancho = tw + extra + 2 * pad[0]
    bx0 = x - ancho / 2 if anchor == "mm" else x - pad[0]
    box = [bx0, y - h / 2 - pad[1], bx0 + ancho, y + h / 2 + pad[1]]
    d.rounded_rectangle(box, radius=int(h / 2 + pad[1]), fill=fill if fill else mix(BG, col, 0.18), outline=col, width=2)
    if check:
        palomita(d, box[0] + pad[0] + h * 0.55, y, h / 38, col)
    d.text((box[0] + pad[0] + extra + tw / 2, y), txt, font=fuente, fill=texto_col or col, anchor="mm")
    return box


def flecha(d, p0, p1, col, w=4, cab=18):
    d.line([p0, p1], fill=col, width=w)
    a = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
    for s in (-1, 1):
        d.line([p1, (p1[0] - cab * math.cos(a + s * 0.45), p1[1] - cab * math.sin(a + s * 0.45))], fill=col, width=w)


def corchete(d, x0, x1, y, col, txt=None, fuente=None, p=1.0, arriba=True, lado=None):
    """Calibrador horizontal con etiqueta (arriba, abajo o a la derecha si lado="der")."""
    if p <= 0:
        return
    xm = (x0 + x1) / 2
    a, b = lerp(xm, x0, p), lerp(xm, x1, p)
    h = 14
    d.line([(a, y), (b, y)], fill=col, width=4)
    d.line([(a, y - h), (a, y + h)], fill=col, width=4)
    d.line([(b, y - h), (b, y + h)], fill=col, width=4)
    if txt and p > 0.6:
        f = fuente or F(F_MONO, 30)
        if lado == "der":
            pildora(d, b + 26, y, txt, col, f, anchor="lm", fill=PAPEL_BG)
        else:
            pildora(d, xm, y - 44 if arriba else y + 44, txt, col, f, fill=PAPEL_BG)


def palomita(d, x, y, s, col, p=1.0, w=None):
    w = w or max(2, int(8 * s))
    a, b, c = (x - 20 * s, y + 2 * s), (x - 6 * s, y + 16 * s), (x + 22 * s, y - 16 * s)
    if p <= 0:
        return
    if p < 0.4:
        q = p / 0.4
        d.line([a, (lerp(a[0], b[0], q), lerp(a[1], b[1], q))], fill=col, width=w)
    else:
        q = min(1, (p - 0.4) / 0.6)
        d.line([a, b, (lerp(b[0], c[0], q), lerp(b[1], c[1], q))], fill=col, width=w, joint="curve")


def corazon(d, x, y, s, col):
    r = 22 * s
    d.ellipse([x - 2 * r, y - r, x, y + r], fill=col)
    d.ellipse([x, y - r, x + 2 * r, y + r], fill=col)
    d.polygon([(x - 2 * r + 2 * s, y + 0.35 * r), (x + 2 * r - 2 * s, y + 0.35 * r), (x, y + 2.3 * r)], fill=col)


# ----------------------------------------------------------------------------
# SONIDOS (sobrios / clínicos)
# ----------------------------------------------------------------------------
def s_beep():
    t = v2._t(0.11)
    return np.sin(2 * np.pi * 980 * t) * np.clip(t / 0.004, 0, 1) * np.clip((0.11 - t) / 0.02, 0, 1) * 0.4


def s_tic():
    t = v2._t(0.03)
    return np.sin(2 * np.pi * 3000 * t) * v2._env(len(t), 0.0005, 170) * 0.5


def s_ok():
    out = np.zeros(int(0.35 * SR))
    for i, f in enumerate([880, 1318.5]):
        t = v2._t(0.25)
        s = (np.sin(2 * np.pi * f * t) + 0.2 * np.sin(4 * np.pi * f * t)) * v2._env(len(t), 0.003, 9) * 0.35
        i0 = int(i * 0.09 * SR)
        out[i0:i0 + len(s)] += s
    return out


def s_alerta():
    out = np.zeros(int(0.45 * SR))
    for i, f in enumerate([740, 554]):
        t = v2._t(0.18)
        s = np.sin(2 * np.pi * f * t) * np.clip(np.sin(np.pi * t / 0.18) * 3, 0, 1) * 0.3
        i0 = int(i * 0.2 * SR)
        out[i0:i0 + len(s)] += s
    return out


def s_swoosh():
    return v2.SFX["whoosh"] * 0.6


def s_latido():
    """Lub-dub grave."""
    out = np.zeros(int(0.5 * SR))
    for t0, f, a in [(0.0, 62, 1.0), (0.18, 75, 0.7)]:
        t = v2._t(0.16)
        s = np.sin(2 * np.pi * f * t) * v2._env(len(t), 0.004, 22) * a
        i0 = int(t0 * SR)
        out[i0:i0 + len(s)] += s
    return out


SFX = {"beep": s_beep(), "tic": s_tic(), "ok": s_ok(), "alerta": s_alerta(), "swoosh": s_swoosh(),
       "latido": s_latido(), "click": v2.SFX["click"], "pop": v2.SFX["pop"] * 0.5}
SFX_VOL = {"beep": 0.5, "tic": 0.45, "ok": 0.6, "alerta": 0.55, "swoosh": 0.45, "latido": 0.9, "click": 0.6, "pop": 0.5}


def musica(dur):
    """Pad ambiental + pulso grave a 75 lpm."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    acordes = [[110.0, 164.81, 220.0, 261.63], [87.31, 130.81, 174.61, 220.0],
               [130.81, 196.0, 261.63, 329.63], [98.0, 146.83, 196.0, 246.94]]
    seg = 6.4
    for i in range(int(dur / seg) + 1):
        i0, i1 = int(i * seg * SR), min(n, int((i + 1) * seg * SR + 1.5 * SR))
        if i0 >= n:
            break
        tt = t[i0:i1] - i * seg
        env = np.clip(tt / 1.5, 0, 1) * np.clip((seg + 1.5 - tt) / 1.5, 0, 1)
        for f in acordes[i % 4]:
            for det in (0.998, 1.002):
                out[i0:i1] += np.sin(2 * np.pi * f * det * tt) * env * 0.05
    fase = np.mod(t, RR)
    out += np.sin(2 * np.pi * 55 * t) * np.exp(-fase * 14) * 0.12
    out *= np.clip(t / 2, 0, 1) * np.clip((dur - t) / 2.5, 0, 1)
    return out / (np.max(np.abs(out)) + 1e-6)


# ----------------------------------------------------------------------------
# SINCRONÍA CON PALABRAS
# ----------------------------------------------------------------------------
def tpal(esc, sub, k=0, fin=False):
    pal = esc["_palabras"]
    m = [w for w in pal if sub.lower() in w[2].lower()]
    if not m:
        raise KeyError(f"'{sub}' no está en el texto de {esc['id']}")
    w = m[min(k, len(m) - 1)]
    return w[1] if fin else w[0]


# ----------------------------------------------------------------------------
# ESCENAS
# ----------------------------------------------------------------------------
CY = 900


def doce(d, t, x0, y0, cw, ch, col_fn, jit=0.0, t_ini=0.0, mm=10):
    """Mini ECG de 12 derivaciones (formato 3x4)."""
    rnd = np.random.default_rng(int(t * 30))
    for r, fila in enumerate(LAYOUT):
        for c, lead in enumerate(fila):
            k = r * 4 + c
            q = eo(t, t_ini + k * 0.05, 0.4)
            if q <= 0:
                continue
            bx0, by0 = x0 + c * cw, y0 + r * ch
            box = [bx0 + 6, by0 + 6, bx0 + cw - 6, by0 + ch - 6]
            col = col_fn(lead)
            papel(d, box, mm, r=16, borde=mix(BG, col, 0.5))
            prog = clamp01((t - t_ini - k * 0.05) / 0.9)
            t_fin = (box[2] - box[0] - 28) / (25 * mm) * prog
            yb = by0 + ch * 0.6
            pts = puntos_traza(box[0] + 12, yb, 25 * mm, 10 * mm * 0.85, 0.05, 0.05 + t_fin,
                               lambda s_, L=lead: ecg(s_, L, rr=0.68), 160)
            if jit > 0:
                pts = [(x, y + rnd.normal(0, jit)) for x, y in pts]
            trazo(d, pts, col, 3, glow=jit == 0)
            d.text((box[0] + 14, box[1] + 24), lead, font=F(F_MONO, 24), fill=mix(BG, col, 0.9), anchor="lm")


def esc_intro(fr, d, fx, t, dur, esc):
    t_esto = 0.1
    t_ecg = tpal(esc, "electrocardiograma.")
    t_gar = tpal(esc, "garabatos,")
    t_ens = tpal(esc, "enseño")
    t_3 = tpal(esc, "3")
    for k in range(3):
        fx.en(0.235 + k * RR, "beep")
    fx.en(t_ecg, "ok", vol=0.6)
    fx.en(t_ens, "ok")
    fx.en(t_3, "tic")
    # garabatos: el trazo tiembla mientras se dice "garabatos" y se ordena con "enseño"
    caos = clamp01((t - t_gar + 0.2) / 0.3) * (1 - clamp01((t - t_ens) / 0.4))
    ordenado = t > t_ens

    def col(lead):
        if ordenado:
            return mix(BLANCO, VERDE, clamp01((t - t_ens) / 0.4))
        return mix(BLANCO, CORAL, caos * 0.7)

    doce(d, t, 50, 500, (W - 100) / 4, 220, col, jit=9 * caos, t_ini=t_esto)
    q = eo(t, t_ecg, 0.45)
    if q > 0:
        pildora(d, W / 2, 1210, "ECG DE 12 DERIVACIONES", CIAN, F(F_MONO, 32))
    q = eo(t, t_3, 0.45)
    if q > 0:
        box = pildora(d, W / 2, 1310, "MENOS DE 3 MINUTOS", VERDE, F(F_BLACK, 44), fill=mix(BG, VERDE, 0.12))
        # cronómetro pequeño a la izquierda de la píldora
        cx, cy = box[0] - 50, 1310
        d.ellipse([cx - 30, cy - 30, cx + 30, cy + 30], outline=VERDE, width=4)
        a = -math.pi / 2 + (t - t_3) * 4
        d.line([(cx, cy), (cx + 22 * math.cos(a), cy + 22 * math.sin(a))], fill=VERDE, width=4)
        d.rectangle([cx - 6, cy - 42, cx + 6, cy - 32], fill=VERDE)


def esc_papel(fr, d, fx, t, dur, esc):
    mm = 34
    box = [70, 470, W - 70, 1330]
    ox, oy = 70 + 2 * mm, 470 + 3 * mm
    papel(d, box, mm, origen=(ox, oy))
    t_25 = tpal(esc, "25")
    t_peq = tpal(esc, "pequeño")
    t_hor = tpal(esc, "horizontal")
    t_ver = tpal(esc, "vertical.")
    t_gra = tpal(esc, "grande,")
    t_020 = tpal(esc, "0.20")
    fx.en(t_25, "tic")
    if t > t_25:
        pildora(d, W / 2, 470 + 1.5 * mm, "25 mm/s  ·  10 mm/mV", CIAN, F(F_MONO, 32), fill=PAPEL_BG)
    # cuadro pequeño
    sx, sy = ox + 5 * mm, oy + 9 * mm
    fx.en(t_peq, "pop", vol=0.8)
    q = eo(t, t_peq)
    if q > 0:
        d.rectangle([sx, sy, sx + mm, sy + mm], fill=mix(PAPEL_BG, VERDE, 0.3), outline=VERDE, width=4)
        d.text((sx + mm + 18, sy + mm / 2), "1 mm", font=F(F_MONO, 28), fill=VERDE, anchor="lm")
    fx.en(t_hor, "tic")
    q = eo(t, t_hor)
    if q > 0:
        y = sy + mm + 34
        d.line([(sx, y), (sx + mm, y)], fill=VERDE, width=4)
        for x in (sx, sx + mm):
            d.line([(x, y - 10), (x, y + 10)], fill=VERDE, width=4)
        pildora(d, sx + mm / 2, y + 64, "0.04 s", VERDE, F(F_MONO, 34), fill=PAPEL_BG)
    fx.en(t_ver, "tic")
    q = eo(t, t_ver)
    if q > 0:
        x = sx - 30
        d.line([(x, sy), (x, sy + mm)], fill=CIAN, width=4)
        for y in (sy, sy + mm):
            d.line([(x - 10, y), (x + 10, y)], fill=CIAN, width=4)
        pildora(d, x - 26 - d.textlength("0.1 mV", font=F(F_MONO, 34)) / 2 - 22, sy + mm / 2, "0.1 mV", CIAN,
                F(F_MONO, 34), fill=PAPEL_BG)
    # cuadro grande
    bx, by = ox + 13 * mm, oy + 6 * mm
    fx.en(t_gra, "pop", vol=0.8)
    q = eo(t, t_gra)
    if q > 0:
        s_ = min(1.0, q)
        d.rectangle([bx, by, bx + 5 * mm * s_, by + 5 * mm * s_], fill=mix(PAPEL_BG, CORAL, 0.18), outline=CORAL,
                    width=5)
        if q >= 1:
            d.text((bx + 2.5 * mm, by + 5 * mm + 34), "5 × 1 mm", font=F(F_MONO_M, 28), fill=CORAL, anchor="mm")
    fx.en(t_020, "ok")
    q = eo(t, t_020)
    if q > 0:
        pildora(d, bx + 2.5 * mm, by - 50, "0.20 s  ·  0.5 mV", CORAL, F(F_MONO, 34), fill=PAPEL_BG)
    # resumen al pie del papel
    q = eo(t, t_020 + 0.4)
    if q > 0:
        pildora(d, W / 2, box[3] - 70, "1 cuadro grande = 5 pequeños = 0.20 s", BLANCO, F(F_MONO_M, 28),
                fill=PAPEL_BG)


def esc_ondas(fr, d, fx, t, dur, esc):
    mm = 30
    box = [60, 470, W - 60, 1330]
    pps, ppmv = 25 * mm * 1.7, 10 * mm * 1.05
    x0, y0 = 110, 1030
    papel(d, box, mm, origen=(x0, y0))
    t_p = tpal(esc, "P,")
    t_qrs = tpal(esc, "QRS,")
    t_t = tpal(esc, "T,")
    t_ini, t_fin = 0.0, 0.62
    head = t_ini + (t_fin - t_ini) * ei(t, 0.2, max(1.0, t_p - 0.2))
    fn = lambda s: latido(s)
    # sombreado por componente
    zonas = [(t_p, 0.04, 0.165, VERDE, "P", "Despolarización auricular"),
             (t_qrs, 0.198, 0.278, CORAL, "QRS", "Despolarización ventricular"),
             (t_t, 0.37, 0.58, CIAN, "T", "Repolarización ventricular")]
    for (tz, a, b, col, nom, desc) in zonas:
        fx.en(tz, "ok" if nom != "QRS" else "beep", vol=0.8)
        q = eo(t, tz, 0.4)
        if q <= 0:
            continue
        xa, xb = x0 + a * pps, x0 + b * pps
        pts = puntos_traza(x0, y0, pps, ppmv, a, b, fn, 80, rel=False)
        poly = [(xa, y0)] + pts + [(xb, y0)]
        d.polygon(poly, fill=mix(PAPEL_BG, col, 0.35 * min(1, q)))
        ytop = min(pp[1] for pp in pts)
        yl = min(ytop - 70, y0 - 120)
        pildora(d, (xa + xb) / 2, yl, nom, col, F(F_BLACK, 44), fill=PAPEL_BG)
    trazo(d, puntos_traza(x0, y0, pps, ppmv, t_ini, head, fn, 500), BLANCO, 5)
    # línea isoeléctrica
    for x in range(int(box[0] + 20), int(box[2] - 20), 28):
        d.line([(x, y0), (x + 14, y0)], fill=mix(PAPEL_BG, GRIS, 0.5), width=2)
    # leyendas
    for i, (tz, a, b, col, nom, desc) in enumerate(zonas):
        q = eo(t, tz + 0.15, 0.4)
        if q <= 0:
            continue
        y = 1180 + i * 52
        xo = (1 - min(1, q)) * 200
        d.ellipse([110 + xo, y - 11, 132 + xo, y + 11], fill=col)
        d.text((150 + xo, y), f"{nom}", font=F(F_MONO, 30), fill=col, anchor="lm")
        d.text((255 + xo, y), desc, font=F(F_SEMI, 32), fill=BLANCO, anchor="lm")


def esc_frontales(fr, d, fx, t, dur, esc):
    cx, cy, R = W / 2, CY + 20, 360
    q0 = ei(t, 0, 0.6)
    d.ellipse([cx - R, cy - R, cx + R, cy + R], outline=mix(BG, BORDE, q0), width=3)
    d.ellipse([cx - R * 0.55, cy - R * 0.55, cx + R * 0.55, cy + R * 0.55], outline=mix(BG, BORDE, 0.6 * q0), width=2)
    corazon(d, cx, cy - 10, 1.6 * q0 + 0.01, mix(BG, CORAL, 0.8))
    t_12 = tpal(esc, "12")
    fx.en(t_12, "tic")
    q = eo(t, t_12)
    if q > 0:
        pildora(d, W / 2, 470, "12 DERIVACIONES = 6 FRONTALES + 6 PRECORDIALES", GRIS, F(F_MONO_M, 26))
    derivs = [("DI", 0, CIAN, "DI,"), ("DII", 60, CIAN, "DII"), ("DIII", 120, CIAN, "DIII,"),
              ("aVR", -150, AMBAR, "aVR,"), ("aVL", -30, AMBAR, "aVL"), ("aVF", 90, AMBAR, "aVF.")]
    for nom, ang, col, clave in derivs:
        tz = tpal(esc, clave)
        fx.en(tz, "tic")
        q = eo(t, tz, 0.5)
        if q <= 0:
            continue
        a = math.radians(ang)
        L = R * min(1, q)
        p_neg = (cx - L * math.cos(a), cy - L * math.sin(a))
        p_pos = (cx + L * math.cos(a), cy + L * math.sin(a))
        d.line([p_neg, (cx, cy)], fill=mix(BG, col, 0.35), width=3)
        flecha(d, (cx, cy), p_pos, col, 5, 24)
        lx, ly = cx + (R + 70) * math.cos(a), cy + (R + 70) * math.sin(a)
        pildora(d, lx, ly, nom, col, F(F_MONO, 34), fill=BG)
        d.text((cx + (R - 55) * math.cos(a + 0.12), cy + (R - 55) * math.sin(a + 0.12)), f"{ang:+d}°",
               font=F(F_MONO_M, 24), fill=mix(BG, col, 0.8), anchor="mm")
    # leyenda
    for i, (txt, col, clave) in enumerate([("BIPOLARES", CIAN, "bipolares"), ("AUMENTADAS", AMBAR, "aumentadas")]):
        tz = tpal(esc, clave)
        q = eo(t, tz)
        if q > 0:
            x = W / 2 + (i - 0.5) * 420
            pildora(d, x, 1380, txt, col, F(F_MONO, 30))


def torso(d, cx, top, a=1.0):
    """Silueta de tórax con esternón y costillas; devuelve la y de los espacios intercostales 4 y 5."""
    col = mix(BG, (70, 100, 135), a)
    pts = [(cx - 70, top), (cx - 120, top + 40), (cx - 330, top + 90), (cx - 400, top + 170), (cx - 385, top + 470),
           (cx - 360, top + 800), (cx + 360, top + 800), (cx + 385, top + 470), (cx + 400, top + 170),
           (cx + 330, top + 90), (cx + 120, top + 40), (cx + 70, top)]
    d.polygon(pts, fill=mix(BG, PANEL, a))
    d.line(pts, fill=col, width=3, joint="curve")
    gap = 62
    costillas = [top + 120 + i * gap for i in range(7)]
    for i, y in enumerate(costillas):
        for sg in (-1, 1):
            curva = [(cx + sg * (40 + u * 300), y + 30 * u * u + 8 * u) for u in np.linspace(0, 1, 24)]
            d.line(curva, fill=mix(BG, (48, 72, 100), a), width=5, joint="curve")
    d.rounded_rectangle([cx - 24, top + 70, cx + 24, top + 520], radius=18, fill=mix(BG, (44, 66, 92), a))
    # espacios intercostales (entre costillas): 4º y 5º
    y4 = (costillas[3] + costillas[4]) / 2 + 6
    y5 = (costillas[4] + costillas[5]) / 2 + 10
    return y4, y5


def esc_precordiales(fr, d, fx, t, dur, esc):
    cx, top = W / 2, 500
    q0 = ei(t, 0, 0.6)
    # corazón tenue detrás del tórax
    pul = 1 + 0.05 * math.exp(-((t - 0.235) % RR) * 8)
    y4, y5 = torso(d, cx, top, q0)
    corazon(d, cx + 90, y5 - 60, 2.0 * pul * q0 + 0.01, mix(PANEL, CORAL, 0.16))
    d.text((cx - 410, y4), "4º", font=F(F_MONO_M, 24), fill=mix(BG, GRIS, q0), anchor="rm")
    d.text((cx - 410, y5), "5º", font=F(F_MONO_M, 24), fill=mix(BG, GRIS, q0), anchor="rm")
    pos = {"V1": (cx - 50, y4), "V2": (cx + 50, y4), "V3": (cx + 115, (y4 + y5) / 2 + 4),
           "V4": (cx + 180, y5), "V5": (cx + 268, y5), "V6": (cx + 350, y5)}
    t_hor = tpal(esc, "horizontal.")
    t_v12 = tpal(esc, "V1", k=1)
    t_v4 = tpal(esc, "V4,")
    t_v6 = tpal(esc, "V6,", k=1)
    tiempos = {"V1": t_v12, "V2": t_v12 + 0.15, "V3": t_v4 - 0.2, "V4": t_v4, "V5": t_v6 - 0.2, "V6": t_v6}
    t_todas = tpal(esc, "V1")
    # líneas anatómicas verticales
    for nom, col in (("V4", CIAN), ("V6", CIAN)):
        if t > tiempos[nom]:
            x = pos[nom][0]
            q = ei(t, tiempos[nom], 0.5)
            for y in range(int(top + 60), int(top + 60 + 700 * q), 26):
                d.line([(x, y), (x, y + 12)], fill=mix(BG, col, 0.45), width=2)
    for nom, (x, y) in pos.items():
        fx.en(tiempos[nom], "click")
        q = eo(t, tiempos[nom], 0.4)
        if q > 0:
            r = 20 * min(1.25, q)
            d.ellipse([x - r - 9, y - r - 9, x + r + 9, y + r + 9], fill=mix(PANEL, AMBAR, 0.3))
            d.ellipse([x - r, y - r, x + r, y + r], fill=AMBAR, outline=(255, 255, 255), width=3)
            d.text((x, y - 44), nom, font=F(F_MONO, 28), fill=AMBAR, anchor="mm")
        elif t > t_todas:
            d.ellipse([x - 14, y - 14, x + 14, y + 14], outline=mix(PANEL, AMBAR, 0.6), width=3)
    fx.en(t_hor, "tic")
    if t > t_hor:
        pildora(d, W / 2, 452, "PLANO HORIZONTAL", AMBAR, F(F_MONO, 26))
    rot = [("V1–V2 · 4º EIC paraesternal", tpal(esc, "esternón;"), (W / 2, 1372)),
           ("V4 · 5º EIC medioclavicular", tpal(esc, "medioclavicular;"), (W / 2 - 205, 1436)),
           ("V6 · medioaxilar", tpal(esc, "medioaxilar."), (W / 2 + 300, 1436))]
    for txt, tz, (x, y) in rot:
        if t > tz:
            pildora(d, x, y, txt, CIAN, F(F_MONO_M, 26), fill=BG)


TERRITORIOS = {"inferior": (["II", "III", "aVF"], AMBAR, "INFERIOR"),
               "lateral": (["I", "aVL", "V5", "V6"], CIAN, "LATERAL"),
               "septal": (["V1", "V2"], VIOLETA, "SEPTAL"),
               "anterior": (["V3", "V4"], CORAL, "ANTERIOR")}
LAYOUT = [["I", "aVR", "V1", "V4"], ["II", "aVL", "V2", "V5"], ["III", "aVF", "V3", "V6"]]


def esc_caras(fr, d, fx, t, dur, esc):
    x0, y0 = 50, 520
    cw, ch = (W - 100) / 4, 230
    tiempos = {"inferior": tpal(esc, "DII,"), "lateral": tpal(esc, "DI,"), "septal": tpal(esc, "V1"),
               "anterior": tpal(esc, "V3")}
    activo_lead = {}
    for k, (leads, col, nom) in TERRITORIOS.items():
        fx.en(tiempos[k], "ok", vol=0.7)
        for l in leads:
            activo_lead[l] = (tiempos[k], col, nom)
    mm = 11
    for r, fila in enumerate(LAYOUT):
        for c, lead in enumerate(fila):
            bx0, by0 = x0 + c * cw, y0 + r * ch
            box = [bx0 + 6, by0 + 6, bx0 + cw - 6, by0 + ch - 6]
            q_in = eo(t, 0.1 + (r * 4 + c) * 0.05, 0.4)
            if q_in <= 0:
                continue
            info = activo_lead.get(lead)
            on = info and t > info[0]
            q = eo(t, info[0], 0.35) if info else 0
            borde = info[1] if on else BORDE
            papel(d, box, mm, r=18, borde=borde)
            if on:
                d.rounded_rectangle(box, radius=18, outline=info[1], width=int(2 + 3 * min(1, q)))
            col_tr = info[1] if on else mix(BG, BLANCO, 0.75)
            yb = by0 + ch * 0.62
            # aparece el trazo barriendo
            prog = clamp01((t - 0.1 - (r * 4 + c) * 0.05) / 0.8)
            t_fin = (box[2] - box[0] - 30) / (25 * mm) * prog
            pts = puntos_traza(box[0] + 12, yb, 25 * mm, 10 * mm * 0.85, 0.05, 0.05 + t_fin,
                               lambda s, L=lead: ecg(s, L, rr=0.68), 200)
            trazo(d, pts, col_tr, 3, glow=on)
            d.text((box[0] + 16, box[1] + 26), lead, font=F(F_MONO, 28), fill=(info[1] if on else GRIS), anchor="lm")
    # etiquetas de territorio
    for i, (k, (leads, col, nom)) in enumerate(TERRITORIOS.items()):
        q = eo(t, tiempos[k], 0.4)
        if q > 0:
            x = W / 2 + ((i % 2) - 0.5) * 470
            y = 1300 + (i // 2) * 84
            pildora(d, x, y, nom, col, F(F_MONO, 32))
    q = eo(t, tiempos["anterior"] + 0.8, 0.4)
    if q > 0:
        d.text((W / 2, 488), "aVR: mira la cavidad · suele ser negativa", font=F(F_MONO_M, 24), fill=GRIS, anchor="mm")


def tira(d, box, mm, t_ini, t_fin, lead="II", col=BLANCO, y_frac=0.62, glow=True, n=600, **kw):
    yb = box[1] + (box[3] - box[1]) * y_frac
    x0 = box[0] + 20
    pts = puntos_traza(x0, yb, 25 * mm, 10 * mm, t_ini, t_fin, lambda s: ecg(s, lead, **kw), n)
    pts = [p for p in pts if p[0] < box[2] - 14]
    trazo(d, pts, col, 4, glow)
    return x0, yb


def esc_ritmo(fr, d, fx, t, dur, esc):
    mm = 18
    box = [50, 470, W - 50, 900]
    papel(d, box, mm, origen=(box[0] + 20, 470))
    t_p = tpal(esc, "P,")
    t_avr = tpal(esc, "aVR,")
    t_rr = tpal(esc, "R-R")
    t_reg = tpal(esc, "regulares.")
    span = (box[2] - box[0] - 40) / (25 * mm)
    head = span * ei(t, 0.1, min(2.5, t_p))
    x0, yb = tira(d, box, mm, 0.0, head, "II", BLANCO)
    d.text((box[0] + 24, box[1] + 30), "DII", font=F(F_MONO, 30), fill=GRIS, anchor="lm")
    pps = 25 * mm
    n_lat = int(span / RR) + 1
    # P antes de cada QRS
    for k in range(n_lat):
        tp = k * RR + 0.10
        if tp > span - 0.05:
            continue
        ti = t_p + k * 0.18
        fx.en(ti, "tic")
        q = eo(t, ti, 0.35)
        if q > 0:
            x = x0 + tp * pps
            y = yb - 0.15 * 10 * mm
            d.ellipse([x - 26, y - 26, x + 26, y + 26], outline=VERDE, width=4)
            d.text((x, y - 50), "P", font=F(F_MONO, 30), fill=VERDE, anchor="mm")
    # aVR: P negativa
    box2 = [50, 950, 520, 1300]
    q = eo(t, t_avr, 0.45)
    fx.en(t_avr, "tic")
    for (bx, lead, col, txt, tz) in [(box2, "II", VERDE, "P (+) en DII", tpal(esc, "DII")),
                                     ([560, 950, W - 50, 1300], "aVR", CORAL, "P (−) en aVR", t_avr)]:
        q = eo(t, tz, 0.45)
        if q <= 0:
            continue
        papel(d, bx, 14, r=20)
        xx, yy = bx[0] + 20, bx[1] + (bx[3] - bx[1]) * 0.6
        pts = puntos_traza(xx, yy, 25 * 14 * 1.6, 10 * 14 * 0.9, 0.0, min(0.62, 0.62 * min(1, q)),
                           lambda s, L=lead: ecg(s, L), 200)
        trazo(d, pts, col, 4)
        xp = xx + 0.10 * 25 * 14 * 1.6
        d.ellipse([xp - 24, yy - 24 - (12 if lead == "II" else -10), xp + 24, yy + 24 - (12 if lead == "II" else -10)],
                  outline=col, width=3)
        d.text((bx[0] + 24, bx[1] + 32), lead, font=F(F_MONO, 28), fill=GRIS, anchor="lm")
        d.text(((bx[0] + bx[2]) / 2, bx[3] - 34), txt, font=F(F_MONO, 30), fill=col, anchor="mm")
    # R-R regulares
    fx.en(t_rr, "tic")
    for k in range(n_lat - 1):
        tr0, tr1 = k * RR + 0.235, (k + 1) * RR + 0.235
        if tr1 > span:
            continue
        q = eo(t, t_rr + k * 0.15, 0.35)
        corchete(d, x0 + tr0 * pps, x0 + tr1 * pps, box[1] + 70, CIAN, "0.80 s" if q > 0.6 else None,
                 F(F_MONO, 26), min(1, q) if q > 0 else 0, arriba=False)
    fx.en(t_reg + 0.3, "ok")
    if t > t_reg + 0.3:
        pildora(d, W / 2, 1385, "RITMO SINUSAL", VERDE, F(F_BLACK, 44), fill=mix(BG, VERDE, 0.12), check=True)


def esc_frecuencia(fr, d, fx, t, dur, esc):
    mm = 24
    box = [50, 470, W - 50, 1010]
    x0 = box[0] + 60
    papel(d, box, mm, origen=(x0, 470))
    pps = 25 * mm
    off = 0.235  # una onda R cae justo sobre la línea gruesa x0
    yb = 800
    head = (box[2] - x0 - 20) / pps * ei(t, 0.1, 1.6)
    pts = puntos_traza(x0, yb, pps, 10 * mm, -0.07, head, lambda s_: ecg(s_ + off), 600, rel=False)
    trazo(d, [p for p in pts if p[0] < box[2] - 14], BLANCO, 4)
    t_div = tpal(esc, "Divide")
    t_gr = tpal(esc, "grandes")
    t_4 = tpal(esc, "4,")
    t_75 = tpal(esc, "75")
    t_norm = tpal(esc, "normal")
    serie = ["300", "150", "100", "75", "60", "50"]
    y_num = 900
    if t > t_div:
        pildora(d, x0, y_num, "R", VERDE, F(F_MONO, 28), fill=PAPEL_BG)
    for i, num in enumerate(serie):
        ti = t_gr + 0.1 + i * 0.2
        fx.en(ti, "tic")
        if t > ti:
            x = x0 + (i + 1) * 5 * mm
            hl = num == "75" and t > t_75
            col = CORAL if hl else AMBAR
            d.line([(x, box[1] + 20), (x, y_num - 26)], fill=mix(PAPEL_BG, col, 0.65 if hl else 0.3), width=3)
            pildora(d, x, y_num, num, col, F(F_MONO, 28), fill=PAPEL_BG, pad=(14, 10))
    fx.en(t_4, "beep")
    for k in range(4):
        tk = t_4 - 0.4 + k * 0.1
        if t > tk:
            xa = x0 + k * 5 * mm
            d.rectangle([xa + 4, 948, xa + 5 * mm - 4, 988], fill=mix(PAPEL_BG, CORAL, 0.5))
            d.text((xa + 2.5 * mm, 968), str(k + 1), font=F(F_MONO, 24), fill=BLANCO, anchor="mm")
    if t > t_div:
        tarjeta(d, [80, 1050, W - 80, 1215])
        partes = [("300", BLANCO, t_div), (" ÷ ", GRIS, t_div), ("4", CORAL, t_4), (" = ", GRIS, t_75),
                  ("75", VERDE, t_75), (" lpm", GRIS, t_75)]
        f = F(F_BLACK, 92)
        tot = sum(d.textlength(p[0], font=f) for p in partes)
        x = W / 2 - tot / 2
        for txt, col, tz in partes:
            if t > tz:
                d.text((x, 1132), txt, font=f, fill=col, anchor="lm")
            x += d.textlength(txt, font=f)
    fx.en(t_norm, "ok")
    if t > t_norm:
        bx0, bx1, y = 120, W - 120, 1330
        escala = lambda v: bx0 + (v - 30) / (150 - 30) * (bx1 - bx0)
        d.rounded_rectangle([bx0, y - 14, bx1, y + 14], radius=14, fill=mix(BG, CORAL, 0.35))
        d.rounded_rectangle([escala(60), y - 14, escala(100), y + 14], radius=14, fill=VERDE)
        for v in (60, 100):
            d.text((escala(v), y + 46), str(v), font=F(F_MONO, 30), fill=BLANCO, anchor="mm")
        d.text((bx0, y - 44), "BRADICARDIA", font=F(F_MONO_M, 24), fill=GRIS, anchor="lm")
        d.text((bx1, y - 44), "TAQUICARDIA", font=F(F_MONO_M, 24), fill=GRIS, anchor="rm")
        d.text(((escala(60) + escala(100)) / 2, y - 44), "NORMAL", font=F(F_MONO, 26), fill=VERDE, anchor="mm")
        xm = escala(75)
        d.polygon([(xm, y + 18), (xm - 13, y + 38), (xm + 13, y + 38)], fill=BLANCO)


def qrs_icono(d, x, y, signo, col, s=1.0):
    """Mini complejo QRS positivo o negativo."""
    h = 70 * s * signo
    pts = [(x - 50 * s, y), (x - 18 * s, y), (x - 10 * s, y + 0.15 * h), (x, y - h), (x + 10 * s, y + 0.2 * h),
           (x + 18 * s, y), (x + 50 * s, y)]
    d.line(pts, fill=col, width=5, joint="curve")


def esc_eje(fr, d, fx, t, dur, esc):
    cx, cy, R = W / 2 - 140, CY - 20, 300
    q0 = ei(t, 0, 0.5)
    t_norm = tpal(esc, "normal.")
    t_der = tpal(esc, "derecha;")
    t_izq = tpal(esc, "izquierda.")
    t_di = tpal(esc, "DI")
    # sectores
    sectores = [(-30, 90, VERDE, "NORMAL", t_norm), (90, 180, CORAL, "DERECHA", t_der),
                (-90, -30, AMBAR, "IZQUIERDA", t_izq)]
    for a0, a1, col, nom, tz in sectores:
        q = eo(t, tz, 0.4)
        if q > 0:
            d.pieslice([cx - R, cy - R, cx + R, cy + R], a0, a1, fill=mix(BG, col, 0.22 * min(1, q)),
                       outline=mix(BG, col, 0.7), width=2)
            am = math.radians((a0 + a1) / 2)
            pildora(d, cx + (R + 10) * math.cos(am), cy + (R + 10) * math.sin(am), nom, col, F(F_MONO, 22),
                    fill=BG, pad=(12, 8))
    d.ellipse([cx - R, cy - R, cx + R, cy + R], outline=mix(BG, BORDE, q0), width=3)
    # ejes DI y aVF
    fx.en(t_di, "tic")
    q = eo(t, t_di, 0.4)
    if q > 0:
        L = R * min(1, q)
        d.line([(cx - L, cy), (cx, cy)], fill=mix(BG, CIAN, 0.4), width=3)
        flecha(d, (cx, cy), (cx + L, cy), CIAN, 4)
        d.line([(cx, cy - L), (cx, cy)], fill=mix(BG, AMBAR, 0.4), width=3)
        flecha(d, (cx, cy), (cx, cy + L), AMBAR, 4)
        d.text((cx + R - 10, cy - 28), "DI 0°", font=F(F_MONO, 28), fill=CIAN, anchor="rm")
        d.text((cx, cy + R + 34), "aVF +90°", font=F(F_MONO, 28), fill=AMBAR, anchor="mm")
        d.text((cx, cy - R - 30), "−90°", font=F(F_MONO_M, 24), fill=GRIS, anchor="mm")
        d.text((cx - R - 20, cy), "±180°", font=F(F_MONO_M, 24), fill=GRIS, anchor="rm")
    # vector del eje
    estados = [(t_norm, 60, (1, 1, 1)), (t_der, 120, (-1, 1, 1)), (t_izq, -55, (1, -1, -1))]
    ang, signos, col = None, None, BLANCO
    for i, (tz, a, sg) in enumerate(estados):
        if t > tz - 0.3:
            prev = estados[i - 1][1] if i > 0 else 0
            u = ei(t, tz - 0.3, 0.6)
            ang = lerp(prev, a, u)
            signos = sg
            col = [VERDE, CORAL, AMBAR][i]
    if ang is not None:
        fx.en(estados[0][0] - 0.3, "swoosh", vol=0.6)
        fx.en(estados[1][0] - 0.3, "swoosh", vol=0.6)
        fx.en(estados[2][0] - 0.3, "swoosh", vol=0.6)
        a = math.radians(ang)
        tip = (cx + R * 0.92 * math.cos(a), cy + R * 0.92 * math.sin(a))
        d.line([(cx, cy), tip], fill=mix(BG, col, 0.3), width=22)
        flecha(d, (cx, cy), tip, col, 9, 34)
        d.ellipse([cx - 14, cy - 14, cx + 14, cy + 14], fill=BLANCO)
    # mini QRS de DI, aVF y DII
    fichas = [("DI", 0, CIAN), ("aVF", 1, AMBAR), ("DII", 2, VIOLETA)]
    for nom, idx, cl in fichas:
        bx0, by0 = W - 300, 560 + idx * 210
        q = eo(t, t_di + idx * 0.12, 0.4)
        if idx == 2:
            q = eo(t, tpal(esc, "DII"), 0.4)
        if q <= 0:
            continue
        tarjeta(d, [bx0, by0, W - 50, by0 + 180], r=22)
        d.text((bx0 + 24, by0 + 30), nom, font=F(F_MONO, 28), fill=cl, anchor="lm")
        sg = signos[idx] if signos else 1
        qrs_icono(d, bx0 + 125, by0 + 115, sg, cl, 1.0)
        d.text((W - 80, by0 + 30), "+" if sg > 0 else "−", font=F(F_BLACK, 44), fill=VERDE if sg > 0 else CORAL,
               anchor="rm")
    if ang is not None:
        nom = ["EJE NORMAL", "DESVIACIÓN DERECHA", "DESVIACIÓN IZQUIERDA"][[VERDE, CORAL, AMBAR].index(col)]
        pildora(d, W / 2, 1380, nom, col, F(F_BLACK, 40))
    fx.en(t_norm, "ok")
    fx.en(t_der, "alerta")
    fx.en(t_izq, "alerta")


def esc_intervalos(fr, d, fx, t, dur, esc):
    mm = 26
    box = [50, 470, W - 50, 1080]
    x0, y0 = 150, 840
    pps, ppmv = 25 * mm * 1.35, 10 * mm * 0.95
    papel(d, box, mm, origen=(x0, y0))
    head = 0.66 * ei(t, 0.1, 1.2)
    trazo(d, puntos_traza(x0, y0, pps, ppmv, 0.0, head, lambda s_: latido(s_), 500), BLANCO, 5)
    t_pr = tpal(esc, "PR")
    t_qrs = tpal(esc, "QRS,")
    t_qt = tpal(esc, "QTc,")
    X = lambda s_: x0 + s_ * pps
    items = [("PR", 0.075, 0.205, VERDE, t_pr, 945, "0.12 – 0.20 s", "3 a 5 cuadros pequeños"),
             ("QRS", 0.205, 0.28, CORAL, t_qrs, 995, "< 0.12 s", "< 3 cuadros pequeños"),
             ("QTc", 0.205, 0.555, AMBAR, t_qt, 1045, "< 440 ms (H) · < 460 ms (M)", "")]
    for i, (nom, a, b, col, tz, y, val, sub_) in enumerate(items):
        fx.en(tz, "tic")
        fx.en(tz + 0.35, "ok", vol=0.6)
        q = eo(t, tz, 0.45)
        if q <= 0:
            continue
        for xx in (X(a), X(b)):
            for yy in range(int(y0 + 70), int(y - 14), 20):
                d.line([(xx, yy), (xx, yy + 9)], fill=mix(PAPEL_BG, col, 0.7), width=2)
        corchete(d, X(a), X(b), y, col, nom, F(F_MONO, 26), min(1, q), lado="der")
    for i, (nom, a, b, col, tz, y, val, sub_) in enumerate(items):
        q = eo(t, tz + 0.25, 0.45)
        if q <= 0:
            continue
        by0 = 1110 + i * 96
        xo = (1 - min(1, q)) * 300
        tarjeta(d, [60 + xo, by0, W - 60 + xo, by0 + 84], borde=mix(BG, col, 0.7), r=22)
        d.text((95 + xo, by0 + 42), nom, font=F(F_MONO, 32), fill=col, anchor="lm")
        d.text((225 + xo, by0 + 42), val, font=F(F_BOLD, 36), fill=BLANCO, anchor="lm")
        if sub_:
            d.text((W - 90 + xo, by0 + 42), sub_, font=F(F_MED, 24), fill=GRIS, anchor="rm")


def esc_st(fr, d, fx, t, dur, esc):
    t_iso = tpal(esc, "isoeléctrica")
    t_elev = tpal(esc, "elevación")
    t_inf = tpal(esc, "infarto")
    t_dep = tpal(esc, "depresión")
    t_tinv = tpal(esc, "invertida")
    t_isq = tpal(esc, "isquemia")
    casos = [("NORMAL", dict(), VERDE, 0.1, None),
             ("ELEVACIÓN ST", dict(st=0.28, T=0.45), CORAL, t_elev, "Infarto agudo"),
             ("DEPRESIÓN ST", dict(st=-0.2, T=0.12), AMBAR, t_dep, "Isquemia"),
             ("T INVERTIDA", dict(T=-0.3), VIOLETA, t_tinv, "Isquemia")]
    mm = 13
    for i, (nom, kw, col, tz, diag) in enumerate(casos):
        r, c = divmod(i, 2)
        bx = [50 + c * 500, 480 + r * 430, 50 + c * 500 + 480, 480 + r * 430 + 400]
        q = eo(t, tz, 0.45)
        fx.en(tz, "alerta" if i == 1 else ("tic" if i == 0 else "pop"))
        if q <= 0:
            continue
        papel(d, bx, mm, r=22, borde=col)
        yb = bx[1] + 250
        # isoeléctrica
        if t > t_iso:
            qq = ei(t, t_iso, 0.6)
            for x in range(int(bx[0] + 14), int(bx[0] + 14 + (bx[2] - bx[0] - 28) * qq), 24):
                d.line([(x, yb), (x + 12, yb)], fill=CIAN, width=2)
        if q > 0:
            head = 0.66 * clamp01((t - tz) / 0.8)
            pts = puntos_traza(bx[0] + 24, yb, 25 * mm * 1.35, 10 * mm * 1.15, 0.0, head,
                               lambda s, kw=kw: latido(s, **{**dict(P=.15, Q=-.1, R=1.3, S=-.25, T=.35), **kw}), 300)
            trazo(d, pts, col, 4)
            d.text((bx[0] + 22, bx[1] + 32), nom, font=F(F_MONO, 26), fill=col, anchor="lm")
            if i in (1, 2) and t > tz + 0.6:
                # resalta el segmento ST
                xs0 = bx[0] + 24 + 0.28 * 25 * mm * 1.35
                xs1 = bx[0] + 24 + 0.40 * 25 * mm * 1.35
                yst = yb - kw["st"] * 10 * mm * 1.15
                d.rounded_rectangle([xs0 - 6, min(yst, yb) - 16, xs1 + 6, max(yst, yb) + 16], radius=10, outline=col,
                                    width=3)
            if diag and t > (t_inf if i == 1 else t_isq):
                pildora(d, (bx[0] + bx[2]) / 2, bx[3] - 40, diag, col, F(F_SEMI, 28), fill=PAPEL_BG)
    q = eo(t, t_iso, 0.4)
    if q > 0:
        d.text((W / 2, 1365), "- - -  línea isoeléctrica (segmento PR / TP)", font=F(F_MONO_M, 26), fill=CIAN,
               anchor="mm")
    q = eo(t, tpal(esc, "contiguas"), 0.4)
    if q > 0:
        pildora(d, W / 2, 1420, "≥ 2 derivaciones contiguas", CORAL, F(F_MONO, 28))


def esc_resumen(fr, d, fx, t, dur, esc):
    pasos = [("RITMO", "¿Sinusal? P antes de cada QRS", "ritmo,", VERDE),
             ("FRECUENCIA", "300 ÷ cuadros grandes", "frecuencia,", CORAL),
             ("EJE", "DI y aVF (y DII)", "eje,", CIAN),
             ("INTERVALOS", "PR · QRS · QTc", "intervalos", AMBAR),
             ("ST-T", "Elevación · depresión · T", "ST.", VIOLETA)]
    for i, (nom, sub, clave, col) in enumerate(pasos):
        tz = tpal(esc, clave)
        fx.en(tz, "ok", vol=0.7)
        q = eo(t, tz - 0.15, 0.45)
        if q <= 0:
            continue
        y = 520 + i * 165
        xo = (1 - min(1, q)) * 400
        tarjeta(d, [60 + xo, y, W - 60 + xo, y + 140], borde=mix(BG, col, 0.7))
        d.ellipse([90 + xo, y + 30, 170 + xo, y + 110], fill=mix(BG, col, 0.2), outline=col, width=3)
        d.text((130 + xo, y + 70), str(i + 1), font=F(F_MONO, 40), fill=col, anchor="mm")
        d.text((205 + xo, y + 52), nom, font=F(F_BLACK, 46), fill=BLANCO, anchor="lm")
        d.text((205 + xo, y + 102), sub, font=F(F_MED, 28), fill=GRIS, anchor="lm")
        palomita(d, W - 125 + xo, y + 70, 1.4, col, clamp01((t - tz) / 0.4))
    # traza decorativa
    t_ord = tpal(esc, "orden")
    q = eo(t, t_ord, 0.4)
    if q > 0:
        pildora(d, W / 2, 1385, "SIEMPRE EN EL MISMO ORDEN", VERDE, F(F_MONO, 30))


def boton(d, x, y, w, h, txt, col, activo, icono=None):
    fill = col if activo else mix(BG, col, 0.15)
    d.rounded_rectangle([x - w / 2, y - h / 2, x + w / 2, y + h / 2], radius=int(h / 2), fill=fill, outline=col, width=3)
    d.text((x + (18 if icono else 0), y), txt, font=F(F_BLACK, 42), fill=BG if activo else col, anchor="mm")
    if icono == "guardar":
        ix, iy = x - w / 2 + 60, y
        c = BG if activo else col
        d.polygon([(ix - 16, iy - 24), (ix + 16, iy - 24), (ix + 16, iy + 24), (ix, iy + 10), (ix - 16, iy + 24)],
                  fill=c)
    if icono == "seguir":
        ix, iy = x - w / 2 + 60, y
        c = BG if activo else col
        d.line([(ix - 18, iy), (ix + 18, iy)], fill=c, width=7)
        d.line([(ix, iy - 18), (ix, iy + 18)], fill=c, width=7)


def esc_outro(fr, d, fx, t, dur, esc):
    t_g = tpal(esc, "Guarda")
    t_com = tpal(esc, "comentarios")
    t_s = tpal(esc, "sígueme")
    x0, x1, y0 = 60, W - 60, 640
    pps, ppmv = 330, 150
    vent = (x1 - x0) / pps
    head = t % vent
    pts = puntos_traza(x0, y0, pps, ppmv, 0, head, lambda s_: ecg(s_ + int(t / vent) * vent), 400)
    trazo(d, pts, mix(BG, VERDE, 0.7), 4)
    if pts:
        cabeza(d, *pts[-1], VERDE, 7)
    taps = [t_g + 0.3, t_s + 0.1]
    fx.en(taps[0], "click")
    fx.en(taps[0] + 0.05, "ok", vol=0.6)
    fx.en(taps[1], "click")
    fx.en(taps[1] + 0.05, "ok", vol=0.8)
    q = eo(t, 0.2, 0.45)
    if q > 0:
        boton(d, W / 2, 900, 560 * min(1, q), 120, "GUARDADO" if t > taps[0] else "GUARDAR", CIAN, t > taps[0],
              "guardar")
    q = eo(t, 0.4, 0.45)
    if q > 0:
        boton(d, W / 2, 1060, 560 * min(1, q), 120, "SIGUIENDO" if t > taps[1] else "SEGUIR", VERDE, t > taps[1],
              "seguir")
    fx.en(t_com, "pop")
    if t > t_com:
        tarjeta(d, [120, 1170, W - 120, 1300], borde=VIOLETA, r=30)
        temas = ["Arritmias en el ECG", "Bloqueos de rama", "Infarto en el ECG"]
        u = t - t_com
        tema = temas[int(u / 1.8) % 3]
        n = min(len(tema), int((u % 1.8) * 22))
        d.text((160, 1235), tema[:n] + ("|" if int(t * 3) % 2 == 0 else ""), font=F(F_MED, 40), fill=BLANCO,
               anchor="lm")
    # cursor: toca el extremo derecho de cada botón (no tapa el texto)
    objetivos = [(W / 2 + 220, 900), (W / 2 + 220, 1060)]
    pos = None
    if taps[0] - 0.8 < t < taps[1] + 0.6:
        if t < taps[0]:
            u = ei(t, taps[0] - 0.8, 0.8)
            pos = (lerp(W - 80, objetivos[0][0], u), lerp(H - 420, objetivos[0][1], u))
        elif t < taps[1] - 0.6:
            pos = objetivos[0]
        else:
            u = ei(t, taps[1] - 0.6, 0.6)
            pos = (objetivos[0][0], lerp(objetivos[0][1], objetivos[1][1], u))
    if pos:
        for tt in taps:
            if 0 <= t - tt < 0.4:
                r = 30 + (t - tt) * 160
                d.ellipse([pos[0] - r, pos[1] - r, pos[0] + r, pos[1] + r], outline=BLANCO, width=3)
        d.ellipse([pos[0] - 24, pos[1] - 24, pos[0] + 24, pos[1] + 24], fill=mix(BG, BLANCO, 0.85))


ANIM = {"intro": esc_intro, "papel": esc_papel, "ondas": esc_ondas, "frontales": esc_frontales,
        "precordiales": esc_precordiales, "caras": esc_caras, "ritmo": esc_ritmo, "frecuencia": esc_frecuencia,
        "eje": esc_eje, "intervalos": esc_intervalos, "st": esc_st, "resumen": esc_resumen, "outro": esc_outro}


# ----------------------------------------------------------------------------
# FONDO, CABECERA, SUBTÍTULOS, MONITOR
# ----------------------------------------------------------------------------
def fondo():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    base = np.zeros((H, W, 3), np.float32)
    top, bot = np.array([8, 18, 34], np.float32), np.array([3, 6, 14], np.float32)
    k = (yy / H)[:, :, None]
    base[:] = top * (1 - k) + bot * k
    glow = np.exp(-(((xx - W * 0.5) / (W * 0.7)) ** 2 + ((yy - 820) / (H * 0.35)) ** 2))[:, :, None]
    base += glow * np.array([10, 40, 50], np.float32)
    img = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    for x in range(0, W, 30):
        d.line([(x, 0), (x, H)], fill=(12, 24, 40) if x % 150 else (17, 33, 54), width=1)
    for y in range(0, H, 30):
        d.line([(0, y), (W, y)], fill=(12, 24, 40) if y % 150 else (17, 33, 54), width=1)
    return img


def cabecera(d, idx, t_esc, dur, esc, total):
    # barra de progreso
    m = 50
    d.rounded_rectangle([m, 58, W - m, 64], radius=3, fill=(30, 44, 64))
    prog = (idx + clamp01(t_esc / dur)) / total
    d.rounded_rectangle([m, 58, m + (W - 2 * m) * prog, 64], radius=3, fill=esc["acento"])
    d.text((m, 108), "ECG · 25 mm/s", font=F(F_MONO_M, 24), fill=GRIS, anchor="lm")
    d.text((W - m, 108), f"{idx + 1:02d} / {total:02d}", font=F(F_MONO_M, 24), fill=GRIS, anchor="rm")
    # kicker + título
    p = eo(t_esc, 0.05, 0.5)
    if p > 0:
        a = min(1, p)
        yo = 30 * (1 - a)
        d.text((W / 2, 205 + yo), esc["kicker"], font=F(F_MONO, 30), fill=mix(BG, esc["acento"], a), anchor="mm")
        tam = 84 if len(esc["titulo"]) <= 18 else 72
        d.text((W / 2, 290 + yo), esc["titulo"], font=F(F_BLACK, tam), fill=mix(BG, BLANCO, a), anchor="mm")
        w = d.textlength(esc["titulo"], font=F(F_BLACK, tam))
        lw = w * ei(t_esc, 0.3, 0.5)
        d.rounded_rectangle([W / 2 - lw / 2, 352 + yo, W / 2 + lw / 2, 358 + yo], radius=3, fill=esc["acento"])
    if esc.get("paso"):
        for i in range(5):
            x = W / 2 + (i - 2) * 48
            on = i < esc["paso"]
            d.ellipse([x - 9, 400 - 9, x + 9, 400 + 9], fill=esc["acento"] if on else (36, 52, 76))


def subtitulos(d, grupos, t, acento):
    for g in grupos:
        if g[0][0] <= t < g[-1][1] + 0.08:
            break
    else:
        return
    f = F(F_BOLD, 60)
    esp = d.textlength(" ", font=f)
    pal = [w[2] for w in g]
    anch = [d.textlength(p, font=f) for p in pal]
    lineas, act, ac = [], [], 0
    for i, a in enumerate(anch):
        if act and ac + esp + a > W - 150:
            lineas.append(act)
            act, ac = [], 0
        ac += (esp if act else 0) + a
        act.append(i)
    lineas.append(act)
    ent = clamp01((t - g[0][0]) / 0.15)
    y0 = 1555 - (len(lineas) - 1) * 38 + 14 * (1 - ent)
    for li, idxs in enumerate(lineas):
        tot = sum(anch[i] for i in idxs) + esp * (len(idxs) - 1)
        x = W / 2 - tot / 2
        y = y0 + li * 76
        for i in idxs:
            a, b, _ = g[i]
            if t >= b:
                col = BLANCO
            elif t >= a:
                col = acento
            else:
                col = mix(BG, BLANCO, 0.45)
            d.text((x + 2, y + 4), pal[i], font=f, fill=(0, 0, 0), anchor="lm")
            d.text((x, y), pal[i], font=f, fill=col, anchor="lm")
            if a <= t < b:
                d.rounded_rectangle([x, y + 36, x + anch[i], y + 42], radius=3, fill=acento)
            x += anch[i] + esp


def monitor(d, t, acento):
    y0, x0, x1 = 1790, 50, W - 50
    d.line([(x0, 1720), (x1, 1720)], fill=(24, 38, 58), width=2)
    pps, ppmv = 220, 55
    vent = 3.2
    pts = puntos_traza(x0 + 200, y0, (x1 - x0 - 200) / vent, ppmv, t - vent, t, lambda s: ecg(s), 300)
    for i in range(1, len(pts)):
        a = i / len(pts)
        d.line([pts[i - 1], pts[i]], fill=mix(BG, VERDE, 0.15 + 0.85 * a), width=3)
    cabeza(d, *pts[-1], VERDE, 5)
    pul = math.exp(-((t - 0.235) % RR) * 7)
    corazon(d, x0 + 30, y0 - 6, 0.55 + 0.15 * pul, CORAL)
    d.text((x0 + 70, y0 - 2), "75", font=F(F_MONO, 54), fill=VERDE, anchor="lm")
    d.text((x0 + 70, y0 + 42), "LPM", font=F(F_MONO_M, 20), fill=GRIS, anchor="lm")


# ----------------------------------------------------------------------------
# DURACIONES, GUION Y RENDER
# ----------------------------------------------------------------------------
def duraciones(args):
    if args.voz_dir:
        arch = sorted(glob.glob(os.path.join(args.voz_dir, "escena_*")))
        assert len(arch) == len(ESCENAS), f"Se esperaban {len(ESCENAS)} audios escena_XX"
        auds = [v2.leer_audio(a) for a in arch]
        return [len(a) / SR for a in auds], auds
    from kokoro_onnx import Kokoro
    k = Kokoro(args.modelo, args.voces)
    out = []
    for e in ESCENAS:
        s, sr = k.create(e.get("voz", e["texto"]), voice=args.voz_ref, speed=args.velocidad, lang="es")
        s = np.asarray(s)
        idx = np.where(np.abs(s) > 0.02)[0]
        out.append((idx[-1] - idx[0]) / sr if len(idx) else len(s) / sr)
        print(f"  {e['id']}: {out[-1]:.2f}s")
    return out, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo")
    ap.add_argument("--voces")
    ap.add_argument("--voz-ref", default="em_alex")
    ap.add_argument("--velocidad", type=float, default=1.0)
    ap.add_argument("--voz-dir")
    ap.add_argument("--out", default=".")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    print("Calculando tiempos...")
    habla, audios = duraciones(args)
    durs = [max(MIN_DUR, LEAD + h + PAD) for h in habla]
    ini = np.concatenate([[0], np.cumsum(durs)])
    total = float(ini[-1])
    print(f"Duración total: {total:.1f}s")

    srt, guion, n = [], [], 1
    guion.append("GUION PARA ELEVENLABS — CÓMO LEER UN ECG EN MENOS DE 3 MINUTOS\n")
    guion.append("Las siglas y los números están escritos como se pronuncian en español (cu erre ese, a ve efe,\n"
                 "de dos, ese te, cero punto doce...) para que ElevenLabs no los lea en inglés.\n"
                 "Los subtítulos del video los muestran en su forma escrita (QRS, aVF, DII, ST, 0.12).\n"
                 f"Genera un audio por escena y colócalo en el tiempo indicado, o pásame los audios\n"
                 f"(escena_01.mp3 ... escena_{len(ESCENAS):02d}.mp3) y re-sincronizo el video.\n")
    for i, (e, h) in enumerate(zip(ESCENAS, habla)):
        e["_palabras"] = v2.palabras_con_tiempo(e["texto"], LEAD, LEAD + h)
        e["_grupos"] = v2.agrupar(e["_palabras"], 32)
        for g in e["_grupos"]:
            srt.append(f"{n}\n{v2.fmt_srt(ini[i] + g[0][0])} --> {v2.fmt_srt(ini[i] + g[-1][1])}\n"
                       f"{' '.join(w[2] for w in g)}\n")
            n += 1
        guion.append(f"\n[ESCENA {i + 1:02d} — {e['titulo']}]  empieza en {v2.fmt_mmss(ini[i] + LEAD)}  "
                     f"(voz aprox. {h:.1f}s)\n{e.get('voz', e['texto'])}\n")
    guion.append("\n\nTEXTO COMPLETO (para pegar de una sola vez):\n\n" +
                 "\n\n".join(e.get("voz", e["texto"]) for e in ESCENAS) + "\n")
    with open(os.path.join(args.out, "subtitulos.srt"), "w", encoding="utf-8") as f:
        f.write("\n".join(srt))
    with open(os.path.join(args.out, "guion_elevenlabs.txt"), "w", encoding="utf-8") as f:
        f.write("".join(guion))

    fx = v2.FX()
    bg = fondo()
    tmp = tempfile.mkdtemp()
    mudo = os.path.join(tmp, "v.mp4")
    proc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s",
                             f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf",
                             "18", "-pix_fmt", "yuv420p", mudo], stdin=subprocess.PIPE)
    nf = int(math.ceil(total * FPS))
    t_prev, idx_prev = -1.0, -1
    for fi in range(nf):
        t = fi / FPS
        idx = min(len(ESCENAS) - 1, int(np.searchsorted(ini, t, side="right") - 1))
        e = ESCENAS[idx]
        te = t - ini[idx]
        if idx != idx_prev:
            t_prev, idx_prev = -1.0, idx
        fx.frame(te, t_prev, t)
        t_prev = te
        fr = bg.copy()
        d = ImageDraw.Draw(fr)
        ANIM[e["id"]](fr, d, fx, te, durs[idx], e)
        # transición: el contenido entra con un barrido suave
        if te < 0.22 and idx > 0:
            a = 1 - ease_in_out(te / 0.22)
            fr = Image.blend(fr, bg, a)
            d = ImageDraw.Draw(fr)
        cabecera(d, idx, te, durs[idx], e, len(ESCENAS))
        subtitulos(d, e["_grupos"], te, e["acento"])
        monitor(d, t, e["acento"])
        if idx == len(ESCENAS) - 1:
            fr = Image.blend(Image.new("RGB", fr.size, (0, 0, 0)), fr, clamp01((durs[idx] - te) / 0.6))
        proc.stdin.write(fr.tobytes())
        if fi % (FPS * 10) == 0:
            print(f"  frame {fi}/{nf}")
    proc.stdin.close()
    proc.wait()

    nmu = int(total * SR) + SR
    efx = np.zeros(nmu)
    for i in range(1, len(ESCENAS)):
        fx.sonidos.append((ini[i] - 0.08, "swoosh", 0.5))
    for tg, nom, vol in fx.sonidos:
        s = SFX[nom] * SFX_VOL[nom] * vol
        i0 = int(max(0, tg) * SR)
        efx[i0:i0 + len(s)] += s[:max(0, nmu - i0)]
    voz = np.zeros(nmu)
    if audios:
        for i, a in enumerate(audios):
            i0 = int((ini[i] + LEAD) * SR)
            voz[i0:i0 + len(a)] += a[:max(0, nmu - i0)]
    mus = np.pad(musica(total), (0, nmu - int(total * SR)))
    pistas = {f"{NOMBRE}.mp4": efx * 0.6 + mus * 0.16, f"{NOMBRE}_sin_musica.mp4": efx * 0.6}
    if audios:
        pistas = {f"{NOMBRE}_con_voz.mp4": efx * 0.35 + mus * 0.08 + voz * 0.95}
    for nom, a in pistas.items():
        a = a[:int(total * SR)]
        pk = np.max(np.abs(a)) + 1e-6
        if pk > 0.97:
            a = a / pk * 0.97
        wav = os.path.join(tmp, "a.wav")
        sf.write(wav, a.astype(np.float32), SR)
        sal = os.path.join(args.out, nom)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", mudo, "-i", wav, "-c:v", "copy", "-c:a", "aac", "-b:a",
                        "192k", "-shortest", "-movflags", "+faststart", sal], check=True)
        print("Listo:", sal)


if __name__ == "__main__":
    main()
