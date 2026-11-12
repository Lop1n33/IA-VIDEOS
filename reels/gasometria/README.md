# Reel: Cómo interpretar una gasometría arterial en menos de 3 minutos

Video vertical 1080x1920, de unos 2:31, **sin voz**. Usa el mismo estilo que el reel de ECG v2: monitor clínico oscuro, Inter con JetBrains Mono, subtítulos karaoke y efectos sobrios. Reutiliza el motor de `../ecg_v2/generar.py` y cambia las escenas, la cabecera y el monitor inferior, que aquí es un "analizador" con pH, PaCO₂, HCO₃⁻ y PaO₂ que se ponen en rojo cuando están alterados.

| Archivo | Qué es |
|---|---|
| `reel_gasometria.mp4` | Video con efectos y música |
| `reel_gasometria_sin_musica.mp4` | Solo con efectos |
| `guion_elevenlabs.txt` | Guion por escena con tiempos, escrito para pronunciarse bien en español |
| `subtitulos.srt` | Subtítulos |

## Contenido
1. **Intro:** "Seguramente has visto esto: una gasometría arterial…". Un reporte que se imprime, sus números se revuelven y luego se ordenan.
2. **Valores normales:** pH 7.35–7.45 · PaCO₂ 35–45 mmHg · HCO₃⁻ 22–26 mEq/L · PaO₂ 80–100 mmHg.
3. **Balanza ácido-base:** el CO₂ es ácido y lo regula el pulmón; el HCO₃⁻ es base y lo regula el riñón.
4. **Paso 1, el pH:** escala con acidemia y alcalemia.
5. **Paso 2, el origen:** los 4 trastornos con flechas. Si el pH y la PaCO₂ van en sentido opuesto, es respiratorio; si el pH y el HCO₃⁻ van en el mismo sentido, es metabólico.
6. **Paso 3, la compensación:** fórmula de Winter, PaCO₂ = 1.5 × HCO₃⁻ + 8 ± 2, y cómo detectar un segundo trastorno.
7. **Paso 4, el anión gap:** gamblegram, Na⁺ − (Cl⁻ + HCO₃⁻), normal de 8 a 12, con las causas de AG elevado y AG normal.
8. **Paso 5, la oxigenación:** PaO₂ y medidor de PaO₂/FiO₂ (umbrales de 300, 200 y 100).
9. **Caso clínico:** pH 7.25, PaCO₂ 30, HCO₃⁻ 14, Na⁺ 140 y Cl⁻ 100. Resultado: acidosis metabólica compensada con anión gap de 26 (elevado), como en la cetoacidosis diabética.
10. **Resumen y cierre.**

## Agregar la voz
```bash
python generar.py --voz-dir carpeta_con_escena_01..12 --out .
```
