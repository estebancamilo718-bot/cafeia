# Resultados del experimento pareado de preprocesamiento CaféIA v2

**Fecha:** 2026-09-27
**Ámbito:** TRAIN y VAL exclusivamente. TEST no se abrió ni se evaluó.
**Carpeta de evidencia:** `experiments/mobilenet_v2_preprocessing_20260927-114627/`

## Resultado ejecutivo

El candidato que conserva la proporción y agrega relleno **no mejoró** el control. El F1 macro de VAL bajó de `0.647844` a `0.591710`, una diferencia absoluta de `-0.056134`. También retrocedieron precision, recall y F1 de ácaro rojo.

Por tanto, el experimento no justifica cambiar el preprocesamiento ni reemplazar el modelo web. El checkpoint activo `models/mobilenet_finetuned_epoch6.pt`, el manifiesto y el umbral provisional 0,70 permanecieron intactos.

## Diseño efectivamente comparado

Las dos ramas parten del mismo archivo:

- Checkpoint inicial: `models/mobilenet.pt`.
- SHA-256: `9248cc767425c9efec643bcc2cabd758e8f2b28ab4a6967908713fc1d0b9c5c1`.
- Manifiesto: SHA-256 `1ea21d6b2b480b830065c5d4d1d90f531234cc2aa244d7bb98c5873363866dab`.
- Semilla: 42.

La rama A reutiliza la corrida control `mobilenet_finetune_20260922-103426`. Antes de reutilizarla se comprobó:

- igualdad de checkpoint inicial, manifiesto y configuración de entrenamiento;
- 301/301 tensores de VAL idénticos entre el transformador legado y el control explícito;
- 30/30 comprobaciones idénticas de aumentos sobre ejemplos de TRAIN y semillas fijadas;
- reproducción exacta del F1 inicial `0.6327072392` y del F1 seleccionado `0.6478439521`.

La rama B fue la única corrida nueva. Conservó arquitectura, pesos de clase, aumentos, optimizador, tasas, capas entrenables, BatchNorm, lote, semilla y presupuesto. El único cambio principal fue el redimensionamiento proporcional con relleno centrado.

## Historial del candidato

| Época candidata | Pérdida TRAIN | F1 macro VAL | Mejora sobre el mejor previo |
|---:|---:|---:|---|
| 0 | — | 0.536497 | Referencia inicial con el nuevo preprocesamiento |
| 1 | 0.800734 | 0.585385 | Sí |
| **2** | **0.767776** | **0.591710** | **Sí; checkpoint seleccionado** |
| 3 | 0.746700 | 0.588636 | No |
| 4 | 0.723123 | 0.580049 | No |
| 5 | 0.747160 | 0.581591 | No |
| 6 | 0.707061 | 0.578558 | No; cuarta época consecutiva sin mejora |

La parada temprana se activó después de la época 6. La corrida candidata duró `158.06 s`. El control había ejecutado 10 épocas y durado `416.40 s`; las duraciones se informan como evidencia operativa, no como métrica de selección.

## Comparación de VALIDACIÓN

| Rama | F1 macro | Errores / 301 | Accuracy descriptiva |
|---|---:|---:|---:|
| A. Control, resize directo | **0.647844** | **79** | **0.737542** |
| B. Proporción + relleno | 0.591710 | 97 | 0.677741 |
| Candidato − control | **−0.056134** | **+18** | **−0.059801** |

### Precision, recall y F1 por clase

| Clase | Rama | Precision | Recall | F1 | Soporte |
|---|---|---:|---:|---:|---:|
| Hoja sana | Control | 0.848101 | 0.858974 | 0.853503 | 156 |
| Hoja sana | Candidato | 0.798701 | 0.788462 | 0.793548 | 156 |
| Hoja sana | Diferencia | −0.049400 | −0.070513 | −0.059955 | — |
| Ácaro rojo | Control | 0.357143 | 0.483871 | 0.410959 | 31 |
| Ácaro rojo | Candidato | 0.325000 | 0.419355 | 0.366197 | 31 |
| Ácaro rojo | Diferencia | **−0.032143** | **−0.064516** | **−0.044762** | — |
| Roya | Control | 0.722772 | 0.640351 | 0.679070 | 114 |
| Roya | Candidato | 0.635514 | 0.596491 | 0.615385 | 114 |
| Roya | Diferencia | −0.087258 | −0.043860 | −0.063685 | — |

