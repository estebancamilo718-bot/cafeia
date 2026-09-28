# Protocolo previo al experimento CaféIA v2

**Estado:** especificación cerrada antes del entrenamiento; no ejecutado al redactar esta versión.
**Fecha:** 2026-09-26.
**Objetivo:** probar un único cambio de preprocesamiento que conserve la geometría de la hoja y medir si mejora la clasificación de ácaro rojo sin sacrificar el F1 macro de validación.

> **Cierre posterior, 2026-09-27:** el experimento se ejecutó una vez y concluyó. La copia del protocolo tomada antes del entrenamiento está en `experiments/mobilenet_v2_preprocessing_20260927-114627/protocol_snapshot.md`; los resultados se reportan en `reports/V2_PREPROCESSING_RESULTS.md`. El candidato no sustituyó al modelo activo.

## 1. Elementos que quedan congelados

- Manifiesto: `data/processed/manifest.csv`, SHA-256 `1ea21d6b2b480b830065c5d4d1d90f531234cc2aa244d7bb98c5873363866dab`.
- Particiones actuales: 880 imágenes de TRAIN, 301 de VAL y 300 de TEST, agrupadas como está documentado en la versión 1.
- Semilla: 42.
- Modelo web activo: `models/mobilenet_finetuned_epoch6.pt`, SHA-256 `4ab4e52fc3d417fe5fb126ff1e5b346f080c55ffa80232cffd5d6e6622e46c94`.
- Umbral de interfaz: 0,70, todavía provisional y no calibrado.
- Arquitectura, pérdida ponderada, pesos de clase, aumentos, capas entrenables, BatchNorm, optimizador, tasas de aprendizaje, tamaño de lote, máximo de épocas y paciencia de parada temprana de la corrida de ajuste fino v1.

El conjunto TEST ya fue utilizado para cerrar la versión 1. **No se consultará para diseñar, ajustar, detener, seleccionar ni presentar como evaluación independiente de la versión 2.** Sus cifras históricas permanecerán identificadas únicamente como resultados cerrados de v1.

## 2. Auditoría de la implementación real

### Datos y preprocesamiento

| Elemento | Implementación comprobada | Evidencia |
|---|---|---|
| Lectura | `ImageOps.exif_transpose`, luego conversión RGB | `src/common.py`, líneas 28–30 |
| Tamaño de TRAIN/VAL | Las 1.181 imágenes son 1920×1080, relación 16:9 y orientación horizontal | Lectura de metadatos PIL limitada a las filas TRAIN/VAL del manifiesto |
| Redimensionado v1 | `Resize((224, 224))` | `src/common.py`, línea 15 |
| Efecto geométrico | Todas las imágenes 16:9 se fuerzan a 1:1; la proporción original no se conserva | Consecuencia directa y reproducible de los dos puntos anteriores |
| Aumento, solo TRAIN | `RandomHorizontalFlip()` y `RandomRotation(15)` | `src/common.py`, líneas 16–17 |
| VAL | Sin aumento aleatorio | Construcción `Leaves(..., training=False)` |
| Tensor y normalización | `ToTensor`; media ImageNet `[0.485, 0.456, 0.406]`, desviación `[0.229, 0.224, 0.225]` | `src/common.py`, líneas 18–19 |

### Distribución, pérdida y optimización del candidato activo

| Elemento | Valor comprobado |
|---|---|
| Conteos TRAIN | sana 448; ácaro rojo 93; roya 339 |
| Pesos de clase | sana `0.6547619048`; ácaro rojo `3.1541218638`; roya `0.8652900688` |
| Pérdida | entropía cruzada ponderada; pesos calculados solo con TRAIN |
| Arquitectura | MobileNetV3 Small |
| Capas entrenables | módulos `features.10`, `features.11`, `features.12` y `classifier.3` |
| Parámetros entrenables | 647.715 de 1.520.931 (42,59 %) |
| Optimizador | Adam |
| Tasas | `1e-5` para los tres módulos del extractor; `1e-4` para la última capa clasificadora |
| BatchNorm | estadísticas `running_mean`, `running_var` y contador congeladas en modo evaluación; parámetros afines de los módulos descongelados conservan gradientes |
| Lote | 16 |
| Presupuesto v1 | máximo 15 épocas; parada temprana tras 4 sin mejora; la corrida terminó tras 10 y seleccionó la época 6 |
| Selección | F1 macro de VAL, no accuracy |

Los pesos de clase **ya existen** en v1; no forman parte de la novedad propuesta.

## 3. Problemas demostrados e hipótesis

### Hechos demostrados

1. El redimensionado actual altera la relación de aspecto de todas las imágenes de TRAIN y VAL de 16:9 a 1:1.
2. Ácaro rojo es la clase más débil del candidato activo en VAL: precision `0.357143`, recall `0.483871` y F1 `0.410959`, con soporte 31.
3. De las 31 imágenes reales de ácaro rojo en VAL, 15 se clasifican correctamente, 14 como roya y 2 como sanas.
4. También hay 27 falsos positivos de ácaro: 8 hojas sanas y 19 hojas con roya se predicen como ácaro rojo.
5. La clase es minoritaria en TRAIN (93 de 880), aunque la pérdida ya compensa el desbalance con pesos de clase.

