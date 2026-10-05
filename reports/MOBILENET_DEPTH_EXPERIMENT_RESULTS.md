# Resultados: profundidad del ajuste fino de MobileNet

**Experimento:** `experiments/mobilenet_depth_20260930-155127/`

**Protocolo preregistrado:** [`MOBILENET_DEPTH_EXPERIMENT_PROTOCOL.md`](MOBILENET_DEPTH_EXPERIMENT_PROTOCOL.md)

**Datos usados:** TRAIN y VAL de RoCoLe limpio; TEST no se abrió ni evaluó.

**Conclusión:** el candidato cumple los tres criterios operativos exploratorios, pero no reemplaza el modelo web.

## Intervención ejecutada

Las seis corridas partieron del mismo checkpoint `candidate_initial_epoch0.pt`, SHA-256 `9248cc767425c9efec643bcc2cabd758e8f2b28ab4a6967908713fc1d0b9c5c1`, con F1 macro inicial de VAL `0.6327072392`.

| Rama | Módulos `features` entrenables | Clasificador | Parámetros entrenables |
|---|---|---|---:|
| Control | 10, 11, 12 | `classifier.3` | 647.715 |
| Candidato | 7, 8, 9, 10, 11, 12 | `classifier.3` | 791.331 |

Se conservaron arquitectura, preprocesamiento directo a 224 × 224, aumentos, particiones, pesos de clase, Adam, tasa `1e-5` para el extractor, tasa `1e-4` para la última capa y estadísticas BatchNorm congeladas. La única intervención fue añadir `features.7–9` al conjunto entrenable.

## F1 macro por semilla

| Semilla | Control | Candidato | Candidato − control | Época control | Época candidato |
|---:|---:|---:|---:|---:|---:|
| 42 | 0.647844 | 0.664024 | +0.016180 | 6 | 7 |
| 43 | 0.661584 | 0.674492 | +0.012907 | 10 | 10 |
| 44 | 0.660879 | 0.665216 | +0.004337 | 15 | 3 |
| **Media ± DE muestral** | **0.656769 ± 0.007737** | **0.667911 ± 0.005731** | **+0.011142 ± 0.006116** | — | — |

El candidato obtuvo mayor F1 macro en las tres parejas. La ganancia no fue uniforme: la semilla 44 solo mejoró `0.004337`. Tres semillas no permiten afirmar que una diferencia pequeña sea estable en nuevas muestras.

## Precision, recall y F1 por clase

La notación `media ± DE` usa desviación estándar muestral entre las tres semillas.

### Hoja sana

| Rama | Semilla | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| Control | 42 | 0.848101 | 0.858974 | 0.853503 |
| Control | 43 | 0.837500 | 0.858974 | 0.848101 |
| Control | 44 | 0.843750 | 0.865385 | 0.854430 |
| **Control** | **media ± DE** | **0.843117 ± 0.005329** | **0.861111 ± 0.003701** | **0.852012 ± 0.003418** |
| Candidato | 42 | 0.850000 | 0.871795 | 0.860759 |
| Candidato | 43 | 0.852564 | 0.852564 | 0.852564 |
| Candidato | 44 | 0.833333 | 0.865385 | 0.849057 |
| **Candidato** | **media ± DE** | **0.845299 ± 0.010442** | **0.863248 ± 0.009792** | **0.854127 ± 0.006006** |
| **Diferencia de medias** |  | **+0.002182** | **+0.002137** | **+0.002115** |

### Daño por ácaro rojo

| Rama | Semilla | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| Control | 42 | 0.357143 | 0.483871 | 0.410959 |
| Control | 43 | 0.411765 | 0.451613 | 0.430769 |
| Control | 44 | 0.361702 | 0.548387 | 0.435897 |
| **Control** | **media ± DE** | **0.376870 ± 0.030306** | **0.494624 ± 0.049275** | **0.425875 ± 0.013170** |
| Candidato | 42 | 0.350877 | 0.645161 | 0.454545 |
| Candidato | 43 | 0.451613 | 0.451613 | 0.451613 |
| Candidato | 44 | 0.424242 | 0.451613 | 0.437500 |
| **Candidato** | **media ± DE** | **0.408911 ± 0.052089** | **0.516129 ± 0.111745** | **0.447886 ± 0.009113** |
| **Diferencia de medias** |  | **+0.032041** | **+0.021505** | **+0.022011** |

El promedio mejora, pero el recall de ácaro es inestable: sube `+0.161290` con semilla 42, no cambia con 43 y baja `−0.096774` con 44. Su desviación estándar pasa de `0.049275` a `0.111745`. Por tanto, este experimento no demuestra una mejora consistente de ácaro rojo aunque mejore su media.

### Roya

| Rama | Semilla | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| Control | 42 | 0.722772 | 0.640351 | 0.679070 |
| Control | 43 | 0.728972 | 0.684211 | 0.705882 |
| Control | 44 | 0.765957 | 0.631579 | 0.692308 |
| **Control** | **media ± DE** | **0.739234 ± 0.023350** | **0.652047 ± 0.028198** | **0.692420 ± 0.013407** |
| Candidato | 42 | 0.797619 | 0.587719 | 0.676768 |
| Candidato | 43 | 0.719298 | 0.719298 | 0.719298 |
| Candidato | 44 | 0.735849 | 0.684211 | 0.709091 |
| **Candidato** | **media ± DE** | **0.750922 ± 0.041279** | **0.663743 ± 0.068136** | **0.701719 ± 0.022203** |
| **Diferencia de medias** |  | **+0.011688** | **+0.011696** | **+0.009299** |

