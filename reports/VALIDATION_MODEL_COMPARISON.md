# Comparación de modelos en validación

Comparación exclusiva sobre las 301 imágenes de la partición `val` del manifiesto conservado (SHA256 `1ea21d6b2b480b830065c5d4d1d90f531234cc2aa244d7bb98c5873363866dab`). Los tres experimentos usaron semilla 42, la misma partición y selección por F1 macro de validación. No se consultó `test`.

## Resumen

| Modelo | Mejor época | F1 macro | Recall hoja sana | Recall ácaro rojo | Recall roya | Errores / 301 |
|---|---:|---:|---:|---:|---:|---:|
| MobileNetV3 Small | 9 | 0.632707 | 0.878205 | 0.516129 | 0.552632 | 85 |
| ResNet18, extractor congelado | 8 | 0.594740 | 0.769231 | 0.483871 | 0.578947 | 100 |
| CNN pequeña desde cero | 7 | 0.438571 | 0.525641 | 0.451613 | 0.438596 | 155 |

MobileNet obtiene el F1 macro de validación más alto. También logra el mayor recall en hoja sana y ácaro rojo; ResNet18 logra el mayor recall en roya. Esta comparación no es una evaluación final ni autoriza conclusiones sobre `test`.

## Precision, recall y F1 por clase

| Modelo | Clase | Precision | Recall | F1 | Soporte |
|---|---|---:|---:|---:|---:|
| MobileNetV3 Small | Hoja sana | 0.778409 | 0.878205 | 0.825301 | 156 |
| MobileNetV3 Small | Ácaro rojo | 0.363636 | 0.516129 | 0.426667 | 31 |
| MobileNetV3 Small | Roya | 0.777778 | 0.552632 | 0.646154 | 114 |
| CNN pequeña | Hoja sana | 0.677686 | 0.525641 | 0.592058 | 156 |
| CNN pequeña | Ácaro rojo | 0.200000 | 0.451613 | 0.277228 | 31 |
| CNN pequeña | Roya | 0.454545 | 0.438596 | 0.446429 | 114 |
| ResNet18 | Hoja sana | 0.805369 | 0.769231 | 0.786885 | 156 |
| ResNet18 | Ácaro rojo | 0.348837 | 0.483871 | 0.405405 | 31 |
| ResNet18 | Roya | 0.605505 | 0.578947 | 0.591928 | 114 |

## Matrices de confusión

Filas: clase real. Columnas: clase predicha.

### MobileNetV3 Small

| Real / predicha | Hoja sana | Ácaro rojo | Roya |
|---|---:|---:|---:|
| Hoja sana | 137 | 10 | 9 |
| Ácaro rojo | 6 | 16 | 9 |
| Roya | 33 | 18 | 63 |

### CNN pequeña

| Real / predicha | Hoja sana | Ácaro rojo | Roya |
|---|---:|---:|---:|
| Hoja sana | 82 | 28 | 46 |
| Ácaro rojo | 3 | 14 | 14 |
| Roya | 36 | 28 | 50 |

### ResNet18

| Real / predicha | Hoja sana | Ácaro rojo | Roya |
|---|---:|---:|---:|
| Hoja sana | 120 | 6 | 30 |
| Ácaro rojo | 3 | 15 | 13 |
| Roya | 26 | 22 | 66 |

## Diagnóstico de MobileNet

La clase que más limita a MobileNet en términos relativos es **ácaro rojo**: tiene la precision más baja (0.363636), el recall más bajo (0.516129) y el F1 más bajo (0.426667). De sus 31 ejemplos, 16 se clasifican correctamente, 9 se confunden con roya y 6 con hoja sana. Además, 28 imágenes de otras clases se predicen erróneamente como ácaro rojo: 18 de roya y 10 sanas. Su soporte es menor que el de las otras clases, pero estas métricas y conteos no demuestran por sí solos la causa de los errores.

Por conteo absoluto, la confusión más frecuente de MobileNet es **roya → hoja sana** (33 imágenes), seguida de **roya → ácaro rojo** (18), **hoja sana → ácaro rojo** (10), y luego **hoja sana → roya** y **ácaro rojo → roya** (9 cada una). Por eso, aunque ácaro rojo es la clase más débil proporcionalmente, roya aporta más falsos negativos absolutos: 51 de 114 imágenes de roya se asignan a otra clase.

## Evidencia

- MobileNet: `experiments/mobilenet_10ep_20260920-181113/`
- CNN: `experiments/cnn_10ep_20260921-125200/`
- ResNet18: `experiments/resnet18_10ep_20260921-130620/`
- Cada carpeta contiene configuración, historial, mejor checkpoint, métricas, matriz, predicciones por imagen, todos los errores y una muestra de errores.
