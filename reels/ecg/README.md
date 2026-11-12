# Reel: Cómo leer un electrocardiograma — Biología en Minutos

Video vertical 1080x1920, de unos 2:43, **sin voz**. Tiene estilo de monitor clínico: fondo oscuro con cuadrícula, papel de ECG milimetrado, trazos neón y tipografía **Inter** con **JetBrains Mono** para los datos. Los efectos de sonido son sobrios (bips de monitor sincronizados con el QRS, tics y confirmaciones) y la música es ambiental, con un pulso a 75 lpm.

| Archivo | Qué es |
|---|---|
| `reel_ecg.mp4` | Video con efectos y música |
| `reel_ecg_sin_musica.mp4` | Solo con efectos |
| `guion_elevenlabs.txt` | Guion por escena con tiempos; números y siglas deletreados para que la pronunciación sea correcta |
| `subtitulos.srt` | Subtítulos (con cifras: 0.04 s, 25 mm/s…) |

## Estructura
**Fundamentos**
1. El papel: 25 mm/s; 1 mm = 0.04 s y 0.1 mV; 5 mm = 0.20 s
2. Ondas: P (despolarización auricular), QRS (despolarización ventricular) y T (repolarización ventricular)

**Derivaciones**
3. Plano frontal: sistema hexaxial con DI, DII y DIII (bipolares) y aVR, aVL y aVF (aumentadas), con sus ángulos
4. Precordiales: V1 a V6 sobre el tórax (4º EIC paraesternal, 5º EIC en la línea medioclavicular y línea medioaxilar)
5. Caras del corazón: ECG de 12 derivaciones agrupado en territorios inferior, lateral, septal y anterior

**Los 5 pasos**
1. Ritmo: P antes de cada QRS, P (+) en DII y (−) en aVR, R-R regular
2. Frecuencia: 300 ÷ cuadros grandes, con la serie 300-150-100-75-60-50 y el rango normal de 60 a 100
3. Eje: DI y aVF (y DII); eje normal, desviación derecha y desviación izquierda
4. Intervalos: PR de 0.12 a 0.20 s, QRS menor de 0.12 s, QTc menor de 440 ms (H) o 460 ms (M)
5. ST-T: elevación, depresión y T invertida frente a la línea isoeléctrica

Cierra con un resumen y una llamada a la acción (guardar, comentar y seguir).

Las formas de onda se generan matemáticamente con proporciones reales (25 mm/s, 10 mm/mV) y una morfología distinta para cada una de las 12 derivaciones.

## Agregar la voz
```bash
python generar.py --voz-dir carpeta_con_escena_01..13 --out .
```
Fuentes incluidas en `fonts/` (licencia SIL OFL).
