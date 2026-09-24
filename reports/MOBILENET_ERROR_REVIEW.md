# Revisión visual dirigida de errores de MobileNet

Revisión previa al ajuste fino, realizada sobre once imágenes de la muestra de errores de validación del checkpoint original (época 9). Las etiquetas y archivos se conservaron sin cambios. Estas observaciones describen lo visible; no validan ni corrigen la clase agronómica y no establecen causalidad.

## Roya predicha como hoja sana

| Imagen | Puntuación de hoja sana | Observación visual |
|---|---:|---|
| `data/raw/coffee___rust/C5P11E1.jpg` | 0.989574 | Envés claro y casi uniforme ocupando gran parte del encuadre; se ven muy pocos puntos rojizos pequeños y varias hojas en el fondo. |
| `data/raw/coffee___rust/C5P7E1.jpg` | 0.972346 | Envés pálido con puntos marrón/anaranjado pequeños y dispersos, además de numerosos puntos claros; no hay una lesión grande dominante. |
| `data/raw/coffee___rust/C11P32H2.jpg` | 0.923018 | Haz verde brillante, con pocos puntos anaranjados aislados y daño irregular en el borde; iluminación intensa y fondo complejo. |

## Roya predicha como ácaro rojo

| Imagen | Puntuación de ácaro rojo | Observación visual |
|---|---:|---|
| `data/raw/coffee___rust/C6P14H2.jpg` | 0.833188 | Hoja mayormente verde con un parche amplio, pálido y difuso cerca del borde; reflejos fuertes y frutos/hojas en el fondo. |
| `data/raw/coffee___rust/C4P27E2.jpg` | 0.825965 | Hoja plegada que muestra dos superficies, con marcas marrones pequeñas y puntos oscuros; aparece una mano y vegetación de fondo. |

## Ácaro rojo predicho como roya

| Imagen | Puntuación de roya | Observación visual |
|---|---:|---|
| `data/raw/coffee___red_spider_mite/C12P1H2.jpg` | 0.883126 | Múltiples lesiones circulares oscuras rodeadas por halos amarillos/anaranjados; también hay perforación y hojas afectadas en el fondo. |
| `data/raw/coffee___red_spider_mite/C10P9E2.jpg` | 0.820202 | Numerosas manchas claras y marrones, algunas con centro oscuro, junto con una zona blanca irregular sobre el envés. |

## Ácaro rojo predicho como hoja sana

| Imagen | Puntuación de hoja sana | Observación visual |
|---|---:|---|
| `data/raw/coffee___red_spider_mite/C11P32E2.jpg` | 0.574784 | Envés verde brillante y bastante uniforme, con pocas marcas pequeñas y daño menor en el borde. |
| `data/raw/coffee___red_spider_mite/C6P40H2.jpg` | 0.522585 | Hojas oscuras y brillantes; la hoja central está algo desenfocada y presenta pocas áreas marrones amplias. |

## Hoja sana predicha como ácaro rojo

| Imagen | Puntuación de ácaro rojo | Observación visual |
|---|---:|---|
| `data/raw/coffee___healthy/C11P11H1.jpg` | 0.773832 | Hoja verde uniforme con reflejos muy intensos y saturación alta; el fondo contiene varias hojas. |
| `data/raw/coffee___healthy/C10P19E1.jpg` | 0.588361 | Envés verde casi uniforme con contraste fuerte entre sol y sombra; el fondo contiene vegetación con puntos oscuros. |

## Alcance

La muestra sugiere que los errores incluyen señales pequeñas o dispersas, iluminación variable, hojas vistas por ambas superficies, desenfoque y contexto de fondo. No se concluye que alguno de esos factores sea la causa del error; para sostenerlo haría falta un análisis sistemático sobre más imágenes y variables controladas.
