# Preparación del repositorio GitHub

**Fecha:** 2026-09-23
**Rama local:** `main`
**Remoto:** no configurado al preparar esta versión.

## Repositorio e inclusión prevista

No existía un repositorio Git en esta carpeta. Se inicializó uno nuevo sin borrar ni mover archivos locales. La selección final contiene 57 archivos y aproximadamente 6,38 MiB.

Los archivos de mayor tamaño previstos eran:

| Ruta | Bytes |
|---|---:|
| `models/mobilenet_finetuned_epoch6.pt` | 6,208,871 |
| `data/processed/manifest.csv` | 195,139 |
| `frontend/package-lock.json` | 57,264 |
| `src/audit_rocole_annotations.py` | 18,964 |
| `src/finetune_mobilenet.py` | 18,439 |
| `frontend/app/page.tsx` | 18,210 |
| `reports/DATASET_PROVENANCE_AUDIT.md` | 17,019 |

El manifiesto se conserva como metadato reproducible; las imágenes a las que hace referencia no se versionan.

## Checkpoint de despliegue

- Ruta incluida: `models/mobilenet_finetuned_epoch6.pt`.
- SHA256 verificado: `4ab4e52fc3d417fe5fb126ff1e5b346f080c55ffa80232cffd5d6e6622e46c94`.
- `render.yaml` configura exactamente `MODEL_PATH=models/mobilenet_finetuned_epoch6.pt`.
- El backend usa la misma ruta como valor predeterminado y verifica `MODEL_SHA256` antes de cargar el archivo.

Los checkpoints `models/mobilenet.pt`, `models/cnn.pt`, `models/resnet18.pt` y todos los checkpoints de `experiments/` permanecen localmente, pero están excluidos de Git.

## Exclusiones verificadas

`git check-ignore -v` confirmó la exclusión de:

- `.venv/` y cachés Python;
- `frontend/node_modules/`, `frontend/.next/` y `*.tsbuildinfo`;
- `data/raw/` y archivos comprimidos;
- descargas y evidencias voluminosas de `provenance/`;
- `experiments/`, respaldos y todos los demás archivos `.pt`;
- archivos `.env` locales, temporales, logs y metadatos del sistema;
- capturas PNG de verificación que contienen ejemplos visuales del dataset.

Se conservaron expresamente `.env.example`, `.env.backend.example`, `frontend/.env.local.example`, `provenance/rocole_mendeley_v2/README.md` y el checkpoint desplegable.

## Revisión de seguridad y procedencia

- No se encontraron rutas absolutas de perfiles personales dentro de los archivos previstos.
- No se encontraron claves privadas, tokens comunes, credenciales embebidas ni URLs con usuario y contraseña.
- Las configuraciones de producción dependen de variables de entorno; los dominios presentes en `.env.example` son marcadores `.example`.
- `ATTRIBUTIONS.md` y el README textual de procedencia conservan autores, DOI y licencia declarada de RoCoLe sin incluir el dataset descargado.
- No se asignó automáticamente una licencia nueva al código propio del proyecto.

La revisión final del índice y el commit local deben hacerse después de añadir este informe.
