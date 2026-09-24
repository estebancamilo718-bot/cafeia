# Resultados de la evaluación final en TEST

**Fecha:** 2026-09-22
**Protocolo preregistrado:** `reports/FINAL_PROTOCOL.md`
**Partición:** 300 imágenes de TEST del manifiesto SHA-256 `1ea21d6b2b480b830065c5d4d1d90f531234cc2aa244d7bb98c5873363866dab`
**Selección cerrada antes de TEST:** MobileNetV3 Small ajustado, época 6, elegido por F1 macro de validación `0.6478439521`.

## Conclusión

El candidato principal obtuvo en TEST **F1 macro 0.623486**, **accuracy 0.716667** y **85 errores de 300**. Su F1 macro bajó `0.024358` respecto a validación. La disminución se informa sin cambiar el checkpoint, el umbral ni el protocolo.

La referencia MobileNet congelada obtuvo un F1 macro de TEST ligeramente mayor (`0.629352`) y ResNet18 la mayor accuracy (`0.740000`), pero estos resultados no reabren la selección. El candidato principal permanece fijado por el criterio predeclarado de F1 macro de validación. Seleccionar de nuevo con TEST convertiría la evaluación final en otra etapa de ajuste.

## Comparación de validación frente a TEST

| Modelo fijado | Rol | F1 macro VAL | F1 macro TEST | Δ TEST−VAL | Accuracy VAL | Accuracy TEST | Errores TEST |
|---|---|---:|---:|---:|---:|---:|---:|
| MobileNet ajustado, época 6 | Principal | 0.647844 | 0.623486 | -0.024358 | 0.737542 | 0.716667 | 85 |
| MobileNet congelado, época 9 | Referencia | 0.632707 | 0.629352 | -0.003356 | 0.717608 | 0.720000 | 84 |
| ResNet18 congelado, época 8 | Referencia | 0.594740 | 0.608927 | +0.014187 | 0.667774 | 0.740000 | 78 |
| CNN pequeña, época 7 | Referencia | 0.438571 | 0.427482 | -0.011089 | 0.485050 | 0.473333 | 158 |

El F1 macro de TEST descriptivamente más alto corresponde a MobileNet congelado, pero la diferencia frente al candidato es `0.005866` y no se usa para reemplazarlo. ResNet18 tiene menos errores y mayor accuracy, pero su F1 macro es menor; en particular, solo recupera 7 de las 31 imágenes de ácaro rojo. Esto ilustra por qué accuracy no fue el criterio de selección.

## Métricas de TEST por clase

| Modelo | Clase | Precision | Recall | F1 | Soporte |
|---|---|---:|---:|---:|---:|
| MobileNet ajustado | Hoja sana | 0.881944 | 0.824675 | 0.852349 | 154 |
| MobileNet ajustado | Ácaro rojo | 0.291667 | 0.451613 | 0.354430 | 31 |
| MobileNet ajustado | Roya | 0.685185 | 0.643478 | 0.663677 | 115 |
| MobileNet congelado | Hoja sana | 0.853503 | 0.870130 | 0.861736 | 154 |
| MobileNet congelado | Ácaro rojo | 0.307692 | 0.516129 | 0.385542 | 31 |
| MobileNet congelado | Roya | 0.725275 | 0.573913 | 0.640777 | 115 |
| ResNet18 congelado | Hoja sana | 0.821656 | 0.837662 | 0.829582 | 154 |
| ResNet18 congelado | Ácaro rojo | 0.350000 | 0.225806 | 0.274510 | 31 |
| ResNet18 congelado | Roya | 0.699187 | 0.747826 | 0.722689 | 115 |
| CNN pequeña | Hoja sana | 0.634783 | 0.474026 | 0.542751 | 154 |
| CNN pequeña | Ácaro rojo | 0.203390 | 0.387097 | 0.266667 | 31 |
| CNN pequeña | Roya | 0.452381 | 0.495652 | 0.473029 | 115 |

Ácaro rojo sigue siendo la clase más débil del candidato principal: tiene la menor precision (`0.291667`), recall (`0.451613`) y F1 (`0.354430`). El soporte de esta clase es 31, considerablemente menor que sana (154) y roya (115), pero el soporte por sí solo no demuestra la causa de los errores.

Frente a su propia validación, el candidato cambió así:

- Hoja sana: F1 `0.853503 → 0.852349`; recall `0.858974 → 0.824675`.
- Ácaro rojo: F1 `0.410959 → 0.354430`; recall `0.483871 → 0.451613`.
- Roya: F1 `0.679070 → 0.663677`; recall `0.640351 → 0.643478`.

## Matrices de confusión de TEST

Filas: clase real. Columnas: clase predicha. El orden es Hoja sana, Ácaro rojo y Roya.

