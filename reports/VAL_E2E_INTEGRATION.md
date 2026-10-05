# Comprobación E2E con fotografías reales de VAL

**Fecha:** 2026-09-28

**Alcance:** comprobación de integración sobre 15 fotografías de VAL; no es una evaluación independiente ni una nueva estimación de precisión global. No se abrieron imágenes, anotaciones ni predicciones de TEST.

## Selección fijada antes de predecir

El subcomando `select` no carga el checkpoint. Con semilla textual 42 ordena grupos y archivos mediante SHA256, elige cinco grupos distintos por clase y una imagen por grupo. Los 15 grupos también son distintos entre clases. El archivo fijado es `reports/val_e2e/selection.csv`, SHA256 `242ffc4c78d1e28bab89f3550f65f11f385ce0d0d4511c38b18b59b6e0793f3f`.

Cada fila se contrastó con la comparación de anotaciones originales ya auditada: relación `derived_content_consistent`, una sola anotación y coincidencia de etiqueta tras convertir `rust_level_1` a `rust_level_4` en la clase local única roya.

| Archivo | Planta/grupo | Etiqueta local | Anotación original | ID de anotación |
|---|---|---|---|---|
| `C4P26H1.jpg` | `C4P26` | Hoja sana | `healthy` | `cjvo7rh3ptusp0828w33071pg` |
| `C12P1H1.jpg` | `C12P1` | Hoja sana | `healthy` | `cjvqzn5rbk0sx0a087r6jvoqk` |
| `C9P5E2.jpg` | `C9P5` | Hoja sana | `healthy` | `cjvqry9wji6610804hamjlsnw` |
| `C2P18E1.jpg` | `C2P18` | Hoja sana | `healthy` | `cjvnz0eh4pr5s0828cfppc8u9` |
| `C8P6H1.jpg` | `C8P6` | Hoja sana | `healthy` | `cjvphbd477be90804mxibwk50` |
| `C11P37E2.jpg` | `C11P37` | Ácaro rojo | `red_spider_mite` | `cjvqzjemajxs10828zbdybn9i` |
| `C10P40E2.jpg` | `C10P40` | Ácaro rojo | `red_spider_mite` | `cjvqx1pg5j7ff07954pdb50yo` |
| `C12P13E2.jpg` | `C12P13` | Ácaro rojo | `red_spider_mite` | `cjvr02166k4bq0828eyrh9s9n` |
| `C2P15E2.jpg` | `C2P15` | Ácaro rojo | `red_spider_mite` | `cjvnyy9j3psai0838ockd3uah` |
| `C2P22E2.jpg` | `C2P22` | Ácaro rojo | `red_spider_mite` | `cjvnz4ihtpsy00828gc9ykrtw` |
| `C8P3H1.jpg` | `C8P3` | Roya | `rust_level_1` | `cjvpgszo77fsd0866bv6oehm5` |
| `C8P12E1.jpg` | `C8P12` | Roya | `rust_level_1` | `cjvpke8m282z10838yf6lv7nc` |
| `C10P36E2.jpg` | `C10P36` | Roya | `rust_level_1` | `cjvqwtsqhjr4x0a70eq9op1gm` |
| `C5P12E1.jpg` | `C5P12` | Roya | `rust_level_2` | `cjvocguikwnd80a08gqm2eovj` |
| `C1P9E2.jpg` | `C1P9` | Roya | `rust_level_2` | `cjvo60distcs40a70135092qd` |

## Contrato comparado

- Checkpoint: `models/mobilenet_finetuned_epoch6.pt`, SHA256 `4ab4e52fc3d417fe5fb126ff1e5b346f080c55ffa80232cffd5d6e6622e46c94`.
- Orden: `coffee___healthy`, `coffee___red_spider_mite`, `coffee___rust`.
- Preprocesamiento en ambas rutas: orientación EXIF, RGB, `Resize((224, 224))`, `ToTensor` y normalización ImageNet.
- Umbral conservado: `0.70`.
- API local comprobada: `http://127.0.0.1:8010`; `/health` informó el mismo hash y orden de clases.
- Tolerancia absoluta por puntuación: `1e-07`. Es del orden de una unidad de último lugar de float32 cerca de 1 y cubre una diferencia numérica mínima entre procesos o serialización, pero sigue siendo suficientemente estricta para detectar un cambio material de pesos, orden o transformación.

## Resultados completos

Las puntuaciones son salidas softmax y no probabilidades calibradas de acierto.

