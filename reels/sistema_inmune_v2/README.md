# Reel v2: Las células del sistema inmunológico — Biología en Minutos

Video vertical 1080x1920, de unos 84 segundos, **sin voz**: lleva subtítulos estilo karaoke, efectos de sonido caricaturescos y música suave, listo para agregarle la narración con ElevenLabs.

| Archivo | Qué es |
|---|---|
| `reel_sistema_inmune_v2.mp4` | Video con efectos de sonido y música |
| `reel_sistema_inmune_v2_sin_musica.mp4` | Igual, pero solo con efectos (por si pones tu propia música) |
| `guion_elevenlabs.txt` | Guion por escena con el segundo en que empieza cada una |
| `subtitulos.srt` | Subtítulos por frase |

## Efectos de sonido
- "Ding" o campanita cuando se presenta cada célula, más un "whoosh" en su entrada
- "Ñam-ñam-glup" cuando neutrófilos y macrófagos se comen bacterias o virus
- "Boing" cuando los anticuerpos se pegan y marcan a la bacteria (opsonización)
- "Pew" en los disparos de anticuerpos y perforinas, "zap" en los rayos y "boom" en las explosiones
- Alarma cuando el macrófago llama refuerzos, "splat" del pus, tecleo y clic en el cierre

## Agregar la voz
**Opción A:** genera en ElevenLabs un audio por escena con el texto de `guion_elevenlabs.txt` y colócalo en tu editor en el segundo que se indica.

**Opción B (sincronización exacta):** guarda los audios como `escena_01.mp3` … `escena_10.mp3` en una carpeta y ejecuta:
```bash
python generar.py --voz-dir carpeta_audios --out .
```
El video se vuelve a crear con la duración real de tus audios y la voz ya mezclada (`reel_sistema_inmune_v2_con_voz.mp4`).

## Volver a crearlo sin audios
Requiere `kokoro-onnx`, `soundfile`, `pillow`, `numpy` y `ffmpeg`. Kokoro solo se usa para estimar cuánto dura cada escena; su voz no se incluye en el video.
```bash
python generar.py --modelo kokoro-v1.0.int8.onnx --voces voices-v1.0.bin --out .
```