Roya también mejora en promedio, pero no en todas las semillas: con semilla 42 su recall baja de `0.640351` a `0.587719`. La dispersión del recall aumenta.

## Matrices de confusión

Cada celda usa el orden de predicción `sana / ácaro rojo / roya`; las filas son la clase real.

| Rama | Semilla | Sana real | Ácaro real | Roya real |
|---|---:|---|---|---|
| Control | 42 | 134 / 8 / 14 | 2 / 15 / 14 | 22 / 19 / 73 |
| Candidato | 42 | 136 / 11 / 9 | 3 / 20 / 8 | 21 / 26 / 67 |
| Control | 43 | 134 / 6 / 16 | 4 / 14 / 13 | 22 / 14 / 78 |
| Candidato | 43 | 133 / 6 / 17 | 2 / 14 / 15 | 21 / 11 / 82 |
| Control | 44 | 135 / 10 / 11 | 3 / 17 / 11 | 22 / 20 / 72 |
| Candidato | 44 | 135 / 6 / 15 | 4 / 14 / 13 | 23 / 13 / 78 |

Los errores totales control/candidato fueron 79/78, 75/72 y 77/74 para semillas 42, 43 y 44. Esto es descriptivo; la selección no se hizo por accuracy ni por cantidad total de errores.

## Criterios preregistrados

| Criterio | Resultado | Cumple |
|---|---:|---|
| Ganancia media de F1 macro ≥ 0.010 | +0.011142 | sí |
| Delta positivo en al menos 2/3 semillas | 3/3 | sí |
| Ningún recall medio baja más de 0.020 | sana +0.002137; ácaro +0.021505; roya +0.011696 | sí |

El candidato cumple el criterio operativo fijado antes de entrenar. Esto justifica **conservarlo como candidato exploratorio**, no declararlo superior de forma general ni activarlo en la web.

## Controles técnicos y conservación

En las seis corridas se verificó:

- todos los parámetros entrenables estaban en el optimizador y ningún parámetro congelado estaba incluido;
- todos los parámetros entrenables recibieron gradiente y las convoluciones descongeladas tuvieron gradiente no nulo;
- las estadísticas de los 34 módulos BatchNorm permanecieron exactamente iguales;
- el orden de clases fue sana, ácaro rojo y roya;
- el checkpoint inicial y el manifiesto reprodujeron sus hashes esperados;
- no se abrieron imágenes de TEST ni se usaron sus etiquetas, predicciones o métricas.

Los hashes antes y después fueron idénticos:

| Archivo activo | SHA-256 |
|---|---|
| `models/mobilenet.pt` | `9248cc767425c9efec643bcc2cabd758e8f2b28ab4a6967908713fc1d0b9c5c1` |
| `models/mobilenet_finetuned_epoch6.pt` | `4ab4e52fc3d417fe5fb126ff1e5b346f080c55ffa80232cffd5d6e6622e46c94` |
| `data/processed/manifest.csv` | `1ea21d6b2b480b830065c5d4d1d90f531234cc2aa244d7bb98c5873363866dab` |

El modelo web, el umbral 0.70, el manifiesto y las particiones no cambiaron.

## Coste y anomalía de duración

El candidato entrena 143.616 parámetros adicionales, un 22,17 % más que el control, pero conserva exactamente la misma arquitectura de inferencia. Por ello no cambia el número total de parámetros ni el coste estructural de inferencia; solo aumenta el coste de entrenamiento y el checkpoint conserva el mismo orden de magnitud.

Duraciones válidas registradas: control 42 `395,9 s`, control 43 `557,5 s`; candidato 42 `465,5 s`, candidato 43 `584,8 s`, candidato 44 `344,9 s`. La duración bruta de control 44 (`323.070,3 s`) **no es una medición de entrenamiento válida**: la sesión quedó suspendida externamente varios días entre épocas 7 y 8 y `time.perf_counter` incluyó ese intervalo inactivo. Se conserva el valor original por trazabilidad, pero no debe usarse el promedio de duración del control contenido en `comparison.json`. La anomalía no afectó historial, pesos, predicciones o métricas y quedó registrada en `duration_measurement_note.json`.

## Recomendación

Conservar los seis checkpoints y considerar la rama profunda como candidata exploratoria para una futura comprobación independiente. No sustituir todavía el modelo activo porque:

1. VAL ya ha sido usado repetidamente para decisiones;
2. solo se probaron tres semillas;
3. la mejora media de F1 macro es pequeña (`+0.0111`);
4. los recalls de ácaro y roya presentan mayor dispersión y retrocesos en semillas concretas;
5. TEST histórico no debe reutilizarse para decidir sobre esta nueva variante.

La siguiente evidencia útil no es otra búsqueda de hiperparámetros sobre VAL, sino datos nuevos con plantas y sesiones independientes y etiquetas revisadas, especialmente para ácaro rojo. Este experimento no autoriza un nuevo entrenamiento automático ni un cambio del modelo web.

## Evidencias

- `experiments/mobilenet_depth_20260930-155127/preflight.json`
- `experiments/mobilenet_depth_20260930-155127/runs.csv`
- `experiments/mobilenet_depth_20260930-155127/paired_macro_f1.csv`
- `experiments/mobilenet_depth_20260930-155127/comparison.json`
- `experiments/mobilenet_depth_20260930-155127/duration_measurement_note.json`
- por rama y semilla: `configuration.json`, `history.json`, `best_checkpoint.pt`, `validation_metrics.json`, `validation_confusion_matrix.csv`, `validation_predictions.csv`, `optimizer_check.json`, `gradient_check.json`, `batch_norm_check.json` y `summary.json`.
