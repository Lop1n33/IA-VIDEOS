#!/usr/bin/env python3
"""
Reel: CÓMO INTERPRETAR UNA GASOMETRÍA ARTERIAL EN MENOS DE 3 MINUTOS.

Mismo estilo que el reel de ECG v2 (monitor clínico oscuro, Inter + JetBrains Mono,
sin voz, subtítulos karaoke y guion fonético para ElevenLabs). Reutiliza el motor
de ../ecg_v2/generar.py y sustituye las escenas, la cabecera y el monitor inferior.

Uso:
    python generar.py --modelo kokoro.onnx --voces voices.bin --out .
    python generar.py --voz-dir audios_elevenlabs --out .      # con tus audios reales
"""
import importlib.util
import math
import os
import random

import numpy as np
from PIL import ImageDraw

AQUI = os.path.dirname(os.path.abspath(__file__))
_p = os.path.join(AQUI, "..", "ecg_v2", "generar.py")
_spec = importlib.util.spec_from_file_location("ecg_v2", _p)
g = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(g)

W, H = g.W, g.H
F, mix, lerp, clamp01, eo, ei, tpal = g.F, g.mix, g.lerp, g.clamp01, g.eo, g.ei, g.tpal
pildora, tarjeta, flecha, palomita = g.pildora, g.tarjeta, g.flecha, g.palomita
F_BLACK, F_BOLD, F_SEMI, F_MED, F_MONO, F_MONO_M = g.F_BLACK, g.F_BOLD, g.F_SEMI, g.F_MED, g.F_MONO, g.F_MONO_M
BG, PANEL, BORDE, BLANCO, GRIS = g.BG, g.PANEL, g.BORDE, g.BLANCO, g.GRIS
VERDE, CIAN, CORAL, AMBAR, VIOLETA = g.VERDE, g.CIAN, g.CORAL, g.AMBAR, g.VIOLETA

NORMALES = {"pH": "7.40", "PaCO₂": "40", "HCO₃⁻": "24", "PaO₂": "95"}
CASO = {"pH": "7.25", "PaCO₂": "30", "HCO₃⁻": "14", "PaO₂": "92"}
ESTADO = {"valores": NORMALES, "anormales": set()}

# ----------------------------------------------------------------------------
# GUION  (texto = subtítulos; voz = versión fonética para ElevenLabs)
# ----------------------------------------------------------------------------
ESCENAS = [
    dict(id="intro", kicker="GASOMETRÍA ARTERIAL", titulo="¿Solo ves números?", acento=VERDE,
         texto="Seguramente has visto esto: una gasometría arterial. Y si solo ves números sin sentido, "
               "hoy te enseño a interpretarla en menos de 3 minutos.",
         voz="Seguramente has visto esto: una gasometría arterial. Y si solo ves números sin sentido, "
             "hoy te enseño a interpretarla en menos de tres minutos."),
    dict(id="normales", kicker="FUNDAMENTOS · 01", titulo="Valores normales", acento=CIAN,
         texto="Primero, los valores normales: pH de 7.35 a 7.45; PaCO₂ de 35 a 45 mmHg; "
               "bicarbonato de 22 a 26 mEq/L; y PaO₂ de 80 a 100 mmHg.",
         voz="Primero, los valores normales: pe hache de siete punto treinta y cinco a siete punto cuarenta y cinco; "
             "pe ce o dos de treinta y cinco a cuarenta y cinco milímetros de mercurio; bicarbonato de veintidós a "
             "veintiséis miliequivalentes por litro; y pe o dos de ochenta a cien milímetros de mercurio."),
    dict(id="balanza", kicker="FUNDAMENTOS · 02", titulo="Equilibrio ácido-base", acento=AMBAR,
         texto="Piensa en una balanza: el CO₂ actúa como ácido y lo regula el pulmón; el bicarbonato es una base "
               "y lo regula el riñón. El pH depende del equilibrio entre ambos.",
         voz="Piensa en una balanza: el ce o dos actúa como ácido y lo regula el pulmón; el bicarbonato es una base "
             "y lo regula el riñón. El pe hache depende del equilibrio entre ambos."),
    dict(id="ph", kicker="PASO 1 DE 5", titulo="El pH", acento=CORAL, paso=1,
         texto="Paso 1: mira el pH. Si es menor de 7.35, hay acidemia; si es mayor de 7.45, hay alcalemia.",
         voz="Paso uno: mira el pe hache. Si es menor de siete punto treinta y cinco, hay acidemia; si es mayor de "
             "siete punto cuarenta y cinco, hay alcalemia."),
    dict(id="origen", kicker="PASO 2 DE 5", titulo="¿Respiratorio o metabólico?", acento=CIAN, paso=2,
         texto="Paso 2: busca el origen. Si el pH y la PaCO₂ van en sentido opuesto, es respiratorio. "
               "Si el pH y el bicarbonato van en el mismo sentido, es metabólico.",
         voz="Paso dos: busca el origen. Si el pe hache y la pe ce o dos van en sentido opuesto, es respiratorio. "
             "Si el pe hache y el bicarbonato van en el mismo sentido, es metabólico."),
    dict(id="winter", kicker="PASO 3 DE 5", titulo="Compensación", acento=AMBAR, paso=3,
         texto="Paso 3: revisa la compensación. En la acidosis metabólica, usa la fórmula de Winter: "
               "PaCO₂ esperada = 1.5 × HCO₃⁻ + 8 ± 2. Si la PaCO₂ real queda fuera de ese rango, "
               "hay un segundo trastorno.",
         voz="Paso tres: revisa la compensación. En la acidosis metabólica, usa la fórmula de Winter: la pe ce o dos "
             "esperada es igual a uno punto cinco por el bicarbonato, más ocho, más o menos dos. Si la pe ce o dos "
             "real queda fuera de ese rango, hay un segundo trastorno."),
    dict(id="gap", kicker="PASO 4 DE 5", titulo="Anión gap", acento=VIOLETA, paso=4,
         texto="Paso 4: en toda acidosis metabólica, calcula el anión gap: sodio menos la suma de cloro y bicarbonato. "
               "Lo normal es de 8 a 12. Si está elevado, piensa en cetoacidosis, acidosis láctica, insuficiencia "
               "renal o tóxicos; si es normal, en diarrea o acidosis tubular renal.",
         voz="Paso cuatro: en toda acidosis metabólica, calcula el anión gap: sodio menos la suma de cloro y "
             "bicarbonato. Lo normal es de ocho a doce. Si está elevado, piensa en cetoacidosis, acidosis láctica, "
             "insuficiencia renal o tóxicos; si es normal, en diarrea o acidosis tubular renal."),
    dict(id="oxigenacion", kicker="PASO 5 DE 5", titulo="Oxigenación", acento=VERDE, paso=5,
         texto="Paso 5: la oxigenación. La PaO₂ normal es de 80 a 100 mmHg. Calcula el índice PaO₂/FiO₂: "
               "si es menor de 300, hay una alteración importante del intercambio gaseoso.",
         voz="Paso cinco: la oxigenación. La pe o dos normal es de ochenta a cien milímetros de mercurio. Calcula el "
             "índice pe o dos sobre fi o dos: si es menor de trescientos, hay una alteración importante del "
             "intercambio gaseoso."),
    dict(id="caso", kicker="CASO CLÍNICO", titulo="Pongámoslo a prueba", acento=CORAL,
         texto="Pongámoslo a prueba: pH 7.25, PaCO₂ 30 y bicarbonato 14. Hay acidemia, y el pH y el bicarbonato "
               "bajan juntos: es metabólica. Con Winter, 1.5 × 14 + 8 da 29; la PaCO₂ de 30 está en rango, "
               "así que está compensada.",
         voz="Pongámoslo a prueba: pe hache siete punto veinticinco, pe ce o dos treinta y bicarbonato catorce. Hay "
             "acidemia, y el pe hache y el bicarbonato bajan juntos: es metabólica. Con Winter, uno punto cinco por "
             "catorce, más ocho, da veintinueve; la pe ce o dos de treinta está en rango, así que está compensada."),
    dict(id="caso_gap", kicker="CASO CLÍNICO", titulo="Diagnóstico final", acento=VIOLETA,
         texto="Además, con sodio de 140 y cloro de 100, el anión gap es de 26: acidosis metabólica con anión gap "
               "elevado, como en la cetoacidosis diabética.",
         voz="Además, con sodio de ciento cuarenta y cloro de cien, el anión gap es de veintiséis: acidosis "
             "metabólica con anión gap elevado, como en la cetoacidosis diabética."),
    dict(id="resumen", kicker="RESUMEN", titulo="Los 5 pasos", acento=VERDE,
         texto="Recuerda los cinco pasos: pH, origen, compensación, anión gap y oxigenación. "
               "Siempre en ese orden, y ninguna gasometría se te va a escapar.",
         voz="Recuerda los cinco pasos: pe hache, origen, compensación, anión gap y oxigenación. "
             "Siempre en ese orden, y ninguna gasometría se te va a escapar."),
    dict(id="outro", kicker="GASOMETRÍA EN MENOS DE 3 MINUTOS", titulo="¿Te sirvió?", acento=VERDE,
         texto="Guarda este video para tu próxima guardia. ¿Qué tema quieres que explique después? "
               "Déjalo en los comentarios y sígueme para más."),
]