### Hipótesis, todavía no demostradas

- La deformación no uniforme podría distorsionar textura, venación y extensión de zonas pardas o rojizas que ayudan a separar ácaro rojo de roya.
- Conservar la hoja completa y su proporción podría mejorar precision y recall de ácaro rojo. No se afirma que la deformación sea la causa de los errores actuales ni que el cambio vaya a mejorar el resultado.
- El soporte reducido de ácaro en VAL hace que sus métricas sean sensibles a pocas imágenes; cualquier variación deberá informarse también como conteos y matriz de confusión.

El bajo F1 de ácaro por sí solo no demuestra ninguna causa visual o algorítmica.

## 4. Único cambio principal propuesto

Sustituir el `Resize((224, 224))` que estira la imagen por un **ajuste a 224×224 que conserve la relación de aspecto y la hoja completa**. La especificación queda fijada así:

1. aplicar `ImageOps.exif_transpose` y convertir a RGB;
2. **control:** redimensionar directamente a 224×224 con interpolación bilineal y `antialias=True`;
3. **candidato:** multiplicar ambas dimensiones por `224 / max(ancho, alto)`, redondear cada resultado con `round`, redimensionar con interpolación bilineal y `antialias=True`, y completar hasta 224×224;
4. usar relleno constante RGB `(124, 116, 104)`, la media ImageNet multiplicada por 255 y redondeada, para que su valor normalizado quede próximo a cero;
5. centrar el contenido: `izquierda = floor(resto_horizontal / 2)`, `derecha = resto_horizontal - izquierda`, `arriba = floor(resto_vertical / 2)`, `abajo = resto_vertical - arriba`;
6. solo en TRAIN, aplicar después `RandomHorizontalFlip(p=0.5)` y luego `RandomRotation(degrees=15, interpolation=NEAREST, expand=False, fill=0)`;
7. convertir con `ToTensor` y, al final, normalizar con media `[0.485, 0.456, 0.406]` y desviación `[0.229, 0.224, 0.225]`.

El orden completo es, por tanto: **orientación EXIF → RGB → redimensionamiento (y relleno en el candidato) → flip de TRAIN → rotación de TRAIN → tensor → normalización**. VAL omite flip y rotación.

Para las imágenes actuales de 1920×1080, el candidato genera contenido 224×126 y agrega 49 píxeles arriba y 49 abajo; no agrega relleno lateral. La función queda implementada en `src/v2_preprocessing.py`, se identifica mediante un ID versionado y su configuración completa se incorpora al checkpoint candidato para una futura integración.

No se cambiarán simultáneamente la arquitectura, la función de pérdida, los pesos de clase, los aumentos, las capas entrenables, BatchNorm, el optimizador ni las tasas de aprendizaje. Así se aísla el cambio de geometría.

## 5. Diseño pareado y presupuesto

- Inicio de **ambas ramas**: el mismo checkpoint MobileNet congelado de época 9, ruta `models/mobilenet.pt`, SHA-256 `9248cc767425c9efec643bcc2cabd758e8f2b28ab4a6967908713fc1d0b9c5c1`. No se inicia ninguna rama desde el modelo web ajustado.
- Rama A, control: especificación anterior 224×224 sin conservar proporción.
- Rama B, candidato: redimensionamiento proporcional y relleno centrado definido en la sección 4.
- Datos: exactamente las mismas filas TRAIN/VAL del manifiesto y orden de clases de v1; no abrir TEST.
- Semilla: 42.
- Entrenamiento: los últimos tres módulos de `features` y `classifier.3`, con estadísticas BatchNorm congeladas.
- Optimizador: Adam, `1e-5` en extractor y `1e-4` en clasificador.
- Pérdida y pesos: entropía cruzada con los mismos pesos ya calculados en TRAIN.
- Lote: 16.
- Máximo: 15 épocas, sin aumentar el límite de v1.
- Parada temprana: 4 épocas consecutivas sin mejorar el F1 macro de VAL.
- Candidatos: cada rama evalúa el checkpoint inicial con su propio preprocesamiento como época 0 y lo conserva si ninguna época posterior mejora.
- Reutilización permitida del control: la corrida `experiments/mobilenet_finetune_20260922-103426/` solo podrá reutilizarse si se verifica que partió del SHA-256 anterior y coincide en manifiesto, semilla, transformaciones y su orden, aumentos, pesos de clase, arquitectura, parámetros entrenables, BatchNorm, optimizador, tasas, lote, máximo de épocas, paciencia y selección. Además, su checkpoint inicial y su checkpoint seleccionado deben reproducir exactamente sus métricas de VAL con la implementación explícita del control. La equivalencia se archivará en la nueva carpeta del experimento.
- Corridas nuevas: una sola para el candidato. No encadenar búsquedas de hiperparámetros ni nuevas variantes a partir del resultado.
- Presupuesto de cómputo: CPU local. La referencia v1 tardó 416,4 s para 10 épocas; el tope operativo será 15 épocas y 12 minutos en la misma máquina. Esta duración es un presupuesto, no una promesa.

