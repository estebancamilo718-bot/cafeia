# CaféIA

CaféIA es una aplicación web de apoyo visual que clasifica fotografías de hojas de café en tres categorías: **hoja sana**, **roya** y **ácaro rojo**. El analizador usa un backend FastAPI, una interfaz Next.js y un MobileNetV3 Small ajustado sobre la versión limpia y documentada de RoCoLe. No es un diagnóstico ni ofrece certeza absoluta.

La aplicación conserva el analizador como función principal. La guía visual es educativa y utiliza tres ejemplos de TRAIN con anotación original verificada; no convierte la salida del modelo en un diagnóstico.

La interfaz actual presenta dos destinos: **Analizar** y **Guía de hojas**. Las métricas académicas permanecen documentadas en este README y en `reports/`, sin ocupar una tercera sección en la página pública.

## Estado reproducible

- Checkpoint activo: `models/mobilenet_finetuned_epoch6.pt`.
- SHA-256: `4ab4e52fc3d417fe5fb126ff1e5b346f080c55ffa80232cffd5d6e6622e46c94`.
- Orden de salidas: `coffee___healthy`, `coffee___red_spider_mite`, `coffee___rust`.
- Preprocesamiento: orientación EXIF, RGB, redimensionamiento directo a 224×224, tensor y normalización ImageNet.
- Umbral provisional de incertidumbre: `0.70`.
- Filtro experimental de dominio: `models/coffee_domain_guard.pt`, SHA-256 `8060ef83e4a018d6a49e22fc5b59162f4ec6cbba90482e27d7896c79106d90e7`.
- Manifiesto conservado: `data/processed/manifest.csv`, SHA-256 `1ea21d6b2b480b830065c5d4d1d90f531234cc2aa244d7bb98c5873363866dab`.

El backend comprueba los hashes, la compatibilidad del filtro y el orden de clases antes de atender solicitudes. Ambos artefactos se cargan una vez durante el arranque y las fotografías recibidas se procesan en memoria, sin guardarlas.

Cuando el filtro no reconoce suficientemente el aspecto de una fotografía, la primera respuesta sigue ocultando categorías y puntuaciones. La interfaz permite solicitar después **Analizar de todos modos**: esta segunda petición devuelve una comparación limitada con las tres clases, conserva `is_supported_image=false` y advierte que no confirma que la imagen sea una hoja de café. Esta salida no cambia el modelo, el filtro ni sus umbrales.

## Arquitectura

```text
Navegador
  └─ frontend/ (Next.js, TypeScript y Tailwind)
       └─ POST /predict
            └─ backend/main.py (FastAPI)
                 ├─ src/common.py (arquitectura y preprocesamiento)
                 ├─ models/coffee_domain_guard.pt (barrera experimental)
                 └─ models/mobilenet_finetuned_epoch6.pt (tres clases)
```

Los scripts de preparación, entrenamiento y evaluación viven en `src/`. No se ejecutan al usar la aplicación web.

## Consentimiento, privacidad y seguridad web

Antes de habilitar el selector de fotografías, la interfaz solicita una aceptación explícita para enviar la imagen al backend configurado. Rechazar permite seguir consultando la página, pero mantiene bloqueados la carga y el análisis. La decisión puede revisarse o retirarse desde el pie de página; al retirarla se cancela cualquier solicitud y se elimina la selección actual de la interfaz.

La decisión se conserva en `localStorage` bajo una clave versionada. CaféIA no instala cookies publicitarias ni de analítica. El backend valida el tipo, contenido y límite de 10 MB, procesa la fotografía en memoria y no la guarda.

`frontend/next.config.ts` añade Content Security Policy, bloqueo de iframes, `nosniff`, política de referentes y permisos denegados para cámara, micrófono y geolocalización. `NEXT_PUBLIC_API_URL` debe estar definida durante la compilación de producción porque su origen se incorpora tanto al frontend como a `connect-src` de la CSP. Estas medidas reducen riesgos web comunes, pero no sustituyen HTTPS, revisión de dependencias ni supervisión operativa del despliegue.

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
$env:DOMAIN_GUARD_PATH = "models/coffee_domain_guard.pt"
$env:DOMAIN_GUARD_SHA256 = "8060ef83e4a018d6a49e22fc5b59162f4ec6cbba90482e27d7896c79106d90e7"
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

`tests/backend/test_api_contract.py` usa principalmente predictores falsos para comprobar el contrato HTTP; además prueba de forma determinista que el permiso de comparación limitada no altera logits ni el score de dominio. No demuestra exactitud. `tests/backend/test_checkpoint_inference.py` carga el checkpoint y el filtro desplegables y ejecuta una inferencia real sobre una imagen sintética creada en memoria; comprueba integración, no exactitud. `tests/backend/test_domain_guard.py` verifica el cálculo de similitud, persistencia y equivalencia de logits. La CI reproduce estas comprobaciones sin dataset privado ni entrenamiento.