# ----------------------------------------------------------------------------
# UTILIDADES GRÁFICAS
# ----------------------------------------------------------------------------
def flecha_v(d, x, y, arriba, col, s=1.0):
    """Flecha vertical gruesa (↑ o ↓) dibujada como polígono."""
    h, w, cab = 50 * s, 12 * s, 26 * s
    if arriba:
        tip, base, cola = y - h / 2, y - h / 2 + cab, y + h / 2
    else:
        tip, base, cola = y + h / 2, y + h / 2 - cab, y - h / 2
    d.rectangle([x - w / 2, min(base, cola), x + w / 2, max(base, cola)], fill=col)
    d.polygon([(x, tip), (x - cab * 0.75, base), (x + cab * 0.75, base)], fill=col)


def texto_ancho(d, txt, f):
    return d.textlength(txt, font=f)


def barra_rango(d, x0, x1, y, vmin, vmax, nmin, nmax, col_norm=VERDE, valor=None, col_val=BLANCO, alto=16):
    esc = lambda v: x0 + (v - vmin) / (vmax - vmin) * (x1 - x0)
    d.rounded_rectangle([x0, y - alto / 2, x1, y + alto / 2], radius=int(alto / 2), fill=(30, 44, 64))
    d.rounded_rectangle([esc(nmin), y - alto / 2, esc(nmax), y + alto / 2], radius=int(alto / 2), fill=col_norm)
    if valor is not None:
        xv = esc(valor)
        d.polygon([(xv, y + alto / 2 + 4), (xv - 12, y + alto / 2 + 24), (xv + 12, y + alto / 2 + 24)], fill=col_val)
    return esc


# ----------------------------------------------------------------------------
# ESCENAS
# ----------------------------------------------------------------------------
FILAS_TICKET = [("pH", "7.25", "", True), ("pCO₂", "30", "mmHg", True), ("pO₂", "92", "mmHg", False),
                ("HCO₃⁻", "14", "mmol/L", True), ("BE", "−11.5", "mmol/L", False), ("SatO₂", "97", "%", False),
                ("Na⁺", "140", "mmol/L", False), ("K⁺", "4.1", "mmol/L", False), ("Cl⁻", "100", "mmol/L", False),
                ("Lactato", "1.2", "mmol/L", False)]


