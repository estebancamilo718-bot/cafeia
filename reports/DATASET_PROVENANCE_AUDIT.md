# Auditoría documental de procedencia del dataset RoCoLe

**Fecha de corte:** 2026-09-22
**Alcance:** documentación, nombres de archivo, estructura del ZIP y huellas criptográficas. No se abrieron ni interpretaron imágenes, no se consultaron resultados del conjunto de prueba y no se inició ningún entrenamiento.

## Conclusión ejecutiva

La fase exploratoria de entrenamiento queda cerrada. El checkpoint activo y el candidato de ajuste fino se conservaron sin cambios.

La evidencia publicada respalda de forma sólida que RoCoLe fue adquirido sobre **390 plantas** y que se tomaron **cuatro fotografías por planta**, de haz y envés de hojas sanas e infectadas. El ZIP usado en este proyecto contiene exactamente **390 prefijos `CxPy` y cuatro archivos por prefijo** —salvo una anomalía de nomenclatura—, por lo que agrupar por `CxPy` es una interpretación conservadora y bien sustentada de la unidad planta. Unir además los grupos enlazados por duplicados exactos evita que el mismo contenido llegue a particiones distintas. No hay evidencia suficiente para modificar ahora el manifiesto.

No se encontró una leyenda original que expanda formalmente cada carácter del nombre. La correspondencia `H` = haz, `E` = envés y `CxPy` = identificador compuesto de planta está fuertemente sustentada por la documentación y la estructura completa de los nombres, pero debe conservarse como **inferencia documentada**, no como definición textual de los autores. El significado exacto de `C`, de `P` por separado y de los sufijos `1/2` sigue pendiente.

Las anotaciones originales sí existen en varios formatos y fueron elaboradas con evaluación experta. No vienen incluidas en el ZIP derivado de Kaggle usado localmente. Una auditoría posterior descargó la versión 2 original y comprobó que los 12 pares ya son duplicados exactos con etiquetas contradictorias en esa fuente; por ello los 24 archivos no pueden corregirse escogiendo una de esas anotaciones. Véase `reports/ORIGINAL_ANNOTATION_COMPARISON.md`.

## Estados usados en esta auditoría

- **Confirmado:** aparece explícitamente en una fuente primaria o se comprobó de forma reproducible en los archivos locales sin interpretar el contenido visual.
- **Inferencia sustentada:** concuerda con varias evidencias, pero no se encontró una definición explícita de los autores.
- **Pendiente:** la evidencia disponible no permite una conclusión responsable.

## Fuentes verificadas

