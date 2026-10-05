# Auditoría del depósito Xinzhai para CaféIA

**Fecha de cierre:** 2026-09-30

**Objeto:** auditar el archivo asociado con CDMS-YOLO como posible fuente de datos para mejorar la clase `coffee___red_spider_mite`.

**Decisión:** no incorporar ni entrenar con este material en su estado actual.

## Conclusión ejecutiva

El depósito y la publicación existen y son accesibles. El registro [Xinzhai Coffee Plantation Dataset](https://doi.org/10.5281/zenodo.21442135) declara acceso abierto y licencia CC BY 4.0; el artículo relacionado es [CDMS-YOLO](https://doi.org/10.3390/app16189199). El ZIP descargado coincide exactamente con el tamaño y MD5 publicados.

Sin embargo, el contenido real del ZIP **no aporta imágenes anotadas como ácaro rojo**. Contiene 1.020 fotografías y anotaciones YOLO de detección para cinco clases: `brown spot`, `Leaf rust`, `anthracnose`, `Affected by leaf miner` y `healthy`. Por ello no sirve para el objetivo prioritario de ampliar ácaro rojo.

Tampoco puede incorporarse directamente al clasificador de imagen completa. Hay varias hojas por fotografía, 167 imágenes contienen cajas de más de una clase y las cajas señalan regiones u hojas, no una etiqueta única y exclusiva de toda la imagen. Además, faltan identificadores de planta/hoja y existen discrepancias entre el archivo y la descripción del artículo que requieren aclaración de los autores.

## Descarga e integridad

La descarga que estaba segmentada se reanudó reutilizando los segmentos válidos; no se inició una segunda descarga completa. El material se conservó fuera del proyecto en:

`%LOCALAPPDATA%\Temp\cafeia-external-data\xinzhai-zenodo-21442135\`

No se ejecutó código de la descarga. El registro de Zenodo se conservó como `zenodo_record_21442135.json` y el contenido se extrajo después de comprobar las rutas del ZIP.

| Comprobación | Publicado | Archivo local | Resultado |
|---|---:|---:|---|
| Nombre | `data.zip` | `data.zip` | coincide |
| Tamaño | 5.166.455.708 bytes | 5.166.455.708 bytes | coincide |
| MD5 | `31403d6afd8c6c8e762159117a322912` | `31403d6afd8c6c8e762159117a322912` | coincide |
| Licencia del registro | CC BY 4.0 | metadatos conservados | verificada en Zenodo |

El ZIP no incluye un archivo de licencia o README separado. La atribución y la licencia deben conservarse desde el registro de Zenodo: creador `Zhang, Xiaolong`, título `Xinzhai Coffee Plantation Dataset, Baoshan, Yunnan, China`, DOI `10.5281/zenodo.21442135`, publicación 2026-07-19.

## Contenido real del ZIP

Se encontraron 1.020 JPG utilizables, 1.020 archivos de anotación, `classes.txt` y un archivo auxiliar vacío `IMG_20260105_112940.jpg.~#0`, que no se contó como imagen. Las 1.020 imágenes se abrieron correctamente, son RGB y tienen resolución nativa alta:

| Resolución | Imágenes |
|---|---:|
| 3072 × 4096 | 777 |
| 3072 × 4080 | 145 |
| 4096 × 3072 | 89 |
| 4080 × 3072 | 9 |

Las clases se leyeron literalmente de `data/labels/classes.txt`:

| ID | Clase del depósito | Imágenes con al menos una caja | Cajas |
|---:|---|---:|---:|
| 0 | brown spot | 274 | 726 |
| 1 | Leaf rust | 107 | 341 |
| 2 | anthracnose | 759 | 1.403 |
| 3 | Affected by leaf miner | 59 | 60 |
| 4 | healthy | 7 | 8 |

Las incidencias por clase no suman 1.020 porque una fotografía puede contener varias clases. En total hay 2.538 cajas, 853 imágenes con una sola clase anotada y 167 con dos o más clases. Los subconjuntos de una sola clase incluyen 610 imágenes de antracnosis, 145 de mancha marrón, 48 de minador, 44 de roya y solo 6 sanas.

**Hecho confirmado:** no existe una clase `red spider mite` ni equivalente en `classes.txt` o en las anotaciones. Los 433 ejemplos de ácaro que el artículo informa para su conjunto combinado de 3.021 imágenes no están presentes en este ZIP.

## Tipo de anotación y revisión visual

Las anotaciones son archivos YOLO, una fila por caja con `class_id x_center y_center width height` normalizados. Son anotaciones de **detección**, no etiquetas de clasificación de la fotografía completa. El artículo explica que se delimitaron regiones afectadas y que lesiones separadas podían marcarse individualmente.

Se inspeccionó de forma reproducible el primer nombre ordenado de cada conjunto de clase única y el primer caso multiclase:

| Archivo | Anotación presente | Observación de composición, sin reinterpretar la etiqueta |
|---|---|---|
| `IMG_20260105_091927.jpg` | brown spot | escena con muchas hojas, ramas y frutos; dos cajas |
| `IMG_20260105_093005.jpg` | Leaf rust | una hoja principal y otras hojas al fondo; una caja amplia |
| `IMG_20260105_091405.jpg` | anthracnose | varias hojas y cinco cajas en regiones distintas |
| `IMG_20260105_094459.jpg` | Affected by leaf miner | una hoja afectada ocupa gran parte de una escena con otras hojas; una caja |
| `IMG_20260105_092716.jpg` | healthy | una hoja principal con otras hojas alrededor; una caja sobre la hoja |
| `IMG_20260105_091726.jpg` | brown spot + anthracnose | varias hojas; cinco cajas de dos clases |

Estas observaciones comprueban la diferencia entre la unidad anotada y la imagen completa. No se validó ni corrigió ninguna clase por apariencia. En particular, una caja de lesión no autoriza a convertir toda la fotografía en una clase única, y una fotografía sin una caja de las clases de CaféIA no debe convertirse en `sana`.

## Procedencia y separación frente a BarakoBama

### Hechos confirmados en el archivo

- Los 1.020 nombres admiten una fecha y hora: 2026-01-05 entre 09:14:05 y 11:33:09.
- El campo EXIF `DateTime` coincide con ese día; `DateTimeOriginal` y `DateTimeDigitized` están ausentes, así que no se puede tratar como prueba absoluta de la fecha de captura.
- 516 imágenes declaran `OPPO Find X6 Pro` y 504 declaran `iQOO 15`.
- Todas son fotografías nativas de alta resolución con nombres de cámara; el ZIP no contiene las 2.000 imágenes de BarakoBama redimensionadas a 640 × 640 que el artículo usó para formar el conjunto final de 3.021.
- El ZIP solo contiene las cinco clases anteriores, mientras el conjunto combinado descrito por el artículo tiene ocho.

### Inferencia limitada

Por estructura, resolución, nombres y metadatos, el ZIP parece corresponder a un lote de capturas propias separado de BarakoBama. Esto **no demuestra** que cada fotografía sea original ni identifica la planta de origen. La separación por fuente sí es viable a nivel de depósito: no hay que extraer BarakoBama de este ZIP porque ese material no aparece en él.

### Discrepancias que requieren aclaración

| Artículo | Archivo auditado |
|---|---|
| 1.021 capturas propias | 1.020 JPG utilizables |
| capturas a comienzos de febrero de 2026 | nombres y EXIF `DateTime` indican 5 de enero de 2026 |
| dispositivo iQOO 15 | 504 iQOO 15 y 516 OPPO Find X6 Pro |
| conjunto final de ocho clases con ácaro rojo | ZIP de cinco clases sin ácaro rojo |

No se encontró manifiesto que explique la imagen faltante, los dos dispositivos, la fecha, el número de plantas, la cara de la hoja, la identidad de cada hoja o las sesiones biológicas. Los timestamps son identificadores de archivo, no identificadores de planta.

## Duplicados y posible solapamiento con RoCoLe

Se calculó SHA-256 para Xinzhai y pHash de 64 bits para Xinzhai y RoCoLe TRAIN/VAL. Para TEST se usaron exclusivamente los 300 SHA-256 ya registrados en el manifiesto: no se abrieron imágenes, ni se consultaron etiquetas, predicciones o métricas.

| Comprobación | Resultado |
|---|---:|
| Pares SHA-256 idénticos dentro de Xinzhai | 0 |
| Candidatos internos con distancia pHash ≤ 4 | 0 |
| SHA-256 idénticos con RoCoLe TRAIN/VAL | 0 |
| Candidatos pHash ≤ 4 con RoCoLe TRAIN/VAL | 0 |
| Menor distancia pHash frente a TRAIN/VAL | 14 |
| SHA-256 idénticos con hashes registrados de TEST | 0 |

La ausencia de coincidencias SHA-256 solo descarta archivos binariamente idénticos; no descarta copias recodificadas, redimensionadas o recortadas. El pHash amplía la revisión de TRAIN/VAL, pero sigue siendo un filtro y no una prueba de independencia biológica. Por la reserva de TEST no se calculó pHash de sus imágenes.

## Utilidad para CaféIA

### Material que podría servir después de revisión

- Las 107 imágenes con cajas de roya, especialmente las 44 que solo tienen esa clase anotada, podrían formar un lote candidato para revisión experta de **clasificación de imagen**, pero no deben incorporarse automáticamente.
- Las fotografías pueden aportar diversidad de escenas de café para una futura tarea de detección o para desarrollar un filtro de presencia/usabilidad, siempre que los autores confirmen especie, procedencia y unidades de agrupación.
- Los archivos y cajas son reproducibles y tienen una licencia abierta documentada en el registro.

### Material que requiere aclaración o revisión

- cualquier imagen multiclase;
- las seis imágenes `healthy` de clase única, por ser muy pocas y porque la caja no equivale necesariamente a una etiqueta global;
- identificación de planta, hoja y sesión para evitar fugas;
- especie/cultivar y confirmación de que todo el lote procede de plantas de café;
- discrepancias de fecha, dispositivo, conteo y categorías entre artículo y depósito;
- revisión agronómica antes de convertir detección regional en clasificación de hoja.

### Material que no sirve para el objetivo inmediato

- **Ácaro rojo:** no hay imágenes con esa anotación en el depósito, por lo que no mejora la clase prioritaria.
- Las clases `brown spot`, `anthracnose` y `Affected by leaf miner` no corresponden a ninguna de las tres salidas de CaféIA y no pueden recodificarse como `sana`.
- Las escenas con varias hojas o varias clases no sirven como ejemplos directos de una sola hoja con una etiqueta exclusiva.

**Decisión concreta:** descartar este ZIP como fuente prioritaria para mejorar ácaro rojo. Conservarlo solo como material externo auditado. Antes de considerar su subconjunto de roya, solicitar a los autores el manifiesto de procedencia, la explicación de las discrepancias y los identificadores de planta/hoja; después se requeriría revisión experta de una política explícita de conversión a clasificación. No mezclar ni entrenar mientras esos puntos estén pendientes.

## Datos que faltan para un filtro café/no café

El umbral 0,70 del clasificador, el color verde, el nombre del archivo y las puntuaciones del modelo actual no permiten confirmar que una imagen sea una hoja de café. Los casos exploratorios de uva y de una publicación titulada “Roya del cafeto” motivan esta necesidad, pero no constituyen una evaluación.

Conviene separar dos decisiones medibles:

1. **Presencia:** confirmar que la imagen contiene una hoja de café.
2. **Usabilidad:** confirmar que hay una sola hoja suficientemente visible para el clasificador de tres categorías.

Datos positivos faltantes:

- hojas de café confirmadas por procedencia o experto, incluidas sana, roya y daño por ácaro rojo;
- plantas, predios, fechas, dispositivos, fondos, iluminaciones, caras y distancias variadas;
- identificadores de planta/hoja/sesión para separar desarrollo y evaluación;
- ejemplos utilizables de una sola hoja y ejemplos de café deliberadamente no utilizables para evaluar ambas decisiones.

Datos negativos faltantes:

- hojas de otras especies, especialmente cultivos visualmente cercanos, con identidad documentada;
- fotografías sin hojas, pantallas, páginas, gráficas, frutos, objetos y fondos;
- escenas con varias hojas, hoja parcial, desenfoque, reflejos, oclusión y resolución insuficiente;
- fuentes independientes y con licencia, sin asignar etiquetas por filename ni por la salida de CaféIA.

La evaluación debe reservar fuentes, plantas y sesiones no usadas durante el desarrollo y reportar, por separado, recall de aceptación de hojas de café utilizables, recall de rechazo y falsos aceptados. Hasta implementar y medir esa tarea, la interfaz no debe afirmar que reconoce imágenes ajenas al dominio. El mensaje previsto es:

> No se pudo confirmar que la imagen corresponda a una hoja de café. Carga una fotografía de una sola hoja de café.

## Evidencias reproducibles

- Script: [`src/audit_xinzhai_candidate.py`](../src/audit_xinzhai_candidate.py)
- Resumen: [`reports/xinzhai_audit/audit_summary.json`](xinzhai_audit/audit_summary.json)
- Inventario por imagen: [`reports/xinzhai_audit/image_inventory.csv`](xinzhai_audit/image_inventory.csv)
- Cajas: [`reports/xinzhai_audit/boxes.csv`](xinzhai_audit/boxes.csv)
- Duplicados exactos y candidatos perceptuales: archivos CSV en [`reports/xinzhai_audit/`](xinzhai_audit/)

Comando utilizado desde la raíz del proyecto:

```powershell
.\.venv\Scripts\python.exe src\audit_xinzhai_candidate.py `
  --external-root "$env:LOCALAPPDATA\Temp\cafeia-external-data\xinzhai-zenodo-21442135"
```

No se modificaron el dataset de CaféIA, el manifiesto, las particiones, los checkpoints ni el modelo activo. No hubo entrenamiento ni consulta de imágenes, etiquetas o predicciones de TEST.