### MobileNet ajustado, época 6

| Real / predicha | Hoja sana | Ácaro rojo | Roya |
|---|---:|---:|---:|
| Hoja sana | 127 | 7 | 20 |
| Ácaro rojo | 3 | 14 | 14 |
| Roya | 14 | 27 | 74 |

### MobileNet congelado, época 9

| Real / predicha | Hoja sana | Ácaro rojo | Roya |
|---|---:|---:|---:|
| Hoja sana | 134 | 7 | 13 |
| Ácaro rojo | 3 | 16 | 12 |
| Roya | 20 | 29 | 66 |

### ResNet18 congelado, época 8

| Real / predicha | Hoja sana | Ácaro rojo | Roya |
|---|---:|---:|---:|
| Hoja sana | 129 | 4 | 21 |
| Ácaro rojo | 8 | 7 | 16 |
| Roya | 20 | 9 | 86 |

### CNN pequeña, época 7

| Real / predicha | Hoja sana | Ácaro rojo | Roya |
|---|---:|---:|---:|
| Hoja sana | 73 | 28 | 53 |
| Ácaro rojo | 3 | 12 | 16 |
| Roya | 39 | 19 | 57 |

Para el candidato principal, las confusiones más numerosas son roya → ácaro rojo (27), hoja sana → roya (20), roya → hoja sana (14) y ácaro rojo → roya (14). No se deduce su causa únicamente a partir de estos conteos.

## Umbral provisional del candidato principal

El análisis usa la puntuación softmax máxima de cada predicción y mantiene el umbral predeclarado de `0.70`.

| Resultado del umbral | Cantidad | Proporción |
|---|---:|---:|
| Puntuación `< 0.70` | 142 | 47.33 % |
| Puntuación `≥ 0.70` | 158 | 52.67 % |

Entre las **158 predicciones aceptadas**, **140 fueron correctas** y 18 incorrectas: accuracy condicional **0.886076 (88.61 %)**.

Esta cifra describe solo el subconjunto seleccionado por el propio score del modelo. No es la accuracy global, no demuestra calibración y no convierte `0.70` en un umbral óptimo. Las puntuaciones softmax no son probabilidades calibradas de acierto. El umbral tampoco detecta fotografías ajenas al café ni sustituye una evaluación fuera de distribución.

## Compatibilidad y protocolo ejecutado

- Los cuatro checkpoints declararon el mismo manifiesto, semilla 42 y el orden exacto `sana → ácaro rojo → roya`.
- Los cuatro `state_dict` cargaron de forma estricta y produjeron tres salidas.
- Todos usaron `src.common.Leaves(..., training=False)` y `transform(False)`.
- Preprocesamiento: EXIF transpose → RGB → Resize 224×224 → ToTensor → normalización ImageNet.
- Sin aumento en TEST, `shuffle=False`, `batch_size=16`, CPU.
- El evaluador recibió una ruta explícita por checkpoint y escribió únicamente bajo `experiments/final_test_20260922/`.

## Limitaciones

1. TEST contiene una sola partición de 300 imágenes; no se calcularon intervalos de confianza ni validación externa.
2. La distribución está desbalanceada, especialmente para ácaro rojo (31 imágenes).
3. Las imágenes proceden del mismo conjunto RoCoLe y no establecen desempeño en otras fincas, cámaras, iluminaciones o especies.
4. Las puntuaciones softmax no fueron calibradas.
5. La evaluación no mide detección de fotografías ajenas al café ni seguridad agronómica.
6. Después de esta consulta, TEST debe permanecer cerrado para cualquier ajuste futuro. Un nuevo ciclo experimental requeriría otro conjunto final independiente.

## Evidencias

Directorio raíz: `experiments/final_test_20260922/`.

- `protocol_snapshot.json`: protocolo fijado antes de TEST.
- `compatibility.json`: carga, arquitectura, salidas y orden de clases.
- `model_comparison.csv`: comparación resumida de los cuatro modelos.
- `validation_vs_test.csv`: comparación por métrica y clase.
- `final_summary.json`: resultados completos consolidados.
- `mobilenet_finetuned_epoch6/`: métricas, matriz, 300 predicciones y 85 errores del candidato.
- `mobilenet_frozen_epoch9/`: métricas, matriz, 300 predicciones y 84 errores.
- `resnet18_frozen_epoch8/`: métricas, matriz, 300 predicciones y 78 errores.
- `cnn_scratch_epoch7/`: métricas, matriz, 300 predicciones y 158 errores.

## Integridad del modelo activo

La evaluación no escribe en `models/`. El modelo activo de la web continúa siendo `models/mobilenet.pt`; el candidato ajustado se evaluó desde su carpeta de experimento y no lo reemplazó.
