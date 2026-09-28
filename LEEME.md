# CaféIA: instalación, reproducción y ejecución

Este documento describe el estado vigente de CaféIA. La aplicación local funciona con FastAPI y Next.js; la selección de modelos y la evaluación final de la versión 1 ya se cerraron. No se ha realizado un despliegue público.

## 1. Estado del proyecto

- Dataset limpio local: 1.481 imágenes, después de excluir 24 archivos contradictorios y 55 copias redundantes.
- Particiones conservadas en `data/processed/manifest.csv`, semilla 42 y grupos relacionados por duplicados unidos antes de dividir.
- Modelo activo: MobileNetV3 Small ajustado, candidato de época 6.
- F1 macro de validación usado para seleccionarlo: `0.6478439521`.
- Evaluación final cerrada: 300 imágenes de TEST, accuracy `0.716667` y F1 macro `0.623486`.
- Checkpoint desplegable: `models/mobilenet_finetuned_epoch6.pt`.
- SHA-256: `4ab4e52fc3d417fe5fb126ff1e5b346f080c55ffa80232cffd5d6e6622e46c94`.
- Modelo anterior, CNN, ResNet18 y experimentos: conservados localmente, pero excluidos de Git.

El experimento v2 de redimensionamiento con proporción y relleno fue rechazado: obtuvo F1 macro de VAL `0.591710`, frente a `0.647844` del control. No cambió el modelo activo ni el preprocesamiento de la web.

## 2. Arquitectura vigente

```text
frontend/                    Interfaz Next.js, TypeScript y Tailwind
  app/page.tsx               Analizador, guía y resultados del modelo
  lib/                       Validación y coordinación de solicitudes
  public/guide/              Tres ejemplos atribuidos de TRAIN

backend/main.py              FastAPI: /health y /predict
  └─ src/common.py           Modelo, orden de clases y transformaciones
       └─ models/mobilenet_finetuned_epoch6.pt

src/                         Preparación, entrenamiento, validación y evaluación
reports/                     Protocolos, métricas y auditorías
```

La ruta de inferencia es: archivo JPG/PNG → validación de formato y contenido → orientación EXIF y RGB → `Resize((224, 224))` → tensor → normalización ImageNet → MobileNet → softmax sobre tres salidas → respuesta API → presentación web.

El backend carga el checkpoint una vez en el arranque, exige su hash, verifica el orden `sana → ácaro rojo → roya` y no guarda la fotografía recibida.

## 3. Versiones reproducibles

Entorno local verificado:

- Python `3.11.9`.
- Node.js local `25.9.0` y npm `11.12.1`.
- La CI y el objetivo de despliegue usan Node `22`, una versión LTS compatible con el proyecto; su primera ejecución remota ocurrirá después de hacer push.

Las dependencias directas verificadas están fijadas con `==`:

- `requirements-api.txt`: backend e inferencia.
- `requirements-test.txt`: pytest y cliente HTTP de pruebas.
- `requirements-data.txt`: preparación del dataset.
- `requirements.txt`: entorno académico completo y Streamlit heredado.
- `frontend/package-lock.json`: árbol exacto del frontend, instalado con `npm ci`.

No se generó un `pip freeze` global porque incluiría paquetes transitivos y específicos del entorno Windows que no corresponden al despliegue Linux. La CI instala los conjuntos mínimos declarados en Ubuntu.

## 4. Instalación local en Windows

Desde la raíz del repositorio, en PowerShell:

```powershell
py -3.11 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements-api.txt

Set-Location frontend
npm.cmd ci
Copy-Item .env.local.example .env.local
Set-Location ..
```

No es necesario activar el entorno; los comandos usan su intérprete directamente. `.env.local` solo contiene la URL local del backend y está ignorado por Git.

## 5. Ejecutar CaféIA localmente

Abre dos terminales PowerShell en la raíz.

### Backend

