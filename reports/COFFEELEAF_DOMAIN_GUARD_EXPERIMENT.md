# Auditoría CoffeeLeaf-CO y candidato del filtro de dominio

**Fecha de ejecución:** 2026-10-19

**Estado:** rama CoffeeLeaf-CO ejecutada; protocolo externo incompleto; candidato archivado y **no integrado**

**Entrenamiento del clasificador:** ninguno

**Uso de TEST de RoCoLe:** ninguno

## 1. Pregunta y cambio controlado

El filtro activo puede rechazar hojas de café fotografiadas fuera del aspecto de RoCoLe. Se comprobó si ampliar solamente sus referencias positivas con fotografías de campo auditadas de CoffeeLeaf-CO mejora esa cobertura.

Se mantuvieron sin cambios:

- MobileNetV3 Small `models/mobilenet_finetuned_epoch6.pt`, SHA256 `4ab4e52fc3d417fe5fb126ff1e5b346f080c55ffa80232cffd5d6e6622e46c94`;
- `src.common.transform(training=False)`: orientación EXIF, RGB, `Resize((224, 224))`, `ToTensor` y normalización ImageNet;
- similitud coseno media de los cinco vecinos más cercanos;
- umbral del filtro `0.6497240662574768`;
- 880 referencias de TRAIN de RoCoLe del control;
- 153 imágenes de la mitad de evaluación de VAL de RoCoLe y los mismos 200 negativos de desarrollo.

El único cambio del candidato fue agregar 1.197 referencias de la captura propia de CoffeeLeaf-CO ubicadas en la carpeta `train` final. El candidato contiene 2.077 referencias. No se ajustó el umbral, no se entrenó el clasificador y no se convirtieron cajas de detección en etiquetas de hoja completa.

## 2. Fuente y verificación de integridad

