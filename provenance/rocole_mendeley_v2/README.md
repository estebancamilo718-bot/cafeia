# RoCoLe original — registro de procedencia

Este directorio conserva una copia separada de la versión original usada para la auditoría documental. No forma parte de `data/`, no reemplaza la copia de Kaggle y no modifica el manifiesto ni los checkpoints.

## Atribución

- **Título:** *RoCoLe: A robusta coffee leaf images dataset*
- **Autores/contribuyentes:** Jorge Parraga-Alava, Kevin Cusme, Angélica Loor y Esneider Santander
- **Repositorio:** [Mendeley Data, versión 2](https://data.mendeley.com/datasets/c5yvn32dzg/2)
- **DOI:** [10.17632/c5yvn32dzg.2](https://doi.org/10.17632/c5yvn32dzg.2)
- **Fecha de publicación:** 2019-05-17
- **Licencia declarada por el repositorio:** [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/)
- **Artículo relacionado:** [Parraga-Alava et al., *Data in Brief* 25 (2019), 104414](https://doi.org/10.1016/j.dib.2019.104414)

## Descarga conservada

- **Fecha de descarga:** 2026-09-22, zona `America/Bogota`
- **Página:** `https://data.mendeley.com/datasets/c5yvn32dzg/2`
- **Endpoint oficial “Download All”:** `https://data.mendeley.com/public-api/zip/c5yvn32dzg/download/2`
- **Nombre entregado por el endpoint:** `c5yvn32dzg-2.zip`
- **Nombre local descriptivo:** `rocole_mendeley_c5yvn32dzg_v2.zip`
- **Tamaño:** 2,245,588,288 bytes
- **SHA-256 local:** `31daa765fb0cc27d4b9b897fa6350aacf0087ee5771d3c7599d2ac7041b866ff`

El ZIP se conserva intacto. Contiene 1560 JPG y cinco archivos de anotación:

| Archivo dentro de `Annotations/` | Tamaño (bytes) |
|---|---:|
| `RoCoLe-classes.xlsx` | 39,437 |
| `RoCoLE-coco.json` | 1,813,080 |
| `RoCoLE-csv.csv` | 2,220,101 |
| `RoCoLE-json.json` | 2,488,394 |
| `RoCoLe-voc.tar.gz` | 697,591,506 |

Para la comparación se extrajeron, sin sobrescritura, los cuatro archivos de anotación que no son el paquete VOC. El original completo, incluido `RoCoLe-voc.tar.gz`, permanece dentro del ZIP.

| Archivo extraído | SHA-256 |
|---|---|
| `annotations/RoCoLe-classes.xlsx` | `0040a57ffd441bd69ead997309d14c8d7f6fdfc83c5dbdc47805e0bc4da05ef2` |
| `annotations/RoCoLE-coco.json` | `beac06144c2865cd0ceb2ef3f81791334cf1674400184ff1aa123d1e67f7ec4f` |
| `annotations/RoCoLE-csv.csv` | `a9aa6b411569dba7e9ba56fed79e5cd82af04a0ef092e56309158d632ac5205b` |
| `annotations/RoCoLE-json.json` | `286b73725b7c027a6bc9a1118a281b026e1ec9e35c3510398ed6bbc0e579cf99` |

## Política aplicada a TEST

La auditoría solo abrió imágenes enumeradas como `train` o `val` en el manifiesto y las 24 imágenes excluidas antes de particionar. No abrió imágenes de `test`, no decodificó ni comparó sus anotaciones y no calculó predicciones o métricas. El CSV original fue recorrido secuencialmente, pero las etiquetas se decodificaron y conservaron únicamente cuando el nombre estaba en la lista autorizada.

## Evidencias derivadas

- `evidence/annotation_audit_summary.json`: recuentos y comprobaciones agregadas.
- `evidence/train_val_annotation_comparison.csv`: cruce por archivo de TRAIN/VAL.
- `evidence/excluded_conflicts_original_comparison.csv`: cruce de los 24 excluidos.
- `evidence/excluded_conflict_pair_diagnostics.csv`: diagnóstico de los 12 pares.

El procedimiento reproducible está en `src/audit_rocole_annotations.py`.