```powershell
$env:MODEL_PATH = "models/mobilenet_finetuned_epoch6.pt"
$env:MODEL_SHA256 = "4ab4e52fc3d417fe5fb126ff1e5b346f080c55ffa80232cffd5d6e6622e46c94"
$env:MODEL_ID = "mobilenet-v3-small-finetuned-epoch6"
$env:CORS_ALLOWED_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"
& .\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Comprobaciones:

- Salud: `http://127.0.0.1:8000/health`.
- OpenAPI: `http://127.0.0.1:8000/docs`.

### Frontend

```powershell
Set-Location frontend
npm.cmd run dev
```

Abre `http://localhost:3000`.

`MODEL_PATH` elige el checkpoint sin copiarlo sobre otro modelo. `MODEL_SHA256` impide iniciar con pesos inesperados. `CORS_ALLOWED_ORIGINS` es una lista de orígenes exactos, separados por comas y sin `/` final; no se admite `*`.

## 6. Pruebas y compilación

Instala una vez las dependencias de prueba:

```powershell
& .\.venv\Scripts\python.exe -m pip install -r requirements-test.txt
```

Pruebas del backend:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q tests/backend
```

- `test_api_contract.py` sustituye el predictor por un doble determinista. Comprueba contrato, JPG/PNG, contenido real, archivo vacío, exceso de 10 MB, discrepancia de formato y error interno. No prueba el modelo.
- `test_checkpoint_inference.py` verifica el hash, carga el checkpoint real y ejecuta una inferencia sobre una imagen sintética creada en memoria. Prueba integración técnica, no desempeño ni exactitud.

Frontend:

```powershell
Set-Location frontend
npm.cmd run test:request-flow
npm.cmd run build
```

La prueba cubre doble envío, cancelación, sustitución durante una petición, validación previa y error de conexión. La compilación ejecuta TypeScript y genera la salida optimizada.

El flujo manual de navegador pendiente de repetición está en `reports/MANUAL_BROWSER_WALKTHROUGH.md`.

## 7. Integración continua

`.github/workflows/ci.yml` define dos trabajos independientes en Ubuntu:

1. instala `requirements-api.txt` y `requirements-test.txt`, ejecuta pruebas con doble y la inferencia real del checkpoint;
2. ejecuta `npm ci`, las pruebas del flujo y `npm run build`.

La CI no descarga RoCoLe, no accede a `data/raw`, no consulta TEST y no entrena. La primera ejecución en GitHub ocurrirá después del próximo push; el commit local por sí solo no la activa.

## 8. Preparación y experimentación académica

El dataset no se distribuye en Git. Para reconstruirlo desde el ZIP autorizado:

```powershell
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe -m src.prepare --zip "C:\ruta\archive.zip"
```

La preparación valida imágenes, elimina duplicados exactos, excluye conflictos documentados y genera el manifiesto. No debe ejecutarse sobre el estado actual salvo que se pretenda reproducirlo desde cero, porque el manifiesto vigente es una evidencia fijada.

Los comandos históricos de entrenamiento son:

```powershell
& .\.venv\Scripts\python.exe -m src.train --model cnn --epochs 10
& .\.venv\Scripts\python.exe -m src.train --model mobilenet --epochs 10
& .\.venv\Scripts\python.exe -m src.train --model resnet18 --epochs 10
```

No los ejecutes para reemplazar el modelo activo. La selección final ya se cerró y TEST no puede reutilizarse para ajustar decisiones. El evaluador acepta rutas explícitas:

```powershell
& .\.venv\Scripts\python.exe -m src.evaluate --checkpoint "ruta\checkpoint.pt" --output-dir "carpeta\nueva" --model-label "etiqueta" --expected-samples 300 --uncertainty-threshold 0.70
```

Este comando se conserva por reproducibilidad, no como invitación a reevaluar y seleccionar con TEST.

`app.py` es la interfaz Streamlit heredada del primer prototipo. No participa en la aplicación Next.js/FastAPI ni en Render/Vercel; se conserva como evidencia del desarrollo inicial.

## 9. Resultados de la versión 1

| Modelo fijado | F1 macro VAL | F1 macro TEST | Accuracy TEST |
|---|---:|---:|---:|
| MobileNet ajustado, época 6 — activo | 0,647844 | 0,623486 | 0,716667 |
| MobileNet congelado, época 9 | 0,632707 | 0,629352 | 0,720000 |
| ResNet18 congelado, época 8 | 0,594740 | 0,608927 | 0,740000 |
| CNN pequeña, época 7 | 0,438571 | 0,427482 | 0,473333 |

TEST no reabrió la selección: el candidato activo había sido fijado previamente mediante validación. Ácaro rojo continúa siendo su clase más débil: F1 de TEST `0.354430`.

Con el umbral provisional `0.70`, 158/300 predicciones quedaron aceptadas, 140 fueron correctas y 18 incorrectas. La accuracy condicional fue `88.61 %` con cobertura `52.67 %`. No es una garantía para datos nuevos ni demuestra calibración.

## 10. Despliegue público: preparado, no ejecutado

### Backend en Render

`render.yaml` declara:

```text
Build: pip install -r requirements-api.txt
Start: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
Health: /health
```

La ruta `models/mobilenet_finetuned_epoch6.pt` coincide con el archivo incluido en Git. Render requiere definir `CORS_ALLOWED_ORIGINS` con el dominio HTTPS real del frontend.

### Frontend en Vercel

- Root Directory: `frontend`.
- Comando: `npm run build`.
- Variable: `NEXT_PUBLIC_API_URL=https://dominio-real-del-backend`, sin `/` final.

