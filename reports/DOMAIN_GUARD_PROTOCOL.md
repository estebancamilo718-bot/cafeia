# Protocolo del filtro experimental de dominio

**Estado:** fijado antes de construir o evaluar el filtro.

## Objetivo

Comprobar si las representaciones internas del MobileNet activo permiten rechazar fotografías claramente ajenas al dominio de CaféIA sin usar la puntuación softmax ni modificar el clasificador de sana, ácaro rojo y roya.

Este componente no se presentará como detector de hojas de café hasta superar la evaluación indicada aquí. Aunque la supere, el resultado será una comprobación de desarrollo sobre fuentes concretas, no una garantía universal.

## Datos y separación

- Referencias del dominio: solo imágenes de `train` del manifiesto vigente.
- Calibración del umbral: una mitad determinista de grupos `CxPy` de `val`.
- Evaluación positiva: la otra mitad de grupos de `val`, sin grupos compartidos con calibración.
- Negativos hoja/no café: muestra reproducible de PlantVillage, incluyendo hojas sanas de otros cultivos y tomate con ácaro. No se transformarán esas etiquetas en categorías de café.
- Negativos objeto/no hoja: muestra reproducible de repositorios públicos independientes, con resultado separado para perros.
- No se consultará ni reutilizará TEST de CaféIA.

Los archivos externos permanecerán bajo `provenance/` y fuera de Git. Se conservarán URL, identificador, hash y atribución en el manifiesto local.

## Método fijado

1. Cargar el checkpoint activo sin modificarlo.
2. Extraer el vector penúltimo de MobileNetV3 Small, después de `classifier[1]` y antes de dropout/capa final.
3. Normalizar cada vector con norma L2.
4. Conservar como banco de referencia los vectores de TRAIN.
5. Definir el score de dominio como el promedio de las cinco mayores similitudes coseno con TRAIN.
6. Fijar el umbral en el percentil 5 de los scores de calibración de VAL, sin mirar negativos.
7. Aceptar como compatible con el dominio si `score >= umbral`.

Este score no es una probabilidad y no diagnostica una categoría.

## Criterios previos de integración

El filtro solo podrá pasar a una integración experimental si cumple simultáneamente:

1. aceptación global de café en la mitad de evaluación de VAL >= 90 %;
2. aceptación de cada clase de café >= 80 %;
3. rechazo de hojas PlantVillage ajenas al café >= 90 %;
4. rechazo de objetos/no-hojas externos >= 95 %;
5. rechazo de perros externos >= 95 %.

Si falla cualquier criterio, se conservará como resultado negativo y el backend seguirá sin afirmar que detecta café/no café.

## Limitaciones conocidas

- La muestra de objetos no representa todos los objetos, encuadres o dispositivos posibles.
- PlantVillage usa fondos y condiciones diferentes de muchas fotos de campo.
- RoCoLe procede de un dominio limitado.
- Un filtro de distancia puede aceptar entradas desconocidas cercanas a sus referencias o rechazar hojas válidas diferentes.
- Superar este protocolo no reemplaza un conjunto externo capturado bajo las condiciones reales de operación.

## Enmienda previa a la evaluación

La descarga monolítica de CIFAR-10 se interrumpió al 1,9 % por su velocidad y no se utilizó. Además, sus imágenes de 32×32 píxeles eran poco representativas de una carga web real. El acceso automatizado previsto a Wikimedia Commons respondió con límite de solicitudes y tampoco produjo ejemplos usados en la evaluación.

Antes de ejecutar la evaluación externa, esos negativos se sustituyeron por una selección determinista de 25 perros del repositorio `jigsawpieces/dog-api-images`, 25 gatos de `NotAShelf/catApi` y 25 escenas u objetos de los ejemplos de OpenCV. Se conservaron los mismos criterios de aceptación y los negativos no intervinieron en el cálculo del umbral. El manifiesto local registra URL, hash, atribución y licencia de cada archivo.
