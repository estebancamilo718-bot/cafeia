# Proyecto final: agente de clasificación de hojas de café

Proyecto para Visual Studio Code. Estado: preparación de 1481 imágenes verificada; la selección por validación y la evaluación final sobre las 300 imágenes reservadas ya están cerradas. CaféIA carga por variable de entorno el MobileNetV3 Small ajustado de la época 6, sin modificar su checkpoint original. Su F1 macro de validación fue 0.647844 y en TEST obtuvo accuracy 71.67 % y F1 macro 0.6235. Son resultados de ese conjunto fijado, no precisión clínica o agronómica ni garantías para fotografías nuevas. El MobileNet anterior y los experimentos CNN y ResNet18 siguen conservados.

## 1. Abrir y preparar (Windows)

1. Extrae esta carpeta y ábrela completa en Visual Studio Code mediante Archivo > Abrir carpeta.
2. Instala Python 3.11 de 64 bits si no lo tienes y la extensión Python de VS Code.
3. Abre Terminal > Nueva terminal, dentro de esta carpeta.
4. Ejecuta los comandos uno por uno en PowerShell. No es necesario activar el entorno ni cambiar la política de ejecución:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m src.prepare --zip "C:\ruta\archive.zip"
```

Si el ZIP está en otra carpeta, cambia solamente esa ruta. El ZIP del dataset no está incluido en esta plantilla para evitar duplicar aproximadamente 407 MB de imágenes. Usa el archivo que ya descargaste. La preparación verifica las imágenes, elimina duplicados exactos y genera el manifiesto y el informe de distribución.

En VS Code selecciona Python: Select Interpreter y elige `.venv` si no se selecciona automáticamente. Las versiones de requirements son intervalos compatibles de partida, no un entorno bloqueado y probado de entrenamiento. Después de una instalación funcional guarda `python -m pip freeze > requirements-lock.txt` usando el Python del entorno.

## 2. Ejecutar CaféIA localmente (Windows)

La API reutiliza `load_checkpoint()` y `transform(training=False)` de `src/common.py`, mantiene el modelo en memoria desde el arranque y no conserva ni crea copias de las fotografías recibidas. Abre dos terminales de PowerShell en la raíz del proyecto.

Primera terminal, backend:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-api.txt
$env:MODEL_PATH = "models/mobilenet_finetuned_epoch6.pt"
$env:MODEL_SHA256 = "4ab4e52fc3d417fe5fb126ff1e5b346f080c55ffa80232cffd5d6e6622e46c94"
$env:MODEL_ID = "mobilenet-v3-small-finetuned-epoch6"
$env:CORS_ALLOWED_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Comprueba la API en `http://127.0.0.1:8000/health`. La documentación interactiva de FastAPI queda en `http://127.0.0.1:8000/docs`.

Segunda terminal, frontend:

```powershell
Set-Location frontend
Copy-Item .env.local.example .env.local
npm.cmd install
npm.cmd run dev
```

Abre `http://localhost:3000`. Se usa `npm.cmd` porque PowerShell puede bloquear el script `npm.ps1` aunque Node.js esté instalado. Para comprobar la compilación de producción:

```powershell
Set-Location frontend
npm.cmd run build
```

`MODEL_PATH` selecciona el checkpoint sin copiarlo sobre `models/mobilenet.pt`. `MODEL_SHA256` hace que el backend rechace el arranque si el archivo no coincide con el candidato fijado en `reports/FINAL_PROTOCOL.md`; `MODEL_ID` aparece en `/health`. `NEXT_PUBLIC_API_URL` define la URL del backend para el navegador. `CORS_ALLOWED_ORIGINS` es una lista separada por comas de orígenes exactos, sin rutas ni `/` final; no se admite `*`.

### Preparación para Vercel y Render, todavía sin publicar