| Archivo | Etiqueta real | Clase predicha | Sana | Ácaro rojo | Roya | Clasificación | Incierto | Directa = API |
|---|---|---|---:|---:|---:|---|---|---|
| `C4P26H1.jpg` | Hoja sana | Hoja sana | 0.634767 | 0.249167 | 0.116066 | Acierto | Sí | Sí |
| `C12P1H1.jpg` | Hoja sana | Hoja sana | 0.458874 | 0.215593 | 0.325533 | Acierto | Sí | Sí |
| `C9P5E2.jpg` | Hoja sana | Hoja sana | 0.649066 | 0.023243 | 0.327691 | Acierto | Sí | Sí |
| `C2P18E1.jpg` | Hoja sana | Hoja sana | 0.936996 | 0.040645 | 0.022358 | Acierto | No | Sí |
| `C8P6H1.jpg` | Hoja sana | Hoja sana | 0.482675 | 0.078540 | 0.438785 | Acierto | Sí | Sí |
| `C11P37E2.jpg` | Ácaro rojo | Roya | 0.026080 | 0.256660 | 0.717260 | Error | No | Sí |
| `C10P40E2.jpg` | Ácaro rojo | Ácaro rojo | 0.304176 | 0.396354 | 0.299470 | Acierto | Sí | Sí |
| `C12P13E2.jpg` | Ácaro rojo | Ácaro rojo | 0.015907 | 0.634424 | 0.349668 | Acierto | Sí | Sí |
| `C2P15E2.jpg` | Ácaro rojo | Ácaro rojo | 0.064083 | 0.766698 | 0.169218 | Acierto | No | Sí |
| `C2P22E2.jpg` | Ácaro rojo | Ácaro rojo | 0.011053 | 0.851159 | 0.137788 | Acierto | No | Sí |
| `C8P3H1.jpg` | Roya | Roya | 0.019804 | 0.096846 | 0.883350 | Acierto | No | Sí |
| `C8P12E1.jpg` | Roya | Hoja sana | 0.831809 | 0.059398 | 0.108792 | Error | No | Sí |
| `C10P36E2.jpg` | Roya | Roya | 0.005243 | 0.236136 | 0.758621 | Acierto | No | Sí |
| `C5P12E1.jpg` | Roya | Roya | 0.064158 | 0.159574 | 0.776268 | Acierto | No | Sí |
| `C1P9E2.jpg` | Roya | Ácaro rojo | 0.082159 | 0.815725 | 0.102115 | Error | No | Sí |

## A. Conclusión de integración

15/15 casos coincidieron entre inferencia directa y `POST /predict`. La máxima diferencia absoluta observada fue `0`. Coincidieron orden de clases, categoría, las tres puntuaciones y el estado de incertidumbre. Este resultado valida el cableado para la muestra, no la exactitud agronómica.

## B. Conclusión de clasificación

La predicción coincidió con la etiqueta auditada en 12/15 casos y difirió en 3/15. Hay 6 resultados por debajo de 0.70. Son conteos descriptivos de una muestra pequeña de VAL seleccionada para integración; no sustituyen las métricas completas de VAL ni TEST.

Errores conservados:

- `data/raw/coffee___red_spider_mite/C11P37E2.jpg`: etiqueta Ácaro rojo; predicción Roya.
- `data/raw/coffee___rust/C8P12E1.jpg`: etiqueta Roya; predicción Hoja sana.
- `data/raw/coffee___rust/C1P9E2.jpg`: etiqueta Roya; predicción Ácaro rojo.

Resultados inciertos:

- `data/raw/coffee___healthy/C4P26H1.jpg`: clase más probable Hoja sana, puntuación 0.634767.
- `data/raw/coffee___healthy/C12P1H1.jpg`: clase más probable Hoja sana, puntuación 0.458874.
- `data/raw/coffee___healthy/C9P5E2.jpg`: clase más probable Hoja sana, puntuación 0.649066.
- `data/raw/coffee___healthy/C8P6H1.jpg`: clase más probable Hoja sana, puntuación 0.482675.
- `data/raw/coffee___red_spider_mite/C10P40E2.jpg`: clase más probable Ácaro rojo, puntuación 0.396354.
- `data/raw/coffee___red_spider_mite/C12P13E2.jpg`: clase más probable Ácaro rojo, puntuación 0.634424.

## Casos indicados para la comprobación manual en navegador

- ejemplo con etiqueta Hoja sana: `data/raw/coffee___healthy/C4P26H1.jpg`
- ejemplo con etiqueta Ácaro rojo: `data/raw/coffee___red_spider_mite/C11P37E2.jpg`
- ejemplo con etiqueta Roya: `data/raw/coffee___rust/C8P3H1.jpg`
- resultado incierto de la selección: `data/raw/coffee___healthy/C4P26H1.jpg`
- clasificación incorrecta de la selección: `data/raw/coffee___red_spider_mite/C11P37E2.jpg`

### Estado y recorrido manual

La comprobación visual no forma parte del script. En esta ejecución quedó **pendiente** porque el inventario de automatización devolvió cero navegadores y cero aplicaciones controlables. No se afirman clics ni verificaciones visuales.

Con backend y frontend locales activos, abrir `http://127.0.0.1:3000` y seguir este recorrido:

1. Subir `data/raw/coffee___healthy/C4P26H1.jpg`, pulsar **Analizar hoja** y comprobar que la vista previa conserva ese nombre. Debe aparecer **Resultado incierto**, con **Categoría más probable: Hoja sana** y puntuaciones aproximadas 0.634767 / 0.249167 / 0.116066 en orden sana / ácaro rojo / roya.
2. Reemplazarla por `data/raw/coffee___red_spider_mite/C11P37E2.jpg`. Comprobar que el resultado anterior desaparece y que la vista previa cambia antes de analizar. Debe aparecer **Clasificación orientativa: Roya**, con puntuaciones aproximadas 0.026080 / 0.256660 / 0.717260. Es un error de clasificación conservado: la etiqueta auditada es ácaro rojo.
3. Pulsar **Analizar otra fotografía** y verificar que se limpian archivo, vista previa y resultado. Subir `data/raw/coffee___rust/C8P3H1.jpg` y analizar. Debe aparecer **Clasificación orientativa: Roya**, con puntuaciones aproximadas 0.019804 / 0.096846 / 0.883350.
4. Para probar sustitución durante una petición, iniciar el análisis de cualquiera de los tres archivos y seleccionar otro antes de recibir respuesta. La interfaz debe cancelar o invalidar la solicitud anterior y nunca mostrar un resultado asociado a la fotografía reemplazada.

Las diferencias visuales de redondeo deben limitarse al formato porcentual de la interfaz. Las fotografías permanecen en `data/raw`, no se copian a la guía y no se versionan en Git.
