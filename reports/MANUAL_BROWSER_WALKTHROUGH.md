# Recorrido manual breve del analizador

**Objetivo:** verificar en navegador los escenarios cuya lógica fue automatizada en `RELIABILITY_AUDIT.md`. Este documento no afirma que los clics ya se hayan realizado.

## Preparación

1. Inicia backend y frontend con los comandos de `LEEME.md` y abre `http://localhost:3000`.
2. Ten dos JPG/PNG válidos de menos de 10 MiB, `foto A` y `foto B`. No uses TEST.
3. Abre las herramientas del navegador, pestaña **Red/Network**, y activa “Preserve log”. Para poder sustituir una imagen mientras la petición sigue pendiente en una máquina local rápida, aplica temporalmente **Slow 3G** desde el navegador; esto no modifica CaféIA.

## Pasos y resultados esperados

1. **Subir:** elige `foto A` mediante el selector o arrástrala. Deben aparecer la vista previa y el nombre correcto; no debe existir un resultado previo.
2. **Analizar:** pulsa **Analizar hoja**. El botón debe quedar deshabilitado y mostrar estado de carga. Un segundo clic no debe crear otra solicitud. Al terminar, debe mostrarse una de las tres categorías, sus tres puntuaciones y, si la máxima es menor que 0,70, **Resultado incierto** como título principal.
3. **Sustituir durante una petición:** inicia otro análisis de `foto A` y, antes de que responda, selecciona o arrastra `foto B`. La vista previa debe cambiar de inmediato, desaparecer cualquier resultado/error de A y cancelarse o ignorarse la respuesta pendiente. Cuando la petición vieja termine, **nunca** debe aparecer asociada a B. En Network puede figurar como cancelada; eso es esperado.
4. **Volver a analizar:** pulsa **Analizar hoja** con `foto B`. El resultado nuevo debe corresponder a B y la interfaz debe ofrecer reemplazarla o iniciar un nuevo análisis. Quita “Slow 3G” al terminar esta prueba.
5. **Desconexión y recuperación:** detén solo el backend con `Ctrl+C`; conserva el frontend. Intenta analizar otra vez. Debe mostrarse el mensaje de conexión y no un resultado anterior. Reinicia el backend con las mismas variables de entorno y el comando de `LEEME.md`; comprueba `http://127.0.0.1:8000/health` y pulsa de nuevo **Analizar hoja**. El error debe desaparecer al iniciar la nueva solicitud y debe mostrarse una respuesta real.

## Registro mínimo

Anota navegador/versión, ancho aproximado, hora, archivo usado (sin publicarlo), resultado de cada paso y captura únicamente de la interfaz. Si algún paso falla, conserva la entrada de Network y la consola; no uses la puntuación del modelo para decidir la etiqueta real de la fotografía.