- Render puede leer `render.yaml` desde la raíz. Este instala `requirements-api.txt`, inicia `backend.main:app`, usa `/health` y fija `MODEL_PATH`, `MODEL_SHA256` y `MODEL_ID`. Solicita el valor explícito de `CORS_ALLOWED_ORIGINS`.
- El archivo desplegable es `models/mobilenet_finetuned_epoch6.pt`. Su SHA256 debe ser `4ab4e52fc3d417fe5fb126ff1e5b346f080c55ffa80232cffd5d6e6622e46c94`. Es el único `.pt` permitido expresamente por `.gitignore`; `experiments/`, `provenance/`, `.venv`, el dataset, `node_modules` y los artefactos de compilación quedan fuera del despliegue.
- En Vercel, selecciona `frontend` como **Root Directory** y configura `NEXT_PUBLIC_API_URL` con la URL HTTPS que Render asigne al backend, sin `/` final.
- Cuando Vercel asigne el dominio, configura en Render `CORS_ALLOWED_ORIGINS=https://dominio-real.vercel.app`. Agrega otros dominios solamente como elementos explícitos separados por comas.
- Antes de publicar, confirma en el repositorio que el checkpoint desplegable aparece incluido y que los directorios excluidos no están versionados. Después del primer despliegue, comprueba que `/health` devuelve `model_id: mobilenet-v3-small-finetuned-epoch6` y el SHA256 esperado antes de configurar el frontend.
- No se ha publicado ningún servicio. Las URLs reales se configuran cuando se autorice el despliegue.

Los comandos que ejecutará Render están declarados exactamente así:

```text
Build: pip install -r requirements-api.txt
Start: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
Health: /health
```

En Vercel, con `frontend` como **Root Directory**, el comando comprobado es `npm run build`. La variable de producción es `NEXT_PUBLIC_API_URL=https://nombre-real-del-backend.onrender.com`, sin `/` final. En Render, `CORS_ALLOWED_ORIGINS` debe contener el origen exacto asignado por Vercel, por ejemplo `https://nombre-real.vercel.app`; no uses comodines.

La medición local de un solo proceso Uvicorn en CPU fue 309.86 MiB de working set con el modelo cargado y un pico de 351.26 MiB durante las predicciones. El plan gratuito de Render declara 512 MB, por lo que hay margen limitado y el RSS debe comprobarse en sus métricas después de un despliegue autorizado. La memoria privada de Windows medida (776.87 MiB al cargar) no es directamente equivalente al RSS de Linux. No se contrató ningún plan. Detalles en `reports/WEB_MODEL_INTEGRATION.md`.

El repositorio local ya está inicializado en la rama `main`, todavía sin remoto. Antes del primer envío, verifica la selección de archivos:

```powershell
git status --short --ignored
git check-ignore -v models/mobilenet.pt
git check-ignore -v experiments/mobilenet_finetune_20260922-103426/best_checkpoint.pt
git check-ignore -v data/raw/coffee___healthy/C10P11H1.jpg
git check-ignore -v .venv/pyvenv.cfg
git check-ignore -v frontend/node_modules/next/package.json
git check-ignore -v models/mobilenet_finetuned_epoch6.pt
```

Los cinco primeros deben aparecer ignorados; el último no debe producir salida porque es el único checkpoint permitido para despliegue. Antes de un `git add`, revisa también que no se incluyan imágenes del dataset, `provenance/`, `.venv/`, `node_modules/` ni `experiments/`.

