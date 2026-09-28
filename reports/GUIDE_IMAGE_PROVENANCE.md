# Procedencia de la guía visual de CaféIA

**Fecha de corte:** 2026-09-26
**Ámbito:** tres fotografías publicables de `TRAIN`; no se consultaron imágenes, etiquetas ni predicciones de `TEST`.

## Resultado

La guía usa únicamente tres copias de fotografías reales de RoCoLe v2. La ficha oficial de Mendeley identifica la versión 2, sus 1.560 imágenes, los cuatro autores y la licencia [Creative Commons Attribution 4.0](https://data.mendeley.com/datasets/c5yvn32dzg/2). La copia local ya había sido comparada con la anotación original en la auditoría de procedencia: para los tres ejemplos existe una sola fila de anotación, la relación de contenido es inequívoca y la clase local coincide con la original después de la conversión documentada.

| Ficha | Recurso del frontend | Archivo de origen | Partición | Anotación original | ID de anotación | SHA-256 de la copia publicada |
|---|---|---|---|---|---|---|
| Hoja sana | `frontend/public/guide/hoja-sana-rocole-c10p12h1.jpg` | `data/raw/coffee___healthy/C10P12H1.jpg` | TRAIN | `healthy` | `cjvqvlh6dj3yj08049vgpjmkx` | `28abb9a006ed66d44f36b699fb7eb7d536fae29cded20e613ed4508565fccc81` |
| Roya del café | `frontend/public/guide/roya-rocole-c10p27e2.jpg` | `data/raw/coffee___rust/C10P27E2.jpg` | TRAIN | `rust_level_2` | `cjvqwgaawj6au08286qkf7o1l` | `123f468835b7bc7cc92f4a16e45417313803d64ccbbd886d7726866fe6e15b3b` |
| Daño por ácaro rojo | `frontend/public/guide/acaro-rojo-rocole-c11p9h2.jpg` | `data/raw/coffee___red_spider_mite/C11P9H2.jpg` | TRAIN | `red_spider_mite` | `cjvqxbvlejis60804gahz7utf` | `fd49f1929b67941b75f8263b4472580856a80ce287d33b2097a06873e069bc96` |

Las tres copias conservan exactamente los bytes y el SHA-256 de sus archivos locales. No se copiaron otras imágenes. La selección visual buscó ejemplos legibles para la interfaz, pero **la etiqueta se tomó de la anotación original y no se dedujo de la apariencia**.

## Atribución de las fotografías

Cada ficha muestra esta atribución junto a la imagen:

> RoCoLe v2, Jorge Parraga-Alava, Kevin Cusme, Angélica Loor y Esneider Santander, CC BY 4.0; identificador del archivo y partición TRAIN.

Referencia recomendada por el repositorio:

- Parraga-Alava, J.; Cusme, K.; Loor, A.; Santander, E. *RoCoLe: A robusta coffee leaf images dataset*, versión 2. Mendeley Data. DOI: [10.17632/c5yvn32dzg.2](https://doi.org/10.17632/c5yvn32dzg.2).

La interfaz no incluye el dataset completo, las anotaciones originales ni archivos de `VAL` o `TEST`.

## Fuentes de las explicaciones

El texto de la guía es una síntesis breve, no una reproducción de las publicaciones, y enlaza la fuente en cada ficha:

- Hoja sana y cautela sobre variaciones visuales: [Síntomas visuales de deficiencias nutricionales en café: Diagnóstico y manejo, Avance Técnico 478](https://publicaciones.cenicafe.org/index.php/avances_tecnicos/article/view/302), Cenicafé.
- Roya: [Enfermedades foliares del cafeto, Avance Técnico 106](https://publicaciones.cenicafe.org/index.php/avances_tecnicos/article/view/2069), Cenicafé.
- Señales generales asociadas con ácaros rojos: [La arañita roja del cafeto, Avance Técnico 22](https://publicaciones.cenicafe.org/index.php/avances_tecnicos/article/view/2157), Cenicafé.

Las páginas de Cenicafé declaran licencia CC BY-NC-ND 4.0. CaféIA solo las cita y parafrasea; no reutiliza sus fotografías ni añade recomendaciones de pesticidas.

## Distinción documental importante

Las publicaciones de Cenicafé describen información agronómica general. RoCoLe solo denomina la clase `red_spider_mite`; la documentación revisada del dataset no identifica una especie concreta. Por eso la guía habla de **daño por ácaro rojo** y no asigna una especie a la fotografía.

## Evidencia usada

- `provenance/rocole_mendeley_v2/evidence/train_val_annotation_comparison.csv` (conservado localmente y excluido del repositorio de despliegue).
- [Comparación de anotaciones originales](ORIGINAL_ANNOTATION_COMPARISON.md).
- [Auditoría de procedencia](DATASET_PROVENANCE_AUDIT.md).

No se modificaron el dataset, el manifiesto, las particiones, los checkpoints ni el modelo activo durante esta integración.