def esc_intro(fr, d, fx, t, dur, esc):
    t_gas = tpal(esc, "gasometría")
    t_sin = tpal(esc, "sentido,")
    t_ens = tpal(esc, "enseño")
    t_3 = tpal(esc, "3")
    fx.en(t_gas, "ok", vol=0.6)
    fx.en(t_ens, "ok")
    fx.en(t_3, "tic")
    ESTADO["valores"], ESTADO["anormales"] = NORMALES, set()
    # ticket impreso
    x0, x1, y0 = 170, W - 170, 470
    n_vis = clamp01((t - 0.15) / 1.6) * len(FILAS_TICKET)
    alto = 96 + 64 * len(FILAS_TICKET)
    tarjeta(d, [x0, y0, x1, y0 + alto], fill=(14, 22, 38), borde=(46, 70, 100))
    d.text((x0 + 36, y0 + 48), "GASOMETRÍA ARTERIAL", font=F(F_MONO, 30), fill=BLANCO, anchor="lm")
    d.text((x1 - 36, y0 + 48), "37.0 °C", font=F(F_MONO_M, 26), fill=GRIS, anchor="rm")
    d.line([(x0 + 30, y0 + 84), (x1 - 30, y0 + 84)], fill=(46, 70, 100), width=2)
    caos = clamp01((t - t_sin + 0.15) / 0.3) * (1 - clamp01((t - t_ens) / 0.35))
    rnd = random.Random(int(t * 12))
    for i, (nom, val, uni, clave) in enumerate(FILAS_TICKET):
        if i >= n_vis:
            break
        fx.en(0.15 + i * 1.6 / len(FILAS_TICKET), "tic", vol=0.5)
        y = y0 + 124 + i * 64
        v = val
        col_v = BLANCO
        if caos > 0.05:
            v = "".join(str(rnd.randint(0, 9)) if ch.isdigit() else ch for ch in val)
            col_v = mix(BLANCO, CORAL, caos)
        elif t > t_ens and clave:
            col_v = VERDE
        f_n = F(F_SEMI, 34)
        d.text((x0 + 40, y), nom, font=f_n, fill=(VERDE if (t > t_ens and clave) else GRIS), anchor="lm")
        d.text((x0 + 420, y), v, font=F(F_MONO, 38), fill=col_v, anchor="rm")
        d.text((x0 + 450, y), uni, font=F(F_MONO_M, 26), fill=GRIS, anchor="lm")
        if t > t_ens and clave:
            d.rounded_rectangle([x0 + 24, y - 27, x1 - 24, y + 27], radius=14, outline=mix(BG, VERDE, 0.6), width=2)
    q = eo(t, t_3, 0.45)
    if q > 0:
        box = pildora(d, W / 2, 1385, "MENOS DE 3 MINUTOS", VERDE, F(F_BLACK, 44), fill=mix(BG, VERDE, 0.12))
        cx, cy = box[0] - 50, 1385
        d.ellipse([cx - 30, cy - 30, cx + 30, cy + 30], outline=VERDE, width=4)
        a = -math.pi / 2 + (t - t_3) * 4
        d.line([(cx, cy), (cx + 22 * math.cos(a), cy + 22 * math.sin(a))], fill=VERDE, width=4)
        d.rectangle([cx - 6, cy - 42, cx + 6, cy - 32], fill=VERDE)


def esc_normales(fr, d, fx, t, dur, esc):
    ESTADO["valores"], ESTADO["anormales"] = NORMALES, set()
    filas = [("pH", "7.35 – 7.45", "", "pH", 7.1, 7.7, 7.35, 7.45, CORAL),
             ("PaCO₂", "35 – 45", "mmHg", "PaCO₂", 20, 60, 35, 45, AMBAR),
             ("HCO₃⁻", "22 – 26", "mEq/L", "bicarbonato", 10, 38, 22, 26, CIAN),
             ("PaO₂", "80 – 100", "mmHg", "PaO₂", 40, 130, 80, 100, VERDE)]
    for i, (nom, rango, uni, clave, vmin, vmax, nmin, nmax, col) in enumerate(filas):
        tz = tpal(esc, clave)
        fx.en(tz, "tic")
        q = eo(t, tz, 0.45)
        if q <= 0:
            continue
        y = 480 + i * 228
        xo = (1 - min(1, q)) * 400
        tarjeta(d, [60 + xo, y, W - 60 + xo, y + 205], borde=mix(BG, col, 0.7))
        d.text((100 + xo, y + 62), nom, font=F(F_BLACK, 58), fill=col, anchor="lm")
        d.text((W - 100 + xo, y + 52), rango, font=F(F_BOLD, 50), fill=BLANCO, anchor="rm")
        if uni:
            d.text((W - 100 + xo, y + 100), uni, font=F(F_MONO_M, 26), fill=GRIS, anchor="rm")
        p = ei(t, tz + 0.2, 0.5)
        if p > 0.02:
            barra_rango(d, 100 + xo, 100 + xo + (W - 200) * p, y + 158, vmin, vmax, nmin, nmax, col)


def esc_balanza(fr, d, fx, t, dur, esc):
    ESTADO["valores"], ESTADO["anormales"] = NORMALES, set()
    t_co2 = tpal(esc, "CO₂")
    t_pul = tpal(esc, "pulmón;")
    t_bic = tpal(esc, "bicarbonato")
    t_ri = tpal(esc, "riñón.")
    t_ph = tpal(esc, "pH")
    cx, cy = W / 2, 820
    # inclinación: cae a la izquierda con el CO2, a la derecha con el bicarbonato y se equilibra con el pH
    ang = 0.0
    if t > t_co2:
        ang = -0.16 * ei(t, t_co2, 0.6)
    if t > t_bic:
        ang = lerp(-0.16, 0.12, ei(t, t_bic, 0.6))
    if t > t_ph:
        ang = lerp(0.12, 0.0, ei(t, t_ph, 0.8)) + 0.015 * math.sin((t - t_ph) * 3) * math.exp(-(t - t_ph))
    q0 = ei(t, 0, 0.6)
    # base y poste
    d.polygon([(cx - 120, 1130), (cx + 120, 1130), (cx + 60, 1095), (cx - 60, 1095)], fill=mix(BG, (60, 86, 120), q0))
    d.rectangle([cx - 10, cy, cx + 10, 1100], fill=mix(BG, (60, 86, 120), q0))
    L = 360
    ex, ey = L * math.cos(ang), L * math.sin(ang)
    pl, pr = (cx - ex, cy - ey), (cx + ex, cy + ey)
    d.line([pl, pr], fill=mix(BG, (110, 140, 175), q0), width=12)
    d.ellipse([cx - 22, cy - 22, cx + 22, cy + 22], fill=mix(BG, BLANCO, q0))
    # platillos colgantes
    for (px, py), col, tz, nombre, sub, org, t_org in [(pl, CORAL, t_co2, "CO₂", "ÁCIDO", "PULMÓN", t_pul),
                                                        (pr, CIAN, t_bic, "HCO₃⁻", "BASE", "RIÑÓN", t_ri)]:
        yb = py + 170
        d.line([(px, py), (px - 110, yb)], fill=mix(BG, GRIS, q0), width=3)
        d.line([(px, py), (px + 110, yb)], fill=mix(BG, GRIS, q0), width=3)
        d.chord([px - 130, yb - 40, px + 130, yb + 50], 0, 180, fill=mix(BG, (40, 60, 85), q0))
        fx.en(tz, "pop")
        q = eo(t, tz, 0.45)
        if q > 0:
            r = 78 * min(1.15, q)
            d.ellipse([px - r, yb - 2 * r + 10, px + r, yb + 10], fill=mix(BG, col, 0.25), outline=col, width=4)
            d.text((px, yb - r + 10), nombre, font=F(F_BLACK, int((46 if len(nombre) < 4 else 38) * min(1, q))),
                   fill=BLANCO, anchor="mm")
            d.text((px, yb + 62), sub, font=F(F_MONO, 30), fill=col, anchor="mm")
        fx.en(t_org, "tic")
        if t > t_org:
            pildora(d, px, 560, org, col, F(F_MONO, 30))
            d.line([(px, 590), (px, py - 10)], fill=mix(BG, col, 0.35), width=2)
    fx.en(t_ph, "ok")
    q = eo(t, t_ph, 0.5)
    if q > 0:
        tarjeta(d, [cx - 190, 1190, cx + 190, 1330], borde=VERDE)
        d.text((cx - 150, 1260), "pH", font=F(F_BLACK, 56), fill=GRIS, anchor="lm")
        d.text((cx + 150, 1260), "7.40", font=F(F_BLACK, 70), fill=VERDE, anchor="rm")


