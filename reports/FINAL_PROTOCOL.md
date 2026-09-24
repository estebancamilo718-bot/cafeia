# Protocolo congelado de evaluación final

**Registrado:** 2026-09-22, antes de ejecutar o consultar la evaluación de TEST.
**Estado:** selección de modelos cerrada; los cuatro checkpoints quedan fijados por validación.
**Partición final:** las mismas 300 imágenes marcadas como `test` en el manifiesto conservado.
**Directorio nuevo de resultados:** `experiments/final_test_20260922/`.

## Regla de uso de TEST

TEST se evaluará una sola vez para estimar el desempeño final de los cuatro checkpoints ya seleccionados. Sus resultados no se usarán para:

- cambiar el modelo principal;
- ajustar pesos, hiperparámetros, preprocesamiento o particiones;
- modificar el umbral provisional;
- iniciar entrenamiento adicional;
- escoger un checkpoint o una época diferente.

El candidato principal permanece fijado aunque su desempeño en TEST sea inferior al de validación o al de una referencia.

## Manifiesto fijado

- Ruta: `data/processed/manifest.csv`
- SHA-256: `1ea21d6b2b480b830065c5d4d1d90f531234cc2aa244d7bb98c5873363866dab`
- Semilla usada para la partición y los experimentos: `42`
- Cantidad fijada para TEST: `300`

No se regenerará ni modificará el manifiesto durante la evaluación.

## Checkpoints fijados por validación

| Rol | Arquitectura | Checkpoint | Época seleccionada | F1 macro de validación | SHA-256 |
|---|---|---|---:|---:|---|
| **Candidato principal** | MobileNetV3 Small ajustado | `experiments/mobilenet_finetune_20260922-103426/best_checkpoint.pt` | **6** | **0.6478439521** | `4ab4e52fc3d417fe5fb126ff1e5b346f080c55ffa80232cffd5d6e6622e46c94` |
| Referencia | MobileNetV3 Small con extractor congelado | `experiments/mobilenet_10ep_20260920-181113/mobilenet.pt` | 9 | 0.6327072392 | `9248cc767425c9efec643bcc2cabd758e8f2b28ab4a6967908713fc1d0b9c5c1` |
| Referencia | ResNet18 con extractor preentrenado congelado | `experiments/resnet18_10ep_20260921-130620/resnet18.pt` | 8 | 0.5947396341 | `5dcea4bb3a6c5a529e09998bbad081b6ebaf58ca9881b3d25747c5eb041a8567` |
| Referencia | CNN pequeña desde cero | `experiments/cnn_10ep_20260921-125200/cnn.pt` | 7 | 0.4385713520 | `26cdd076e7e6bf1022e761f6fb8e4fcdade0ca24900a4cf91b0ec79bf5cc9553` |

La época 6 del candidato se identifica mediante `selected_candidate_epoch` en el checkpoint y el historial del experimento. El campo `epochs=10` registra las épocas ejecutadas antes de la parada temprana, no la época seleccionada.

## Compatibilidad verificada antes de TEST

Los cuatro archivos se cargaron con `torch.load(..., map_location="cpu", weights_only=True)` mediante `src/common.py`, aceptaron estrictamente sus `state_dict` y completaron una inferencia sintética de forma `1×3×224×224` con salida `1×3`.

Todos declaran:

- `manifest_sha256`: `1ea21d6b2b480b830065c5d4d1d90f531234cc2aa244d7bb98c5873363866dab`;
- semilla `42`;
- tres salidas en este orden exacto:
  1. `coffee___healthy` — Hoja sana;
  2. `coffee___red_spider_mite` — Ácaro rojo;
  3. `coffee___rust` — Roya.

La arquitectura declarada en cada checkpoint coincide con la reconstruida por `src/common.py`: `mobilenet`, `resnet18` o `cnn`. El evaluador recibirá siempre la ruta explícita del checkpoint; no cargará implícitamente `models/mobilenet.pt` ni escribirá en `models/`.

## Preprocesamiento fijado

Se reutilizará `Leaves(..., training=False)` y exactamente `transform(False)` de `src/common.py`:

1. corrección de orientación con `ImageOps.exif_transpose`;
2. conversión a RGB;
3. `Resize((224, 224))`;
4. `ToTensor()`;
5. normalización ImageNet con media `[0.485, 0.456, 0.406]` y desviación `[0.229, 0.224, 0.225]`.

No se aplicará aumento de datos en TEST. El orden del cargador será determinista (`shuffle=False`) y los cuatro modelos recibirán las mismas filas, en el mismo orden.

## Métricas fijadas

Para cada checkpoint se guardarán:

- F1 macro;
- accuracy;
- precision, recall, F1 y soporte por clase;
- matriz de confusión, con filas de clase real y columnas de clase predicha;
- número total de errores;
- una fila por imagen con clase real, clase predicha, acierto y las tres puntuaciones softmax;
- listado completo de errores.

La comparación final presentará validación frente a TEST. El criterio que cerró la selección fue exclusivamente el F1 macro de validación; accuracy será una métrica descriptiva.

## Análisis fijado del umbral para el candidato principal

El umbral provisional permanece en **0.70**. Para cada predicción del MobileNet ajustado se define `puntuación máxima` como el mayor valor de su salida softmax.

Se reportarán:

- cantidad con puntuación máxima `< 0.70`;
- cantidad y proporción con puntuación máxima `>= 0.70`;
- cantidad correcta y accuracy dentro de ese subconjunto aceptado.

Las puntuaciones softmax no se presentarán como probabilidades calibradas de acierto. El umbral no es un detector de fotografías ajenas al café, no garantiza seguridad agronómica y no se modificará a partir de TEST.

## Evidencias previstas

Dentro de `experiments/final_test_20260922/` se crearán, sin sobrescribir resultados existentes:

- `protocol_snapshot.json` con manifiesto, hashes, clases, preprocesamiento y umbral;
- un subdirectorio por checkpoint con métricas, matriz, predicciones y errores;
- `validation_vs_test.csv` y `model_comparison.csv`;
- `compatibility.json` con las comprobaciones de carga;
- `reports/FINAL_TEST_RESULTS.md` como informe final interpretativo.

## Integridad del modelo web

`models/mobilenet.pt` seguirá siendo el checkpoint activo de la web. Su SHA-256 antes de la evaluación es `9248cc767425c9efec643bcc2cabd758e8f2b28ab4a6967908713fc1d0b9c5c1`. La evaluación del candidato ajustado usará su ruta archivada y no reemplazará ni sobrescribirá el modelo activo.
