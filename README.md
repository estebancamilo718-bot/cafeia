# CaféIA

CaféIA es un prototipo académico para clasificar fotografías de hojas de café en tres categorías: hoja sana, roya y ácaro rojo. La aplicación usa un backend FastAPI y una interfaz Next.js con TypeScript y Tailwind.

El modelo desplegable es MobileNetV3 Small ajustado, época 6, seleccionado por F1 macro de validación. En el conjunto final fijado de 300 imágenes obtuvo accuracy de 71.67 % y F1 macro de 0.6235. Estas cifras describen únicamente ese conjunto; las puntuaciones de la interfaz no son probabilidades calibradas, no garantizan acierto en fotografías nuevas y no comprueban que la imagen corresponda a una hoja de café.

## Ejecución local

Las instrucciones completas para Windows, las variables de entorno y los comandos de despliegue están en [LEEME.md](LEEME.md). Resumen:

```powershell
# Terminal 1, desde la raíz
$env:MODEL_PATH = "models/mobilenet_finetuned_epoch6.pt"
$env:MODEL_SHA256 = "4ab4e52fc3d417fe5fb126ff1e5b346f080c55ffa80232cffd5d6e6622e46c94"
$env:MODEL_ID = "mobilenet-v3-small-finetuned-epoch6"
$env:CORS_ALLOWED_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

# Terminal 2
Set-Location frontend
Copy-Item .env.local.example .env.local
npm.cmd install
npm.cmd run dev
```

Abre `http://localhost:3000`. El backend expone su estado en `http://127.0.0.1:8000/health`.

## Modelo e integridad

- Checkpoint desplegable: `models/mobilenet_finetuned_epoch6.pt`.
- SHA256: `4ab4e52fc3d417fe5fb126ff1e5b346f080c55ffa80232cffd5d6e6622e46c94`.
- Orden interno fijado: `coffee___healthy`, `coffee___red_spider_mite`, `coffee___rust`.
- Umbral provisional de incertidumbre: 0.70.

El backend verifica el hash antes de cargar el modelo. Los experimentos, respaldos, imágenes y descargas originales no se incluyen en Git.

## Evidencias

- [Protocolo final](reports/FINAL_PROTOCOL.md)
- [Resultados finales](reports/FINAL_TEST_RESULTS.md)
- [Comparación de validación](reports/VALIDATION_MODEL_COMPARISON.md)
- [Auditoría de procedencia](reports/DATASET_PROVENANCE_AUDIT.md)
- [Integración web](reports/WEB_MODEL_INTEGRATION.md)

## Atribución

El dataset no se distribuye en este repositorio. La atribución de RoCoLe, su licencia declarada y las observaciones sobre la versión derivada están en [ATTRIBUTIONS.md](ATTRIBUTIONS.md). Las dependencias conservan las licencias declaradas en sus respectivos paquetes.