def esc_ph(fr, d, fx, t, dur, esc):
    t_ac = tpal(esc, "acidemia;")
    t_al = tpal(esc, "alcalemia.")
    x0, x1, y = 90, W - 90, 860
    vmin, vmax = 7.0, 7.8
    X = lambda v: x0 + (v - vmin) / (vmax - vmin) * (x1 - x0)
    q0 = ei(t, 0.1, 0.6)
    # zonas
    zonas = [(vmin, 7.35, CORAL, "ACIDEMIA", t_ac), (7.35, 7.45, VERDE, "NORMAL", 0.3), (7.45, vmax, VIOLETA,
                                                                                              "ALCALEMIA", t_al)]
    for a, b, col, nom, tz in zonas:
        on = t > tz
        d.rectangle([X(a), y - 40, X(b), y + 40], fill=mix(BG, col, 0.55 if on else 0.15 * q0))
        if on:
            fx.en(tz, "alerta" if nom != "NORMAL" else "tic", vol=0.6)
            pildora(d, (X(a) + X(b)) / 2, y - 120 if nom != "NORMAL" else y + 130, nom, col,
                    F(F_MONO, 30 if nom != "NORMAL" else 26))
    d.rounded_rectangle([x0, y - 40, x1, y + 40], radius=8, outline=mix(BG, BORDE, q0 + 0.01), width=3)
    for v in [7.0, 7.2, 7.35, 7.45, 7.6, 7.8]:
        d.line([(X(v), y + 40), (X(v), y + 58)], fill=GRIS, width=2)
        d.text((X(v), y + 84), f"{v:.2f}" if v in (7.35, 7.45) else f"{v:.1f}", font=F(F_MONO, 26 if v in (7.35, 7.45)
                                                                                         else 22),
               fill=BLANCO if v in (7.35, 7.45) else GRIS, anchor="mm")
    # marcador
    val = 7.40
    if t > t_ac - 0.3:
        val = lerp(7.40, 7.22, ei(t, t_ac - 0.3, 0.6))
    if t > t_al - 0.3:
        val = lerp(7.22, 7.56, ei(t, t_al - 0.3, 0.7))
    if q0 > 0.5:
        xv = X(val)
        col = CORAL if val < 7.35 else (VIOLETA if val > 7.45 else VERDE)
        d.polygon([(xv, y - 48), (xv - 18, y - 76), (xv + 18, y - 76)], fill=BLANCO)
        d.line([(xv, y - 48), (xv, y + 48)], fill=BLANCO, width=4)
        tarjeta(d, [W / 2 - 200, 1050, W / 2 + 200, 1200], borde=col)
        d.text((W / 2 - 160, 1125), "pH", font=F(F_BLACK, 56), fill=GRIS, anchor="lm")
        d.text((W / 2 + 160, 1125), f"{val:.2f}", font=F(F_BLACK, 76), fill=col, anchor="rm")
    ESTADO["valores"] = dict(NORMALES, pH=f"{val:.2f}")
    ESTADO["anormales"] = {"pH"} if not (7.35 <= val <= 7.45) else set()
    q = eo(t, t_al + 0.6)
    if q > 0:
        d.text((W / 2, 1290), "acidemia / alcalemia = el pH  ·  acidosis / alcalosis = el proceso",
               font=F(F_MONO_M, 22), fill=GRIS, anchor="mm")


def celda_trastorno(d, box, nombre, col, par, q, resalta):
    if q <= 0:
        return
    tarjeta(d, box, borde=col if resalta else mix(BG, col, 0.5), fill=mix(PANEL, col, 0.08 if resalta else 0.0))
    x0, y0, x1, y1 = box
    d.text(((x0 + x1) / 2, y0 + 46), nombre, font=F(F_BOLD, 36), fill=BLANCO, anchor="mm")
    cx = (x0 + x1) / 2
    for k, (var, arriba, c) in enumerate(par):
        x = cx + (k - 0.5) * 200
        d.text((x - 20, y0 + 140), var, font=F(F_BLACK, 40), fill=c, anchor="rm")
        flecha_v(d, x + 20, y0 + 140, arriba, c, 0.9)


def esc_origen(fr, d, fx, t, dur, esc):
    t_op = tpal(esc, "opuesto,")
    t_resp = tpal(esc, "respiratorio.")
    t_mis = tpal(esc, "mismo")
    t_met = tpal(esc, "metabólico.")
    ESTADO["valores"], ESTADO["anormales"] = NORMALES, set()
    filas = [
        ("RESPIRATORIO", CORAL, t_op, "pH y PaCO₂: SENTIDO OPUESTO",
         [("Acidosis respiratoria", [("pH", False, BLANCO), ("PaCO₂", True, CORAL)]),
          ("Alcalosis respiratoria", [("pH", True, BLANCO), ("PaCO₂", False, CORAL)])], t_resp),
        ("METABÓLICO", CIAN, t_mis, "pH y HCO₃: MISMO SENTIDO",
         [("Acidosis metabólica", [("pH", False, BLANCO), ("HCO₃⁻", False, CIAN)]),
          ("Alcalosis metabólica", [("pH", True, BLANCO), ("HCO₃⁻", True, CIAN)])], t_met),
    ]
    for r, (titulo, col, tz, regla, celdas, t_conf) in enumerate(filas):
        y0 = 470 + r * 470
        fx.en(tz, "tic")
        fx.en(t_conf, "ok")
        q = eo(t, tz - 0.4, 0.45)
        if q <= 0:
            continue
        pildora(d, W / 2, y0 + 30, titulo, col, F(F_MONO, 32))
        for c, (nombre, par) in enumerate(celdas):
            box = [60 + c * 490, y0 + 80, 60 + c * 490 + 470, y0 + 300]
            celda_trastorno(d, box, nombre, col, par, eo(t, tz - 0.2 + c * 0.25, 0.45), t > t_conf)
        if t > t_conf:
            pildora(d, W / 2, y0 + 360, regla, col, F(F_MONO, 28), fill=mix(BG, col, 0.12), check=True)


