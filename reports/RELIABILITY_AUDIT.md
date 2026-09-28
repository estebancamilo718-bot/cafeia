# Auditoría del flujo de identificación de CaféIA

**Fecha:** 2026-09-27
**Alcance de datos:** código, checkpoint activo, TRAIN y resultados de VAL ya archivados. No se abrieron imágenes de TEST, no se calcularon métricas nuevas de TEST y no se entrenó ningún modelo.

## Estado fijado

- Checkpoint cargado: `models/mobilenet_finetuned_epoch6.pt`.
- Identificador expuesto por `/health`: `mobilenet-v3-small-finetuned-epoch6`.
- SHA-256 comprobado: `4ab4e52fc3d417fe5fb126ff1e5b346f080c55ffa80232cffd5d6e6622e46c94`.
- Época seleccionada declarada: 6.
- SHA-256 del manifiesto: `1ea21d6b2b480b830065c5d4d1d90f531234cc2aa244d7bb98c5873363866dab`.
- Orden fijado de salidas: `coffee___healthy`, `coffee___red_spider_mite`, `coffee___rust`.
- Umbral provisional conservado: `0.70`.

No se reemplazó el modelo activo, el manifiesto ni ningún resultado histórico.

## Recorrido comprobado

| Etapa | Implementación comprobada | Evidencia |
|---|---|---|
| Selección | La interfaz acepta extensiones JPG/JPEG/PNG, MIME JPEG/PNG y hasta 10 MiB. | `frontend/lib/analysis-input.ts` y prueba unitaria. |
| Validación del servidor | FastAPI vuelve a validar extensión, MIME y tamaño; Pillow verifica el contenido y que el formato real coincida. No escribe el archivo recibido. | `backend/main.py`; respuestas reales 400, 415 y 413. |
| Orientación y color | `ImageOps.exif_transpose` y conversión RGB. | `backend/main.py` y `src/common.py`. |
| Preprocesamiento | `Resize((224, 224))`, `ToTensor()` y normalización ImageNet con media `[0.485, 0.456, 0.406]` y desviación `[0.229, 0.224, 0.225]`. | El backend instancia exactamente `transform(training=False)` de `src/common.py`. |
| Modelo | MobileNetV3 Small ajustado; se reconstruye la arquitectura, se carga el `state_dict` y se deja en evaluación. | Carga estricta mediante `load_checkpoint`; `/health` comprobado. |
| Índices y clases | El backend aborta si `checkpoint["classes"]` no coincide exactamente con el orden fijado. | Comprobación en `Predictor.__init__` y en el verificador. |
| Puntuaciones | `softmax` sobre las tres salidas, máximo para la categoría y las tres puntuaciones completas. | Comparación directa contra POST `/predict`. |
| Respuesta | Categoría interna, etiqueta legible, puntuación máxima, tres puntuaciones, incertidumbre y umbral. | Esquema Pydantic `PredictionResponse`. |
| Interfaz | Valida la forma de la respuesta antes de mostrarla y usa solo etiquetas legibles. Mantiene el analizador como primera sección. | `frontend/app/page.tsx`. |

### Equivalencia numérica real

Se usó exclusivamente la imagen de TRAIN `data/raw/coffee___healthy/C10P12E1.jpg`. La inferencia directa con `load_checkpoint` y `transform(False)` y la llamada HTTP al backend devolvieron:

| Clase | Evaluador directo | POST `/predict` | Diferencia absoluta |
|---|---:|---:|---:|
| Hoja sana | 0.8189849257 | 0.8189849257 | 0.0 |
| Ácaro rojo | 0.0236105081 | 0.0236105081 | 0.0 |
| Roya | 0.1574045569 | 0.1574045569 | 0.0 |

La categoría, el orden y todas las puntuaciones coincidieron. El comando reproducible es:

```powershell
.\.venv\Scripts\python.exe -m src.verify_api_flow --base-url http://127.0.0.1:8000 --checkpoint models/mobilenet_finetuned_epoch6.pt --expected-sha256 4ab4e52fc3d417fe5fb126ff1e5b346f080c55ffa80232cffd5d6e6622e46c94
```

## Fallos encontrados y correcciones

### 1. Sustitución durante una solicitud

Antes, el selector y el arrastre quedaban bloqueados durante `loading`. Además, no existía identidad de solicitud: una respuesta se aplicaba con `setResult` sin comprobar que aún correspondiera a la selección vigente.

Ahora se permite reemplazar la fotografía durante el análisis. `LatestRequestCoordinator` aborta la petición anterior y usa contadores independientes de solicitud y selección; una respuesta obsoleta no puede actualizar resultado, error ni estado de carga de la solicitud nueva.

### 2. Doble envío

Antes, la única barrera era el estado React `loading`, cuya actualización no es sincrónica con dos eventos consecutivos. Ahora existe un bloqueo sincrónico dentro del coordinador; un segundo `begin()` devuelve `null` hasta finalizar o cancelar la solicitud vigente. El botón también sigue deshabilitado visualmente durante la carga.

### 3. Respuesta API asumida sin validación

