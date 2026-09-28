# Propuesta del siguiente experimento: diversidad nueva de ácaro rojo

**Estado:** propuesta previa al entrenamiento. No se ha iniciado ninguna corrida.
**Restricciones:** no usar TEST histórico, no reemplazar el modelo web, no cambiar arquitectura, preprocesamiento, aumentos, optimizador, capas, BatchNorm, pesos de clase ni umbral 0.70 durante la comparación.

## Problema específico

El MobileNet activo tiene en VAL precision 0.357143, recall 0.483871 y F1 0.410959 para ácaro rojo. TRAIN contiene 93 imágenes de esta clase procedentes de 67 prefijos-planta, mientras sana y roya proceden de 215 y 189, respectivamente. Los pesos de clase ya compensan el recuento de imágenes, pero no la diversidad de plantas ni de condiciones de captura.

**Hipótesis:** añadir ejemplos de ácaro rojo confirmados por anotación experta y procedentes de plantas nuevas reducirá ácaro → roya sin depender de más épocas ni de otro cambio de arquitectura.

La evidencia actual no permite sostener esta mejora sin datos nuevos. No se propone sustituir esa carencia por sobremuestreo indefinido, más aumentos o búsqueda abierta de hiperparámetros.

## Datos que faltan antes de ejecutar

1. Un lote de desarrollo de al menos 60 plantas nuevas con la categoría ácaro rojo confirmada por una persona competente, con una o dos fotografías utilizables por planta y metadatos de planta, cara fotografiada, sitio/dispositivo y anotador.
2. Control de duplicados y similitud; ninguna planta, hoja o ráfaga puede aparecer en más de una partición.
3. Un conjunto externo separado, no usado para entrenar, seleccionar ni fijar umbrales, con las tres clases y al menos 30 plantas por clase. Ese mínimo es un presupuesto operativo, no una garantía de potencia estadística; antes de recolectar debe fijarse también el ancho de intervalo de confianza deseado.

La etiqueta debe venir de documentación/anotación, no de la apariencia inferida por el modelo. Si no se consiguen esos datos, el experimento se pospone.

### Justificación de estas metas operativas

Las 60 plantas nuevas no proceden de un cálculo de potencia: son una meta de captura factible que casi duplica las 67 plantas con ácaro disponibles en TRAIN y prioriza unidades biológicas nuevas sobre más fotografías correlacionadas de las mismas plantas. No garantizan una mejora ni una cobertura suficiente de sitios, temporadas o cultivares.

Las 30 plantas por clase forman una evaluación externa piloto balanceada de 90 unidades. Con una decisión por planta, un error equivale a 3,33 puntos de recall en su clase. En el peor caso binomial (`p = 0,5`), el error estándar con 30 unidades es aproximadamente 0,091 y el margen normal de 95 % ronda ±0,18: sirve para descubrir fallos grandes, no para sostener diferencias pequeñas. Como referencia, el mismo cálculo aproximado requiere 96 unidades independientes por clase para margen ±0,10 y 385 para ±0,05. Varias fotos de una planta no aumentan el número de unidades independientes.

Por ello, 60/30 es una puerta mínima de factibilidad. Antes de una afirmación fuerte se fijarán la diferencia mínima relevante, el ancho de intervalo y un cálculo formal con datos piloto. La búsqueda de fuentes y sus verificaciones pendientes está en `reports/RED_MITE_DATA_SOURCE_REVIEW.md`.

## Comparación controlada

Ambas ramas partirán del mismo SHA-256 activo `4ab4e52fc3d417fe5fb126ff1e5b346f080c55ffa80232cffd5d6e6622e46c94`.