def esc_winter(fr, d, fx, t, dur, esc):
    t_win = tpal(esc, "Winter:")
    t_15 = tpal(esc, "1.5")
    t_8 = tpal(esc, "8")
    t_2 = tpal(esc, "2.")
    t_fuera = tpal(esc, "fuera")
    t_seg = tpal(esc, "segundo")
    ESTADO["valores"], ESTADO["anormales"] = NORMALES, set()
    # bloque de compensación (quién compensa a quién)
    q = eo(t, 0.2, 0.45)
    if q > 0:
        for i, (a, b, col) in enumerate([("Problema METABÓLICO", "compensa el PULMÓN (CO₂)", CIAN),
                                         ("Problema RESPIRATORIO", "compensa el RIÑÓN (HCO₃⁻)", CORAL)]):
            y = 500 + i * 92
            tarjeta(d, [60, y, W - 60, y + 76], borde=mix(BG, col, 0.6), r=22)
            d.text((90, y + 38), a, font=F(F_SEMI, 30), fill=col, anchor="lm")
            d.text((W - 90, y + 38), b, font=F(F_SEMI, 30), fill=BLANCO, anchor="rm")
    # fórmula de Winter
    fx.en(t_win, "ok", vol=0.7)
    q = eo(t, t_win, 0.45)
    if q > 0:
        tarjeta(d, [60, 720, W - 60, 960], borde=AMBAR)
        d.text((W / 2, 768), "FÓRMULA DE WINTER", font=F(F_MONO, 28), fill=AMBAR, anchor="mm")
        partes = [("PaCO₂ = ", BLANCO, t_win), ("1.5 × HCO₃⁻", AMBAR, t_15), (" + 8", BLANCO, t_8),
                  (" ± 2", CORAL, t_2)]
        f = F(F_BLACK, 66)
        tot = sum(texto_ancho(d, p[0], f) for p in partes)
        x = W / 2 - tot / 2
        for txt, col, tz in partes:
            fx.en(tz, "tic")
            if t > tz:
                d.text((x, 870), txt, font=f, fill=col, anchor="lm")
            x += texto_ancho(d, txt, f)
        d.text((W / 2, 930), "PaCO₂ esperada en acidosis metabólica", font=F(F_MED, 26), fill=GRIS, anchor="mm")
    # rango esperado y segundo trastorno
    fx.en(t_fuera, "alerta", vol=0.6)
    q = eo(t, t_fuera, 0.45)
    if q > 0:
        x0, x1, y = 120, W - 120, 1130
        a, b = x0 + (x1 - x0) * 0.38, x0 + (x1 - x0) * 0.62
        d.rounded_rectangle([x0, y - 16, x1, y + 16], radius=16, fill=(30, 44, 64))
        d.rounded_rectangle([a, y - 16, b, y + 16], radius=16, fill=VERDE)
        d.text(((a + b) / 2, y - 46), "RANGO ESPERADO", font=F(F_MONO, 24), fill=VERDE, anchor="mm")
        if t > t_seg:
            d.text((x0, y + 52), "PaCO₂ menor:", font=F(F_SEMI, 26), fill=GRIS, anchor="lm")
            d.text((x0, y + 90), "+ alcalosis respiratoria", font=F(F_BOLD, 30), fill=VIOLETA, anchor="lm")
            d.text((x1, y + 52), "PaCO₂ mayor:", font=F(F_SEMI, 26), fill=GRIS, anchor="rm")
            d.text((x1, y + 90), "+ acidosis respiratoria", font=F(F_BOLD, 30), fill=CORAL, anchor="rm")
    fx.en(t_seg, "alerta", vol=0.5)


def esc_gap(fr, d, fx, t, dur, esc):
    t_an = tpal(esc, "anión")
    t_na = tpal(esc, "sodio")
    t_cl = tpal(esc, "cloro")
    t_bic = tpal(esc, "bicarbonato.")
    t_12 = tpal(esc, "12.")
    t_el = tpal(esc, "elevado,")
    t_no = tpal(esc, "normal,")
    ESTADO["valores"], ESTADO["anormales"] = NORMALES, set()
    # gamblegram: cationes vs aniones (mEq/L)
    base, esc_px = 1000, 3.3  # px por mEq
    cols = [(W / 2 - 230, [("Na⁺", 140, CORAL, t_na)], "CATIONES"),
            (W / 2 + 70, [("Cl⁻", 104, CIAN, t_cl), ("HCO₃⁻", 24, AMBAR, t_bic), ("AG", 12, VIOLETA, t_12)],
             "ANIONES")]
    q0 = eo(t, t_an, 0.45)
    if q0 > 0:
        pildora(d, W / 2, 480, "AG = Na⁺ − (Cl⁻ + HCO₃⁻)", VIOLETA, F(F_BOLD, 40), fill=mix(BG, VIOLETA, 0.12))
    for x, segs, nom in cols:
        if q0 <= 0:
            continue
        y = base
        d.text((x + 80, base + 34), nom, font=F(F_MONO, 26), fill=GRIS, anchor="mm")
        for etiqueta, val, col, tz in segs:
            fx.en(tz, "pop", vol=0.7)
            p = ei(t, tz, 0.5)
            if p <= 0:
                break
            h = val * esc_px * p
            d.rectangle([x, y - h, x + 160, y], fill=mix(BG, col, 0.75), outline=col, width=3)
            if p > 0.6:
                d.text((x + 80, y - h / 2), f"{etiqueta} {val}", font=F(F_BOLD, 32 if val > 20 else 26),
                       fill=BLANCO, anchor="mm")
            y -= h
    fx.en(t_12, "ok")
    if t > t_12:
        pildora(d, W / 2 + 330, base - 128 * esc_px - 20, "8 – 12", VIOLETA, F(F_MONO, 30))
    # causas
    for i, (titulo, causas, col, tz) in enumerate([("AG ELEVADO", "Cetoacidosis · Láctica · Renal · Tóxicos", CORAL, t_el),
                                                   ("AG NORMAL", "Diarrea · Acidosis tubular renal", CIAN, t_no)]):
        fx.en(tz, "tic")
        q = eo(t, tz, 0.45)
        if q <= 0:
            continue
        y = 1100 + i * 150
        xo = (1 - min(1, q)) * 300
        tarjeta(d, [60 + xo, y, W - 60 + xo, y + 132], borde=col)
        d.text((95 + xo, y + 42), titulo, font=F(F_MONO, 30), fill=col, anchor="lm")
        d.text((95 + xo, y + 92), causas, font=F(F_SEMI, 32), fill=BLANCO, anchor="lm")