Referencias oficiales: [Render Blueprint](https://render.com/docs/blueprint-spec), [planes de cómputo de Render](https://render.com/docs/compute-plans), [variables de entorno de Vercel](https://vercel.com/docs/environment-variables) y [directorio raíz de monorepos en Vercel](https://vercel.com/docs/monorepos).

## 3. Entrenar el primer modelo

Primero una ejecución de comprobación (una época no equivale a un resultado final):

```powershell
.\.venv\Scripts\python.exe -m src.train --model mobilenet --epochs 1
```

Luego una primera corrida de trabajo:

```powershell
.\.venv\Scripts\python.exe -m src.train --model mobilenet --epochs 10
.\.venv\Scripts\python.exe -m streamlit run app.py
```

La primera ejecución descarga los pesos preentrenados y necesita internet. Sin CUDA disponible se utiliza CPU automáticamente; no se presupone aceleración en una GPU AMD. Si tarda demasiado, se puede usar Colab con GPU: subir y extraer esta carpeta, subir archive.zip, cambiar al directorio del proyecto, instalar requirements y ejecutar `python -m src.prepare --zip /content/archive.zip` y `python -m src.train --model mobilenet --epochs 10`. Descargar después `models/` y `reports/` y copiarlos en la carpeta local.

## 4. Comparación de soluciones

Los tres modelos ya tienen una corrida archivada de 10 épocas con semilla 42 y las mismas particiones. Los comandos reproducibles son:

```powershell
.\.venv\Scripts\python.exe -m src.train --model cnn --epochs 10
.\.venv\Scripts\python.exe -m src.train --model resnet18 --epochs 10
```

- CNN pequeña: modelo desde cero para tener una referencia sencilla.
- MobileNetV3 Small: extractor preentrenado congelado y clasificación adaptada a tres clases.
- ResNet18: segundo extractor preentrenado congelado para comparar.

La comparación por validación está en `reports/VALIDATION_MODEL_COMPARISON.md`. La evaluación final ya se ejecutó una sola vez con el protocolo congelado y está en `reports/FINAL_TEST_RESULTS.md`; sus evidencias están en `experiments/final_test_20260922/`. No se deben usar esos resultados para cambiar el checkpoint, el umbral, el preprocesamiento o los hiperparámetros.

El evaluador actual exige una ruta de checkpoint y una carpeta de salida explícitas; no acepta los antiguos argumentos `--model`. Su forma reproducible es:

```powershell
.\.venv\Scripts\python.exe -m src.evaluate --checkpoint "ruta\checkpoint.pt" --output-dir "carpeta\nueva" --model-label "etiqueta" --expected-samples 300 --uncertainty-threshold 0.70
```

No vuelvas a ejecutarlo para seleccionar modelos. Los JSON existentes contienen precision, recall y F1 por clase, accuracy, matriz de confusión, predicciones por imagen y análisis del umbral fijado.

## 5. Organización

| Archivo o carpeta | Uso |
|---|---|
| AGENTS.md | Contexto e instrucciones para Codex |
| src/prepare.py | Lectura del ZIP, auditoría, división y manifiesto |
| src/common.py | Lectura de imágenes, transformaciones y arquitecturas |
| src/train.py | Entrenamiento y selección por F1 macro de validación |
| src/evaluate.py | Evaluación final sobre prueba |
| app.py | Interfaz local para fotografías |
| backend/main.py | API FastAPI de CaféIA |
| frontend/ | Interfaz Next.js, TypeScript y Tailwind |
| render.yaml | Configuración preparada para Render |
| data/raw/ | Imágenes extraídas localmente |
| data/processed/manifest.csv | Identificadores y partición reproducible |
| models/ | Modelos entrenados |
| reports/ | Auditoría y resultados reales |
| docs/PLAN.md | Ruta académica y tareas pendientes |
| docs/REVISION_BIBLIOGRAFICA.md | Guía para investigar y documentar fuentes |

## 6. Empezar con Codex

Pega este mensaje en el panel de Codex con esta carpeta abierta:

> Lee AGENTS.md, LEEME.md y reports/VERIFICACION.md. Ayúdame con el siguiente paso de CaféIA sin reentrenar ni cambiar la partición salvo que lo solicite. Conserva las tres clases, registra solo resultados reales y explica brevemente cada paso.

## Alcance y límites

Entrada: imagen RGB de una hoja de café. Percepción: preprocesamiento y red convolucional profunda (CNN, una clase de DNN). Acción: emitir categoría y puntuación, o solicitar revisión cuando la puntuación sea baja. El aprendizaje se realiza fuera de línea; subir una foto no reentrena automáticamente la red.

Tres etiquetas disponibles, sin segmentación, localización de lesiones ni estimación de severidad. El ácaro rojo es una plaga; por precisión hablamos de condiciones o afectaciones, no de tres enfermedades. No se garantiza reconocer plantas diferentes ni enfermedades ausentes del conjunto. El umbral 0,70 de la interfaz es provisional y no está calibrado.

La agrupación por prefijo CxPy de los nombres es una decisión conservadora provisional: se observan nombres como C10P10E1 y C10P10H1. Debe confirmarse con la documentación original si corresponde a planta, hoja u otra unidad. No afirmar independencia biológica definitiva sin esa verificación. Las proporciones 60/20/20 son aproximadas por grupos; no se reparte cada foto al azar.

Fuentes de partida:
- Dataset aportado: https://www.kaggle.com/datasets/nirmalsankalana/rocole-a-robusta-coffee-leaf-images-dataset
- API MobileNet: https://docs.pytorch.org/vision/stable/models/generated/torchvision.models.mobilenet_v3_small.html
- Instrucciones académicas: PDF e imagen entregados por el usuario. El usuario confirmó que las instrucciones del PDF 2025B también aplican en 2026; la diferencia sobre duración de exposiciones todavía debe aclararse con el docente.

## Hallazgo real de auditoría

24 archivos con etiquetas contradictorias excluidos provisionalmente y 55 copias duplicadas eliminadas: quedan 1481 imágenes (758 sanas, 568 roya, 155 ácaro rojo). Los grupos CxPy vinculados por duplicados se unen antes de dividir. Consulta reports/dataset_audit.json. No se corrigen etiquetas por suposición.
