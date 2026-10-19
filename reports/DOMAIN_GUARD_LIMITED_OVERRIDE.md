# Análisis limitado tras un rechazo del filtro de dominio

**Fecha:** 2026-10-18

**Estado de esta evidencia:** verificación local previa al despliegue; la URL pública se comprueba tras cada `push`

**Uso de TEST:** ninguno

## 1. Problema observado

El filtro experimental de dominio evita que CaféIA asigne una categoría de café a cualquier archivo que pueda decodificarse como imagen. Esta barrera es necesaria porque el clasificador principal siempre distribuye su salida entre tres categorías —hoja sana, roya y daño por ácaro rojo— incluso cuando la entrada no corresponde a una hoja de café.

Sin embargo, el filtro se construyó con representaciones de TRAIN de RoCoLe. Una hoja de café real fotografiada con otra cámara, fondo, distancia o iluminación puede quedar alejada de esas referencias. En la evaluación de desarrollo fijada, el filtro aceptó **141 de 153** hojas de café de VAL (92,16 %) y rechazó 12 hojas válidas.

El cambio documentado aquí no afirma que el sistema haya aprendido a reconocer todas las hojas de café. Su objetivo es conservar el rechazo seguro como primera respuesta y permitir que la persona solicite conscientemente una comparación limitada cuando considere que la fotografía sí contiene una hoja de café.

## 2. Decisión de diseño

Se conserva un flujo de dos decisiones en la interfaz:

1. La solicitud normal usa `POST /predict` sin autorización adicional.
2. Si el score de dominio está por debajo del umbral activo, la API responde `outside_domain`, no expone una categoría ni puntuaciones y la interfaz ofrece cargar otra fotografía.
3. Como alternativa explícita, la persona puede elegir **“Analizar de todos modos”**.
4. Esa acción vuelve a enviar el mismo archivo mediante una segunda solicitud multipart con `analyze_outside_domain=true`.
5. Si el filtro vuelve a rechazar la imagen, la API devuelve `outside_domain_analyzed`: muestra la comparación entre las tres categorías, pero mantiene `is_supported_image=false` y un mensaje que aclara que no se confirmó que la imagen fuera una hoja de café.

El backend no guarda la fotografía ni conserva estado entre ambas solicitudes. La imagen se vuelve a validar y decodificar en la segunda petición. No se añadió una caché, una sesión ni un token que retenga el contenido.

## 3. Contrato de la API

El campo `analyze_outside_domain` es un booleano multipart opcional y su valor predeterminado es `false`. Omitirlo mantiene el contrato anterior.

| Estado | Dominio | `is_supported_image` | Categoría y puntuaciones | Mensaje |
|---|---|---:|---|---|
| `classified` | Score igual o superior al umbral de dominio; puntuación máxima igual o superior a 0,70 | `true` | Sí | `null` |
| `uncertain` | Score igual o superior al umbral de dominio; puntuación máxima inferior a 0,70 | `true` | Sí | `null` |
| `outside_domain` | Score inferior al umbral y sin autorización adicional | `false` | No: categoría y score son `null`; `scores` es `[]` | Solicita una fotografía de una sola hoja de café |
| `outside_domain_analyzed` | Score inferior al umbral y `analyze_outside_domain=true` | `false` | Sí, únicamente como comparación solicitada | Aclara que la imagen no fue confirmada como café y que solo se comparan tres categorías |

En `outside_domain_analyzed`, `is_uncertain` conserva su significado original: indica si la mayor salida softmax está por debajo del umbral provisional `0.70`. No convierte la imagen en compatible con el dominio y no modifica `is_supported_image`.

## 4. Invariantes de seguridad y coherencia

- La primera respuesta fuera de dominio nunca incluye categoría interna, etiqueta legible, score máximo ni las tres puntuaciones.
- Solo la solicitud que contiene explícitamente `analyze_outside_domain=true` puede aceptar `outside_domain_analyzed` en la interfaz.
- El estado limitado siempre conserva `is_supported_image=false`.
- El permiso adicional no evita las comprobaciones de extensión, MIME, tamaño máximo, contenido real ni decodificación segura de la imagen.
- Una imagen que supera el filtro conserva el flujo normal aunque el cliente envíe el campo adicional.
- El orden de clases permanece `coffee___healthy`, `coffee___red_spider_mite`, `coffee___rust`.
- Las tres puntuaciones deben ser finitas, estar entre 0 y 1, sumar aproximadamente 1 y coincidir con la categoría de puntuación máxima.
- El score del filtro no se presenta como probabilidad de que la imagen sea café.
- Las salidas softmax no se presentan como probabilidades calibradas de acierto.
- El umbral `0.70` sigue controlando únicamente el mensaje de incertidumbre del clasificador; no detecta café/no café.
- El coordinador de solicitudes del frontend conserva una sola petición activa, cancela la anterior al sustituir la fotografía y descarta cualquier respuesta que pertenezca a una selección antigua.

