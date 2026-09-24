# Verificación

Preparación ejecutada sobre 1560 imágenes del ZIP. Se excluyeron 24 archivos (12 pares idénticos con etiquetas contradictorias) y se eliminaron 55 copias redundantes de la misma clase: quedan 1481 imágenes. Listado de conflictos en dataset_audit.json; no se cambió ninguna etiqueta. Revisar con la fuente original antes de reincorporarlas.

Particiones: 880 entrenamiento, 301 validación y 300 prueba. Comprobado: tres clases por partición; ningún hash SHA256 ni grupo compartido entre particiones. Los prefijos CxPy relacionados mediante imágenes duplicadas se unen antes de dividir para reducir filtración entre grupos.

## Modelo disponible

`models/mobilenet.pt` contiene ahora el mejor estado de una corrida nueva de 10 épocas en CPU, con semilla 42 y el mismo SHA256 del manifiesto. La época 9 obtuvo el mejor F1 macro de validación: 0.6327072392132633. El checkpoint y el historial originales de una época quedaron respaldados sin sobrescritura en `experiments/mobilenet_1ep_backup_20260920-180305/`; su F1 fue 0.61008051130533. Los resultados completos de la corrida nueva están en `experiments/mobilenet_10ep_20260920-181113/`. No se ejecutó evaluación sobre prueba.

## Verificación local inicial de CaféIA (20 de septiembre de 2026, checkpoint de una época)

- `python -m compileall -q backend src`: correcto.
- `GET /health`: HTTP 200; modelo `mobilenet` cargado una vez y las tres clases del checkpoint informadas.
- Predicción real por `POST /predict` con `data/raw/coffee___healthy/C10P12E1.jpg`, una imagen del entrenamiento: HTTP 200. Resultado funcional `coffee___healthy`; puntuaciones `coffee___healthy` 0.666461706161499, `coffee___red_spider_mite` 0.13269411027431488 y `coffee___rust` 0.2008441984653473. Marcada como incierta porque 0.666461706161499 es menor que el umbral provisional 0.70. Estas puntuaciones softmax no son probabilidades calibradas de acierto.
- `LEEME.md` enviado como `falso.jpg` y `image/jpeg`: HTTP 400, contenido inválido rechazado.
- JPEG real declarado como PNG: HTTP 415, discordancia de formato rechazada.
- Cuerpo de 10 MB + 1 byte: HTTP 413, límite de tamaño aplicado.
- CORS: `http://localhost:3000` aceptado y `https://example.com` rechazado.
- `npm.cmd run build`: compilación de producción de Next.js 16.3.5 y comprobación TypeScript correctas.
- Servidor de producción del frontend: HTTP 200 en `http://127.0.0.1:3000`; HTML contiene el nombre CaféIA y el flujo “Analiza una hoja”.

No estuvo disponible la automatización visual del navegador integrado, por lo que no se afirma una revisión visual por clics. La integración de predicción sí se comprobó contra el backend real y la interfaz quedó conectada a ese endpoint mediante `NEXT_PUBLIC_API_URL`.

## Corrida nueva de 10 épocas y reinicio de CaféIA (20 de septiembre de 2026)

- Se ejecutó `python -m src.train --model mobilenet --epochs 10` en CPU. Es una corrida nueva desde los pesos preentrenados; el script no carga el checkpoint anterior para continuar el entrenamiento.
- El historial tiene 10 épocas y el mejor F1 macro de validación fue 0.6327072392132633 en la época 9. `models/mobilenet.pt` contiene ese mejor estado, no el estado de la época 10.
- Diferencia frente a la corrida inicial exacta 0.61008051130533: +0.022626727907933297, aproximadamente +3.71 % relativo. No se interpreta como garantía de mejora fuera de esta validación.
- No se ejecutó `src.evaluate`, no se consultó prueba y el umbral permaneció en 0.70.
- El SHA256 del manifiesto permaneció `1ea21d6b2b480b830065c5d4d1d90f531234cc2aa244d7bb98c5873363866dab`.
- FastAPI se reinició después de seleccionar el checkpoint. `GET /health` y el frontend respondieron HTTP 200.
- Comprobación funcional mediante el endpoint real consumido por la web, con una imagen de entrenamiento `data/raw/coffee___rust/C10P12E2.jpg`: roya 0.5930039286613464, ácaro rojo 0.32267072796821594 y hoja sana 0.0843253806233406; indicador de incertidumbre activo. Esta predicción confirma el funcionamiento técnico y no se usa como evaluación.
- El origen `http://127.0.0.1:3000` recibió el encabezado CORS permitido en la respuesta de predicción.

La prueba exploratoria externa informada por el usuario —roya 53.8 %, ácaro rojo 32.8 % y sana 13.4 %— está registrada con el respaldo del checkpoint inicial en `experiments/mobilenet_1ep_backup_20260920-180305/NOTAS.md`. No se trató como etiqueta verificada ni como evaluación formal.

## Comparación explícita en validación (21 de septiembre de 2026)