- **Control:** TRAIN actual como fuente de ejemplos.
- **Candidato:** el mismo TRAIN más el lote nuevo de desarrollo de ácaro rojo como fuente de ejemplos.
- **Único cambio principal:** inclusión de plantas nuevas anotadas como ácaro rojo.
- **Constantes:** MobileNetV3 Small, redimensionamiento directo 224×224, normalización, aumentos, lote 16, entropía cruzada y los pesos v1 ya fijados, Adam, tasas `1e-5`/`1e-4`, capas entrenables y BatchNorm congelado.
- Para que el candidato no reciba simplemente más exposición de clase, ambas ramas usarán por cada bloque equivalente a una época exactamente 448 ejemplos sana, 93 ácaro y 339 roya. La regla será la misma en ambas ramas: selección uniforme por planta y rotación determinista de imágenes dentro de cada planta. En el control, los 93 ejemplos de ácaro proceden solo del conjunto actual; en el candidato, los 93 cupos rotan sobre el conjunto actual más las plantas nuevas. Así el número de contribuciones de cada clase y los pesos de pérdida permanecen iguales; cambia la diversidad disponible.
- Para evitar que un dataset mayor reciba simplemente más optimizaciones, ambas ramas tendrán el mismo número máximo de actualizaciones: 825, equivalente a 15 recorridos actuales de 55 lotes. Se evaluará VAL cada 55 actualizaciones y se aplicará paciencia 4 por F1 macro.
- Se ejecutarán tres pares predefinidos con semillas 42, 43 y 44. Cada par usará exactamente el mismo orden aleatorio entre control y candidato en lo que sea aplicable. Esto limita el presupuesto a seis corridas, sin búsqueda posterior.

El VAL actual queda congelado para selección de desarrollo. El TEST v1 no se abre ni se usa.

## Métricas y criterio previo

Por rama y semilla se guardarán F1 macro, precision/recall/F1 y soporte por clase, matriz de confusión, ácaro → roya, roya → ácaro, historial, duración y coste de inferencia. También se informará la media y dispersión entre semillas.

El candidato solo pasa la fase de desarrollo si, frente al control pareado:

1. mejora el F1 macro medio de VAL al menos 0.02;
2. mejora el recall medio de ácaro al menos 0.10 absoluto;
3. no reduce la precision media de ácaro más de 0.03;
4. no reduce el recall medio de sana ni de roya más de 0.05;
5. cumple 1 y 2 en al menos dos de las tres semillas.

Si falla cualquiera, se descarta como reemplazo. Si pasa, se congela antes de consultar una sola vez el conjunto externo nuevo. Para reemplazar el activo, la mejora de ácaro y F1 macro debe conservar la misma dirección frente al control en ese conjunto externo, sin ajustar nada después de verlo. Una diferencia pequeña con una sola semilla o solo en VAL no bastará.

## Evaluación futura del rechazo

Esta capacidad **no existe todavía**. Se evaluará como un componente distinto de la clasificación de tres clases y nunca usando el umbral softmax 0.70 como detector.

### Colección independiente

Se predefinirán cuatro estratos sin solapamiento con RoCoLe ni con los datos nuevos del clasificador:

1. hojas de café utilizables y dentro de las tres clases;
2. hojas de café con otras alteraciones no cubiertas;
3. fotografías no utilizables: desenfoque, sobre/subexposición, oclusión, hoja demasiado pequeña o varias hojas dominantes;
4. fuera de dominio: hojas de otras especies y objetos/no-hojas, con fondos y colores variados.

Los conjuntos de desarrollo y comprobación final se separarán por planta, sesión, dispositivo y fuente, con duplicados eliminados. Las etiquetas de calidad usarán una rúbrica escrita y doble revisión humana. No se seleccionarán ejemplos a partir de errores del TEST v1.

### Métricas

- sensibilidad de aceptación para café utilizable;
- tasa de falsa aceptación por cada estrato no utilizable/fuera de dominio;
- tasa de falso rechazo;
- AUROC y AUPRC del mecanismo de rechazo;
- cobertura y accuracy/F1 del clasificador exclusivamente entre casos aceptados, con intervalos de confianza;
- resultados separados por dispositivo, sitio y tipo de problema fotográfico.

Solo después de fijar un mecanismo explícito de calidad/OOD, calibrarlo en desarrollo y medirlo una vez en el conjunto independiente podrá afirmarse capacidad de rechazo. El color verde y la puntuación máxima del clasificador de tres clases no constituyen por sí solos ese mecanismo.