La caída global estuvo acompañada por un retroceso en ácaro rojo: se reconocieron correctamente 13 de 31 imágenes, frente a 15 de 31 en el control. No hubo una mejora oculta de recall compensada por precision; ambas métricas disminuyeron.

## Matrices de confusión

Filas reales y columnas predichas, en orden **Hoja sana, Ácaro rojo, Roya**.

### A. Control

| Real \ Predicha | Hoja sana | Ácaro rojo | Roya |
|---|---:|---:|---:|
| Hoja sana | 134 | 8 | 14 |
| Ácaro rojo | 2 | 15 | 14 |
| Roya | 22 | 19 | 73 |

### B. Candidato con relleno

| Real \ Predicha | Hoja sana | Ácaro rojo | Roya |
|---|---:|---:|---:|
| Hoja sana | 123 | 8 | 25 |
| Ácaro rojo | 4 | 13 | 14 |
| Roya | 27 | 19 | 68 |

### Confusiones solicitadas

- Ácaro rojo → roya: `14` en el control y `14` en el candidato; no cambió.
- Roya → sana: `22` en el control y `27` en el candidato; empeoró en 5 imágenes.
- Ácaro rojo → sana también pasó de 2 a 4, mientras los aciertos de ácaro bajaron de 15 a 13.

## Preprocesamiento archivado

El checkpoint candidato contiene el identificador `cafeia-v2-aspect-pad-224-v1` y el diccionario completo de preprocesamiento:

1. orientación EXIF y RGB;
2. escala del lado largo a 224 con interpolación bilineal y antialias;
3. redondeo explícito de dimensiones;
4. relleno constante RGB `(124, 116, 104)`, centrado;
5. flip horizontal y rotación de TRAIN, en ese orden;
6. `ToTensor` y normalización ImageNet.

Checkpoint candidato archivado:

- Ruta: `experiments/mobilenet_v2_preprocessing_20260927-114627/candidate/best_checkpoint.pt`.
- Época: 2.
- SHA-256: `3a5c714ee78fbf467e0299565dbf922daf1cad6b424948efa7a471e4443a94c6`.

Las comprobaciones confirmaron que todos los parámetros entrenables estaban en el optimizador, las convoluciones descongeladas recibieron gradientes y las estadísticas BatchNorm permanecieron sin cambios.

## Integridad y límites

Al terminar se volvieron a verificar estos hashes:

- Modelo web activo: `4ab4e52fc3d417fe5fb126ff1e5b346f080c55ffa80232cffd5d6e6622e46c94`.
- Checkpoint común de inicio: `9248cc767425c9efec643bcc2cabd758e8f2b28ab4a6967908713fc1d0b9c5c1`.
- Manifiesto: `1ea21d6b2b480b830065c5d4d1d90f531234cc2aa244d7bb98c5873363866dab`.

No se consultó TEST, no se cambió el umbral 0,70 y no se sustituyó el modelo activo. Esta es una comparación con una sola semilla; incluso si la diferencia hubiera sido pequeña y favorable, no habría demostrado consistencia entre corridas. En este caso la diferencia es desfavorable, pero tampoco se usa para iniciar automáticamente otra búsqueda.

## Evidencias

- `preprocessing_comparison_train.png`: lámina con tres ejemplos de TRAIN.
- `tensor_preflight.json`: dimensiones, canales, normalización y salida del modelo.
- `control/reuse_equivalence.json`: equivalencia y reproducción del control.
- `control/`: configuración, historial, checkpoint y métricas reutilizadas.
- `candidate/configuration.json`: configuración efectiva completa.
- `candidate/preprocessing.json`: procedimiento exacto y versionado.
- `candidate/history.json`: historial por época.
- `candidate/validation_metrics.json`: métricas y matriz.
- `candidate/validation_predictions.csv`: predicciones de las 301 imágenes de VAL.
- `candidate/validation_errors.csv`: 97 errores de VAL.
- `candidate/validation_error_sample.csv`: muestra estratificada por par real/predicha.
- `comparison.json` y `comparison.csv`: comparación pareada final.
