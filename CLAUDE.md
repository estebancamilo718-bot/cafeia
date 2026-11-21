# CLAUDE.md — CaféIA, rama `entrega2`

Proyecto universitario (Sistemas Inteligentes, Universidad de Ibagué, 2026). Equipo: Nicolas Mauricio Oyuela Mendoza, Camilo Esteban Rubiano Santoro, Nicolas Francisco Tovar Gonzales. Docente: Alexandra De La Cruz Puente.

Objetivo de esta rama: cumplir el requisito de la entrega final de **incluir dos MCP (Model Context Protocol) integrados en el proyecto**, sin afectar la versión publicada. La red neuronal **no cambia**: se conserva el MobileNetV3 Small ajustado que ya está evaluado y fue bien recibido en el avance.

`AGENTS.md` contiene las reglas heredadas de la versión anterior. Las de este archivo tienen prioridad si hay conflicto.

---

## 1. Ramas y despliegue (no negociables)

- **`main` = versión publicada** (Vercel: <https://cafeia.vercel.app>, Render: <https://cafeia-jiwk.onrender.com>). Debe seguir funcionando en todo momento.
- Todo el trabajo va en **`entrega2`**. Nada de commit, merge o push a `main` sin que el usuario lo pida expresamente. Nada de `push --force`.
- Antes de empezar una sesión de trabajo, traer los cambios nuevos de `main` a `entrega2`: los compañeros siguen subiendo cambios a `main`.
- Solo se hace merge a `main` cuando:
  1. Los dos MCP funcionan y están documentados en `reports/`.
  2. Pasan las pruebas del backend (`pytest tests/backend`) y del frontend (`npm run test:request-flow`, `npm run build`).
  3. El flujo completo se probó en local: subir foto → clasificación + % de confianza + advertencia → tarjeta de clima.
  4. El usuario lo aprobó.
- Un push de `entrega2` puede generar un *preview* en Vercel. Ese preview apunta al backend de producción, así que no sirve para probar los cambios: las pruebas se hacen en local.
- No borrar ni modificar los artefactos desplegados (`models/mobilenet_finetuned_epoch6.pt`, `models/coffee_domain_guard.pt`) ni sus hashes.

## 2. Qué se va a construir

Dos servidores MCP montados dentro del backend FastAPI existente (sin servicios nuevos en Render), y un cliente MCP dentro del mismo backend que los usa.

| Servidor MCP | Herramientas | Qué percibe el agente |
|---|---|---|
| `cafeia-clasificador` | `clasificar_hoja`, `estado_modelo` | Sensor **visual**: el MobileNet ya cargado, con el mismo filtro de dominio y el mismo umbral 0.70 que `/predict` |
| `cafeia-clima` | `clima_actual`, `pronostico` | Sensor **ambiental**: temperatura, humedad y lluvia desde **Open-Meteo** (gratis, sin clave) |

```text
Web (Vercel) ── foto + ciudad ──► Backend (Render, FastAPI) = host del agente
                                     └─ cliente MCP ──► /clasificador/mcp (servidor MCP 1)
                                                    └─► /clima/mcp        (servidor MCP 2) ──► Open-Meteo
```

- **Versión gratuita, sin modelo de lenguaje.** La lógica del agente (programada) decide llamar ambos sensores. Es un agente basado en reglas que usa sus sensores mediante MCP. No se usan APIs de pago.
- **Debe ser MCP de verdad:** el backend llama a los servidores **a través del cliente MCP** (mensajes `tools/list` y `tools/call` del protocolo), nunca importando sus funciones directamente.
- Los servidores quedan expuestos en la URL pública del backend para poder demostrarlos con **MCP Inspector**.
- `/predict` y su contrato actual **no cambian**: lo nuevo se agrega a su lado.

## 3. Reglas de contenido

- La tarjeta de clima muestra **solo datos** (temperatura, humedad, lluvia y su fuente). No calcula ni sugiere un "riesgo de roya" mientras no haya una fuente citada que respalde umbrales.
- El navegador tiene la geolocalización bloqueada por la CSP: la ubicación se elige por **ciudad**, con Ibagué por defecto. No cambiar la CSP para pedir ubicación.
- Si Open-Meteo falla o tarda, el análisis de la hoja se muestra igual y la tarjeta de clima informa que no hubo datos. El clima nunca bloquea el diagnóstico.
- Las fotos siguen procesándose en memoria y no se guardan. Si un cambio afectara esto, actualizar el texto de privacidad.
- No presentar el softmax como probabilidad calibrada. El % es la "confianza del modelo".
- No inventar resultados, cifras, citas ni experimentos. Toda cifra que se muestre sale de un archivo en `reports/` o de una respuesta real de la API.

## 4. Reglas metodológicas (heredadas, vigentes)

- No reentrenar ni volver a seleccionar modelo. TEST ya fue usado: no se toca.
- Semilla 42 y `data/processed/manifest.csv` se conservan.
- Mantener el proyecto simple. No agregar APIs de pago, servicios nuevos ni despliegues adicionales.

## 5. Código y estilo

- Servidores MCP con la librería oficial `mcp` de Python. Agregar la dependencia con versión fija en `requirements-api.txt`.
- Reutilizar el predictor ya cargado en `backend/main.py`. No cargar el modelo dos veces: Render gratis tiene 512 MB de RAM.
- Agregar pruebas en `tests/backend/` para los dos MCP: el clima con respuestas simuladas, sin llamar a internet en CI.
- Textos de UI e informes en español. Commits pequeños y descriptivos en español.

## 6. Cómo se explica en la presentación

> "MCP es un protocolo estándar para que un agente se conecte a herramientas externas. CaféIA tiene dos servidores MCP, que son sus sensores: uno visual (la red neuronal) y uno ambiental (el clima, que en la propuesta dijimos que el agente no podía percibir). El agente los consulta por MCP y muestra el diagnóstico junto con las condiciones del clima."

Hay que ser honestos: quien decide qué herramientas usar es la lógica programada del agente, no un modelo de lenguaje. Como trabajo futuro, cualquier asistente compatible con MCP podría conectarse a los mismos servidores sin cambiar nada.

## 7. Plan de trabajo

1. Montar los dos servidores MCP en el backend y probarlos con MCP Inspector en local.
2. Cliente MCP en el backend y endpoint que combina ambos sensores.
3. Tarjeta de clima en el frontend, con selector de ciudad.
4. Pruebas, reporte en `reports/MCP_INTEGRATION.md` y README actualizados.
5. Verificación local completa → aprobación del usuario → merge a `main` → comprobar producción.