def esc_oxigenacion(fr, d, fx, t, dur, esc):
    t_pao2 = tpal(esc, "PaO₂")
    t_ind = tpal(esc, "PaO₂/FiO₂:")
    t_300 = tpal(esc, "300,")
    ESTADO["valores"], ESTADO["anormales"] = NORMALES, set()
    # tarjeta PaO2
    fx.en(t_pao2, "tic")
    q = eo(t, t_pao2, 0.45)
    if q > 0:
        tarjeta(d, [60, 480, W - 60, 620], borde=VERDE)
        d.text((100, 550), "PaO₂", font=F(F_BLACK, 56), fill=VERDE, anchor="lm")
        d.text((W - 100, 550), "80 – 100 mmHg", font=F(F_BOLD, 50), fill=BLANCO, anchor="rm")
    # medidor semicircular PaO2/FiO2 (0–500)
    fx.en(t_ind, "ok", vol=0.7)
    q = eo(t, t_ind, 0.5)
    if q <= 0:
        return
    cx, cy, R = W / 2, 1020, 320
    zonas = [(0, 100, CORAL, "GRAVE"), (100, 200, AMBAR, "MODERADA"), (200, 300, (255, 230, 90), "LEVE"),
             (300, 500, VERDE, "NORMAL")]
    ang = lambda v: 180 + 180 * v / 500
    for a, b, col, nom in zonas:
        d.arc([cx - R, cy - R, cx + R, cy + R], ang(a), ang(b), fill=mix(BG, col, 0.85), width=46)
        am = math.radians((ang(a) + ang(b)) / 2)
        d.text((cx + (R + 62) * math.cos(am), cy + (R + 62) * math.sin(am)), nom, font=F(F_MONO, 22), fill=col,
               anchor="mm")
    for v in (0, 100, 200, 300, 500):
        am = math.radians(ang(v))
        d.text((cx + (R - 64) * math.cos(am), cy + (R - 64) * math.sin(am)), str(v), font=F(F_MONO, 24),
               fill=BLANCO if v == 300 else GRIS, anchor="mm")
    # aguja: primero un valor normal, luego cae por debajo de 300
    v = 452 * ei(t, t_ind, 0.9)
    if t > t_300 - 0.2:
        v = lerp(452, 180, ei(t, t_300 - 0.2, 0.8))
    am = math.radians(ang(v))
    tip = (cx + (R - 30) * math.cos(am), cy + (R - 30) * math.sin(am))
    d.line([(cx, cy), tip], fill=BLANCO, width=8)
    d.ellipse([cx - 18, cy - 18, cx + 18, cy + 18], fill=BLANCO)
    col = VERDE if v >= 300 else ((255, 230, 90) if v >= 200 else (AMBAR if v >= 100 else CORAL))
    d.text((cx, cy + 85), f"{v:.0f}", font=F(F_BLACK, 96), fill=col, anchor="mm")
    d.text((cx, cy + 155), "PaO₂ / FiO₂", font=F(F_MONO, 26), fill=GRIS, anchor="mm")
    if t < t_300 - 0.2:
        d.text((cx, cy + 215), "Ej.: 95 / 0.21 = 452", font=F(F_MONO_M, 28), fill=GRIS, anchor="mm")
    fx.en(t_300, "alerta")
    if t > t_300 + 0.4:
        pildora(d, cx, cy + 222, "< 300: ALTERACIÓN DEL INTERCAMBIO", CORAL, F(F_MONO, 26))


def fila_valor(d, x0, x1, y, nom, val, uni, col):
    d.text((x0, y), nom, font=F(F_BOLD, 40), fill=GRIS, anchor="lm")
    d.text((x1 - 120, y), val, font=F(F_BLACK, 52), fill=col, anchor="rm")
    d.text((x1 - 100, y + 6), uni, font=F(F_MONO_M, 22), fill=GRIS, anchor="lm")


def esc_caso(fr, d, fx, t, dur, esc):
    t_ph = tpal(esc, "7.25,")
    t_acid = tpal(esc, "acidemia,")
    t_met = tpal(esc, "metabólica.")
    t_win = tpal(esc, "Winter,")
    t_29 = tpal(esc, "29;")
    t_comp = tpal(esc, "compensada.")
    ESTADO["valores"], ESTADO["anormales"] = CASO, {"pH", "PaCO₂", "HCO₃⁻"}
    fx.en(t_ph, "beep")
    q = eo(t, t_ph - 0.3, 0.45)
    if q > 0:
        tarjeta(d, [60, 470, W - 60, 760], borde=CORAL)
        fila_valor(d, 110, W - 60, 535, "pH", "7.25", "", CORAL)
        fila_valor(d, 110, W - 60, 615, "PaCO₂", "30", "mmHg", AMBAR)
        fila_valor(d, 110, W - 60, 695, "HCO₃⁻", "14", "mEq/L", CIAN)
    pasos = [("1", "ACIDEMIA", "pH < 7.35", t_acid, CORAL),
             ("2", "METABÓLICA", "pH ↓ y HCO₃⁻ ↓ (mismo sentido)", t_met, CIAN),
             ("3", "COMPENSADA", "Winter: 1.5 × 14 + 8 = 29 (27 – 31)", t_comp, AMBAR)]
    for i, (n, tit, det, tz, col) in enumerate(pasos):
        fx.en(tz, "ok")
        q = eo(t, tz, 0.45)
        if q <= 0:
            continue
        y = 800 + i * 165
        xo = (1 - min(1, q)) * 300
        tarjeta(d, [60 + xo, y, W - 60 + xo, y + 145], borde=col)
        d.ellipse([90 + xo, y + 32, 170 + xo, y + 112], fill=mix(BG, col, 0.2), outline=col, width=3)
        d.text((130 + xo, y + 72), n, font=F(F_MONO, 38), fill=col, anchor="mm")
        d.text((200 + xo, y + 50), tit, font=F(F_BLACK, 44), fill=BLANCO, anchor="lm")
        d.text((200 + xo, y + 102), det, font=F(F_SEMI, 28), fill=GRIS, anchor="lm")
        palomita(d, W - 120 + xo, y + 72, 1.3, col, clamp01((t - tz) / 0.4))
    # cálculo de Winter en vivo, antes de confirmar
    if t_win - 0.1 < t < t_comp:
        partes = [("1.5 × 14 + 8 = ", BLANCO, t_win), ("29", AMBAR, t_29)]
        f = F(F_BLACK, 56)
        tot = sum(texto_ancho(d, p[0], f) for p in partes)
        x = W / 2 - tot / 2
        for txt, col, tz in partes:
            if t > tz:
                d.text((x, 1200), txt, font=f, fill=col, anchor="lm")
            x += texto_ancho(d, txt, f)
        if t > t_29:
            d.text((W / 2, 1270), "PaCO₂ real: 30  →  dentro de 27 – 31", font=F(F_MONO, 28), fill=VERDE, anchor="mm")
    fx.en(t_29, "tic")


