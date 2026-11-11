# Reel: Cómo leer un ECG en menos de 3 minutos (versión 2, corregida)

Video vertical 1080x1920, de unos 2:43, **sin voz**. Usa el estilo de monitor clínico de `reels/ecg` (Inter y JetBrains Mono, papel milimetrado y trazos neón), sin la marca "Biología en Minutos".

| Archivo | Qué es |
|---|---|
| `reel_ecg_v2.mp4` | Video con efectos y música |
| `reel_ecg_v2_sin_musica.mp4` | Solo con efectos |
| `guion_elevenlabs.txt` | Guion por escena con tiempos, escrito para pronunciarse bien en español |
| `subtitulos.srt` | Subtítulos |

## Cambios respecto a la versión 1
**Nueva introducción:** "Seguramente has visto esto. Esto es un electrocardiograma. Y si tenías dudas, o si solo veías garabatos, hoy te enseño a leerlo en menos de 3 minutos." Aparece un ECG de 12 derivaciones que tiembla como garabato y luego se ordena.

**Errores visuales corregidos:**
- Los sombreados y trazos parciales se dibujaban desplazados: el QRS sombreado aparecía a la izquierda de la R y en la intro se veía un trazo "fantasma" desfasado.
- Las etiquetas se encimaban sobre el trazo en las escenas del papel, la frecuencia (300-150-100…) y los intervalos.
- El tórax de las precordiales estaba rehecho de forma burda; ahora tiene costillas, esternón, espacios intercostales 4º y 5º, y el corazón tenue no tapa los electrodos.
- Los paneles vacíos del segmento ST aparecían antes de tiempo.
- El cursor tapaba "GUARDAR" y había un "REC" parpadeando.
- La palomita de "RITMO SINUSAL" se encimaba con el texto.

**Pronunciación:** el guion de voz escribe las siglas como se dicen en español ("cu erre ese", "a ve efe", "de dos", "ese te", "pe erre", "ve uno"…) y corrige "cero punto **uno** milivoltios". Los subtítulos conservan la forma escrita (QRS, aVF, DII, ST).

## Agregar la voz
```bash
python generar.py --voz-dir carpeta_con_escena_01..13 --out .
```
