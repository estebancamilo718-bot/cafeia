# Integración web del candidato MobileNet ajustado

**Fecha:** 2026-09-22
**Estado:** integración local terminada; no se publicó ningún servicio y no se ejecutó entrenamiento.

## Modelo activado por configuración

| Elemento | Valor |
|---|---|
| Identificador servido | `mobilenet-v3-small-finetuned-epoch6` |
| Ruta configurada | `models/mobilenet_finetuned_epoch6.pt` |
| Checkpoint original conservado | `experiments/mobilenet_finetune_20260922-103426/best_checkpoint.pt` |
| Época seleccionada | 6 |
| SHA256 esperado y obtenido | `4ab4e52fc3d417fe5fb126ff1e5b346f080c55ffa80232cffd5d6e6622e46c94` |
| SHA256 del modelo web anterior | `9248cc767425c9efec643bcc2cabd758e8f2b28ab4a6967908713fc1d0b9c5c1` |
| Respaldo adicional del anterior | `experiments/web_activation_backup_20260922-epoch6/previous_active_mobilenet.pt` |
| Orden de clases | `coffee___healthy`, `coffee___red_spider_mite`, `coffee___rust` |
| Umbral provisional | 0.70, sin cambios |

El SHA256 del candidato coincide con `reports/FINAL_PROTOCOL.md`. El backend exige `MODEL_PATH`, `MODEL_SHA256` y `MODEL_ID`; aborta el arranque si el hash no coincide y valida el orden exacto de las tres clases. `models/mobilenet.pt` no fue sobrescrito.

## Equivalencia entre evaluador y API

Se usó `data/raw/coffee___healthy/C10P11H1.jpg`, cuya predicción ya estaba registrada por el evaluador final. No se recalcularon métricas ni se seleccionó otro modelo.

| Clase | Evaluador | `POST /predict` | Diferencia absoluta |
|---|---:|---:|---:|
| Hoja sana | 0.6291125417 | 0.6291120648 | 0.0000004768 |
| Ácaro rojo | 0.1666429937 | 0.1666432172 | 0.0000002235 |
| Roya | 0.2042444944 | 0.2042447329 | 0.0000002384 |

Ambos caminos produjeron la misma categoría y el mismo estado incierto. La diferencia máxima fue `4.77 × 10⁻7`, compatible con redondeo numérico de inferencia por lote frente a inferencia individual.

`GET /health` confirmó:

```json
{
  "status": "ok",
  "model_loaded": true,
  "model": "mobilenet",
  "model_id": "mobilenet-v3-small-finetuned-epoch6",
  "checkpoint_sha256": "4ab4e52fc3d417fe5fb126ff1e5b346f080c55ffa80232cffd5d6e6622e46c94",
  "selected_epoch": 6,
  "uncertainty_threshold": 0.7
}
```

## Interfaz y flujo real

- Una puntuación menor que 0.70 muestra `Resultado incierto` y, en segundo nivel, `Categoría más probable: …`.
- Una puntuación desde 0.70 muestra `Clasificación orientativa: …`.
- La interfaz no contiene `diagnóstico confirmado`, `hoja libre de enfermedad` ni identificadores `coffee___…`.
- Se aclara que el modelo solo distingue hoja sana, roya y ácaro rojo, que las puntuaciones no están calibradas y que el sistema no comprueba si la fotografía corresponde a una hoja de café.
- La sección `Evaluación del prototipo` presenta los resultados fijados de TEST: 300 imágenes, accuracy general 71.67 %, F1 macro 0.6235, 158/300 aceptadas con umbral 0.70, 140 correctas, 18 incorrectas, accuracy entre aceptadas 88.61 % y cobertura 52.67 %. Se identifica ácaro rojo como limitación principal y se advierte que estas cifras no garantizan desempeño en imágenes nuevas.
- Un archivo de texto enviado como `invalido.jpg` y `image/jpeg` fue rechazado con HTTP 400.
- La compilación optimizada de Next.js 16.3.5 y la comprobación TypeScript terminaron correctamente.

Se automatizó el navegador local con Microsoft Edge headless y luego se inspeccionaron las capturas. Las columnas calculadas fueron:

| Ancho | Cuadrícula principal |
|---:|---|
| 390 px | una columna (`358px`) |
| 768 px | dos columnas (`342.5px 342.5px`) |
| 1440 px | dos columnas (`530px 530px`) |

El flujo comprobó carga, vista previa, reemplazo, predicción incierta, predicción desde 0.70, nuevo análisis y error de conexión simulado bloqueando solo la solicitud al backend. El selector recibió foco por teclado y mantuvo una etiqueta accesible. Los contrastes de texto principales medidos quedaron entre 5.51:1 y 11.53:1. El resultado estructurado está en `reports/web_ui_verification/browser_checks.json`. Las seis capturas PNG permanecen como evidencia local, pero `.gitignore` las excluye porque contienen ejemplos visuales del dataset.

## Memoria local del backend

Medición de un único proceso Uvicorn en Windows, CPU:

| Momento | Working set | Memoria privada |
|---|---:|---:|
| Modelo cargado, antes de inferencia | 309.86 MiB | 776.87 MiB |
| Pico de working set durante las predicciones verificadas | 351.26 MiB | — |
| Después de las verificaciones | 327.73 MiB | 807.59 MiB |

El working set es la aproximación local más útil para contrastar con el RSS de Linux; la memoria privada de Windows no es directamente equivalente a la métrica de Render. El plan gratuito de Render declara 512 MB, de modo que el pico local deja margen limitado. Debe comprobarse el RSS real en Render antes de considerar estable ese plan; no se contrató ni se publicó nada.

## Preparación de publicación

- `render.yaml` usa el checkpoint ajustado, fija su hash e identificador, mantiene un solo proceso Uvicorn y deja `CORS_ALLOWED_ORIGINS` como valor explícito por completar.
- `frontend/vercel.json` conserva la compilación Next.js. En Vercel debe seleccionarse `frontend` como directorio raíz y definirse `NEXT_PUBLIC_API_URL`.
- `.gitignore` excluye `.venv/`, `data/raw/`, `provenance/`, `experiments/`, `frontend/node_modules/`, artefactos Next y los demás checkpoints. Permite de forma explícita únicamente `models/mobilenet_finetuned_epoch6.pt` para el despliegue.
- El repositorio Git fue inicializado localmente en la rama `main`. La inclusión final se revisó antes del primer commit; todavía no existe un remoto ni se ha hecho `push`.

Los comandos locales y las variables exactas están en `LEEME.md`. Las referencias de configuración utilizadas son la especificación oficial de [Render Blueprint](https://render.com/docs/blueprint-spec), sus [planes de cómputo](https://render.com/docs/compute-plans) y la configuración de [directorios raíz en monorepos de Vercel](https://vercel.com/docs/monorepos).
