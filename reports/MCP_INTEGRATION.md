# Integración de dos servidores MCP en CaféIA

- **Fecha:** 2026-11-16
- **Rama:** `entrega2`
- **Entrenamiento realizado en este cambio:** ninguno
- **Uso de TEST:** ninguno
- **Modelo:** sin cambios (`models/mobilenet_finetuned_epoch6.pt`, mismo filtro de dominio y umbral 0.70)

## Objetivo

La entrega final exige incluir dos MCP (Model Context Protocol) integrados en el proyecto. CaféIA incorpora dos servidores MCP propios, que funcionan como los **sensores del agente**:

| Servidor MCP | Herramientas | Qué percibe el agente |
|---|---|---|
| `cafeia-clasificador` | `clasificar_hoja`, `estado_modelo` | Sensor visual: el MobileNetV3 ajustado ya desplegado |
| `cafeia-clima` | `clima_actual`, `pronostico` | Sensor ambiental: temperatura, humedad y lluvia de Open-Meteo |

La propuesta original del proyecto señalaba que el agente no conocía la temperatura ni la humedad del cultivo. El segundo servidor cubre esa limitación con datos públicos y gratuitos, sin calcular riesgos que no estén respaldados por una fuente.

## Arquitectura

```text
Navegador (Vercel) ── foto + ciudad ──► POST /analizar  (backend FastAPI = host del agente)
                                           │
                                           ├─ cliente MCP ──► cafeia-clasificador ──► MobileNet + filtro de dominio
                                           └─ cliente MCP ──► cafeia-clima ─────────► Open-Meteo (solo el nombre de la ciudad)

Clientes MCP externos (MCP Inspector, asistentes) ──► /clasificador/mcp  y  /clima/mcp  (Streamable HTTP)
```

- **Host del agente:** `backend/main.py`, endpoint `POST /analizar`.
- **Servidores:** `backend/mcp_servidores.py`, construidos con la librería oficial `mcp` 2.3.0 (`MCPServer`).
- **Datos de clima:** `backend/clima.py`, sobre las APIs de geocodificación y pronóstico de Open-Meteo, limitadas a Colombia.
- `/predict` y su contrato **no cambiaron**.

### El agente usa el protocolo, no las funciones

El backend no importa las funciones de los servidores. Abre un cliente MCP (`mcp.Client`, modo `legacy`) que intercambia mensajes JSON-RPC del protocolo: `initialize`, luego `tools/call`. Los mismos servidores se publican por **Streamable HTTP** (sin sesiones, respuestas JSON), así que cualquier cliente MCP externo puede descubrirlos con `tools/list` y usarlos.

### Regla del agente

1. Siempre consulta el sensor visual (`clasificar_hoja`).
2. Si el filtro de dominio rechaza la imagen, **no** consulta el clima y lo explica.
3. Si la imagen fue aceptada, consulta `clima_actual` y `pronostico` (3 días) para la ciudad elegida.
4. Si el clima falla o tarda más de 15 s, el diagnóstico se muestra igual con un mensaje sobre el clima.

Quien decide qué herramientas usar es esta lógica programada (un agente basado en reglas), no un modelo de lenguaje. No se usan APIs de pago.

## Seguridad y privacidad

- La fotografía se procesa en memoria y no se guarda, igual que antes. Nunca se envía a Open-Meteo: solo viaja el nombre de la ciudad. El texto de privacidad de la web lo indica.
- `/analizar` valida la fotografía con las mismas reglas que `/predict`: extensión, tipo, 10 MB y contenido.
- `clasificar_hoja` vuelve a validar base64, tamaño y formato, porque también es pública por HTTP. Los errores internos no se exponen.
- Las rutas HTTP de MCP verifican la cabecera `Host`: localhost y `cafeia-jiwk.onrender.com`, ampliable con la variable `MCP_ALLOWED_HOSTS`. También limitan el cuerpo de la solicitud a unos 13,4 MB, el equivalente en base64 de 10 MB.
- La primera resolución DNS tras arrancar el servidor falló en local (`getaddrinfo failed`). Por eso `clima.py` reintenta una vez los errores de conexión.