La comprobación E2E local con fotografías reales se mantiene separada porque requiere `data/raw` y la evidencia original, ambos excluidos de Git. `src/verify_val_e2e.py` fija primero 15 imágenes de VAL sin cargar el modelo y después compara inferencia directa con una API HTTP real. Sus resultados están en [reports/VAL_E2E_INTEGRATION.md](reports/VAL_E2E_INTEGRATION.md); no son una nueva evaluación global ni consultan TEST.

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

La barrera de dominio se calibró sin TEST. En su evaluación de desarrollo aceptó 141/153 hojas de café de una porción de VAL y rechazó 200/200 negativos externos concretos: hojas PlantVillage ajenas al café, perros, gatos y escenas/objetos. Estos resultados justifican su integración conservadora, pero no prueban rechazo universal. Véase [el informe del filtro](reports/DOMAIN_GUARD_RESULTS.md).

Una comparación posterior agregó referencias auditadas de CoffeeLeaf-CO a un filtro candidato: la aceptación de 508 fotografías reservadas por imagen de esa fuente subió de 42,72 % a 90,55 %, mientras los 200 negativos concretos continuaron rechazados. El candidato no se activó porque falta la comprobación externa fijada previamente y el margen de los scores negativos se estrechó. Esto mejora cobertura del filtro dentro de esa fuente, no la exactitud del clasificador de tres clases. Véase [la auditoría y comparación](reports/COFFEELEAF_DOMAIN_GUARD_EXPERIMENT.md).

## Datos, modelos y Git

Git incluye código, manifiesto, reportes, tres fotografías atribuidas de la guía, el checkpoint del clasificador y el artefacto del filtro necesarios para desplegar. `.gitignore` excluye el dataset completo, `.venv`, `node_modules`, `.next`, descargas de procedencia, experimentos y checkpoints adicionales.

Los materiales locales excluidos siguen siendo evidencia académica y no deben eliminarse: `data/raw/`, `provenance/`, `experiments/` y los modelos de referencia. La atribución de RoCoLe y de las fotografías está en [ATTRIBUTIONS.md](ATTRIBUTIONS.md) y [reports/GUIDE_IMAGE_PROVENANCE.md](reports/GUIDE_IMAGE_PROVENANCE.md).

## Despliegue público

La aplicación está publicada en estos servicios:

- Frontend: <https://cafeia.vercel.app>
- Backend: <https://cafeia-jiwk.onrender.com>

La configuración reproducible permanece en el repositorio:

- Render puede crear el backend desde `render.yaml`.
- Vercel debe usar `frontend` como Root Directory y definir `NEXT_PUBLIC_API_URL`.
- Render debe recibir `CORS_ALLOWED_ORIGINS` con el origen HTTPS exacto de Vercel.
- Render carga y verifica tanto `MODEL_PATH`/`MODEL_SHA256` como `DOMAIN_GUARD_PATH`/`DOMAIN_GUARD_SHA256`.

Render puede entrar en reposo en el plan gratuito; la primera predicción después de un periodo sin uso puede tardar mientras el servicio inicia y carga los artefactos. Las solicitudes siguientes suelen ser más rápidas. Tras cada despliegue se debe comprobar `/health`, el hash del modelo, CORS y el flujo real desde Vercel.

## Limitaciones

- Solo distingue tres categorías y no estima severidad ni localiza lesiones.
- Ácaro rojo es la clase más débil en la evaluación final.
- El filtro experimental reduce algunos errores fuera de dominio, pero no garantiza reconocer todas las especies, objetos o fotografías no utilizables; también rechazó 12/153 hojas válidas en su comprobación de VAL.
- RoCoLe representa un dominio limitado; falta comprobación externa con plantas, sitios y sesiones independientes.
- CaféIA no sustituye la revisión de una persona experta.

## Evidencias principales

- [Protocolo final](reports/FINAL_PROTOCOL.md)
- [Resultados finales](reports/FINAL_TEST_RESULTS.md)
- [Comparación de validación](reports/VALIDATION_MODEL_COMPARISON.md)
- [Auditoría de procedencia](reports/DATASET_PROVENANCE_AUDIT.md)
- [Auditoría de confiabilidad web](reports/RELIABILITY_AUDIT.md)
- [Resultado del experimento v2](reports/V2_PREPROCESSING_RESULTS.md)
- [Filtro experimental de dominio](reports/DOMAIN_GUARD_RESULTS.md)
- [Protocolo de generalización externa](reports/DOMAIN_GENERALIZATION_V2_PROTOCOL.md)
- [Auditoría CoffeeLeaf-CO y candidato del filtro](reports/COFFEELEAF_DOMAIN_GUARD_EXPERIMENT.md)
- [Comparación limitada tras un rechazo](reports/DOMAIN_GUARD_LIMITED_OVERRIDE.md)

## Licencia

Las licencias y atribuciones de terceros están documentadas, pero el código original de este repositorio aún no tiene una licencia propia. Como el repositorio ya es público, elegir una licencia de código es una decisión pendiente urgente: sin ella no se conceden permisos explícitos de reutilización. No debe asumirse que la licencia CC BY 4.0 del dataset se aplica al código.
