# Protocolo exploratorio: profundidad del ajuste fino de MobileNet

**Registrado antes del entrenamiento:** 2026-09-30

**Estado inicial:** protocolo fijado; ninguna corrida de este experimento se había ejecutado al registrar este documento.

**Alcance:** TRAIN y VAL de RoCoLe limpio. TEST, las 15 imágenes de integración y fotografías externas quedan excluidos.

## Pregunta e hipótesis

El ajuste fino anterior solo adaptó los tres últimos módulos de `model.features`. La hipótesis exploratoria es que adaptar tres módulos adicionales de MobileNetV3 Small puede representar mejor las señales visuales de hoja sana, roya y daño por ácaro rojo sin cambiar ninguna otra parte del entrenamiento.

El único cambio principal será la profundidad de ajuste fino:

| Rama | Módulos entrenables del extractor | Clasificador entrenable | Parámetros entrenables |
|---|---|---|---:|
| Control | `features.10`, `features.11`, `features.12` | `classifier.3` | 647.715 (42,59 %) |
| Candidato | `features.7`, `features.8`, `features.9`, `features.10`, `features.11`, `features.12` | `classifier.3` | 791.331 (52,03 %) |

Los módulos adicionales `features.7–9` son tres bloques `InvertedResidual`; `features.9` realiza la reducción espacial que precede a los bloques finales. Los módulos `features.0–6` y `classifier.0` permanecen congelados.

## Punto de partida fijado

- Checkpoint: `experiments/mobilenet_finetune_20260922-103426/candidate_initial_epoch0.pt`.
- Copia equivalente conservada: `models/mobilenet.pt`.
- SHA-256: `9248cc767425c9efec643bcc2cabd758e8f2b28ab4a6967908713fc1d0b9c5c1`.
- F1 macro inicial de VAL: `0.6327072392132633`.
- Manifiesto: `data/processed/manifest.csv`.
- SHA-256 del manifiesto: `1ea21d6b2b480b830065c5d4d1d90f531234cc2aa244d7bb98c5873363866dab`.
- Orden de clases del checkpoint: `coffee___healthy`, `coffee___red_spider_mite`, `coffee___rust`.

Todas las corridas partirán de esos mismos pesos, no del candidato activo de época 6. El optimizador se inicializará desde cero en cada corrida.

## Constantes controladas

- Arquitectura: MobileNetV3 Small, sin cambios.
- Particiones: 880 TRAIN y 301 VAL del manifiesto vigente.
- Preprocesamiento: corrección EXIF, conversión RGB, `Resize((224, 224))` de torchvision con su interpolación bilineal vigente, `ToTensor` y normalización ImageNet (`mean=[0.485, 0.456, 0.406]`, `std=[0.229, 0.224, 0.225]`).
- Aumentos solo en TRAIN y en el orden existente: redimensionamiento, `RandomHorizontalFlip`, `RandomRotation(15)`, tensor y normalización.
- Pérdida: entropía cruzada con los pesos calculados solo en TRAIN: sana `0.6547619048`, ácaro `3.1541218638`, roya `0.8652900688`.
- Optimizador: Adam con valores predeterminados de PyTorch.
- Tasa del extractor: `1e-5` para todos los módulos `features` descongelados.
- Tasa del clasificador: `1e-4` para `classifier.3`.
- BatchNorm: `running_mean`, `running_var` y `num_batches_tracked` congelados mediante modo evaluación en cada época; los parámetros afines dentro de módulos descongelados conservan gradientes, igual que en el ajuste anterior.
- Lote: 16; CPU si no hay CUDA; sin aumento en VAL.
- Semillas prefijadas: `42`, `43`, `44` para ambas ramas.

Se comprobará por corrida que el optimizador contiene exactamente todos los parámetros entrenables, las convoluciones descongeladas reciben gradientes y las estadísticas BatchNorm no cambian.

## Presupuesto y parada

- Seis corridas: tres semillas × dos ramas.
- Máximo: 15 épocas por corrida.
- Parada temprana: cuatro épocas consecutivas sin mejorar el F1 macro de VAL.
- El checkpoint inicial de época 0 participa como candidato; una corrida puede seleccionar época 0 si el entrenamiento no mejora.
- Selección interna de cada corrida: exclusivamente mayor F1 macro de VAL.
- No se encadenará otro experimento a partir del resultado.

El máximo teórico es 90 épocas, aunque la parada temprana puede reducirlo. El candidato aumenta el coste de entrenamiento porque calcula gradientes en más capas. La arquitectura de inferencia no cambia, por lo que no se espera modificar el número de parámetros ni el coste de una pasada de inferencia.

## Métricas y comparación

Para cada semilla y rama se archivarán historial, duración, checkpoint seleccionado, F1 macro, accuracy descriptiva, precision/recall/F1 por clase y matriz de confusión de VAL. La comparación principal usará:

1. diferencia pareada candidato menos control de F1 macro para cada semilla;
2. promedio y desviación estándar muestral entre las tres semillas;
3. promedio y dispersión de precision, recall y F1 de cada clase;
4. duración y parámetros entrenables como coste.

La accuracy no será criterio de selección.

## Criterio operativo fijado antes de observar resultados

El candidato solo se recomendará para una evaluación posterior si cumple simultáneamente:

1. mejora media de F1 macro de al menos `0.010` frente al control;
2. diferencia de F1 macro positiva en al menos dos de las tres parejas de semillas;
3. ningún recall medio por clase retrocede más de `0.020` frente al control.

Los umbrales son criterios operativos del experimento, no garantías estadísticas. Con solo tres semillas se informará la dispersión y no se afirmará generalización. VAL ya se utilizó en decisiones anteriores; incluso un candidato que cumpla el criterio no reemplazará automáticamente el modelo web ni justificará volver a usar TEST.

## Conservación

- El modelo web activo `models/mobilenet_finetuned_epoch6.pt` no se sobrescribirá.
- `models/mobilenet.pt`, el manifiesto, las particiones y los experimentos anteriores permanecerán intactos.
- Xinzhai queda cerrado como fuente no apta para ácaro rojo; sus imágenes externas no se incorporan.
- No se cambiará el umbral provisional `0.70`.
