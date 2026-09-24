# Contexto para Codex

Proyecto universitario Crop Disease Image Classification, DNNs, usando el ZIP RoCoLe aportado. Primer avance de selección y descripción YA entregado: no reescribirlo sin solicitud. Ayudar al estudiante a entender y ejecutar cada paso.

## Datos comprobados
1560 JPG: coffee___healthy 791; coffee___rust 602; coffee___red_spider_mite 167. Mantener nombres de etiquetas. No inventar otras clases ni confundir ácaro rojo con enfermedad fúngica. No entrenar con etiquetas inferidas visualmente.

## Método
- Preservar semilla 42 y manifiesto. Particiones por prefijo CxPy provisional; confirmar significado con fuente original antes de afirmar separación por planta/hoja.
- No compartir grupos o imágenes duplicadas entre entrenamiento, validación y prueba.
- Aumento de datos solo en entrenamiento. Pesos de clase calculados solo en entrenamiento.
- Selección por F1 macro de validación, prueba reservada para evaluación final.
- Tres soluciones: CNN desde cero, MobileNetV3 Small y ResNet18 con extractor congelado.
- No presentar puntuación softmax como confianza clínica/agronómica calibrada.
- No inventar resultados, citas, autores ni experimentos.

## Trabajo pendiente
Preparación ejecutada y verificada. `models/mobilenet.pt` conserva el MobileNet congelado de la época 9 (F1 macro de validación 0.6327072392) como respaldo local. La web carga ahora, mediante `MODEL_PATH`, la copia desplegable `models/mobilenet_finetuned_epoch6.pt` del candidato ajustado de época 6 (F1 macro de validación 0.6478439521; SHA256 fijado en `reports/FINAL_PROTOCOL.md`). El checkpoint original y todos los experimentos permanecen en `experiments/`. La evaluación final sobre las 300 imágenes reservadas ya se cerró y está en `reports/FINAL_TEST_RESULTS.md`; no usar TEST para volver a seleccionar o ajustar. La aplicación web CaféIA usa FastAPI y Next.js; consultar el estado comprobado en `reports/VERIFICACION.md`. Facilitar CPU o Colab, sin asumir CUDA en AMD. Mantener sencillo el proyecto; no agregar APIs pagas ni despliegues innecesarios.

## Académico
El usuario confirmó que las instrucciones académicas del PDF 2025B también aplican en 2026. El PDF pide revisión, propuesta, informe científico y GitHub; criterios dicen más de dos soluciones aunque fases mencionan una o dos. Imagen y PDF difieren en duración de exposiciones; confirmar con el docente cuál duración de exposición prevalece. Preparar textos en Markdown hasta recibir plantilla IEEE oficial.

Auditoría de limpieza: 24 archivos conflictivos excluidos, 55 copias redundantes eliminadas, 1481 imágenes finales. Unir grupos relacionados por duplicados antes de dividir. Conservar esta política documentada; no reincorporar conflictos sin verificar sus etiquetas.