def esc_caso_gap(fr, d, fx, t, dur, esc):
    t_na = tpal(esc, "140")
    t_cl = tpal(esc, "100,")
    t_26 = tpal(esc, "26:")
    t_el = tpal(esc, "elevado,")
    t_cad = tpal(esc, "cetoacidosis")
    ESTADO["valores"], ESTADO["anormales"] = CASO, {"pH", "PaCO₂", "HCO₃⁻"}
    q = eo(t, 0.1, 0.45)
    if q > 0:
        tarjeta(d, [60, 470, W - 60, 640], borde=BORDE)
        for i, (nom, val, col, tz) in enumerate([("Na⁺", "140", CORAL, t_na), ("Cl⁻", "100", CIAN, t_cl),
                                                 ("HCO₃⁻", "14", AMBAR, 0.1)]):
            x = 60 + (W - 120) * (i + 0.5) / 3
            on = t > tz
            d.text((x, 520), nom, font=F(F_BOLD, 34), fill=GRIS, anchor="mm")
            d.text((x, 585), val if on else "—", font=F(F_BLACK, 56), fill=col if on else GRIS, anchor="mm")
            fx.en(tz, "tic")
    # cálculo
    fx.en(t_26, "beep")
    q = eo(t, t_cl + 0.2, 0.45)
    if q > 0:
        tarjeta(d, [60, 690, W - 60, 900], borde=VIOLETA)
        d.text((W / 2, 735), "ANIÓN GAP", font=F(F_MONO, 28), fill=VIOLETA, anchor="mm")
        partes = [("140 − (100 + 14) = ", BLANCO, t_cl + 0.2), ("26", CORAL, t_26)]
        f = F(F_BLACK, 66)
        tot = sum(texto_ancho(d, p[0], f) for p in partes)
        x = W / 2 - tot / 2
        for txt, col, tz in partes:
            if t > tz:
                d.text((x, 830), txt, font=f, fill=col, anchor="lm")
            x += texto_ancho(d, txt, f)
    fx.en(t_el, "alerta")
    if t > t_el - 0.2:
        pildora(d, W / 2, 960, "ELEVADO  ( > 12 )", CORAL, F(F_MONO, 32), fill=mix(BG, CORAL, 0.12))
    fx.en(t_cad, "ok")
    q = eo(t, t_el + 0.3, 0.5)
    if q > 0:
        tarjeta(d, [60, 1040, W - 60, 1330], borde=VERDE, fill=mix(PANEL, VERDE, 0.06))
        d.text((W / 2, 1090), "DIAGNÓSTICO", font=F(F_MONO, 28), fill=VERDE, anchor="mm")
        d.text((W / 2, 1160), "Acidosis metabólica", font=F(F_BLACK, 56), fill=BLANCO, anchor="mm")
        d.text((W / 2, 1222), "con anión gap elevado, compensada", font=F(F_BOLD, 38), fill=BLANCO, anchor="mm")
        if t > t_cad:
            d.text((W / 2, 1288), "Ej.: cetoacidosis diabética", font=F(F_SEMI, 32), fill=VERDE, anchor="mm")


def esc_resumen(fr, d, fx, t, dur, esc):
    ESTADO["valores"], ESTADO["anormales"] = NORMALES, set()
    pasos = [("pH", "¿Acidemia o alcalemia?", "pH,", CORAL),
             ("ORIGEN", "Respiratorio (PaCO₂) o metabólico (HCO₃⁻)", "origen,", CIAN),
             ("COMPENSACIÓN", "Winter: 1.5 × HCO₃⁻ + 8 ± 2", "compensación,", AMBAR),
             ("ANIÓN GAP", "Na⁺ − (Cl⁻ + HCO₃⁻) · normal 8 – 12", "anión", VIOLETA),
             ("OXIGENACIÓN", "PaO₂ 80 – 100 · PaO₂/FiO₂ > 300", "oxigenación.", VERDE)]
    for i, (nom, sub, clave, col) in enumerate(pasos):
        tz = tpal(esc, clave)
        fx.en(tz, "ok", vol=0.7)
        q = eo(t, tz - 0.15, 0.45)
        if q <= 0:
            continue
        y = 480 + i * 165
        xo = (1 - min(1, q)) * 400
        tarjeta(d, [60 + xo, y, W - 60 + xo, y + 145], borde=mix(BG, col, 0.7))
        d.ellipse([90 + xo, y + 32, 170 + xo, y + 112], fill=mix(BG, col, 0.2), outline=col, width=3)
        d.text((130 + xo, y + 72), str(i + 1), font=F(F_MONO, 40), fill=col, anchor="mm")
        d.text((200 + xo, y + 52), nom, font=F(F_BLACK, 44), fill=BLANCO, anchor="lm")
        d.text((200 + xo, y + 104), sub, font=F(F_MED, 27), fill=GRIS, anchor="lm")
        palomita(d, W - 120 + xo, y + 72, 1.3, col, clamp01((t - tz) / 0.4))


