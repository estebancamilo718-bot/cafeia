# Aceptación y rechazo de imágenes en CaféIA

- **Fecha:** 2026-11-02
- **Estado:** contrato público vigente
- **Entrenamiento realizado en este cambio:** ninguno
- **Uso de TEST:** ninguno

## Objetivo del cambio

La aplicación ahora comunica de forma separada y explícita:

1. si el archivo es técnicamente válido;
2. si el filtro basado en el modelo acepta o rechaza la imagen para el análisis;
3. si una imagen aceptada recibe una clasificación o un resultado incierto.

Se retiró del producto público la opción **Analizar de todos modos** y el parámetro `analyze_outside_domain`. Un rechazo del filtro ya no puede mostrar una categoría ni las puntuaciones de las tres clases.

## Flujo vigente

| Estado | Regla | Respuesta visible |
|---|---|---|
| Archivo no válido | Extensión, MIME, contenido o tamaño no admitidos | Error técnico; no se ejecuta el modelo |
| Imagen rechazada | Score de dominio menor que `0.6497240662574768` | `outside_domain`, sin categoría ni puntuaciones |
| Imagen aceptada y resultado incierto | Score de dominio suficiente; mayor softmax menor que `0.70` | `uncertain`, tres puntuaciones y aviso de incertidumbre |
| Imagen aceptada y clasificada | Score de dominio suficiente; mayor softmax igual o mayor que `0.70` | `classified`, tres puntuaciones y clasificación orientativa |

El umbral `0.70` no acepta ni rechaza una fotografía como hoja de café. Solo controla el mensaje de incertidumbre después de que el filtro de dominio haya aceptado la imagen.

## Modelo que realiza el rechazo

El artefacto activo es `models/coffee_domain_guard.pt`, SHA-256 `8060ef83e4a018d6a49e22fc5b59162f4ec6cbba90482e27d7896c79106d90e7`. Usa la representación penúltima normalizada del MobileNet activo y calcula la media de las cinco mayores similitudes coseno contra 880 embeddings de TRAIN. El backend verifica al arrancar:

- SHA-256 del clasificador y del filtro;
- checkpoint y manifiesto asociados;
- orden de clases;
- dimensión de la representación.

No se cambiaron pesos, referencias ni umbrales en esta implementación. El cambio convierte el rechazo existente en una decisión pública no evadible.

## Instrucciones mostradas antes de cargar

1. Colocar una sola hoja completa sobre un fondo sencillo.
2. Usar luz uniforme, sin filtros, reflejos fuertes ni sombras.
3. Enfocar la hoja y evitar que quede cortada, lejana o movida.
4. Fotografiar haz y envés por separado y subir una imagen cada vez.

Estas instrucciones ayudan a repetir la captura, pero no implican que el filtro identifique la causa específica de un rechazo. En particular, el modelo no tiene salidas separadas para desenfoque, oscuridad, varias hojas o recortes.

## Evidencia disponible y límites

La evaluación de desarrollo ya fijada, sin TEST, registró:

- 141/153 hojas de café de VAL aceptadas;
- 12/153 hojas válidas rechazadas: 3 sanas, 1 de ácaro rojo y 8 de roya;
- 200/200 negativos externos concretos rechazados.

Estos resultados demuestran el comportamiento en ese conjunto concreto, no un detector universal. Una imagen aceptada todavía puede no ser café y una hoja de café válida puede ser rechazada. Por eso el texto de rechazo dice que la imagen no alcanzó la similitud mínima; no afirma que la hoja no sea de café.

## Verificación ejecutada

El 2026-11-02 se obtuvieron estos resultados:

- backend: `23 passed`; incluye rechazo sin categoría ni scores, campo antiguo incapaz de omitirlo y regla inclusiva en la frontera del umbral;
- frontend: `16 passed`; incluye aceptación, incertidumbre y rechazo estricto del estado retirado `outside_domain_analyzed`;
- compilación Next.js: correcta, incluida la comprobación de TypeScript;
- API real con los artefactos activos: `C4P26H1.jpg` fue aceptada con resultado incierto; `C2P18E1.jpg` fue aceptada y clasificada; `Fury_01.jpg` fue rechazada con categoría nula y `scores=[]`;
- contrato OpenAPI: el cuerpo multipart de `POST /predict` solo publica el campo obligatorio `file`; al enviar además el antiguo `analyze_outside_domain=true` con `Fury_01.jpg`, la respuesta real siguió siendo `outside_domain` sin categoría ni puntuaciones;
- navegador Chromium en 390, 768 y 1440 px: instrucciones antes del selector, aceptación explícita, incertidumbre separada, rechazo sin puntuaciones ni bypass, reemplazo durante una solicitud, teclado, consentimiento y recuperación tras desconexión;
- inspección visual de las capturas a 390, 768 y 1440 px: las instrucciones, las dos columnas de escritorio y los estados de aceptación/rechazo permanecen legibles y sin desbordes observados.

El resumen estructurado del navegador está en `reports/web_ui_verification/browser_checks.json`. Las capturas y las fotografías usadas por la verificación permanecen fuera de Git.

La evidencia histórica de la opción retirada se conserva en `reports/DOMAIN_GUARD_LIMITED_OVERRIDE.md`; no describe el contrato público vigente.