## Verificación

### Pruebas automáticas

| Conjunto | Resultado |
|---|---|
| `pytest tests/backend`: 23 pruebas previas + 10 nuevas en `tests/backend/test_mcp.py` | 33 aprobadas |
| `npm run test:request-flow`: 14 previas + 5 nuevas en `lib/analysis.test.ts` | 19 aprobadas |
| `npm run build` (incluye verificación de tipos) | Correcto |

Las pruebas nuevas usan un predictor falso y un Open-Meteo simulado (`httpx2.MockTransport`), así que no salen a internet ni requieren el dataset. Cubren:
- el flujo completo con ambos sensores;
- el clima omitido cuando la imagen es rechazada;
- la falla y el reintento de Open-Meteo;
- una ciudad desconocida;
- `tools/list` por HTTP en ambos servidores;
- el rechazo de un `Host` no autorizado;
- base64 y formato inválidos;
- días fuera de rango.

### Comprobación local con el modelo real (2026-11-16)

- **Cliente MCP externo por HTTP** (`mcp.Client("http://127.0.0.1:8000/clasificador/mcp")`): negoció el protocolo `2026-07-28` y listó `clasificar_hoja` y `estado_modelo`. `estado_modelo` devolvió el checkpoint `4ab4e52f…` y los umbrales 0.70 / 0.6497.
- **Equivalencia con `/predict`:** la misma fotografía (`roya-rocole-c10p27e2.jpg`, imagen de TRAIN de la guía) dio por `/predict` y por `/analizar` exactamente el mismo resultado: `uncertain`, ácaro rojo, 0.5138.
- **Clima por HTTP** (`/clima/mcp`): `pronostico` para Chinchiná devolvió Caldas y 2 días. Una ciudad inexistente devolvió un error claro.
- **Navegador** (frontend compilado contra el backend local): una hoja sana dio 84,6 %, con la tarjeta de clima de Ibagué, Tolima, y los tres pasos MCP en estado OK. Una imagen sintética que no es hoja fue rechazada y el agente marcó el clima como no consultado.
- **Memoria del proceso local** tras cargar el modelo y los dos servidores: unos 364 MB, medida en Windows. Render gratis ofrece 512 MB; conviene revisar el uso real después del despliegue.

## Cómo demostrar los MCP

**En la web:** subir una foto, elegir la ciudad y señalar la tarjeta de clima y la lista «Cómo trabajó el agente».

**Con MCP Inspector**, un cliente MCP oficial y gratuito:

```bash
npx @modelcontextprotocol/inspector
```

En la interfaz, elegir transporte **Streamable HTTP** y la URL:
- local: `http://127.0.0.1:8000/clasificador/mcp` o `http://127.0.0.1:8000/clima/mcp`;
- producción, después del merge: `https://cafeia-jiwk.onrender.com/clasificador/mcp` o `/clima/mcp`.

Luego se listan las herramientas y se ejecuta, por ejemplo, `pronostico` con `ciudad = Ibagué`.

### Comprobación con MCP Inspector (2026-11-17)

Después de la verificación anterior, los dos servidores locales se agregaron a MCP Inspector v2.15.0 con transporte Streamable HTTP. Inspector negoció el protocolo `2025-11-25` y listó las dos herramientas de cada servidor. Se ejecutaron `estado_modelo` y `pronostico` (Ibagué, 3 días), y el panel de mensajes mostró los `tools/list` y `tools/call` correspondientes con estado OK.

## Limitaciones

- La selección de herramientas es programada, no la hace un modelo de lenguaje. Como trabajo futuro, un asistente compatible con MCP podría usar estos mismos servidores sin cambios.
- La tarjeta de clima muestra solo datos. No hay umbrales climáticos de riesgo de roya o ácaro respaldados por una fuente citada, así que no se calcula ninguno.
- El clima depende de la disponibilidad de Open-Meteo y de que la ciudad exista en su geocodificador. Se toma el primer resultado dentro de Colombia.
- El modelo y sus métricas no cambian. Siguen vigentes las limitaciones de `reports/FINAL_TEST_RESULTS.md`.