def esc_outro(fr, d, fx, t, dur, esc):
    ESTADO["valores"], ESTADO["anormales"] = NORMALES, set()
    t_g = tpal(esc, "Guarda")
    t_com = tpal(esc, "comentarios")
    t_s = tpal(esc, "sígueme")
    # valores normales "latiendo" arriba
    for i, (nom, val) in enumerate(NORMALES.items()):
        q = eo(t, 0.1 + i * 0.12, 0.4)
        if q <= 0:
            continue
        x = 60 + (W - 120) * (i + 0.5) / 4
        pul = 1 + 0.04 * math.sin(t * 4 + i)
        tarjeta(d, [x - 112, 520, x + 112, 700], borde=mix(BG, VERDE, 0.6), r=24)
        d.text((x, 565), nom, font=F(F_BOLD, 32), fill=GRIS, anchor="mm")
        d.text((x, 640), val, font=F(F_BLACK, int(58 * pul)), fill=VERDE, anchor="mm")
    taps = [t_g + 0.3, t_s + 0.1]
    fx.en(taps[0], "click")
    fx.en(taps[0] + 0.05, "ok", vol=0.6)
    fx.en(taps[1], "click")
    fx.en(taps[1] + 0.05, "ok", vol=0.8)
    q = eo(t, 0.2, 0.45)
    if q > 0:
        g.boton(d, W / 2, 900, 560 * min(1, q), 120, "GUARDADO" if t > taps[0] else "GUARDAR", CIAN, t > taps[0],
                "guardar")
    q = eo(t, 0.4, 0.45)
    if q > 0:
        g.boton(d, W / 2, 1060, 560 * min(1, q), 120, "SIGUIENDO" if t > taps[1] else "SEGUIR", VERDE, t > taps[1],
                "seguir")
    fx.en(t_com, "pop")
    if t > t_com:
        tarjeta(d, [120, 1170, W - 120, 1300], borde=VIOLETA, r=30)
        temas = ["Trastornos del potasio", "Hiponatremia", "Electrolitos séricos"]
        u = t - t_com
        tema = temas[int(u / 1.8) % 3]
        n = min(len(tema), int((u % 1.8) * 22))
        d.text((160, 1235), tema[:n] + ("|" if int(t * 3) % 2 == 0 else ""), font=F(F_MED, 40), fill=BLANCO,
               anchor="lm")
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


ANIM = {"intro": esc_intro, "normales": esc_normales, "balanza": esc_balanza, "ph": esc_ph, "origen": esc_origen,
        "winter": esc_winter, "gap": esc_gap, "oxigenacion": esc_oxigenacion, "caso": esc_caso,
        "caso_gap": esc_caso_gap, "resumen": esc_resumen, "outro": esc_outro}


# ----------------------------------------------------------------------------
# CABECERA Y MONITOR INFERIOR (analizador de gases)
# ----------------------------------------------------------------------------
def cabecera(d, idx, t_esc, dur, esc, total):
    m = 50
    d.rounded_rectangle([m, 58, W - m, 64], radius=3, fill=(30, 44, 64))
    prog = (idx + clamp01(t_esc / dur)) / total
    d.rounded_rectangle([m, 58, m + (W - 2 * m) * prog, 64], radius=3, fill=esc["acento"])
    d.text((m, 108), "GASOMETRÍA ARTERIAL", font=F(F_MONO_M, 24), fill=GRIS, anchor="lm")
    d.text((W - m, 108), f"{idx + 1:02d} / {total:02d}", font=F(F_MONO_M, 24), fill=GRIS, anchor="rm")
    p = eo(t_esc, 0.05, 0.5)
    if p > 0:
        a = min(1, p)
        yo = 30 * (1 - a)
        d.text((W / 2, 205 + yo), esc["kicker"], font=F(F_MONO, 30), fill=mix(BG, esc["acento"], a), anchor="mm")
        tam = 84
        while d.textlength(esc["titulo"], font=F(F_BLACK, tam)) > W - 120 and tam > 50:
            tam -= 4
        d.text((W / 2, 290 + yo), esc["titulo"], font=F(F_BLACK, tam), fill=mix(BG, BLANCO, a), anchor="mm")
        w = d.textlength(esc["titulo"], font=F(F_BLACK, tam))
        lw = w * ei(t_esc, 0.3, 0.5)
        d.rounded_rectangle([W / 2 - lw / 2, 352 + yo, W / 2 + lw / 2, 358 + yo], radius=3, fill=esc["acento"])
    if esc.get("paso"):
        for i in range(5):
            x = W / 2 + (i - 2) * 48
            on = i < esc["paso"]
            d.ellipse([x - 9, 400 - 9, x + 9, 400 + 9], fill=esc["acento"] if on else (36, 52, 76))


def monitor(d, t, acento):
    d.line([(50, 1720), (W - 50, 1720)], fill=(24, 38, 58), width=2)
    vals, anorm = ESTADO["valores"], ESTADO["anormales"]
    n = len(vals)
    for i, (nom, val) in enumerate(vals.items()):
        x = 50 + (W - 100) * (i + 0.5) / n
        col = CORAL if nom in anorm else VERDE
        d.text((x, 1764), nom, font=F(F_SEMI, 26), fill=GRIS, anchor="mm")
        d.text((x, 1818), val, font=F(F_BLACK, 50), fill=col, anchor="mm")
    # indicador de análisis
    a = 0.5 + 0.5 * math.sin(t * 4)
    d.ellipse([W - 62, 1748, W - 50, 1760], fill=mix(BG, VERDE, a))


# ----------------------------------------------------------------------------
if __name__ == "__main__":
    g.ESCENAS = ESCENAS
    g.ANIM = ANIM
    g.NOMBRE = "reel_gasometria"
    g.cabecera = cabecera
    g.monitor = monitor
    import sys
    out = "."
    if "--out" in sys.argv:
        out = sys.argv[sys.argv.index("--out") + 1]
    g.main()
    # encabezado del guion adaptado a este tema
    ruta = os.path.join(out, "guion_elevenlabs.txt")
    txt = open(ruta, encoding="utf-8").read()
    ini = txt.index("[ESCENA 01")
    cab = ("GUION PARA ELEVENLABS — CÓMO INTERPRETAR UNA GASOMETRÍA ARTERIAL EN MENOS DE 3 MINUTOS\n"
           "Las siglas y los números están escritos como se pronuncian en español (pe hache, pe ce o dos,\n"
           "pe o dos, fi o dos, siete punto treinta y cinco...) para que ElevenLabs no los lea en inglés.\n"
           "Los subtítulos del video los muestran en su forma escrita (pH, PaCO₂, HCO₃⁻, PaO₂/FiO₂, 7.35).\n"
           f"Genera un audio por escena y colócalo en el tiempo indicado, o pásame los audios\n"
           f"(escena_01.mp3 ... escena_{len(ESCENAS):02d}.mp3) y re-sincronizo el video.\n\n")
    open(ruta, "w", encoding="utf-8").write(cab + txt[ini:])