El experimento pareado debe guardarse en una carpeta nueva con subcarpetas `control/` y `candidate/`. Cada rama debe conservar configuración, historial, referencia o copia verificable del checkpoint, duración y métricas de VAL. El candidato debe añadir hashes, nombres de parámetros entrenables, comprobación del optimizador, comprobación de gradientes y estado de BatchNorm.

## 6. Comparación y criterio fijado antes de entrenar

### Referencia v1 en VALIDACIÓN

| Clase | Precision | Recall | F1 | Soporte |
|---|---:|---:|---:|---:|
| Hoja sana | 0.848101 | 0.858974 | 0.853503 | 156 |
| Ácaro rojo | 0.357143 | 0.483871 | 0.410959 | 31 |
| Roya | 0.722772 | 0.640351 | 0.679070 | 114 |
| **F1 macro** |  |  | **0.647844** | 301 |

Matriz v1, filas reales y columnas predichas en orden **sana, ácaro rojo, roya**:

```text
[[134,  8, 14],
 [  2, 15, 14],
 [ 22, 19, 73]]
```

### Selección dentro de v2

- Métrica única de selección por época: mayor F1 macro de VAL.
- En cada época: pérdida de TRAIN y F1 macro de VAL.
- Para el checkpoint seleccionado: accuracy descriptiva; precision, recall y F1 por clase; soporte; matriz de confusión; predicciones por imagen y muestra de errores.
- La versión v2 solo se considerará candidata a reemplazo si supera el F1 macro v1 de `0.6478439521`. Se reportarán de todos modos los cambios absolutos de precision, recall y F1 de cada clase, especialmente ácaro rojo, incluso si retroceden.
- No se cambiará el umbral 0,70 como respuesta al resultado. El umbral no participa en la selección.

### Comparación control–candidato

- Ambos resultados deben proceder del mismo checkpoint inicial fijado arriba y de las mismas filas TRAIN/VAL.
- Comparación principal: F1 macro del mejor checkpoint de cada rama, seleccionado internamente por F1 macro de VAL.
- Comparaciones secundarias obligatorias: precision, recall y F1 por clase, matriz de confusión, número de errores ácaro→roya y roya→sana, épocas ejecutadas y duración.
- La hipótesis enfocada en ácaro solo recibe apoyo si mejoran sus métricas y conteos sin presentar como consistente una diferencia pequeña observada con una única semilla.

No se promete mejora. Una subida de recall de ácaro acompañada por muchos falsos positivos debe presentarse como intercambio de precision/recall, no como éxito sin matices.

## 7. Coste de inferencia

La arquitectura, los 1.520.931 parámetros y la entrada tensorial 224×224 permanecen iguales, por lo que el coste de la red no cambia. El nuevo ajuste geométrico puede añadir un coste pequeño de CPU que debe medirse, no suponerse.

Antes de cualquier promoción se medirán v1 y v2 en el mismo equipo y proceso, usando una imagen de TRAIN fija:

- tiempo de preprocesamiento y latencia total por imagen, con calentamiento y al menos 50 repeticiones;
- mediana y percentil 95;
- memoria con el modelo cargado y pico durante una predicción;
- tamaño del checkpoint y conteo de parámetros.

La comparación debe usar el preprocesamiento propio de cada versión y lote 1. No se usarán imágenes de TEST para medir coste.

## 8. Desarrollo y evaluación futura

Durante desarrollo solo se usarán TRAIN para actualizar pesos y VAL para parada temprana, selección y diagnóstico. Debido a que VAL interviene repetidamente en decisiones, su resultado es una estimación de desarrollo y no una comprobación externa independiente.

Para una comprobación externa válida de v2 hace falta una colección nueva que:

- proceda de plantas no presentes en RoCoLe y conserve un identificador verificable de planta;
- incluya diferentes fincas o lotes, fechas, dispositivos, iluminación y fondos;
- contenga ambas caras de la hoja como observaciones identificadas, no como muestras independientes sin vínculo;
- tenga etiquetas revisadas por personal con competencia agronómica y documente cómo se confirmó cada condición;
- identifique la especie del ácaro solo si existe evidencia taxonómica, sin trasladar ese dato desde Cenicafé a RoCoLe;
- incluya suficientes plantas con ácaro rojo para estimar su recall con intervalos útiles, fijando el tamaño muestral antes de observar resultados;
- elimine duplicados exactos y cercanos antes de dividir y asigne todas las fotos de una planta a una sola partición;
- quede congelada antes de evaluar y no se reutilice para ajustar el modelo o el umbral.

Hasta disponer de esos datos, la comparación v1–v2 se limitará a TRAIN/VAL y no se presentará como generalización independiente.
