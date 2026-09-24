# Comparación de las anotaciones originales de RoCoLe

**Fecha de corte:** 2026-09-22
**Ámbito autorizado:** TRAIN, VAL y los 24 archivos excluidos por contradicción. TEST permaneció reservado: no se abrieron sus imágenes, no se decodificaron ni compararon sus etiquetas y no se calcularon predicciones o métricas.

## Resultado ejecutivo

Se descargó [RoCoLe versión 2 desde Mendeley Data](https://data.mendeley.com/datasets/c5yvn32dzg/2), DOI [10.17632/c5yvn32dzg.2](https://doi.org/10.17632/c5yvn32dzg.2), mediante su endpoint oficial “Download All”. El paquete original y su atribución quedaron preservados en `provenance/rocole_mendeley_v2/` sin modificar `data/`, el manifiesto, los experimentos ni los modelos.

La copia original contiene 1560 JPG y anotaciones CSV, JSON, COCO, VOC y XLSX, en concordancia con el [artículo original](https://pmc.ncbi.nlm.nih.gov/articles/PMC6727496/). El ZIP conservado mide 2,245,588,288 bytes y tiene SHA-256 `31daa765fb0cc27d4b9b897fa6350aacf0087ee5771d3c7599d2ac7041b866ff`.

Los resultados son:

- **1181/1181 archivos de TRAIN/VAL** tienen un nombre original único, una anotación única y contenido consistente con la fotografía original redimensionada.
- **0/1181 son idénticos byte a byte** al original. La versión local tiene imágenes redimensionadas/recodificadas; por ejemplo, la copia local comprobada mide 1920×1080 y su original 2048×1152. Los SHA-256 crudos se registraron, pero no se declararon equivalentes.
- La verificación secundaria de contenido de los 1181 pares obtuvo correlaciones entre `0.999854244` y `0.999987790`, con error absoluto medio entre `0.126519` y `0.393121` sobre versiones grises 128×72. Esta prueba respalda la derivación, pero **no sustituye la identidad SHA-256**.
- **1181/1181 etiquetas de TRAIN/VAL coinciden** con las anotaciones originales después de la conversión explícita de las cuatro severidades de roya. No se encontraron discrepancias.
- Los **12 pares/24 archivos excluidos también son duplicados exactos en el paquete original**. Cada par comparte un SHA-256 original, pero sus dos nombres tienen anotaciones de clase diferentes. Las anotaciones originales reproducen la contradicción y no permiten escoger una etiqueta correcta.

## Método de relación y límites

La comparación usó estas capas de evidencia, en orden:

1. SHA-256 del archivo local y del archivo original para identidad byte a byte.
2. `External ID` original frente al nombre local, exigiendo una coincidencia única.
3. Anotación única del CSV original para ese `External ID`.
4. Solo cuando los SHA-256 diferían por el redimensionamiento, correlación de Pearson y error absoluto medio entre versiones grises reducidas a 128×72.

El paso 4 no se usó para deducir una clase por apariencia; únicamente comprueba si dos archivos nombrados de igual forma representan el mismo contenido transformado. Una relación se marcó como copia derivada consistente si el nombre era único, la correlación era al menos `0.995` y el error absoluto medio no superaba `2.0`.

Por tanto, el conteo debe interpretarse en dos niveles:

| Tipo de relación en TRAIN/VAL | Archivos |
|---|---:|
| Identidad exacta por SHA-256 | 0 |
| Nombre único + anotación única + contenido derivado consistente | 1181 |
| Sin correspondencia original | 0 |
| Ambigua o con similitud insuficiente | 0 |

No es correcto afirmar que los archivos locales sean copias byte a byte del original. Sí es correcto afirmar que los 1181 archivos autorizados se relacionan inequívocamente como derivados redimensionados, dentro de los criterios documentados.

## Conversión explícita de etiquetas

La clasificación original conserva cuatro niveles de severidad de roya. Para compararla con las tres clases de este proyecto se aplicó únicamente esta tabla:

| Clasificación original | Significado original | Categoría local comparada |
|---|---|---|
| `healthy` | Sana | `coffee___healthy` / sana |
| `red_spider_mite` | Ácaro rojo | `coffee___red_spider_mite` / ácaro rojo |
| `rust_level_1` | Roya, 1–5 % del área afectada | `coffee___rust` / roya |
| `rust_level_2` | Roya, 6–20 % | `coffee___rust` / roya |
| `rust_level_3` | Roya, 21–50 % | `coffee___rust` / roya |
| `rust_level_4` | Roya, más de 50 % | `coffee___rust` / roya |

No se infirió ninguna etiqueta visualmente. La conversión solo colapsa los cuatro valores originales `rust_level_*` en la categoría local única “roya”.

## Comparación de TRAIN y VAL

### Resultado por partición

| Partición | Archivos | Etiquetas coincidentes | Discrepancias | Correspondencias derivadas consistentes |
|---|---:|---:|---:|---:|
| TRAIN | 880 | 880 | 0 | 880 |
| VAL | 301 | 301 | 0 | 301 |
| **Total** | **1181** | **1181** | **0** | **1181** |

### Conteos originales y conversión a tres clases

| Partición | Sana | Ácaro rojo | Roya N1 | Roya N2 | Roya N3 | Roya N4 | Roya fusionada |
|---|---:|---:|---:|---:|---:|---:|---:|
| TRAIN | 448 | 93 | 214 | 82 | 26 | 17 | **339** |
| VAL | 156 | 31 | 58 | 40 | 12 | 4 | **114** |
| **Total** | **604** | **124** | **272** | **122** | **38** | **21** | **453** |

Los conteos fusionados coinciden exactamente con las clases locales: TRAIN contiene 448 sana, 93 ácaro rojo y 339 roya; VAL contiene 156 sana, 31 ácaro rojo y 114 roya.

## Revisión de los 24 archivos excluidos

Los 24 nombres existen tanto en el ZIP original como en su CSV de anotaciones. En cada par:

- las dos copias locales son idénticas por SHA-256;
- las dos copias originales también son idénticas por SHA-256;
- el CSV original asigna una anotación distinta a cada nombre;
- después de fusionar los niveles de roya, las dos anotaciones siguen siendo clases diferentes;
- cada anotación original coincide nominalmente con la carpeta de la versión Kaggle, pero no resuelve qué clase corresponde al contenido duplicado.

| Par | Primer nombre y etiqueta original | Segundo nombre y etiqueta original | Dictamen |
|---:|---|---|---|
| 1 | `C12P36E1.jpg` — sana | `C11P23E1.jpg` — ácaro rojo | Mismo SHA original, etiquetas contradictorias |
| 2 | `C10P23E2.jpg` — ácaro rojo | `C12P32E2.jpg` — roya N1 | Mismo SHA original, etiquetas contradictorias |
| 3 | `C10P26E2.jpg` — ácaro rojo | `C12P36E2.jpg` — roya N3 | Mismo SHA original, etiquetas contradictorias |
| 4 | `C10P30E2.jpg` — ácaro rojo | `C12P40E2.jpg` — roya N1 | Mismo SHA original, etiquetas contradictorias |
| 5 | `C10P30H2.jpg` — ácaro rojo | `C12P40H2.jpg` — roya N1 | Mismo SHA original, etiquetas contradictorias |
| 6 | `C11P15H2.jpg` — ácaro rojo | `C12P25H2.jpg` — roya N1 | Mismo SHA original, etiquetas contradictorias |
| 7 | `C11P19E2.jpg` — ácaro rojo | `C12P29E2.jpg` — roya N3 | Mismo SHA original, etiquetas contradictorias |
| 8 | `C11P19H2.jpg` — ácaro rojo | `C12P29H2.jpg` — roya N3 | Mismo SHA original, etiquetas contradictorias |
| 9 | `C11P20E2.jpg` — ácaro rojo | `C12P30E2.jpg` — roya N3 | Mismo SHA original, etiquetas contradictorias |
| 10 | `C11P20H2.jpg` — ácaro rojo | `C12P30H2.jpg` — roya N4 | Mismo SHA original, etiquetas contradictorias |
| 11 | `C11P24E2.jpg` — ácaro rojo | `C10P38E2.jpg` — roya N1 | Mismo SHA original, etiquetas contradictorias |
| 12 | `C2P38E2.jpg` — ácaro rojo | `C3P29E2.jpg` — roya N1 | Mismo SHA original, etiquetas contradictorias |

### Resolución documental

**No existe una resolución documental dentro de RoCoLe versión 2.** El paquete original confirma la contradicción: el mismo contenido binario aparece con dos nombres y dos anotaciones incompatibles. El CSV no indica cuál registro debe prevalecer, y la inspección visual no resolvería la procedencia ni está autorizada como método de etiquetado.

La exclusión completa de los 12 hashes —los 24 nombres— fue, por tanto, la decisión correcta. No se deben reincorporar ni relabelar sin una corrección emitida por los autores o sin los archivos fuente distintos que deberían ocupar esas rutas.

## Casos sin correspondencia o ambiguos

| Caso | Cantidad | Interpretación |
|---|---:|---|
| TRAIN/VAL sin nombre original | 0 | Todos los nombres tienen contraparte original. |
| TRAIN/VAL sin anotación | 0 | Todos tienen una fila de anotación única. |
| TRAIN/VAL con múltiples filas de anotación | 0 | No se encontró ambigüedad por fila duplicada. |
| TRAIN/VAL con discrepancia tras conversión | 0 | Las 1181 etiquetas coinciden. |
| Excluidos sin nombre/anotación original | 0 | Los 24 están presentes. |
| Excluidos con identidad y clase inequívocas | 0 | Los 24 pertenecen a 12 hashes con etiquetas contradictorias. |

La única ambigüedad comprobada dentro del ámbito autorizado es la de esos 12 hashes conflictivos. No se hizo ninguna afirmación sobre TEST.

## Recomendación

**Conservar la versión limpia actual de 1481 imágenes, su manifiesto y sus particiones.** La comparación valida todas las etiquetas de TRAIN/VAL y confirma que excluir los 24 archivos contradictorios era necesario incluso frente al original. No hay evidencia que justifique regenerar automáticamente las particiones ni invalidar los experimentos actuales.

No se recomienda crear ahora una “versión corregida” que elija una etiqueta para esos pares. Solo debe prepararse una nueva versión si los autores publican una corrección verificable o proporcionan las fotografías fuente distintas asociadas a cada nombre. En ese caso se deberá versionar un nuevo manifiesto, documentar los cambios y repetir los experimentos que se quieran comparar; no se debe usar TEST para decidirlo.

## Evidencias

- [Registro y atribución del paquete original](../provenance/rocole_mendeley_v2/README.md)
- `provenance/rocole_mendeley_v2/rocole_mendeley_c5yvn32dzg_v2.zip`
- `provenance/rocole_mendeley_v2/annotations/`
- `provenance/rocole_mendeley_v2/evidence/annotation_audit_summary.json`
- `provenance/rocole_mendeley_v2/evidence/train_val_annotation_comparison.csv`
- `provenance/rocole_mendeley_v2/evidence/excluded_conflicts_original_comparison.csv`
- `provenance/rocole_mendeley_v2/evidence/excluded_conflict_pair_diagnostics.csv`
- `src/audit_rocole_annotations.py`

## Integridad del proyecto

Durante esta auditoría no se modificaron etiquetas, imágenes de trabajo, `data/processed/manifest.csv`, particiones, checkpoints ni el umbral de incertidumbre. No se entrenó ningún modelo y el modelo activo no fue reemplazado.