## 5. Por qué no se redujo el umbral del filtro

El umbral de dominio desplegado continúa en **`0.6497240662574768`**. La siguiente auditoría se recalculó de forma read-only durante esta tarea a partir de `experiments/domain_guard_20261018-001/validation_scores.csv`, los 200 negativos de desarrollo ya fijados y la inferencia del clasificador sobre VAL. No se consultó TEST.

| Umbral de dominio | Hojas de VAL aceptadas | Tasa de aceptación | Hojas añadidas frente al umbral activo | Aciertos entre las añadidas | Negativos externos rechazados |
|---:|---:|---:|---:|---:|---:|
| 0,649724 (activo) | 141/153 | 92,16 % | 0 | No aplica | 200/200 |
| 0,625 | 145/153 | 94,77 % | 4 | No calculado en esta auditoría | 200/200 |
| 0,600 | 148/153 | 96,73 % | 7 | 3/7 | 200/200 |
| 0,580 | 150/153 | 98,04 % | 9 | No calculado en esta auditoría | 200/200 |
| 0,550 | 151/153 | 98,69 % | 10 | 3/10 | 200/200 |
| 0,500 | 152/153 | 99,35 % | 11 | No calculado en esta auditoría | 200/200 |

Entre las 12 hojas rechazadas por el umbral activo, el clasificador acertó 5 y falló 7. Reducir el corte a 0,60 recuperaría siete hojas, pero solo tres de esas siete recibirían la categoría anotada. A 0,55 se recuperarían diez, con solo tres aciertos entre ellas. Por tanto, aceptar más entradas no equivale a clasificarlas mejor.

Los 200 negativos concretos siguen rechazados hasta 0,50, pero esto no demuestra seguridad para otros objetos o plantas. Al reducir el umbral a 0,49 ya se aceptarían dos negativos de ese conjunto. Elegir un corte después de observar fotografías encontradas en Internet o estos resultados sería reajustar la barrera sobre ejemplos ya inspeccionados. La opción limitada conserva el umbral fijado y hace visible la incertidumbre de dominio sin degradar silenciosamente la primera barrera.

## 6. Cambios que no se realizaron

- No se entrenó ni ajustó ningún modelo.
- No se modificaron los pesos de MobileNet ni del filtro de dominio.
- No se cambió el checkpoint activo `models/mobilenet_finetuned_epoch6.pt`.
- No se cambió el artefacto `models/coffee_domain_guard.pt`.
- No se modificó el umbral de dominio `0.6497240662574768`.
- No se modificó el umbral softmax provisional `0.70`.
- No se cambió el manifiesto, ninguna partición ni una etiqueta.
- No se consultaron imágenes, etiquetas, predicciones ni métricas de TEST.
- Las fotografías exploratorias de Internet no se incorporaron a TRAIN, VAL ni a una evaluación independiente.

## 7. Pruebas ejecutadas hasta ahora

### Backend

