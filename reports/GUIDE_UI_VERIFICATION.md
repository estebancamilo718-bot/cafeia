# Verificación de la guía visual de CaféIA

> **Actualización de interfaz:** la navegación actual conserva “Analizar” y “Guía visual”. La antigua tercera sección “Sobre el modelo” se retiró de la página; sus cifras permanecen en `README.md`, `reports/FINAL_TEST_RESULTS.md` y la evidencia histórica siguiente.

> **Comprobación 2026-10-04:** las 5 pruebas del flujo frontend, TypeScript y `next build` finalizaron correctamente; el HTML local respondió 200, mostró “Agente IA para hojas de café” y no incluyó “Evaluación del prototipo” ni “Sobre el modelo”. Edge y el navegador integrado no estuvieron disponibles para una nueva inspección visual, por lo que las capturas y la tabulación manual siguen pendientes.

**Fecha:** 2026-09-26
**URL local:** `http://localhost:3000`

## Comprobaciones realizadas

| Comprobación | Resultado |
|---|---|
| Compilación de producción | `npm.cmd run build` finalizó correctamente con Next.js 16.3.5; TypeScript y las 3 páginas estáticas se generaron sin error |
| Frontend local | HTTP 200 en `/` |
| Contenido inicial | El HTML incluye “Analiza una hoja de café” antes de la guía |
| Navegación | El HTML incluye “Analizar”, “Guía de hojas” y “Sobre el modelo” con destinos internos |
| Guía | El HTML incluye “Conoce las hojas de café” y no muestra cadenas `coffee___` |
| Fotografías | Los tres recursos responden HTTP 200, `image/jpeg`, con tamaños 228.648, 212.178 y 313.519 bytes |
| Contraste calculado | Texto principal verde/crema 11,53:1; texto secundario 6,83:1; terracota/crema 5,78:1; botón blanco/terracota 5,51:1; foco terracota/crema 5,78:1 |
| API | `/health` respondió `status: ok`, modelo `mobilenet-v3-small-finetuned-epoch6`, época 6 y SHA-256 esperado |
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
- Estructura adaptable declarada: una columna por defecto, dos para el analizador desde 768 px y tres para la guía desde 1024 px.
- Respeto de `prefers-reduced-motion`.

## Limitación de esta sesión

Se intentó abrir la aplicación mediante las superficies disponibles de Chrome, navegador integrado y Edge, pero las tres devolvieron `Browser is not available`. Por tanto, **no se afirma una inspección visual ni una prueba real de tabulación a 390, 768 y 1440 px**. Esas revisiones quedan pendientes en un navegador disponible. La compilación, la estructura adaptable del código, las respuestas HTTP y el flujo real del backend sí fueron comprobados.

## Revisión visual pendiente

En un navegador con herramientas de desarrollo:

1. abrir `http://localhost:3000`;
2. comprobar a 390, 768 y 1440 px que no exista desplazamiento horizontal y que el analizador siga visible primero;
3. recorrer con `Tab` la navegación, el selector, “Analizar hoja”, el enlace a la ficha, “Analizar otra fotografía” y los tres “Ver detalles”;
4. cargar y reemplazar una imagen;
5. usar el ejemplo `frontend/public/guide/roya-rocole-c10p27e2.jpg` para comprobar que “Resultado incierto” permanezca como título principal y que “Consultar las tres categorías” lleve a la guía;
6. detener temporalmente el backend y confirmar el mensaje de conexión, luego reiniciarlo.