La fuente primaria fue [DECAFIA / CoffeeLeaf-CO v2.0.0 en Zenodo](https://zenodo.org/records/22756170), DOI `10.5281/zenodo.22756170`, publicada bajo CC BY 4.0. El repositorio de sus autores es [estebanr25/decafia-research](https://github.com/estebanr25/decafia-research).

| Elemento | Valor verificado |
|---|---|
| Archivo | `CoffeeLeaf-CO-v2.zip` |
| Tamaño | 167.503.504 bytes |
| MD5 publicado y obtenido | `2ba46bd8f7a23708d982ff578760f1fa` |
| SHA256 local fijado | `8d0652baeab1f1731c5ecc5dfe99387125aa84f76df92fe2175cd80f7d0225a5` |
| Imágenes finales legibles | 2.315 JPEG |
| Captura propia / campo | 1.705 |
| Fuente Silva et al. | 610 |
| Duplicados exactos internos | 0 |
| Coincidencias SHA256 con RoCoLe TRAIN/VAL | 0 |
| Coincidencias con hashes registrados de RoCoLe TEST | 0; no se abrieron sus imágenes |

La ausencia de coincidencias SHA256 no descarta copias recortadas, redimensionadas o recomprimidas. El análisis perceptual de casi duplicados exigido por el protocolo sigue pendiente.

### Inconsistencias documentales encontradas

El contenido real no coincide por completo con su manifiesto publicado:

- `provenance_manifest.csv` contiene 2.769 filas, mientras el ZIP final contiene 2.315 imágenes;
- 454 filas residuales corresponden a RoCoLe, cuyas imágenes fueron excluidas de la versión 2;
- la columna `split` difiere de la carpeta final en 1.097 imágenes; para este experimento se usó la ubicación real de cada archivo;
- el manifiesto conserva el identificador anterior `3` para minador, mientras las etiquetas finales usan `2`;
- `MINEIRO_111` conserva en el manifiesto un conteo anterior, pero `CORRECTIONS.md` documenta la eliminación de una caja espuria; la auditoría comprobó la etiqueta final corregida.

Las anotaciones son de **detección por cajas** para roya, coco/vaquita y minador; no son etiquetas exclusivas de clasificación de la hoja completa. CoffeeLeaf-CO no contiene la categoría ácaro rojo y no publica identificadores suficientes de planta o sesión. Por ello sus imágenes se usaron aquí únicamente como referencias positivas del dominio café, no para mejorar ni evaluar las tres clases.

## 3. Separación usada

De las 1.705 capturas propias:

| Papel en este experimento | Carpeta final de los autores | Imágenes |
|---|---|---:|
| Referencias del candidato | `train` | 1.197 |
| Comprobación positiva reservada | `val` | 255 |
| Comprobación positiva reservada | `test` de CoffeeLeaf-CO | 253 |

El banco candidato se construyó antes de abrir las 508 imágenes reservadas; el archivo y su hash se escribieron después dentro de la misma ejecución, por lo que no fue un precompromiso criptográfico. La tercera fila llamada `test` es la partición proporcionada por los autores de CoffeeLeaf-CO; **no es TEST de RoCoLe**. Se informa como comprobación interna reservada por imagen de la misma fuente, no como evaluación externa independiente, porque faltan identificadores de planta/sesión.

## 4. Resultados

### 4.1. Hojas de RoCoLe VAL

| Conjunto positivo | Control activo | Candidato | Diferencia absoluta |
|---|---:|---:|---:|
| Total VAL evaluado | 141/153 (92,16 %) | 142/153 (92,81 %) | +0,65 pp |
| Sana | 72/75 (96,00 %) | 72/75 (96,00 %) | 0,00 pp |
| Ácaro rojo | 12/13 (92,31 %) | 12/13 (92,31 %) | 0,00 pp |
| Roya | 57/65 (87,69 %) | 58/65 (89,23 %) | +1,54 pp |

El único ejemplo adicional aceptado fue `C1P13E2.jpg`, anotado como roya; su score pasó de `0.631591499` a `0.672714114`. Estas cifras miden aceptación por el filtro, no acierto de la categoría sana/roya/ácaro.

### 4.2. Negativos fijados de desarrollo

| Resultado sobre 200 negativos | Control activo | Candidato |
|---|---:|---:|
| Aceptados incorrectamente | 0/200 | 0/200 |
| Rechazados | 200/200 | 200/200 |
| Score mediano | 0,314179 | 0,469129 |
| Score máximo observado | 0,499923 | 0,607623 |
| Margen hasta el umbral | 0,149801 | 0,042101 |

El candidato mantuvo el rechazo de estos 200 ejemplos concretos, pero elevó el score de 199/200 y acercó varios negativos al umbral. El score máximo candidato correspondió a una hoja sana de papa de PlantVillage. Este estrechamiento del margen impide inferir que la seguridad se conserva para objetos o plantas no representados en el benchmark.

### 4.3. Capturas propias de CoffeeLeaf-CO reservadas

| Partición positiva de los autores | Control activo | Candidato | Diferencia absoluta |
|---|---:|---:|---:|
| `val` (255) | 109/255 (42,75 %) | 227/255 (89,02 %) | +46,27 pp |
| `test` CoffeeLeaf-CO (253) | 108/253 (42,69 %) | 233/253 (92,09 %) | +49,41 pp |
| Total reservado (508) | 217/508 (42,72 %) | 460/508 (90,55 %) | +47,83 pp |

El candidato redujo de 291 a 48 los rechazos sobre estas 508 fotografías. Es una mejora clara de cobertura dentro de CoffeeLeaf-CO, pero no mide exactitud de clasificación ni demuestra generalización a cualquier fotografía de Internet.

Como comprobación interna, el candidato aceptó 1.180/1.197 (98,58 %) de sus propias referencias frente a 533/1.197 (44,53 %) del control. Este resultado no se trata como evaluación porque esas imágenes forman parte del artefacto candidato.

## 5. Decisión

El artefacto se conserva como **candidato no integrado**:

- ruta local ignorada por Git: `experiments/domain_guard_external_coffeeleaf_20261019-001/candidate_final/candidate_guard_not_integrated.pt`;
- tamaño: 8.510.858 bytes, 2,36 veces el artefacto activo;
- SHA256: `93879c4f97ff829e2303d6f4879a6c3771c65255a663417d871cc9362d332952`.

No sustituye `models/coffee_domain_guard.pt` porque el protocolo previo exige una comprobación externa congelada con BRACOL y esta no se ejecutó. También faltan el análisis perceptual de casi duplicados y las mediciones de memoria, arranque y latencia; además, el margen observado frente a los negativos disminuyó. Activarlo ahora seleccionaría el sistema con evidencia incompleta.

El clasificador web y el filtro activo permanecen intactos. Para evitar que una hoja externa rechazada quede en un callejón sin salida, la interfaz incorpora por separado una acción explícita **Analizar de todos modos**; esa salida conserva el estado fuera de dominio y presenta sus puntuaciones como comparación limitada. No constituye una mejora del modelo.

## 6. Evidencia reproducible

- Auditoría: `src/prepare_coffeeleaf_guard_audit.py`.
- Comparación control/candidato: `src/experiment_external_domain_guard.py`.
- Resumen de auditoría local: `experiments/domain_guard_external_coffeeleaf_20261019-001/audit/audit_summary.json`.
- Configuración, scores por imagen y resultados locales: `experiments/domain_guard_external_coffeeleaf_20261019-001/candidate_final/`.
- Protocolo previo: `reports/DOMAIN_GENERALIZATION_V2_PROTOCOL.md`.
- Manejo de rechazos en la interfaz: `reports/DOMAIN_GUARD_LIMITED_OVERRIDE.md`.

La ejecución duró 43,22 segundos en CPU con lote 32. Los ZIP, las imágenes de CoffeeLeaf-CO, los embeddings y el candidato permanecen separados y excluidos de Git. El repositorio conserva solo los scripts, el protocolo, este informe y las atribuciones necesarias para reproducir la decisión.

## 7. Limitación principal

Este experimento mejora la evidencia sobre **aceptación de fotografías de hojas de café dentro de CoffeeLeaf-CO**. No aporta ejemplos de ácaro rojo, no mejora demostrablemente su clasificación y no permite prometer identificación universal. Para comprobar esa clase fuera de RoCoLe siguen haciendo falta fotografías originales etiquetadas por una fuente competente, separadas por planta/sesión y reservadas antes de cualquier ajuste.
