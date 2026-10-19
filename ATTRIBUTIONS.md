# Atribuciones y licencias de terceros

## Dataset RoCoLe

El dataset de imágenes no se incluye en este repositorio. El checkpoint desplegable fue entrenado a partir de la versión limpia documentada del dataset derivado de RoCoLe.

- **Título:** *RoCoLe: A robusta coffee leaf images dataset*.
- **Autores:** Jorge Parraga-Alava, Kevin Cusme, Angélica Loor y Esneider Santander.
- **Repositorio original:** [Mendeley Data, versión 2](https://data.mendeley.com/datasets/c5yvn32dzg/2).
- **DOI del dataset:** [10.17632/c5yvn32dzg.2](https://doi.org/10.17632/c5yvn32dzg.2).
- **Artículo:** [Parraga-Alava et al., *Data in Brief* 25 (2019), 104414](https://doi.org/10.1016/j.dib.2019.104414).
- **Licencia declarada por el repositorio original:** [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/).

La copia derivada usada para preparar el proyecto se obtuvo de [Kaggle](https://www.kaggle.com/datasets/nirmalsankalana/rocole-a-robusta-coffee-leaf-images-dataset). Kaggle y Mendeley muestran licencias distintas; esa discrepancia está documentada y no se interpreta como una sustitución de la licencia original. Véanse `reports/DATASET_PROVENANCE_AUDIT.md` y `reports/ORIGINAL_ANNOTATION_COMPARISON.md`.

El registro local completo de atribución, sin las descargas ni las imágenes, se conserva en `provenance/rocole_mendeley_v2/README.md`.

## CoffeeLeaf-CO / DECAFIA

CoffeeLeaf-CO v2.0.0 se usó de forma separada para auditar un candidato experimental del filtro de dominio. Sus imágenes no se incorporaron al clasificador, a la guía ni al repositorio, y el artefacto candidato no se despliega.

- **Registro oficial:** [Zenodo, versión 2.0.0](https://zenodo.org/records/22756170).
- **DOI:** [10.5281/zenodo.22756170](https://doi.org/10.5281/zenodo.22756170).
- **Repositorio de los autores:** [estebanr25/decafia-research](https://github.com/estebanr25/decafia-research).
- **Licencia declarada:** [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/).

La verificación de integridad, las inconsistencias documentales encontradas y el alcance exacto del uso están en `reports/COFFEELEAF_DOMAIN_GUARD_EXPERIMENT.md`.

## Modelo y software

El modelo desplegable usa MobileNetV3 Small y pesos preentrenados proporcionados por [TorchVision](https://pytorch.org/vision/stable/models/generated/torchvision.models.mobilenet_v3_small.html), posteriormente ajustados con el dataset del proyecto.

Las dependencias Python se declaran en `requirements*.txt`. Las dependencias JavaScript, sus versiones y metadatos de licencia se conservan en `frontend/package-lock.json`. Cada dependencia mantiene su propia licencia; este documento no la reemplaza.

Este repositorio no asigna por sí mismo una licencia adicional al código original del proyecto. Aunque el repositorio ya es público, la persona autora aún debe escoger y añadir explícitamente una licencia para conceder permisos de reutilización sobre ese código.