Antes, la interfaz convertía el JSON a `Prediction` mediante una aserción de TypeScript. Ahora comprueba en ejecución categorías, tres puntuaciones únicas, tipos y rangos antes de mostrar la respuesta. Una respuesta incompatible produce un error visible en vez de asociar datos incompletos a la foto.

## Escenarios verificados

| Escenario | Verificación real | Resultado |
|---|---|---|
| Imagen válida | Inferencia directa y POST real con una imagen de TRAIN | HTTP 200; puntuaciones idénticas. |
| Contenido no-imagen con nombre `.jpg` | POST real | HTTP 400. |
| JPEG presentado como PNG | POST real | HTTP 415. |
| Archivo de 10 MiB + 1 byte | POST real | HTTP 413. |
| Formato/tamaño en la interfaz | Prueba unitaria de `validateSelectedImage` | Caso válido aceptado; formato y exceso rechazados. |
| Doble envío | Prueba unitaria del coordinador | Segundo inicio bloqueado. |
| Reemplazo pendiente | Prueba unitaria del coordinador | Solicitud antigua abortada y respuesta marcada obsoleta. |
| Cancelación | Prueba unitaria del coordinador | Respuesta tardía no aplicable. |
| Backend desconectado | Prueba unitaria de la traducción del `TypeError` de `fetch` | Mensaje específico para comprobar que el backend esté encendido. |
| Compilación | `npm.cmd run build` | Correcta, incluido TypeScript. |
| Servicios | GET real a frontend y `/health` | Ambos HTTP 200; portada contiene título y selector. |

`npm.cmd run test:request-flow` ejecutó 5 pruebas: 5 correctas, 0 fallidas.

La automatización visual no estuvo disponible: el proveedor de control devolvió inventarios vacíos de aplicaciones y navegadores. Por ello no se afirma haber realizado clics, arrastre, selección de archivo ni revisión visual en navegador en esta auditoría. Esos recorridos manuales siguen pendientes, aunque su lógica, la API real y la compilación sí fueron comprobadas.

## TRAIN y entrenamiento activo

La auditoría previa establece que cada prefijo `CxPy` representa de forma fuertemente sustentada una unidad-planta; la expansión literal de `C` y `P` permanece pendiente. Los conteos siguientes no son mutuamente excluyentes porque una planta puede aportar imágenes de varias clases.

| Clase | Imágenes TRAIN | Prefijos-planta `CxPy` distintos | Grupos del manifiesto tras unir relaciones por duplicados | Peso de clase |
|---|---:|---:|---:|---:|
| Hoja sana | 448 | 215 | 208 | 0.6547619 |
| Ácaro rojo | 93 | 67 | 66 | 3.1541219 |
| Roya | 339 | 189 | 182 | 0.8652901 |

TRAIN contiene 880 imágenes, 223 prefijos-planta y 214 grupos conectados del manifiesto. En ácaro rojo, 41 plantas aportan una sola imagen y 26 aportan dos. Hay 209 prefijos-planta con más de una de las tres etiquetas, coherente con que la etiqueta corresponde a la fotografía/hoja y no a un diagnóstico único de toda la planta.

- Los pesos se calculan solo con TRAIN mediante `N / (K × n_clase)` y coinciden exactamente con la configuración archivada.
- La pérdida es entropía cruzada ponderada; los pesos de clase ya existen y no son una novedad propuesta.
- El `DataLoader` usa `shuffle=True`, lote 16 y ningún `sampler` especial. No hay sobremuestreo explícito.
- El ajuste activo entrenó `features.10`, `features.11`, `features.12` y `classifier.3`; Adam usó `1e-5` y `1e-4`, respectivamente. BatchNorm conservó sus estadísticas.
- El preprocesamiento activo sigue siendo el redimensionamiento directo a 224×224. La variante v2 con proporción y relleno ya fue descartada por VAL y no se integró.
- La comprobación local encontró cero desacuerdos entre `label` y la carpeta de las 880 rutas TRAIN. La comparación original ya archivada verificó las anotaciones de TRAIN/VAL y no se repitió.

## Limitaciones vigentes

- En VAL archivado, ácaro rojo sigue siendo la clase más débil: precision 0.357143, recall 0.483871 y F1 0.410959 sobre 31 imágenes. Sus errores incluyen 14 casos ácaro → roya; también existen 19 casos roya → ácaro.
- Las 67 plantas con ácaro en TRAIN representan mucha menos diversidad documentada que las otras clases. El peso de pérdida corrige contribución numérica, pero no crea plantas, condiciones de captura ni manifestaciones nuevas.
- CaféIA solo separa sana, roya y ácaro rojo dentro del dominio aprendido. No reconoce otras enfermedades, carencias nutricionales, daños mecánicos ni severidad.
- Las puntuaciones softmax no son probabilidades calibradas de acierto. El umbral 0.70 solo gobierna el mensaje de incertidumbre; no detecta hojas de otras especies, objetos ni fotos inutilizables.
- No hay todavía una evaluación independiente de rechazo fuera de dominio ni de calidad fotográfica.

La propuesta única para el siguiente experimento y el protocolo de rechazo se fijan en `reports/NEXT_EXPERIMENT_PROTOCOL.md`.
