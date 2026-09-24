# Cómo desarrollaremos el proyecto

1. **Datos y entorno (ahora):** abrir carpeta, instalar, auditar ZIP; inspeccionar ejemplos por clase y confirmar significado de identificadores. Entregable: auditoría reproducible.
2. **Revisión bibliográfica (prioridad académica):** localizar publicación original de RoCoLe y estudios de clasificación de hojas de café; registrar métodos, división y métricas. Formular pregunta: ¿qué desempeño tienen tres arquitecturas al clasificar las tres condiciones del ZIP bajo una misma partición por grupos?
3. **Primer experimento:** MobileNet por una época para comprobar el flujo, después entrenamiento real. Interpretar pérdida y F1 de validación, observar errores.
4. **Comparación:** CNN pequeña, MobileNet y ResNet18; misma división, métricas y presupuesto documentado. Registrar duración y entorno. Las dos redes preentrenadas empiezan como extractores congelados; fine-tuning queda como mejora futura.
5. **Agente demostrable:** carga de imagen, clasificación, puntuación y solicitud de revisión ante incertidumbre. Probar fotos externas con cautela; documentar diferencias de iluminación/fondo/dominio.
6. **Cierre:** evaluar prueba una vez fijados experimentos, escribir resultados reales y limitaciones, integrar informe IEEE, preparar sustentación y subir código a GitHub cuando el estudiante lo indique.

## Lo que solicita cada fuente

| Fuente | Requisito |
|---|---|
| Primer avance pegado en conversación | Entorno, objetivos, entradas/percepción, acciones y retos; ya entregado |
| PDF, fase 1 | Revisión bibliográfica y estudio del problema |
| Imagen, semana 8 | Artículo IEEE con estado del arte; presentación 5 min |
| PDF, fase 1 | Presentación 10 min |
| Imagen, semana 12 | Añadir propuesta y justificación; presentación 5 min |
| PDF, fase 2 | Propuesta; presentación 10 min |
| Cierre | Informe científico, metodología, resultados, conclusiones y sustentación de 10 min |

La imagen asigna 20% a actividades, 10% a selección, 20% a avance I, 20% a avance II y 30% a cierre. El usuario confirmó que las instrucciones del PDF 2025B también aplican en 2026. Su listado no incluye el título de café suministrado por el estudiante, por lo que usamos ese título como selección actual. La imagen y el PDF difieren en la duración de las exposiciones; esa diferencia sí debe confirmarse con el docente.

## Artículo: secciones pendientes
Título; autores reales del grupo; resumen; introducción; estado del arte; metodología (datos, partición, preprocesamiento, arquitecturas, entrenamiento, métricas); resultados; discusión; conclusiones; trabajo futuro; referencias. No redactar resultados hasta entrenar. Usar plantilla IEEE del profesor cuando esté disponible.