| Fuente | Carácter | Evidencia relevante |
|---|---|---|
| [Artículo original en *Data in Brief*](https://pmc.ncbi.nlm.nih.gov/articles/PMC6727496/) ([DOI](https://doi.org/10.1016/j.dib.2019.104414)) | Primaria, revisada por pares | 1560 imágenes, 390 plantas, cuatro imágenes por planta, haz y envés, seis categorías originales, captura y anotación. |
| [Repositorio original Mendeley Data, versión 2](https://data.mendeley.com/datasets/c5yvn32dzg/2) ([DOI](https://doi.org/10.17632/c5yvn32dzg.2)) | Primaria, repositorio citado por el artículo | Registro del dataset original, autores, fecha, licencia CC BY 4.0 y descripción de las anotaciones. |
| [Tesis de ESPAM MFL](https://repositorio.espam.edu.ec/handle/42000/1104) ([PDF](https://repositorio.espam.edu.ec/server/api/core/bitstreams/18548207-03c5-4292-9b7e-27432a988485/content)) | Primaria para la adquisición y el proyecto que originó el dataset | Lugar de captura, 480 plantas en la parcela, 390 disponibles, toma de haz/envés, renombrado masivo y uso de Labelbox. Los anexos muestran la secuencia de nombres. |
| [Página de la versión derivada en Kaggle](https://www.kaggle.com/datasets/nirmalsankalana/rocole-a-robusta-coffee-leaf-images-dataset) ([metadatos de la API](https://www.kaggle.com/api/v1/datasets/view/nirmalsankalana/rocole-a-robusta-coffee-leaf-images-dataset)) | Secundaria/derivada | Publicada por Nirmal Sankalana en 2025; declara 1560 imágenes organizadas en tres clases y describe una reorganización en carpetas. No es el repositorio de los autores originales. |
| `archive.zip`, copia local usada por el proyecto | Evidencia local | 1560 JPG, tres carpetas y ningún archivo de anotación. SHA-256 `16638a4488f3f910ad702bc991d6dade5539f5100e7ae66a7140e614c4c9a6f5`. |

La publicación y Mendeley atribuyen el trabajo a Jorge Parraga-Alava, Kevin Cusme, Angélica Loor y Esneider Santander. El registro de Kaggle pertenece a otro publicador. Además, el original declara **CC BY 4.0**, mientras que la API de Kaggle muestra **MIT**. Esta discrepancia de licencia es un problema documental pendiente; no debe asumirse que el registro derivado puede cambiar la licencia del material original.

## Dataset original frente a la versión de Kaggle

### Hechos confirmados

El artículo original informa estas seis categorías de clasificación:

| Categoría original | Cantidad |
|---|---:|
| Sana | 791 |
| Ácaro rojo | 167 |
| Roya, nivel 1 | 344 |
| Roya, nivel 2 | 166 |
| Roya, nivel 3 | 62 |
| Roya, nivel 4 | 30 |
| **Total** | **1560** |

Los niveles de roya representan intervalos de área afectada de la hoja: 1–5 %, 6–20 %, 21–50 % y más de 50 %, respectivamente. El artículo indica que un experto estableció la presencia y severidad usadas como verdad de referencia. También informa anotaciones de segmentación y clasificación en JSON, CSV, COCO, PASCAL VOC y XLSX.

La copia local derivada contiene únicamente:

| Carpeta local | Cantidad |
|---|---:|
| `coffee___healthy` | 791 |
| `coffee___red_spider_mite` | 167 |
| `coffee___rust` | 602 |
| **Total** | **1560** |

El ZIP local no incluye CSV, JSON, XLSX, XML ni otros archivos de anotación. Solo contiene JPG. La API de Kaggle registra una versión creada/actualizada el 2025-01-25, de 406,614,464 bytes; el ZIP local mide 406,401,184 bytes. El registro del proyecto identifica esa página como origen, pero, sin una huella publicada por Kaggle ni una descarga comparativa independiente, no se puede afirmar identidad criptográfica con el archivo que Kaggle sirve actualmente.

### Inferencia sustentada sobre las tres carpetas

Los cuatro conteos de roya originales suman exactamente `344 + 166 + 62 + 30 = 602`, igual al contenido de `coffee___rust`; sana y ácaro rojo conservan exactamente sus conteos originales. La explicación más sustentada es que la versión de Kaggle agrupó los cuatro niveles de severidad bajo una sola clase de roya y dejó las otras dos clases sin fusionar.

Esto explica numéricamente las tres carpetas, pero **no sustituye una tabla de transformación**: Kaggle no aporta el script de conversión, una versión de las anotaciones ni el historial archivo-a-clase. Por tanto, el responsable exacto de cada asignación y el procedimiento usado para copiar o renombrar archivos permanecen pendientes.

## Auditoría de la nomenclatura

La enumeración de nombres del ZIP, sin abrir las imágenes, produjo:

- 390 prefijos únicos con forma `CxPy`.
- `C` toma valores de 1 a 12 y `P` de 1 a 40.
- 390 archivos `E1`, 390 `E2`, 390 `H1` y 389 `H2`.
- Un nombre anómalo, `C11P11HE.jpg`, ocupa el cuarto lugar del grupo `C11P11`. No se infiere que su nombre correcto sea `H2`; debe contrastarse con el original.
- Cada prefijo tiene cuatro archivos contando esa anomalía.

| Elemento | Estado | Interpretación responsable |
|---|---|---|
| `CxPy` completo | **Inferencia fuertemente sustentada** | Identifica una planta o posición de planta. Hay 390 combinaciones, exactamente tantas como plantas fotografiadas, y cuatro imágenes por combinación, igual que las cuatro imágenes por planta documentadas. |
| `C` y su número | **Pendiente** | Primer índice de la ubicación de campo, con valores 1–12. La parcela tenía 480 plantas y la malla observable es compatible con 12 × 40, pero ninguna fuente localizada expande formalmente la letra `C`. No se debe afirmar “calle”, “columna”, “clon” u otro término sin confirmación. |
| `P` y su número | **Inferencia sustentada / expansión pendiente** | Segundo índice, con valores 1–40, probablemente planta o posición dentro del primer índice. La expansión literal de `P` no se encontró en una leyenda de los autores. |
| `E` | **Inferencia fuertemente sustentada** | Envés. La documentación dice que se fotografiaron haz y envés y los nombres forman pares `E/H`; no se encontró una leyenda explícita del carácter. |
| `H` | **Inferencia fuertemente sustentada** | Haz, con la misma salvedad anterior. |
| Sufijo `1` o `2` | **Pendiente** | Distingue dos hojas o dos instancias de adquisición dentro de la planta. No codifica de forma estable la clase: ambos números aparecen en más de una carpeta. No se encontró la regla exacta que asigna 1 y 2. |

Los anexos de la tesis muestran secuencias como `C1P1E1`, `C1P1E2`, `C1P1H1` y `C1P1H2`, pero no incluyen una leyenda formal. Esa evidencia permite reconocer el patrón, no expandir sin reservas todas sus letras.

## Planta, hoja, cara fotografiada y alcance de la etiqueta

### Varias fotografías de una planta

**Confirmado.** El artículo informa cuatro imágenes por cada una de 390 plantas. La coincidencia exacta con los 390 prefijos y cuatro archivos por prefijo respalda tratar `CxPy` como unidad planta.

### Varias fotografías de una misma hoja

**Inferencia sustentada, no confirmación completa.** Las fuentes explican que se fotografiaron el haz y el envés de hojas sanas e infectadas. Es razonable emparejar `E1/H1` y `E2/H2` como dos caras de una misma hoja, pero la documentación encontrada no enlaza explícitamente esos sufijos con identificadores de hojas físicas. No se debe afirmar esa correspondencia como hecho hasta obtener la leyenda original o confirmación de los autores.

### Alcance de las etiquetas

**Confirmado:** las anotaciones originales clasifican cada objeto/imagen y la severidad de roya se define por porcentaje de área afectada de la hoja. En la versión de Kaggle, la carpeta es necesariamente una etiqueta por archivo: un mismo prefijo `CxPy` puede aparecer en dos o tres carpetas distintas. Por tanto, la carpeta no representa un diagnóstico único de toda la planta.

**Pendiente:** las fuentes no precisan si la clase de una fotografía debía describir solo los signos visibles en la cara fotografiada o el estado de toda la hoja física propagado entre ambas caras. Tampoco se encontró una regla de prioridad cuando una hoja presenta simultáneamente más de una condición. No se debe resolver esa ambigüedad inspeccionando visualmente los archivos.

Como comprobación puramente nominal, los 390 prefijos se distribuyen así según las carpetas en que aparecen sus cuatro archivos:

| Combinación de carpetas dentro de un `CxPy` | Prefijos |
|---|---:|
| Sana + roya | 254 |
| Sana + ácaro rojo + roya | 74 |
| Sana + ácaro rojo | 46 |
| Solo sana | 10 |
| Ácaro rojo + roya | 2 |
| Solo roya | 4 |

Estos conteos muestran que la clase no es una propiedad única del prefijo/planta. No permiten inferir si una etiqueta individual es correcta.

## Los 24 archivos con etiquetas contradictorias

La limpieza local encontró 12 pares de archivos **idénticos byte a byte** ubicados bajo etiquetas distintas, es decir, 24 rutas conflictivas. Se excluyó el hash completo de cada par y no se eligió una etiqueta por apariencia. Además, se retiraron 55 copias redundantes con la misma etiqueta; quedaron 1481 imágenes.

### Qué puede comprobarse

- **Confirmado:** el original ofrece anotaciones de clasificación y segmentación en varios formatos, y el artículo atribuye la verdad de referencia a evaluación experta.
- **Confirmado:** esas anotaciones no están presentes en el ZIP local de Kaggle.
- **Confirmado en la auditoría posterior:** cada par también comparte un SHA-256 en el paquete original, pero sus dos nombres tienen anotaciones originales incompatibles.
- **Confirmado:** el conflicto no fue introducido únicamente por la reorganización de Kaggle; ya está presente en RoCoLe versión 2.

La versión original no ofrece una regla para decidir cuál anotación debe prevalecer. La exclusión de ambos nombres de cada hash sigue siendo la única resolución responsable mientras los autores no publiquen una corrección o los archivos fuente distintos.

## Evaluación de la agrupación y las particiones actuales

### Agrupación por `CxPy`

**Dictamen: apropiada y conservadora con la evidencia actual.** Mantiene juntas las cuatro fotografías asociadas a una planta documentada y, si los pares `E/H` fueran efectivamente caras de la misma hoja, también evita separar esa hoja entre particiones. Es una unidad más estricta que agrupar por imagen y reduce el riesgo de fuga de información.

### Unión de grupos relacionados por duplicados

**Dictamen: conservadora para evitar fuga.** `src/prepare.py` une dos prefijos cuando existe contenido exactamente duplicado entre ellos. Así, ni el duplicado ni otras imágenes de sus grupos pueden quedar en particiones diferentes. La operación reduce 390 prefijos nominales a 352 grupos conectados.

Hay una salvedad documental: el código forma esas uniones antes de excluir los hashes con etiquetas contradictorias. Por ello, dos prefijos pueden permanecer unidos aunque el único archivo que los relacionaba haya sido eliminado. Esto no crea fuga; puede hacer la partición más gruesa de lo necesario. La auditoría posterior confirmó que los 12 hashes conflictivos ya están duplicados en RoCoLe versión 2, por lo que no son un artefacto exclusivo del empaquetado de Kaggle. Mantener la unión sigue siendo la opción prudente.

### ¿Debe corregirse ahora el manifiesto?

**No.** No hay evidencia documental que justifique reemplazar automáticamente la agrupación o la partición actual. Se conserva sin cambios `data/processed/manifest.csv`, SHA-256 `1ea21d6b2b480b830065c5d4d1d90f531234cc2aa244d7bb98c5873363866dab`, con semilla 42.

Una corrección solo estaría justificada si las anotaciones/índices originales demuestran que `CxPy` no identifica una planta, que una planta aparece bajo varios prefijos no conectados, o que la reorganización de Kaggle alteró de manera verificable las correspondencias de archivos y clases.

Si se genera un manifiesto corregido, los resultados obtenidos con la partición actual dejarían de ser comparables de manera directa con resultados nuevos. Esto afecta a:

- `experiments/mobilenet_10ep_20260920-181113`
- `experiments/cnn_10ep_20260921-125200`
- `experiments/resnet18_10ep_20260921-130620`
- `experiments/mobilenet_finetune_20260922-103426`
- Los informes comparativos y métricas de validación derivados de esas corridas.

Los checkpoints seguirían siendo evidencia histórica, pero habría que repetir las tres referencias y cualquier ajuste fino que se quisiera comparar bajo la nueva partición. La decisión no debe apoyarse en el conjunto de prueba.

## Conservación de los modelos

No se escribió ni reemplazó ningún checkpoint durante esta auditoría:

| Rol | Archivo | SHA-256 |
|---|---|---|
| MobileNet activo | `models/mobilenet.pt` | `9248cc767425c9efec643bcc2cabd758e8f2b28ab4a6967908713fc1d0b9c5c1` |
| Candidato ajustado archivado | `experiments/mobilenet_finetune_20260922-103426/best_checkpoint.pt` | `4ab4e52fc3d417fe5fb126ff1e5b346f080c55ffa80232cffd5d6e6622e46c94` |
| Referencia inicial del ajuste fino | `experiments/mobilenet_finetune_20260922-103426/candidate_initial_epoch0.pt` | `9248cc767425c9efec643bcc2cabd758e8f2b28ab4a6967908713fc1d0b9c5c1` |

## Problemas y dudas pendientes

1. No existe en las fuentes localizadas una leyenda explícita de `C`, `P`, `E`, `H`, `1` y `2`.
2. Falta confirmar documentalmente si `E1/H1` y `E2/H2` son las dos caras de la misma hoja física.
3. No está definido si la clase se asignó por signos visibles en cada cara o por el estado de la hoja completa.
4. La conversión exacta de las seis categorías/anotaciones originales a las tres carpetas de Kaggle no está versionada.
5. Las anotaciones originales no acompañan la copia de Kaggle y, aun después de recuperarlas, los 12 pares conservan dos etiquetas incompatibles para el mismo contenido.
6. Existe el nombre anómalo `C11P11HE.jpg`.
7. La licencia declarada por Kaggle no coincide con la licencia del repositorio original.

## Seguimiento completado y siguiente acción

RoCoLe versión 2 fue descargado directamente de Mendeley Data y quedó preservado en `provenance/rocole_mendeley_v2/`. La comparación autorizada de TRAIN/VAL y los 24 excluidos está en `reports/ORIGINAL_ANNOTATION_COMPARISON.md`: las 1181 etiquetas de TRAIN/VAL coinciden tras fusionar los niveles de roya y los 12 hashes conflictivos permanecen irresolubles en la fuente original.

Se conserva el dataset limpio y el manifiesto actual. La siguiente acción documental, sin alterar datos, es solicitar a los autores una leyenda formal de nomenclatura y una corrección de los 12 hashes si existe. No se deben reincorporar ni relabelar esos archivos por su apariencia y no se encadenan nuevos experimentos.
