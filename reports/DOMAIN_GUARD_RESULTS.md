# Resultado del filtro experimental de dominio

**Fecha:** 2026-10-18

**Estado:** integrado como barrera experimental previa; no modifica el clasificador de tres clases.

**Uso de TEST:** ninguno.

## Decisión

Se integró un filtro de similitud en el espacio interno del mismo MobileNet activo. Su función es evitar que la API fuerce una categoría de café en ejemplos claramente alejados de las imágenes de desarrollo. Si la similitud no alcanza el umbral fijado, la API responde `outside_domain`, deja vacías las tres puntuaciones y muestra:

> No se pudo confirmar que la imagen corresponda a una hoja de café. Carga una fotografía de una sola hoja de café.

El score de dominio no es una probabilidad. El umbral de incertidumbre del clasificador permanece en 0,70 y no se usa para decidir café/no café.

## Artefactos fijados

| Elemento | Valor |
|---|---|
| Checkpoint activo | `models/mobilenet_finetuned_epoch6.pt` |
| SHA256 del checkpoint | `4ab4e52fc3d417fe5fb126ff1e5b346f080c55ffa80232cffd5d6e6622e46c94` |
| Filtro desplegable | `models/coffee_domain_guard.pt` |
| SHA256 del filtro | `8060ef83e4a018d6a49e22fc5b59162f4ec6cbba90482e27d7896c79106d90e7` |
| Método | media de las 5 mayores similitudes coseno contra 880 embeddings de TRAIN |
| Umbral de dominio | `0.6497240662574768` |
| Calibración | mitad de grupos de VAL, separada por grupo de la evaluación |

El filtro verifica al iniciar que su metadato de checkpoint y el orden de clases coincidan con el modelo cargado. El backend también exige el SHA256 esperado de ambos artefactos.

## Resultados de desarrollo

### Hojas de café de VAL reservadas para esta comprobación

| Clase anotada | Aceptadas | Total | Tasa de aceptación |
|---|---:|---:|---:|
| Sana | 72 | 75 | 96,00 % |
| Ácaro rojo | 12 | 13 | 92,31 % |
| Roya | 57 | 65 | 87,69 % |
| **Total** | **141** | **153** | **92,16 %** |

El filtro rechazó 12 hojas de café válidas de esta porción de VAL: 3 sanas, 1 de ácaro rojo y 8 de roya. Es un coste real de la barrera y debe comunicarse al usuario como solicitud de otra fotografía, no como ausencia de enfermedad.

### Negativos externos

| Fuente y categoría documental | Rechazadas | Total | Tasa de rechazo |
|---|---:|---:|---:|
| PlantVillage: hojas de manzano, uva, papa y tomate; tomate con araña roja | 125 | 125 | 100 % |
| Fotografías de perros | 25 | 25 | 100 % |
| Fotografías de gatos | 25 | 25 | 100 % |
| Escenas y objetos variados de OpenCV | 25 | 25 | 100 % |
| **Total externo** | **200** | **200** | **100 %** |

Fuentes conservadas en el manifiesto local ignorado por Git:

- PlantVillage: <https://github.com/spMohanty/PlantVillage-Dataset>
- perros: <https://github.com/jigsawpieces/dog-api-images>
- gatos: <https://github.com/NotAShelf/catApi>
- escenas/objetos: <https://github.com/opencv/opencv/tree/5.x/samples/data>

## Verificación de integración

Con el checkpoint y el filtro reales se enviaron tres archivos a `POST /predict`:

| Ejemplo | Procedencia | Score de dominio | Respuesta |
|---|---|---:|---|
| `C10P12E1.jpg` | RoCoLe, TRAIN, sana | 0,817994 | `classified`; hoja sana, score 0,818985 |
| `Fury_01.jpg` | repositorio externo de perros | 0,241393 | `outside_domain`; sin categoría ni scores de café |
| `03d9267c-...HL 5671.JPG` | PlantVillage, manzano sano | 0,260898 | `outside_domain`; sin categoría ni scores de café |

La prueba unitaria adicional comprueba que el cálculo conjunto de logits y embedding produce los mismos logits que el `forward` original del modelo.

## Alcance y límites

- Pasar este conjunto de desarrollo no demuestra rechazo universal de perros, objetos, otras plantas ni fotografías inutilizables.
- PlantVillage tiene condiciones visuales distintas de una captura móvil de campo; un duplicado recodificado o un dominio nuevo podría comportarse de otra manera.
- Una imagen aceptada por el filtro aún puede no ser café, y una hoja de café válida puede ser rechazada.
- El filtro no mejora por sí mismo la distinción entre sana, roya y ácaro rojo. La limitación conocida de ácaro rojo permanece.
- TEST de CaféIA no se reutilizó para construir, calibrar ni evaluar esta decisión.

## Evidencia reproducible

- protocolo previo: `reports/DOMAIN_GUARD_PROTOCOL.md`;
- constructor: `src/build_domain_guard.py`;
- preparador de negativos: `src/prepare_ood_benchmark.py`;
- evaluador: `src/evaluate_domain_guard.py`;
- evidencia local completa: `experiments/domain_guard_20261018-001/`;
- pruebas: `tests/backend/test_domain_guard.py` y `tests/backend/test_api_contract.py`.

Las imágenes externas y los ejemplos de RoCoLe no se incorporan al frontend ni se publican en Git.
