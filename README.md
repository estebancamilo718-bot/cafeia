# CaféIA

CaféIA es un prototipo académico web que clasifica fotografías de hojas de café en tres categorías: **hoja sana**, **roya** y **ácaro rojo**. El analizador usa un backend FastAPI, una interfaz Next.js y un MobileNetV3 Small ajustado sobre la versión limpia y documentada de RoCoLe.

La aplicación conserva el analizador como función principal. La guía visual es educativa y utiliza tres ejemplos de TRAIN con anotación original verificada; no convierte la salida del modelo en un diagnóstico.

## Estado reproducible

- Checkpoint activo: `models/mobilenet_finetuned_epoch6.pt`.
- SHA-256: `4ab4e52fc3d417fe5fb126ff1e5b346f080c55ffa80232cffd5d6e6622e46c94`.
- Orden de salidas: `coffee___healthy`, `coffee___red_spider_mite`, `coffee___rust`.
- Preprocesamiento: orientación EXIF, RGB, redimensionamiento directo a 224×224, tensor y normalización ImageNet.
- Umbral provisional de incertidumbre: `0.70`.
- Manifiesto conservado: `data/processed/manifest.csv`, SHA-256 `1ea21d6b2b480b830065c5d4d1d90f531234cc2aa244d7bb98c5873363866dab`.

El backend comprueba el hash y el orden de clases antes de atender solicitudes. El checkpoint se carga una vez durante el arranque y las fotografías recibidas se procesan en memoria, sin guardarlas.

## Arquitectura

```text
Navegador
  └─ frontend/ (Next.js, TypeScript y Tailwind)
       └─ POST /predict
            └─ backend/main.py (FastAPI)
                 ├─ src/common.py (arquitectura y preprocesamiento)
                 └─ models/mobilenet_finetuned_epoch6.pt
```

Los scripts de preparación, entrenamiento y evaluación viven en `src/`. No se ejecutan al usar la aplicación web.

## Ejecución local en Windows

Requisitos verificados: Python 3.11.9, Node.js compatible con el objetivo Node 22 de CI y npm con soporte para `package-lock.json` v3. Las dependencias directas de Python están fijadas en `requirements-api.txt`; las del frontend están bloqueadas por `frontend/package-lock.json`.

```powershell
# Una vez, desde la raíz
py -3.11 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements-api.txt

Set-Location frontend
npm.cmd ci
Copy-Item .env.local.example .env.local
Set-Location ..
```

Backend, en la primera terminal desde la raíz:

```powershell
$env:MODEL_PATH = "models/mobilenet_finetuned_epoch6.pt"
$env:MODEL_SHA256 = "4ab4e52fc3d417fe5fb126ff1e5b346f080c55ffa80232cffd5d6e6622e46c94"
$env:MODEL_ID = "mobilenet-v3-small-finetuned-epoch6"
$env:CORS_ALLOWED_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"
& .\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Frontend, en la segunda terminal:

```powershell
Set-Location frontend
npm.cmd run dev
```

Abre `http://localhost:3000`. El estado del backend queda en `http://127.0.0.1:8000/health` y su documentación interactiva en `http://127.0.0.1:8000/docs`.

Las instrucciones ampliadas, incluidas investigación y despliegue, están en [LEEME.md](LEEME.md).

## Pruebas

```powershell
# Backend: contrato con dobles y carga/inferencia real del checkpoint
& .\.venv\Scripts\python.exe -m pip install -r requirements-test.txt
& .\.venv\Scripts\python.exe -m pytest -q tests/backend

# Frontend
Set-Location frontend
npm.cmd run test:request-flow
npm.cmd run build
```

`tests/backend/test_api_contract.py` usa un predictor falso y no demuestra inferencia real. `tests/backend/test_checkpoint_inference.py` carga el checkpoint desplegable y ejecuta una inferencia real sobre una imagen sintética creada en memoria; comprueba integración, no exactitud. La CI reproduce estas comprobaciones sin dataset privado ni entrenamiento.

## Resultados fijados

El candidato se eligió antes de consultar TEST, por F1 macro de validación `0.647844`. Sobre las 300 imágenes de TEST fijadas obtuvo:

| Métrica | Resultado |
|---|---:|
| Accuracy general | 71,67 % |
| F1 macro | 0,6235 |
| F1 hoja sana | 0,8523 |
| F1 roya | 0,6637 |
| F1 ácaro rojo | 0,3544 |
| Predicciones con puntuación ≥ 0,70 | 158/300 |
| Correctas dentro de esas 158 | 140 |
| Accuracy condicional | 88,61 % |

Estas cifras describen exclusivamente ese conjunto. Las puntuaciones softmax no son probabilidades calibradas de acierto; `0.70` no detecta imágenes ajenas al café y no garantiza desempeño en fotografías nuevas.

## Datos, modelos y Git

Git incluye código, manifiesto, reportes, tres fotografías atribuidas de la guía y el único checkpoint necesario para desplegar. `.gitignore` excluye el dataset completo, `.venv`, `node_modules`, `.next`, descargas de procedencia, experimentos y checkpoints adicionales.

Los materiales locales excluidos siguen siendo evidencia académica y no deben eliminarse: `data/raw/`, `provenance/`, `experiments/` y los modelos de referencia. La atribución de RoCoLe y de las fotografías está en [ATTRIBUTIONS.md](ATTRIBUTIONS.md) y [reports/GUIDE_IMAGE_PROVENANCE.md](reports/GUIDE_IMAGE_PROVENANCE.md).

## Despliegue público

El repositorio está **preparado**, pero no se ha publicado la aplicación:

- Render puede crear el backend desde `render.yaml`.
- Vercel debe usar `frontend` como Root Directory y definir `NEXT_PUBLIC_API_URL`.
- Render debe recibir `CORS_ALLOWED_ORIGINS` con el origen HTTPS exacto de Vercel.

Las URLs de ejemplo no representan servicios activos. Después de un despliegue autorizado se debe comprobar `/health`, el hash del modelo, CORS, memoria y el flujo real desde el dominio asignado.

## Limitaciones

- Solo distingue tres categorías y no estima severidad ni localiza lesiones.
- Ácaro rojo es la clase más débil en la evaluación final.
- No existe un mecanismo medido para rechazar otras especies, objetos o fotografías no utilizables.
- RoCoLe representa un dominio limitado; falta comprobación externa con plantas, sitios y sesiones independientes.
- CaféIA no sustituye la revisión de una persona experta.

## Evidencias principales

- [Protocolo final](reports/FINAL_PROTOCOL.md)
- [Resultados finales](reports/FINAL_TEST_RESULTS.md)
- [Comparación de validación](reports/VALIDATION_MODEL_COMPARISON.md)
- [Auditoría de procedencia](reports/DATASET_PROVENANCE_AUDIT.md)
- [Auditoría de confiabilidad web](reports/RELIABILITY_AUDIT.md)
- [Resultado del experimento v2](reports/V2_PREPROCESSING_RESULTS.md)

## Licencia

Las licencias y atribuciones de terceros están documentadas, pero el código original de este repositorio aún no tiene una licencia propia. La persona autora debe decidirla antes de una publicación abierta; no debe asumirse que la licencia CC BY 4.0 del dataset se aplica al código.