Se evaluaron los mejores checkpoints de MobileNetV3 Small, CNN pequeña y ResNet18 exclusivamente sobre las mismas 301 imágenes de `val`, con semilla 42 y el manifiesto sin cambios. No se consultó `test`. MobileNet obtuvo F1 macro 0.6327072392; ResNet18, 0.5947396341; y CNN, 0.4385713520. La tabla completa, las métricas por clase y las tres matrices están en `reports/VALIDATION_MODEL_COMPARISON.md`.

ResNet18 quedó archivado sin sobrescritura en `experiments/resnet18_10ep_20260921-130620/`, con configuración, historial, mejor checkpoint (época 8), duración, métricas, matriz, predicciones por imagen y errores para inspección. El SHA256 del checkpoint archivado es `5dcea4bb3a6c5a529e09998bbad081b6ebaf58ca9881b3d25747c5eb041a8567`.

El checkpoint activo de la web sigue siendo `models/mobilenet.pt`. Su SHA256 `9248cc767425c9efec643bcc2cabd758e8f2b28ab4a6967908713fc1d0b9c5c1` coincide con la copia seleccionada de la corrida MobileNet de 10 épocas.

## Interfaz renovada y servicios locales (21 de septiembre de 2026)

- `npm.cmd run build`: compilación optimizada de Next.js 16.3.5 y comprobación TypeScript correctas.
- Frontend nuevo: HTTP 200 en `http://127.0.0.1:3000`; el HTML contiene “CaféIA” y “Analiza una hoja de café”.
- Backend: HTTP 200 en `/health`, con `model_loaded: true` y `model: mobilenet`.
- Flujo real: `POST /predict` desde el origen permitido `http://127.0.0.1:3000`, usando la imagen de entrenamiento `data/raw/coffee___rust/C10P12E2.jpg`, devolvió roya 0.5930039287, ácaro rojo 0.3226707280 y hoja sana 0.0843253806; se marcó incierto al no alcanzar 0.70. Es una comprobación funcional, no una evaluación.
- El diseño usa una columna antes de 768 px y dos columnas desde 768 px; por código se comprobaron los estados y puntos de quiebre solicitados para 390, 768 y 1440 px. No estuvo disponible la automatización visual del navegador integrado, por lo que no se afirma una inspección visual o por clics en esos anchos.

## Ajuste fino controlado de MobileNet (22 de septiembre de 2026)

Se ejecutó un único experimento desde el checkpoint MobileNet de la época 9, sin consultar `test` y sin modificar el modelo activo. Se descongelaron solamente `features.10`, `features.11`, `features.12` y `classifier.3`, con Adam a 1e-5 para el extractor y 1e-4 para el clasificador. Las estadísticas BatchNorm permanecieron congeladas.

La época 6 fue seleccionada con F1 macro de validación 0.6478439521 frente a 0.6327072392 del candidato inicial. La parada temprana se activó en la época 10. Roya → hoja sana bajó de 33 a 22, pero el recall de ácaro rojo retrocedió de 0.5161290323 a 0.4838709677. La evidencia completa y la comparación por clase están en `experiments/mobilenet_finetune_20260922-103426/RESULTADOS.md`.

`models/mobilenet.pt` conserva el SHA256 `9248cc767425c9efec643bcc2cabd758e8f2b28ab4a6967908713fc1d0b9c5c1`; el candidato ajustado no se activó en la web. El manifiesto conserva el SHA256 `1ea21d6b2b480b830065c5d4d1d90f531234cc2aa244d7bb98c5873363866dab`.

## Integración web del candidato ajustado (22 de septiembre de 2026)

Después de cerrar la selección y la evaluación final, CaféIA se configuró para cargar por variable de entorno una copia sin cambios del candidato MobileNet ajustado, época 6: `models/mobilenet_finetuned_epoch6.pt`. Su SHA256 `4ab4e52fc3d417fe5fb126ff1e5b346f080c55ffa80232cffd5d6e6622e46c94` coincide con `reports/FINAL_PROTOCOL.md`. `models/mobilenet.pt` no se sobrescribió y se añadió un respaldo de activación en `experiments/web_activation_backup_20260922-epoch6/`.

`GET /health` confirmó el identificador `mobilenet-v3-small-finetuned-epoch6`, SHA256 correcto, época 6, orden de clases fijado y umbral 0.70. Una imagen registrada por el evaluador y enviada por `POST /predict` produjo la misma categoría y diferencias absolutas menores que `5 × 10⁻7` en las tres puntuaciones. Un archivo no imagen disfrazado de JPEG fue rechazado con HTTP 400.

La compilación de Next.js 16.3.5 terminó correctamente. Mediante Edge headless se comprobó visualmente el diseño a 390, 768 y 1440 px, además de carga, reemplazo, resultado incierto, clasificación desde 0.70, nuevo análisis, foco del selector y error de conexión. Las capturas y el resultado automatizado están en `reports/web_ui_verification/`; el informe completo, incluida la medición de memoria, está en `reports/WEB_MODEL_INTEGRATION.md`.
