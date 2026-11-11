#!/usr/bin/env python3
"""
Reel — "Biología en Minutos": CÓMO LEER UN ELECTROCARDIOGRAMA (ECG) PASO A PASO.

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
LEAD, PAD, MIN_DUR = 0.25, 1.0, 5.0
MARCA = "BIOLOGÍA EN MINUTOS"
NOMBRE = "reel_ecg"

# ----------------------------------------------------------------------------
# ESTILO
# ----------------------------------------------------------------------------
FD = os.path.join(AQUI, "fonts")
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
    dict(id="intro", kicker=MARCA, titulo="Cómo leer un ECG", acento=VERDE,
         texto="¡Hola! Soy Biología en Minutos, y hoy vas a aprender a leer un electrocardiograma paso a paso."),
    dict(id="papel", kicker="FUNDAMENTOS · 01", titulo="El papel del ECG", acento=CORAL,
         texto="Primero, el papel. A 25 mm/s, cada cuadro pequeño mide 1 mm: equivale a 0.04 segundos en horizontal "
               "y a 0.1 mV en vertical. Un cuadro grande, de cinco pequeños, equivale a 0.20 segundos.",
         voz="Primero, el papel. A veinticinco milímetros por segundo, cada cuadro pequeño mide un milímetro: "
             "equivale a cero punto cero cuatro segundos en horizontal, y a cero punto un milivoltios en vertical. "
             "Un cuadro grande, de cinco pequeños, equivale a cero punto dos segundos."),
    dict(id="ondas", kicker="FUNDAMENTOS · 02", titulo="Ondas del latido", acento=VERDE,
         texto="Cada latido tiene tres componentes: la onda P, que es la despolarización auricular; el complejo QRS, "
               "la despolarización ventricular; y la onda T, la repolarización ventricular.",
         voz="Cada latido tiene tres componentes: la onda P, que es la despolarización auricular; el complejo Q R S, "
             "la despolarización ventricular; y la onda T, la repolarización ventricular."),
    dict(id="frontales", kicker="DERIVACIONES · 03", titulo="Plano frontal", acento=CIAN,
         texto="El ECG tiene 12 derivaciones. Seis son del plano frontal: las bipolares DI, DII y DIII, "
               "y las monopolares aumentadas aVR, aVL y aVF.",
         voz="El electrocardiograma tiene doce derivaciones. Seis son del plano frontal: las bipolares D uno, D dos "
             "y D tres, y las monopolares aumentadas a V R, a V L y a V F."),
    dict(id="precordiales", kicker="DERIVACIONES · 04", titulo="Precordiales", acento=AMBAR,
         texto="Las otras seis son las precordiales, de V1 a V6, y registran el plano horizontal. V1 y V2 van en el "
               "cuarto espacio intercostal, a los lados del esternón; V4, en el quinto espacio, línea medioclavicular; "
               "y V6, en la línea medioaxilar.",
         voz="Las otras seis son las precordiales, de V uno a V seis, y registran el plano horizontal. V uno y V dos "
             "van en el cuarto espacio intercostal, a los lados del esternón; V cuatro, en el quinto espacio, línea "
             "medioclavicular; y V seis, en la línea medioaxilar."),
    dict(id="caras", kicker="DERIVACIONES · 05", titulo="Caras del corazón", acento=VIOLETA,
         texto="Cada grupo mira una cara del corazón: DII, DIII y aVF, la cara inferior; DI, aVL, V5 y V6, la lateral; "
               "V1 y V2, el septo; y V3 y V4, la cara anterior.",
         voz="Cada grupo mira una cara del corazón: D dos, D tres y a V F, la cara inferior; D uno, a V L, V cinco y "
             "V seis, la lateral; V uno y V dos, el septo; y V tres y V cuatro, la cara anterior."),
    dict(id="ritmo", kicker="PASO 1 DE 5", titulo="Ritmo", acento=VERDE, paso=1,
         texto="Paso 1: el ritmo. Es sinusal si cada QRS va precedido de una onda P, positiva en DII y negativa en aVR, "
               "y si los intervalos R-R son regulares.",
         voz="Paso uno: el ritmo. Es sinusal si cada Q R S va precedido de una onda P, positiva en D dos y negativa "
             "en a V R, y si los intervalos R R son regulares."),
    dict(id="frecuencia", kicker="PASO 2 DE 5", titulo="Frecuencia", acento=CORAL, paso=2,
         texto="Paso 2: la frecuencia. Divide 300 entre el número de cuadros grandes que hay entre dos ondas R. "
               "Si hay 4, la frecuencia es de 75 lpm. Lo normal es de 60 a 100.",
         voz="Paso dos: la frecuencia. Divide trescientos entre el número de cuadros grandes que hay entre dos ondas R. "
             "Si hay cuatro, la frecuencia es de setenta y cinco latidos por minuto. Lo normal es de sesenta a cien."),
    dict(id="eje", kicker="PASO 3 DE 5", titulo="Eje eléctrico", acento=CIAN, paso=3,
         texto="Paso 3: el eje eléctrico. Mira el QRS en DI y aVF: si ambos son positivos, el eje es normal. "
               "Si DI es negativo, hay desviación a la derecha; si aVF es negativo y DII también, desviación a la izquierda.",
         voz="Paso tres: el eje eléctrico. Mira el Q R S en D uno y a V F: si ambos son positivos, el eje es normal. "
             "Si D uno es negativo, hay desviación a la derecha; si a V F es negativo y D dos también, desviación a la "
             "izquierda."),
    dict(id="intervalos", kicker="PASO 4 DE 5", titulo="Intervalos", acento=AMBAR, paso=4,
         texto="Paso 4: los intervalos. El PR normal mide de 0.12 a 0.20 segundos, de 3 a 5 cuadros pequeños. "
               "El QRS, menos de 0.12 segundos. Y el QT corregido, menos de 440 ms en hombres y de 460 en mujeres.",
         voz="Paso cuatro: los intervalos. El P R normal mide de cero punto doce a cero punto veinte segundos, de tres a "
             "cinco cuadros pequeños. El Q R S, menos de cero punto doce segundos. Y el Q T corregido, menos de "
             "cuatrocientos cuarenta milisegundos en hombres y de cuatrocientos sesenta en mujeres."),
    dict(id="st", kicker="PASO 5 DE 5", titulo="Segmento ST y onda T", acento=CORAL, paso=5,
         texto="Paso 5: el segmento ST y la onda T. Compáralos con la línea isoeléctrica. Una elevación del ST en dos "
               "derivaciones contiguas sugiere un infarto agudo; una depresión o una T invertida, isquemia.",
         voz="Paso cinco: el segmento S T y la onda T. Compáralos con la línea isoeléctrica. Una elevación del S T en "
             "dos derivaciones contiguas sugiere un infarto agudo; una depresión o una T invertida, isquemia."),
    dict(id="resumen", kicker="RESUMEN", titulo="Los 5 pasos", acento=VERDE,
         texto="Recuerda los cinco pasos: ritmo, frecuencia, eje, intervalos y segmento ST. "
               "Siempre en el mismo orden, y no se te escapará nada.",
         voz="Recuerda los cinco pasos: ritmo, frecuencia, eje, intervalos y segmento S T. "
             "Siempre en el mismo orden, y no se te escapará nada."),
    dict(id="outro", kicker=MARCA, titulo="¿Te sirvió?", acento=VERDE,
         texto="Guarda este video para tu próxima guardia. ¿Qué tema quieres que expliquemos después? "
               "Déjalo en los comentarios y regálame un follow."),
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


def puntos_traza(x0, y0, pps, ppmv, t0, t1, fn, n=None):
    n = n or max(2, int((t1 - t0) * pps / 2))
    ts = np.linspace(t0, t1, n)
    vs = fn(ts)
    return [(x0 + (tt - t0) * pps, y0 - vv * ppmv) for tt, vv in zip(ts, vs)]


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


def pildora(d, x, y, txt, col, fuente, fill=None, anchor="mm", pad=(22, 12), texto_col=None):
    tw = d.textlength(txt, font=fuente)
    h = fuente.size
    if anchor == "mm":
        bx0 = x - tw / 2 - pad[0]
    else:  # lm
        bx0 = x - pad[0]
    box = [bx0, y - h / 2 - pad[1], bx0 + tw + 2 * pad[0], y + h / 2 + pad[1]]
    d.rounded_rectangle(box, radius=int(h / 2 + pad[1]), fill=fill if fill else mix(BG, col, 0.18), outline=col, width=2)
    d.text(((box[0] + box[2]) / 2, y), txt, font=fuente, fill=texto_col or col, anchor="mm")
    return box


def flecha(d, p0, p1, col, w=4, cab=18):
    d.line([p0, p1], fill=col, width=w)
    a = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
    for s in (-1, 1):
        d.line([p1, (p1[0] - cab * math.cos(a + s * 0.45), p1[1] - cab * math.sin(a + s * 0.45))], fill=col, width=w)


def corchete(d, x0, x1, y, col, txt=None, fuente=None, p=1.0, arriba=True):
    """Calibrador horizontal con etiqueta."""
    if p <= 0:
        return
    xm = (x0 + x1) / 2
    a, b = lerp(xm, x0, p), lerp(xm, x1, p)
    h = 16
    d.line([(a, y), (b, y)], fill=col, width=4)
    d.line([(a, y - h), (a, y + h)], fill=col, width=4)
    d.line([(b, y - h), (b, y + h)], fill=col, width=4)
    if txt and p > 0.6:
        pildora(d, xm, y - 44 if arriba else y + 44, txt, col, fuente or F(F_MONO, 30))


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


def esc_intro(fr, d, fx, t, dur, esc):
    # monitor: trazo DII que barre toda la pantalla
    x0, x1, y0 = 40, W - 40, CY - 60
    pps, ppmv = 380, 210
    vent = (x1 - x0) / pps
    head = t % vent
    ciclo = int(t / vent)
    for k in range(int(t / RR) + 2):
        tr = k * RR + 0.235
        fx.en(tr, "beep")
        if k < 3:
            fx.en(tr - 0.05, "latido", vol=0.8)
    # traza vieja (se borra delante del cabezal) y nueva
    if ciclo > 0:
        pts = puntos_traza(x0, y0, pps, ppmv, head + 0.12, vent, lambda s: ecg(s + (ciclo - 1) * vent))
        trazo(d, pts, mix(BG, VERDE, 0.35), 3, glow=False)
    pts = puntos_traza(x0, y0, pps, ppmv, 0, head, lambda s: ecg(s + ciclo * vent))
    trazo(d, pts, VERDE, 5)
    if pts:
        cabeza(d, *pts[-1], VERDE)
    # lectura del monitor
    p = eo(t, 0.3)
    if p > 0:
        tarjeta(d, [80, CY + 210, W - 80, CY + 420], fill=mix(BG, PANEL, 0.9))
        d.text((130, CY + 260), "FC", font=F(F_MONO_M, 30), fill=GRIS, anchor="lm")
        pulso = math.exp(-((t - 0.235) % RR) * 8)
        corazon(d, 150, CY + 335, 0.9 + 0.25 * pulso, CORAL)
        d.text((230, CY + 335), "75", font=F(F_MONO, 110), fill=VERDE, anchor="lm")
        d.text((420, CY + 355), "lpm", font=F(F_MONO_M, 34), fill=GRIS, anchor="lm")
        d.text((W - 130, CY + 260), "DERIV. II  ·  25 mm/s", font=F(F_MONO_M, 26), fill=GRIS, anchor="rm")
        d.text((W - 130, CY + 335), "RITMO SINUSAL", font=F(F_MONO, 34), fill=CIAN, anchor="rm")
    # los 5 pasos como chips
    t_paso = tpal(esc, "paso")
    pasos = ["RITMO", "FRECUENCIA", "EJE", "INTERVALOS", "ST-T"]
    for i, ps in enumerate(pasos):
        ti = t_paso + i * 0.14
        fx.en(ti, "tic")
        q = eo(t, ti, 0.4)
        if q > 0:
            fila = 0 if i < 3 else 1
            col_i = i if i < 3 else i - 3
            n_f = 3 if fila == 0 else 2
            x = W / 2 + (col_i - (n_f - 1) / 2) * 320
            y = CY - 330 + fila * 92 - 20 * (1 - min(1, q))
            pildora(d, x, y, f"{i + 1}  {ps}", VERDE if i % 2 == 0 else CIAN, F(F_MONO, 30))


def esc_papel(fr, d, fx, t, dur, esc):
    mm = 34
    box = [70, 470, W - 70, 1330]
    ox, oy = 70 + 2 * mm, 470 + 3 * mm
    p = ei(t, 0, 0.5)
    papel(d, box, mm, origen=(ox, oy))
    t_25 = tpal(esc, "25")
    t_peq = tpal(esc, "pequeño")
    t_hor = tpal(esc, "horizontal")
    t_ver = tpal(esc, "vertical")
    t_gra = tpal(esc, "grande,")
    t_020 = tpal(esc, "0.20")
    # velocidad
    fx.en(t_25, "tic")
    q = eo(t, t_25)
    if q > 0:
        pildora(d, W / 2, 470 + 60, "25 mm/s  ·  10 mm/mV", CIAN, F(F_MONO, 32), fill=PAPEL_BG)
    # cuadro pequeño (con zoom)
    sx, sy = ox + 3 * mm, oy + 8 * mm
    fx.en(t_peq, "pop", vol=0.8)
    q = eo(t, t_peq)
    if q > 0 and t < t_gra + 0.2:
        g = 1 + 0.15 * math.sin(t * 6)
        d.rectangle([sx - 3, sy - 3, sx + mm + 3, sy + mm + 3], outline=VERDE, width=int(5 * g))
        d.text((sx + mm / 2, sy - 30), "1 mm", font=F(F_MONO, 28), fill=VERDE, anchor="mm")
    fx.en(t_hor, "tic")
    q = eo(t, t_hor)
    if q > 0:
        y = sy + mm + 40
        flecha(d, (sx, y), (sx + mm * 1.0 + 70 * min(1, q), y), VERDE, 4)
        pildora(d, sx + mm + 210, y, "0.04 s", VERDE, F(F_MONO, 34), fill=PAPEL_BG)
    fx.en(t_ver, "tic")
    q = eo(t, t_ver)
    if q > 0:
        x = sx - 40
        flecha(d, (x, sy + mm), (x, sy - 70 * min(1, q)), CIAN, 4)
        pildora(d, x, sy - 120, "0.1 mV", CIAN, F(F_MONO, 34), fill=PAPEL_BG)
    # cuadro grande
    bx, by = ox + 14 * mm - 2 * mm, oy + 5 * mm
    bx = ox + 12 * mm
    fx.en(t_gra, "pop", vol=0.8)
    q = eo(t, t_gra)
    if q > 0:
        s = min(1, q)
        d.rectangle([bx, by, bx + 5 * mm * s, by + 5 * mm * s], outline=CORAL, width=6)
        if q > 0.8:
            for k in range(1, 5):
                d.line([(bx + k * mm, by + 5 * mm + 6), (bx + k * mm, by + 5 * mm + 22)], fill=CORAL, width=3)
            d.text((bx + 2.5 * mm, by + 5 * mm + 52), "5 × 1 mm", font=F(F_MONO_M, 28), fill=CORAL, anchor="mm")
    fx.en(t_020, "ok")
    q = eo(t, t_020)
    if q > 0:
        pildora(d, bx + 2.5 * mm, by - 50, "0.20 s  ·  0.5 mV", CORAL, F(F_MONO, 34), fill=PAPEL_BG)
    # tira de ECG de fondo en la parte baja
    yb = oy + 20 * mm
    tt = clamp01(t / max(1, dur - 1)) * 2.4
    pts = puntos_traza(box[0] + 20, yb, 25 * mm, 10 * mm, 0, tt, lambda s: ecg(s), n=400)
    pts = [pp for pp in pts if pp[0] < box[2] - 20]
    trazo(d, pts, mix(BG, VERDE, 0.85), 3)


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
        pts = puntos_traza(x0, y0, pps, ppmv, a, b, fn, 80)
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


def torso(d, cx, cy, s, a=1.0):
    col = mix(BG, (60, 90, 125), a)
    pts = [(cx - 330 * s, cy - 330 * s), (cx - 170 * s, cy - 400 * s), (cx - 70 * s, cy - 410 * s),
           (cx + 70 * s, cy - 410 * s), (cx + 170 * s, cy - 400 * s), (cx + 330 * s, cy - 330 * s),
           (cx + 360 * s, cy + 80 * s), (cx + 300 * s, cy + 420 * s), (cx - 300 * s, cy + 420 * s),
           (cx - 360 * s, cy + 80 * s)]
    d.polygon(pts, fill=mix(BG, PANEL, a), outline=col)
    d.line(pts + [pts[0]], fill=col, width=3)
    # esternón y costillas
    d.rounded_rectangle([cx - 22 * s, cy - 360 * s, cx + 22 * s, cy + 60 * s], radius=int(18 * s),
                        fill=mix(BG, (40, 60, 85), a))
    for i in range(6):
        y = cy - 300 * s + i * 62 * s
        for bb in ([cx - 330 * s, y - 40 * s, cx - 30 * s, y + 80 * s], [cx + 30 * s, y - 40 * s, cx + 330 * s, y + 80 * s]):
            d.arc(bb, start=200, end=340, fill=mix(BG, (45, 68, 95), a), width=3)


def esc_precordiales(fr, d, fx, t, dur, esc):
    cx, cy, s = W / 2, CY + 40, 1.15
    q0 = ei(t, 0, 0.6)
    torso(d, cx, cy, s, q0)
    # corazón detrás (lado izquierdo del paciente = derecha de la pantalla)
    hx, hy = cx + 60, cy - 30
    pul = 1 + 0.06 * math.exp(-((t - 0.235) % RR) * 8)
    corazon(d, hx, hy - 40, 2.6 * pul * q0 + 0.01, mix(BG, CORAL, 0.45))
    # planos
    t_hor = tpal(esc, "horizontal")
    fx.en(t_hor, "tic")
    if t > t_hor:
        q = ei(t, t_hor, 0.5)
        y = hy + 30
        d.line([(cx - 400 * q, y), (cx + 400 * q, y)], fill=mix(BG, AMBAR, 0.5), width=2)
        d.text((cx - 390, y - 26), "PLANO HORIZONTAL", font=F(F_MONO_M, 24), fill=mix(BG, AMBAR, 0.8), anchor="lm")
    # posiciones de los electrodos
    pos = {"V1": (cx - 38, cy - 70), "V2": (cx + 38, cy - 70), "V3": (cx + 95, cy - 18),
           "V4": (cx + 160, cy + 35), "V5": (cx + 250, cy + 35), "V6": (cx + 330, cy + 35)}
    claves = {"V1": "V1", "V2": "V2", "V3": "V4,", "V4": "V4,", "V5": "V6,", "V6": "V6,"}
    t_todas = tpal(esc, "V1")  # "de V1 a V6": se insinúan todas
    for nom, (x, y) in pos.items():
        tz = tpal(esc, claves[nom], k=1 if nom in ("V1", "V2", "V5", "V6") else 0)
        if nom in ("V3", "V5"):
            tz += 0.25
        fx.en(tz, "click")
        fant = eo(t, t_todas, 0.4)
        q = eo(t, tz, 0.4)
        if q > 0:
            r = 22 * min(1.3, q)
            d.ellipse([x - r - 10, y - r - 10, x + r + 10, y + r + 10], fill=mix(BG, AMBAR, 0.25))
            d.ellipse([x - r, y - r, x + r, y + r], fill=AMBAR, outline=(255, 255, 255), width=3)
            d.text((x, y - 52), nom, font=F(F_MONO, 30), fill=AMBAR, anchor="mm")
        elif fant > 0:
            d.ellipse([x - 16, y - 16, x + 16, y + 16], outline=mix(BG, AMBAR, 0.5), width=3)
    # rótulos anatómicos
    rot = [("4º EIC · paraesternal", "esternón", (cx, cy - 170), CIAN),
           ("5º EIC · línea medioclavicular", "medioclavicular", (cx + 160, cy + 115), CIAN),
           ("Línea medioaxilar", "medioaxilar", (cx + 330, cy + 115), CIAN)]
    for i, (txt, clave, (x, y), col) in enumerate(rot):
        tz = tpal(esc, clave)
        q = eo(t, tz)
        if q > 0:
            yy = [560, 1340, 1405][i]
            xx = [W / 2, W / 2 - 70, W / 2 + 70][i] if i else W / 2
            xx = W / 2
            d.line([(x, y), (x, yy + (22 if i == 0 else -22))], fill=mix(BG, col, 0.6), width=2)
            pildora(d, xx if i == 0 else (x - 120 if i == 1 else x - 230), yy, txt, col, F(F_MONO_M, 26), fill=BG)
    if t > t_hor:
        # líneas verticales de referencia
        for (x, txt) in [(cx + 160, ""), (cx + 330, "")]:
            for y in range(int(cy - 300), int(cy + 360), 26):
                d.line([(x, y), (x, y + 12)], fill=mix(BG, CIAN, 0.25), width=2)


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
    q = eo(t, t_reg + 0.3, 0.45)
    if q > 0:
        bx = pildora(d, W / 2, 1385, "      RITMO SINUSAL", VERDE, F(F_BLACK, 44), fill=mix(BG, VERDE, 0.12))
        palomita(d, bx[0] + 50, 1385, 1.3, VERDE, clamp01((t - t_reg - 0.3) / 0.35))


def esc_frecuencia(fr, d, fx, t, dur, esc):
    mm = 17
    box = [50, 470, W - 50, 900]
    x0 = box[0] + 60
    papel(d, box, mm, origen=(x0, 470))
    pps = 25 * mm
    # desplazamos para que una R caiga en una línea gruesa (x0)
    off = 0.235
    span = (box[2] - box[0] - 80) / pps
    head = span * ei(t, 0.1, 1.6)
    yb = box[1] + (box[3] - box[1]) * 0.66
    pts = puntos_traza(x0, yb, pps, 10 * mm, 0, head, lambda s: ecg(s + off), 600)
    trazo(d, [p for p in pts if p[0] < box[2] - 14], BLANCO, 4)
    t_div = tpal(esc, "Divide")
    t_gr = tpal(esc, "grandes")
    t_4 = tpal(esc, "4,")
    t_75 = tpal(esc, "75")
    t_norm = tpal(esc, "normal")
    # marcas 300-150-100-75-60-50 sobre las líneas gruesas
    serie = ["300", "150", "100", "75", "60", "50"]
    for i, num in enumerate(serie):
        ti = t_gr + 0.1 + i * 0.22
        fx.en(ti, "tic")
        q = eo(t, ti, 0.35)
        if q > 0:
            x = x0 + (i + 1) * 5 * mm
            hl = num == "75" and t > t_75
            col = CORAL if hl else AMBAR
            d.line([(x, box[1] + 90), (x, box[3] - 20)], fill=mix(PAPEL_BG, col, 0.6 if hl else 0.3), width=3)
            pildora(d, x, box[1] + 60, num, col, F(F_MONO, 30 if not hl else 36), fill=PAPEL_BG)
    # R inicial
    q = eo(t, t_div, 0.35)
    if q > 0:
        pildora(d, x0, box[1] + 60, "R", VERDE, F(F_MONO, 30), fill=PAPEL_BG)
    # contador de cuadros grandes
    fx.en(t_4, "beep")
    if t > t_4 - 0.4:
        for k in range(4):
            q = eo(t, t_4 - 0.4 + k * 0.1, 0.3)
            if q > 0:
                xa = x0 + k * 5 * mm
                d.rectangle([xa + 3, box[3] - 70, xa + 5 * mm - 3, box[3] - 24], fill=mix(PAPEL_BG, CORAL, 0.45))
                d.text((xa + 2.5 * mm, box[3] - 47), str(k + 1), font=F(F_MONO, 26), fill=BLANCO, anchor="mm")
    # fórmula
    q = eo(t, t_div, 0.45)
    if q > 0:
        tarjeta(d, [80, 960, W - 80, 1160])
        partes = [("300", BLANCO, t_div), (" ÷ ", GRIS, t_div), ("4", CORAL, t_4), (" = ", GRIS, t_75),
                  ("75", VERDE, t_75), (" lpm", GRIS, t_75)]
        f = F(F_BLACK, 96)
        tot = sum(d.textlength(p[0], font=f) for p in partes)
        x = W / 2 - tot / 2
        for txt, col, tz in partes:
            if t > tz:
                d.text((x, 1060), txt, font=f, fill=col, anchor="lm")
            x += d.textlength(txt, font=f)
    # rango normal
    fx.en(t_norm, "ok")
    q = eo(t, t_norm, 0.45)
    if q > 0:
        bx0, bx1, y = 120, W - 120, 1300
        escala = lambda v: bx0 + (v - 30) / (150 - 30) * (bx1 - bx0)
        d.rounded_rectangle([bx0, y - 14, bx1, y + 14], radius=14, fill=mix(BG, CORAL, 0.35))
        d.rounded_rectangle([escala(60), y - 14, escala(100), y + 14], radius=14, fill=VERDE)
        for v in (60, 100):
            d.text((escala(v), y + 48), str(v), font=F(F_MONO, 30), fill=BLANCO, anchor="mm")
        d.text((bx0, y - 46), "BRADICARDIA", font=F(F_MONO_M, 24), fill=GRIS, anchor="lm")
        d.text((bx1, y - 46), "TAQUICARDIA", font=F(F_MONO_M, 24), fill=GRIS, anchor="rm")
        d.text((W / 2, y - 46), "NORMAL", font=F(F_MONO, 26), fill=VERDE, anchor="mm")
        xm = escala(75)
        d.polygon([(xm, y + 18), (xm - 14, y + 40), (xm + 14, y + 40)], fill=BLANCO)


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
            d.text((cx + R * 0.62 * math.cos(am), cy + R * 0.62 * math.sin(am)), nom, font=F(F_MONO, 24),
                   fill=col, anchor="mm")
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
    estados = [(t_norm, 60, (1, 1, 1)), (t_der, 120, (-1, 1, 1)), (t_izq, -60, (1, -1, -1))]
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
    box = [50, 470, W - 50, 1060]
    x0, y0 = 90, 900
    pps, ppmv = 25 * mm * 1.0 * 1.35, 10 * mm * 0.95
    papel(d, box, mm, origen=(x0, y0))
    head = 0.66 * ei(t, 0.1, 1.2)
    trazo(d, puntos_traza(x0, y0, pps, ppmv, 0.0, head, lambda s: latido(s), 500), BLANCO, 5)
    t_pr = tpal(esc, "PR")
    t_qrs = tpal(esc, "QRS,")
    t_qt = tpal(esc, "QT")
    X = lambda s: x0 + s * pps
    items = [("PR", 0.075, 0.205, VERDE, t_pr, 560, "0.12 – 0.20 s", "3–5 cuadros pequeños"),
             ("QRS", 0.205, 0.28, CORAL, t_qrs, 640, "< 0.12 s", "< 3 cuadros pequeños"),
             ("QT", 0.205, 0.555, AMBAR, t_qt, 1010, "QTc < 440 ms (H) · < 460 ms (M)", "Corregir con la FC")]
    for i, (nom, a, b, col, tz, y, val, sub) in enumerate(items):
        fx.en(tz, "tic")
        fx.en(tz + 0.35, "ok", vol=0.6)
        q = eo(t, tz, 0.45)
        if q <= 0:
            continue
        # líneas guía
        for xx in (X(a), X(b)):
            for yy in range(int(y + 20), int(y0 + 40), 22):
                d.line([(xx, yy), (xx, yy + 10)], fill=mix(PAPEL_BG, col, 0.6), width=2)
        corchete(d, X(a), X(b), y, col, nom, F(F_MONO, 30), min(1, q), arriba=(i != 2))
    # tarjetas de valores
    for i, (nom, a, b, col, tz, y, val, sub) in enumerate(items):
        q = eo(t, tz + 0.25, 0.45)
        if q <= 0:
            continue
        by0 = 1100 + i * 98
        xo = (1 - min(1, q)) * 300
        tarjeta(d, [60 + xo, by0, W - 60 + xo, by0 + 86], borde=mix(BG, col, 0.7), r=22)
        d.text((95 + xo, by0 + 43), nom, font=F(F_MONO, 34), fill=col, anchor="lm")
        d.text((230 + xo, by0 + 43), val, font=F(F_BOLD, 38), fill=BLANCO, anchor="lm")
        d.text((W - 90 + xo, by0 + 43), sub, font=F(F_MED, 24), fill=GRIS, anchor="rm") if i < 2 else None


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
        papel(d, bx, mm, r=22, borde=col if q > 0 else BORDE)
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
    t_f = tpal(esc, "follow.")
    # monitor de fondo
    x0, x1, y0 = 60, W - 60, 640
    pps, ppmv = 330, 150
    vent = (x1 - x0) / pps
    head = t % vent
    pts = puntos_traza(x0, y0, pps, ppmv, 0, head, lambda s: ecg(s + int(t / vent) * vent), 400)
    trazo(d, pts, mix(BG, VERDE, 0.7), 4)
    if pts:
        cabeza(d, *pts[-1], VERDE, 7)
    # cursor/tap
    taps = [(t_g + 0.3, (W / 2, 900)), (t_f + 0.1, (W / 2, 1060))]
    fx.en(taps[0][0], "click")
    fx.en(taps[0][0] + 0.05, "ok", vol=0.6)
    fx.en(taps[1][0], "click")
    fx.en(taps[1][0] + 0.05, "ok", vol=0.8)
    q = eo(t, 0.2, 0.45)
    if q > 0:
        boton(d, W / 2, 900, 560 * min(1, q), 120, "GUARDAR", CIAN, t > taps[0][0], "guardar")
    q = eo(t, 0.4, 0.45)
    if q > 0:
        boton(d, W / 2, 1060, 560 * min(1, q), 120, "SEGUIDO" if t > taps[1][0] else "SEGUIR", VERDE,
              t > taps[1][0], "seguir")
    # burbuja de comentario
    fx.en(t_com, "pop")
    q = eo(t, t_com, 0.45)
    if q > 0:
        bx = [120, 1170, W - 120, 1300]
        tarjeta(d, bx, borde=VIOLETA, r=30)
        d.polygon([(200, 1300), (240, 1300), (205, 1335)], fill=PANEL)
        temas = ["Arritmias en el ECG", "Bloqueos de rama", "Infarto en el ECG"]
        u = t - t_com
        tema = temas[int(u / 1.8) % 3]
        n = min(len(tema), int((u % 1.8) * 22))
        d.text((160, 1235), tema[:n] + ("|" if int(t * 3) % 2 == 0 else ""), font=F(F_MED, 40), fill=BLANCO,
               anchor="lm")
    # cursor
    pos = None
    if taps[0][0] - 0.8 < t < taps[1][0] + 0.6:
        if t < taps[0][0]:
            u = ei(t, taps[0][0] - 0.8, 0.8)
            pos = (lerp(W - 120, W / 2 + 120, u), lerp(H - 300, 920, u))
        elif t < taps[1][0] - 0.6:
            pos = (W / 2 + 120, 920)
        else:
            u = ei(t, taps[1][0] - 0.6, 0.6)
            pos = (W / 2 + 120, lerp(920, 1080, u))
    if pos:
        for tt, (px, py) in taps:
            if 0 <= t - tt < 0.4:
                r = 30 + (t - tt) * 200
                d.ellipse([px + 120 - r, py + 20 - r, px + 120 + r, py + 20 + r] if False else
                          [pos[0] - r, pos[1] - r, pos[0] + r, pos[1] + r], outline=BLANCO, width=3)
        d.ellipse([pos[0] - 26, pos[1] - 26, pos[0] + 26, pos[1] + 26], fill=mix(BG, BLANCO, 0.85))


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
    d.text((m, 108), "● REC", font=F(F_MONO, 24), fill=CORAL if int(t_esc * 2) % 2 == 0 else mix(BG, CORAL, 0.4),
           anchor="lm")
    d.text((W - m, 108), "ECG · 12 DERIVACIONES", font=F(F_MONO_M, 24), fill=GRIS, anchor="rm")
    # kicker + título
    p = eo(t_esc, 0.05, 0.5)
    if p > 0:
        a = min(1, p)
        yo = 30 * (1 - a)
        d.text((W / 2, 205 + yo), esc["kicker"], font=F(F_MONO, 30), fill=mix(BG, esc["acento"], a), anchor="mm")
        tam = 84 if len(esc["titulo"]) <= 18 else 70
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
    guion.append(f"GUION PARA ELEVENLABS — {MARCA}: CÓMO LEER UN ECG\n")
    guion.append("El texto de la voz está escrito con los números y siglas deletreados para que la pronunciación\n"
                 "sea correcta (los subtítulos del video los muestran en cifras).\n"
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
