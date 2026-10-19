# Verificación de la interfaz de CaféIA

> **Actualización visual 2026-10-18:** se incorporó una cabecera completa, una marca SVG propia, una portada editorial inspirada en la jerarquía visual de AgroTolima y tarjetas fotográficas para las tres categorías. Se retiraron las expresiones “Sistema de apoyo visual” y “Referencia educativa”, así como el bloque general de aclaración solicitado. Las fuentes y atribuciones necesarias permanecen dentro de “Ver detalles”.

> **Comprobación 2026-10-18:** la revisión automatizada se repitió contra el backend con el filtro de dominio cargado. Además de los estados aceptado, incierto y desconexión, se envió una fotografía externa de un perro: la página mostró “No se pudo confirmar la hoja”, incluyó la instrucción de cargar una sola hoja de café, ocultó las puntuaciones de las tres clases y no expuso identificadores internos.

> **Comprobación 2026-10-14:** se rediseñó la interfaz del analizador con una identidad visual más sobria, jerarquía tipográfica consistente, paneles de entrada/resultado alineados, estados de carga/error/resultado unificados y una guía educativa secundaria. La revisión automatizada en Edge produjo capturas reales a 390, 768 y 1440 px y verificó el flujo contra el backend activo.

> **Actualización de interfaz:** la navegación actual conserva “Analizar” y “Guía de hojas”. La antigua tercera sección “Sobre el modelo” se retiró de la página; sus cifras permanecen en `README.md`, `reports/FINAL_TEST_RESULTS.md` y la evidencia histórica siguiente.

> **Comprobación 2026-10-04:** las 5 pruebas del flujo frontend, TypeScript y `next build` finalizaron correctamente; el HTML local respondió 200, mostró “Agente IA para hojas de café” y no incluyó “Evaluación del prototipo” ni “Sobre el modelo”. Edge y el navegador integrado no estuvieron disponibles para una nueva inspección visual, por lo que las capturas y la tabulación manual siguen pendientes.

**Fecha de la última comprobación:** 2026-10-18
**URL local:** `http://localhost:3000`

## Comprobaciones realizadas

| Comprobación | Resultado |
|---|---|
| Compilación de producción | `npm.cmd run build` finalizó correctamente con Next.js 16.3.5 y webpack; TypeScript y las páginas estáticas se generaron sin error |
| Pruebas frontend | 11/11 verificaciones pasaron, incluidas concurrencia, consentimiento y validación de las respuestas clasificadas o fuera de dominio |
| Frontend local | HTTP 200 en `/` |
| Contenido inicial | El HTML incluye “Analiza una hoja de café” antes de la guía |
| Navegación | La cabecera incluye la marca CaféIA, “Analizar”, “Categorías”, acceso a privacidad y llamada principal; en móvil conserva la marca y el acceso directo al analizador |
| Categorías | Incluye “Explora las hojas por categoría”, las tres fotografías autorizadas y no muestra cadenas `coffee___` |
| Diseño adaptable | El analizador usa una columna a 390 px y dos a 768/1440 px; las categorías usan una, dos y tres columnas respectivamente, sin desbordamiento horizontal |
| Estados | Se capturaron el estado inicial, resultado incierto, resultado aceptado y error de conexión |
| Fuera de dominio | Se capturó el rechazo de una fotografía de perro; no se mostraron categorías ni puntuaciones de café |
| Sustitución | La prueba reemplazó una imagen antes de analizar y confirmó que la interfaz mostró el archivo vigente |
| Consentimiento inicial | El modal mostró la finalidad, la ausencia de almacenamiento y la ausencia de cookies publicitarias o analíticas |
| Rechazo | “Continuar sin analizar” cerró el modal y mantuvo deshabilitado el selector de archivos |
| Aceptación | “Aceptar y continuar” persistió la decisión versionada en `localStorage` y habilitó el selector |
| Retirada | La gestión desde el pie de página volvió a bloquear el selector y eliminó la selección actual |
| Encabezados de seguridad | Se comprobaron CSP, `nosniff`, `DENY` para iframes y permisos de cámara, micrófono y geolocalización deshabilitados |
| Fotografías | Los tres recursos responden HTTP 200, `image/jpeg`, con tamaños 228.648, 212.178 y 313.519 bytes |
| Contraste calculado | Botón blanco/verde 12,42:1; texto secundario sobre blanco 6,53:1; terracota oscuro/crema 6,52:1 |
| API | `/health` respondió `status: ok`, modelo `mobilenet-v3-small-finetuned-epoch6`, época 6, hashes esperados del modelo y filtro, y `domain_guard_loaded: true` |
| CORS local | El origen permitido `http://localhost:3000` recibió `access-control-allow-origin`; un origen ajeno no recibió ese encabezado |
| Predicción real, estado orientativo | El ejemplo sano de TRAIN obtuvo puntuación máxima 0,846378 y `is_uncertain: false` |
| Predicción real, estado incierto | El ejemplo de roya de TRAIN obtuvo puntuación máxima 0,513834 y `is_uncertain: true` |
| Predicción real adicional | El ejemplo de ácaro rojo de TRAIN obtuvo puntuación máxima 0,771145 y `is_uncertain: false` |
| Archivo inválido | Un archivo Markdown declarado como JPEG fue rechazado con HTTP 415 |
| Modelo y umbral | El backend continuó usando el checkpoint activo fijado y umbral 0,70 |

Las predicciones anteriores son pruebas funcionales sobre ejemplos de TRAIN; no son métricas ni una reevaluación del modelo.

## Accesibilidad comprobable en código

- Enlace de salto al analizador.
- `nav` con nombre accesible y enlaces de sección.
- Selector con `label`, ayuda asociada, tipo/tamaño aceptado y texto de reemplazo.
- Estado dinámico con `aria-live` y `aria-busy`; errores con `role="alert"`.
- Botón de análisis deshabilitado sin archivo o durante la petición.
- Fichas con texto alternativo específico y controles nativos `details/summary` accionables con teclado.
- Indicadores de foco visibles para enlaces, controles, botones y resúmenes.
- Objetivos interactivos principales de al menos 40–44 px de alto.
- Estructura adaptable declarada: una columna por defecto, dos para el analizador desde 768 px; las categorías pasan a dos columnas desde 680 px y tres desde 1120 px.
- Respeto de `prefers-reduced-motion`.

## Evidencia visual y alcance

`scripts/verify_frontend.mjs` controló Edge en modo local, ajustó el viewport a 390, 768 y 1440 px, capturó tanto el analizador como las tarjetas en esos tamaños, comprobó las tres pestañas del aviso, rechazo, aceptación y retirada, usó imágenes de VAL solo para comprobación local, realizó predicciones reales y guardó el resumen en `reports/web_ui_verification/browser_checks.json`. Las fotografías de VAL y las capturas PNG permanecen fuera de Git.

La comprobación confirmó foco programático y nombres accesibles del selector. Sigue siendo recomendable que una persona recorra manualmente toda la página con `Tab` y un lector de pantalla antes de una publicación pública; la automatización no sustituye esa revisión humana.