No hay todavía URL pública. Las direcciones `.example` son marcadores y no servicios activos. Tras publicar de forma autorizada se deben verificar `/health`, hash, CORS, memoria, archivo inválido, predicción y recuperación ante desconexión.

La medición local histórica fue aproximadamente 310 MiB de working set con el modelo cargado y 351 MiB durante predicción. Es orientativa; el consumo debe medirse de nuevo en Linux y en el servicio elegido.

## 11. Archivos versionados y material local

Git debe contener:

- backend, frontend y scripts reproducibles;
- manifiesto, reportes académicos y atribuciones;
- tres imágenes atribuidas de la guía;
- `models/mobilenet_finetuned_epoch6.pt` y ningún otro checkpoint;
- configuración de Render, Vercel y CI;
- plantillas `.env` sin secretos.

Git no debe contener:

- `.venv`, `node_modules`, `.next` o cachés;
- `data/raw` ni paquetes ZIP;
- descargas completas de procedencia;
- `experiments` ni checkpoints de respaldo;
- `.env` locales, tokens o credenciales.

Los archivos ignorados siguen siendo importantes localmente. No borres `data/raw`, `provenance`, `experiments` ni modelos de referencia mientras sean evidencia del trabajo académico.

## 12. Alcance y limitaciones

- Solo existen tres salidas; no cubre otras enfermedades, deficiencias o daños.
- No hay segmentación, localización de lesiones ni severidad.
- Las puntuaciones softmax no son probabilidades calibradas.
- El umbral `0.70` controla el mensaje de incertidumbre; no detecta hojas de otras especies ni objetos.
- La clase ácaro rojo tiene menor soporte y peor desempeño.
- Falta evaluación externa con plantas, sesiones y sitios independientes.
- La guía resume señales generales y no asigna una especie concreta de ácaro al dataset.
- CaféIA no reemplaza una evaluación agronómica experta.

## 13. Evidencias y atribución

- `reports/FINAL_PROTOCOL.md`: selección congelada antes de TEST.
- `reports/FINAL_TEST_RESULTS.md`: evaluación final.
- `reports/VALIDATION_MODEL_COMPARISON.md`: comparación por validación.
- `reports/DATASET_PROVENANCE_AUDIT.md`: procedencia y unidades originales.
- `reports/ORIGINAL_ANNOTATION_COMPARISON.md`: anotaciones y conflictos.
- `reports/RELIABILITY_AUDIT.md`: flujo web y errores de concurrencia.
- `reports/V2_PREPROCESSING_RESULTS.md`: candidato v2 descartado.
- `ATTRIBUTIONS.md`: licencias y fuentes de terceros.

El código del proyecto todavía no tiene una licencia propia. Elegirla antes de abrir públicamente el repositorio sigue siendo una decisión de la persona autora.