Se ejecutó:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\backend -q
```

Resultado: **20 pruebas correctas** y una advertencia de deprecación de Starlette/AnyIO sin efecto sobre el resultado.

Las pruebas cubren, entre otros casos:

- omitir el campo conserva `outside_domain` sin scores;
- enviar `analyze_outside_domain=false` conserva el rechazo inicial;
- enviar `true` devuelve `outside_domain_analyzed`, tres scores e `is_supported_image=false`;
- el permiso no cambia una imagen aceptada por el filtro;
- un booleano multipart inválido produce HTTP 422;
- la rama real de `Predictor.predict` usa los mismos logits antes y después del permiso y solo cambia qué información se expone;
- los archivos inválidos, vacíos, con MIME incoherente y mayores de 10 MB siguen siendo rechazados;
- los errores internos no se exponen al cliente.

### Frontend

Se ejecutó desde `frontend/`:

```powershell
npm.cmd run test:request-flow
```

Resultado: **16 pruebas correctas**.

Las pruebas comprueban:

- validación estricta de los cuatro estados;
- rechazo de un `outside_domain` que filtre una categoría;
- rechazo de un resultado limitado que afirme `is_supported_image=true`;
- aceptación del resultado limitado solo cuando la solicitud fue explícita;
- doble envío, cancelación y sustitución segura de fotografía;
- consentimiento y validación local de formato/tamaño.

## 8. Verificaciones completadas antes del despliegue

- `npm.cmd run build`: compilación de producción correcta con TypeScript y cuatro páginas estáticas generadas.
- `/health`: cargó `mobilenet-v3-small-finetuned-epoch6`, SHA256 `4ab4e52fc3d417fe5fb126ff1e5b346f080c55ffa80232cffd5d6e6622e46c94`, filtro SHA256 `8060ef83e4a018d6a49e22fc5b59162f4ec6cbba90482e27d7896c79106d90e7`, orden de clases esperado y umbral `0.70`.
- Primera petición real con `Fury_01.jpg`: `outside_domain`, score de dominio `0.2413930595`, categoría `null` y `scores=[]`.
- Segunda petición del mismo archivo con `analyze_outside_domain=true`: `outside_domain_analyzed`, el mismo score de dominio `0.2413930595`, `is_supported_image=false` y puntuaciones hoja sana `0.7358204126`, ácaro rojo `0.0244774930` y roya `0.2397020906`. Este ejemplo demuestra el contrato, no una identificación correcta del perro.
- El verificador de navegador confirmó a 390, 768 y 1440 píxeles la disposición adaptable; a 390 y 1440 verificó además el rechazo y la comparación limitada.
- La sustitución de una fotografía durante una petición mantuvo visible el archivo nuevo, ocultó el resultado obsoleto y volvió a habilitar el análisis.
- Se comprobó el resultado incierto, una clasificación normal, error de conexión, foco del selector por teclado y retirada del consentimiento.
- La inspección visual real de las capturas `outside_domain_1440.png`, `outside_domain_analyzed_390.png` y `outside_domain_analyzed_1440.png` confirmó que no aparecen identificadores internos y que el aviso de alcance acompaña las puntuaciones.

La evidencia local se conserva en `reports/web_ui_verification/browser_checks.json` y sus PNG. Las capturas están ignoradas por Git porque contienen fotografías locales de comprobación.

## 9. Riesgos y limitaciones restantes

- El análisis limitado puede mostrar una categoría de café para un perro, otra planta u otro objeto si la persona decide continuar. La advertencia y `is_supported_image=false` son parte obligatoria del resultado.
- El campo multipart expresa una decisión del cliente, pero el servidor no exige criptográficamente una solicitud anterior. Un consumidor directo de la API puede enviarlo en su primera petición. No es un control de autenticación.
- El filtro sigue rechazando algunas hojas de café válidas y puede aceptar entradas desconocidas. Los 200 negativos evaluados no representan todas las imágenes posibles.
- Una fotografía de Google no aporta por sí misma procedencia, licencia ni etiqueta verificable; no sirve para reajustar ni evaluar el modelo.
- Este cambio mejora el manejo de falsos rechazos en la interfaz, pero no mejora la exactitud del clasificador de sana, roya y ácaro rojo.
- El modelo conserva las limitaciones documentadas de RoCoLe, en particular la menor representación y el desempeño variable de ácaro rojo.
- No se puede prometer identificación correcta de todas las hojas de café con los datos actuales. Mejorar generalización requiere datos externos de café con procedencia y etiquetas verificadas, diversidad de captura y separación por planta o sesión, bajo un protocolo nuevo que no reutilice TEST v1 para decidir.
- La API pública sigue requiriendo controles operativos del servicio —observabilidad, límites de solicitudes y capacidad— si se ofrece a un volumen real. CORS no sustituye esos controles.

## 10. Evidencia relacionada

- Diseño y resultados del filtro: `reports/DOMAIN_GUARD_RESULTS.md`.
- Protocolo original del filtro: `reports/DOMAIN_GUARD_PROTOCOL.md`.
- Protocolo futuro de generalización: `reports/DOMAIN_GENERALIZATION_V2_PROTOCOL.md`.
- Scores usados en la auditoría: `experiments/domain_guard_20261018-001/validation_scores.csv`.
- Contrato y validación del backend: `backend/main.py` y `tests/backend/test_api_contract.py`.
- Contrato y coordinación del frontend: `frontend/lib/prediction.ts`, `frontend/lib/latest-request.ts` y sus pruebas.
