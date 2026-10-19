# Protocolo V2 de generalización de dominio

> **Nota de ejecución (2026-10-19):** la rama del filtro con referencias de CoffeeLeaf-CO se ejecutó sin entrenamiento y quedó archivada como candidata, no integrada. La comprobación externa de BRACOL fijada aquí sigue pendiente; por ello no se activó el artefacto. La auditoría, los resultados y la decisión están en `reports/COFFEELEAF_DOMAIN_GUARD_EXPERIMENT.md`. El resto de este documento se conserva sin reescribir como registro previo.

**Fecha de registro:** 2026-10-18

**Estado:** protocolo previo a la descarga, inspección y entrenamiento

**Alcance:** filtro café/no café y clasificador de `sana`, `roya` y `ácaro rojo`

## 1. Decisión que motiva este protocolo

El filtro de dominio activo reconoce bien ejemplos cercanos a RoCoLe, pero puede rechazar hojas de café reales fotografiadas con otras cámaras, fondos, distancias o condiciones de luz. El clasificador también fue desarrollado principalmente con RoCoLe, por lo que una respuesta correcta dentro de ese conjunto no demuestra generalización a fotografías externas.

El objetivo de esta versión es comprobar, mediante una comparación controlada, si datos externos con procedencia y licencia verificables reducen esos rechazos sin aumentar de forma inaceptable la aceptación de imágenes ajenas al café ni perjudicar la clasificación de las tres clases actuales.

Este protocolo **no autoriza todavía ninguna descarga ni entrenamiento**. Tampoco autoriza sustituir los modelos activos.

## 2. Hechos documentados sobre las fuentes

### 2.1. DECAFIA / CoffeeLeaf-CO, versión 2.0.0

Fuentes primarias:

- registro de datos: [Zenodo, DOI 10.5281/zenodo.22756170](https://doi.org/10.5281/zenodo.22756170);
- repositorio de los autores: [estebanr25/decafia-research](https://github.com/estebanr25/decafia-research);
- subconjunto brasileño redistribuido por los autores: [Silva et al., DOI 10.17632/vfxf4trtcg.5](https://doi.org/10.17632/vfxf4trtcg.5).

Hechos declarados por sus autores:

- licencia de las imágenes y anotaciones: **CC BY 4.0**;
- 2.315 imágenes, 12.794 instancias anotadas mediante cajas y 1.113 imágenes de fondo descritas como hojas sanas;
- 1.705 imágenes son capturas propias de *Coffea arabica* en El Socorro, Santander, Colombia, con teléfonos Android, luz natural y sin un montaje controlado;
- 610 imágenes proceden de Silva et al. y conservan licencia CC BY 4.0;
- las clases de detección son `roya`, `coco` o `vaquita` y `minador`;
- la anotación se realizó con dos anotadores independientes y adjudicación de desacuerdos; se informa un kappa de Cohen de 0,91;
- el manifiesto publicado registra por imagen el nombre, la partición, la fuente, SHA256, cantidad de anotaciones y clases presentes;
- la versión 1 contenía 454 imágenes de RoCoLe; la versión 2 declara haberlas eliminado.

Limitaciones documentales:

- es un conjunto de **detección por cajas**, no una clasificación exclusiva de la hoja completa;
- una imagen puede contener más de una alteración o más de una hoja;
- `sana` no es una clase detectada: los autores representan hojas sanas mediante archivos de etiquetas vacíos;
- la documentación pública revisada no proporciona identificadores inequívocos de planta, hoja o sesión para todas las imágenes;
- no contiene una clase de ácaro rojo.

### 2.2. BRACOL, versión 1

Fuentes primarias:

- datos de los autores: [Mendeley Data, DOI 10.17632/yy2k5y8mxg.1](https://doi.org/10.17632/yy2k5y8mxg.1);
- publicación asociada: [Esgario, Krohling y Ventura, DOI 10.1016/j.compag.2019.105162](https://doi.org/10.1016/j.compag.2019.105162).

Hechos declarados por sus autores:

- licencia: **CC BY 4.0**;
- 1.747 fotografías originales de hojas completas de *Coffea arabica*;
- incluye hojas sanas y hojas afectadas por roya, minador, mancha marrón o phoma y cercospora;
- las fotografías se tomaron con distintos teléfonos y en distintas épocas en Espírito Santo, Brasil;
- muestran principalmente el envés de la hoja, sobre fondo blanco y bajo condiciones parcialmente controladas;
- el reconocimiento de los estreses para el etiquetado fue asistido por una persona experta;
- el repositorio distingue las imágenes originales de hoja completa de un conjunto derivado de recortes de síntomas;
- una hoja puede presentar uno o más estreses y la etiqueta de hoja corresponde al estrés predominante.

Limitaciones documentales:

- no contiene una clase de ácaro rojo;
- la documentación pública revisada no aporta identificadores inequívocos de planta, hoja o sesión;
- el fondo blanco y el encuadre controlado no representan por sí solos fotografías de campo o imágenes encontradas en Internet.

### 2.3. Lo que no se afirmará

- No se asumirá independencia de RoCoLe solo porque cambien el país, la especie de café, el dispositivo o los autores. Esa independencia debe comprobarse mediante archivos y hashes.
- No se considerará que una caja de roya convierte automáticamente toda la fotografía en una muestra de clasificación `roya`.
- No se interpretará un archivo de anotaciones vacío como `sana` fuera de los casos que la propia fuente identifique expresamente como hoja sana.
- No se mapeará minador, phoma, cercospora, coco, imágenes multiclase o casos indeterminados a `sana`.
- No se afirmará una mejora para ácaro rojo: ninguna de estas dos fuentes aporta ejemplos externos verificados de esa clase.

## 3. Hipótesis e intervenciones controladas

### 3.1. Filtro de dominio

**Problema específico:** el filtro actual se construyó con referencias de TRAIN de RoCoLe y rechaza algunas hojas válidas cuyo aspecto difiere de ese dominio.

**Hipótesis:** agregar al desarrollo referencias auditadas de hojas de café tomadas en campo en CoffeeLeaf-CO aumentará la cobertura de hojas reales externas sin perder de forma material la capacidad de rechazar entradas no relacionadas con café.

**Cambio principal:** diversidad de las referencias positivas de café. Se mantendrán iguales el extractor, el preprocesamiento, las referencias negativas, la semilla y la regla de cálculo del score. Cualquier cambio adicional exigirá otro protocolo.

**Control:** filtro activo `models/coffee_domain_guard.pt`, evaluado sin alteraciones.

**Candidato:** mismo procedimiento del control, con las referencias positivas elegibles de la captura propia de CoffeeLeaf-CO agregadas al conjunto de desarrollo. Si el artefacto guarda todas las representaciones y su tamaño resulta inviable, cualquier reducción mediante prototipos se tratará como una intervención adicional y no se mezclará con esta comparación.

### 3.2. Clasificador de tres clases

**Problema específico:** el clasificador puede depender de fondos, iluminación y encuadres propios de RoCoLe.

**Hipótesis condicionada:** ejemplos externos confirmados de hoja sana y roya podrían mejorar la representación de esas dos clases fuera de RoCoLe, siempre que su conversión a etiqueta de imagen completa sea válida y no perjudique ácaro rojo.

**Condición previa obligatoria:** el experimento de clasificador no se ejecutará si una revisión humana documentada no puede construir un subconjunto inequívoco. La revisión debe excluir imágenes con varias hojas relevantes, varias clases, lesiones de otra alteración o correspondencia dudosa entre caja y hoja principal. Una predicción de CaféIA nunca podrá validar una etiqueta.

**Cambio principal:** adición de ejemplos externos auditados de `sana` y `roya` procedentes solo de la captura propia de CoffeeLeaf-CO. Se mantendrán arquitectura, checkpoint inicial, preprocesamiento, aumentos, optimizador, capas entrenables, BatchNorm, presupuesto y semillas de la configuración de control fijada antes de entrenar. El muestreo deberá impedir que el mayor número de ejemplos de sana o roya desplace a ácaro rojo.

**Control:** una corrida reproducible con la configuración vigente y sin imágenes externas, iniciada desde el mismo checkpoint que el candidato. No se considerará equivalente un control iniciado desde pesos distintos.

**Candidato:** el mismo control más el subconjunto externo auditado. BRACOL no formará parte del entrenamiento ni de la selección.

## 4. Separación entre desarrollo y evaluación externa

### 4.1. Desarrollo

- RoCoLe TRAIN y VAL conservarán sus archivos, grupos, manifiesto y particiones actuales.
- CoffeeLeaf-CO se usará, si supera la auditoría, solo como fuente de desarrollo.
- Para aislar procedencia se considerará inicialmente únicamente su captura propia de 1.705 imágenes; las 610 imágenes derivadas de Silva et al. quedarán fuera del primer experimento.
- Se respetarán las particiones oficiales de desarrollo mientras no existan identificadores mejores. Si se descubren identificadores de planta, hoja o sesión, se reagrupará antes de cualquier uso y se registrará el cambio.
- Si no es posible reconstruir unidades biológicas, las métricas se describirán como evaluación por imagen, no por planta.

### 4.2. Evaluación externa fijada

- BRACOL se reservará completo hasta congelar el control, el candidato, todos los umbrales y el código de evaluación.
- Solo se considerará el conjunto de **hojas completas originales**. No se usarán los recortes de síntomas como observaciones independientes.
- Para la comparación del clasificador se fijará, antes de inferir, un manifiesto con las hojas cuya etiqueta primaria sea expresamente `sana` o `roya`. Se excluirán otros estreses, etiquetas indeterminadas y casos con múltiples estreses no resolubles documentalmente.
- BRACOL se consultará una sola vez después de congelar el candidato. Sus resultados decidirán aceptar o descartar ese candidato, pero no se usarán para modificarlo ni para escoger un segundo candidato.
- Como BRACOL no incluye ácaro rojo, su F1 macro externa cubrirá solo `sana` y `roya`. No se presentará como F1 macro de las tres clases de CaféIA.

### 4.3. Exclusión de TEST de la versión 1

- No se abrirán imágenes, etiquetas, predicciones ni métricas de TEST de RoCoLe.
- TEST v1 no se usará para seleccionar ejemplos, umbrales, hiperparámetros, épocas ni modelos.
- La comparación contra TEST v1 ya publicada permanecerá como resultado histórico cerrado, no como evaluación independiente de esta nueva decisión.
- Para buscar contaminación se podrá comparar cada archivo externo contra el inventario de hashes de TEST ya registrado, sin abrir la imagen de TEST ni consultar su etiqueta. Una coincidencia causará la exclusión del archivo externo; no se investigará visualmente usando TEST.

## 5. Auditoría obligatoria antes de entrenar

La descarga futura, si se autoriza, se conservará fuera de `data/` y excluida de Git. Para cada fuente se registrará DOI, versión, fecha de acceso, licencia, cita, nombre del archivo, tamaño y checksum publicado.

La auditoría generará sin modificar las fuentes:

1. inventario de archivos, dimensiones, modo de color y estado de lectura;
2. manifiesto de procedencia y etiqueta original;
3. SHA256 de cada archivo;
4. hashes perceptuales reproducibles, algoritmo y umbral incluidos;
5. componentes de duplicados exactos y cercanos dentro de cada fuente, entre ambas fuentes y contra RoCoLe;
6. evidencia de si los nombres o metadatos permiten agrupar por planta, hoja o sesión;
7. lista de inclusiones y exclusiones con motivo, sin cambiar la etiqueta original;
8. hoja de revisión humana para cualquier propuesta de convertir anotaciones de detección a clasificación.

Los duplicados y casi duplicados se mantendrán en el mismo grupo. Si un componente toca el conjunto de evaluación externa y el desarrollo, se excluirá del desarrollo. Una ausencia de coincidencias SHA256 no descarta recortes, redimensionamientos, recompressión u otras copias transformadas; por eso se exige también el análisis perceptual.

## 6. Presupuesto experimental

Este protocolo fija como máximo:

- una construcción de control y una de candidato para el filtro;
- una corrida de control y una de candidato del clasificador por cada una de las semillas `42`, `43` y `44`;
- un máximo de 15 épocas por corrida, con parada temprana tras 4 épocas consecutivas sin mejorar el F1 macro de VAL de RoCoLe;
- selección exclusivamente mediante desarrollo: RoCoLe VAL y, cuando corresponda, la partición de desarrollo auditada de CoffeeLeaf-CO;
- una sola consulta final a BRACOL una vez congelado el candidato.

No se iniciarán variantes adicionales a partir del resultado sin presentar primero la comparación completa.

## 7. Métricas fijadas

### 7.1. Filtro de dominio

Se informará por fuente, no solo de forma agregada:

- recall de hojas de café aceptadas y tasa de falso rechazo;
- especificidad y tasa de falsa aceptación sobre el conjunto independiente de negativos no café ya fijado para desarrollo;
- matriz `café aceptado/rechazado` por fuente;
- cantidad total evaluada, intervalos binomiales de Wilson al 95 % y diferencia pareada entre control y candidato;
- distribución del score, dejando explícito que no es una probabilidad;
- resultados separados para RoCoLe VAL, CoffeeLeaf-CO de desarrollo y BRACOL externo.

El umbral softmax provisional de incertidumbre `0.70` pertenece al clasificador y **no** se usará como detector café/no café. El umbral del filtro se congelará usando solo desarrollo antes de abrir BRACOL.

### 7.2. Clasificador

En RoCoLe VAL se informarán:

- F1 macro de las tres clases;
- precision, recall y F1 de `sana`, `roya` y `ácaro rojo`;
- matriz de confusión completa;
- errores `ácaro rojo -> roya`, `ácaro rojo -> sana` y `roya -> sana`;
- promedio, desviación estándar y valores individuales para las tres semillas.

En BRACOL se informarán por separado:

- precision, recall y F1 de `sana` y `roya`;
- F1 macro de esas dos clases y balanced accuracy;
- matriz de confusión binaria;
- cobertura del filtro antes de clasificar;
- resultados del clasificador sobre todas las imágenes elegibles y sobre las aceptadas por el filtro, sin ocultar los rechazos.

No se calculará una métrica externa de ácaro rojo porque estas fuentes no aportan esa clase.

## 8. Criterio previo de aceptación o descarte

El candidato no sustituirá automáticamente a los modelos activos. Pasará a revisión solo si cumple simultáneamente todos los criterios aplicables.

### 8.1. Filtro

1. mejora el recall de hojas de café en BRACOL al menos **5 puntos porcentuales absolutos** frente al control, sobre exactamente los mismos archivos;
2. no reduce el recall de hojas de café en RoCoLe VAL en más de **2 puntos porcentuales**;
3. no aumenta la tasa de falsa aceptación del conjunto negativo fijado en más de **1 punto porcentual**;
4. no introduce un fallo demostrado que asocie el resultado de una fotografía anterior a una imagen nueva ni cambia el contrato de la API sin pruebas.

### 8.2. Clasificador

1. el F1 macro medio de RoCoLe VAL no retrocede más de **0,01** frente a su control pareado;
2. el recall medio de ácaro rojo en RoCoLe VAL no retrocede más de **0,02**, aunque el promedio global mejore;
3. en BRACOL, el F1 macro de `sana` y `roya` supera al control al menos **0,03** y el recall de ninguna de esas clases retrocede más de **0,02**;
4. la dirección de las diferencias se presenta para cada semilla; una ventaja pequeña o inestable no se describirá como mejora demostrada;
5. no se usa ningún resultado externo para crear otra variante dentro del mismo experimento.

Estos umbrales son **reglas operativas fijadas antes del experimento**, no garantías estadísticas ni clínicas. La ausencia de identificadores por planta impide interpretar los intervalos por imagen como independencia biológica completa.

## 9. Costes y verificaciones de despliegue

Se registrarán para control y candidato:

- duración de auditoría, revisión humana y entrenamiento;
- cantidad de imágenes incluidas y excluidas por fuente y motivo;
- tamaño de checkpoints y del artefacto del filtro;
- memoria RSS al iniciar el backend, con los modelos cargados y durante una predicción;
- tiempo de inicio del servicio y carga de modelos;
- latencia de inferencia p50 y p95 en CPU para la misma muestra reproducible;
- impacto sobre el arranque en frío de Render;
- obligaciones de atribución de CC BY 4.0.

Como la arquitectura del clasificador no cambia, se espera que su coste de inferencia sea parecido al actual; esto es una **hipótesis que debe medirse**, no un hecho. El artefacto del filtro sí podría crecer al agregar referencias y aumentar memoria o tiempo de arranque.

## 10. Limitaciones que permanecerán

- Ni CoffeeLeaf-CO ni BRACOL contienen ácaro rojo; la generalización externa de esa clase seguirá sin comprobarse.
- No se podrá afirmar que el sistema reconoce todas las hojas de café ni todas las condiciones foliares.
- BRACOL aporta un cambio de especie, país y dispositivos, pero su fondo blanco no representa toda la fotografía de campo.
- CoffeeLeaf-CO aporta condiciones de campo, pero sus cajas de detección no equivalen por sí solas a etiquetas exclusivas de hoja completa.
- La falta de identificadores de planta o sesión puede inflar la precisión de las estimaciones por imagen.
- Las puntuaciones softmax seguirán sin ser probabilidades calibradas de acierto, y el score del filtro seguirá sin ser una probabilidad de que la imagen sea café.
- Las fotografías encontradas en Internet no deben usarse para ajustar ni evaluar sin licencia, procedencia y etiqueta verificadas.

## 11. Evidencias que deberá producir una ejecución futura

Una ejecución autorizada deberá crear una carpeta de experimento nueva y conservar:

- copias de este protocolo y de las configuraciones exactas;
- registros de versión, licencia y checksums de las descargas;
- manifiestos auditados, grupos de duplicados y decisiones de inclusión;
- historial y duración de cada corrida;
- checkpoints de control y candidato sin sobrescribir los activos;
- predicciones por imagen y métricas completas de desarrollo;
- evaluación externa congelada de BRACOL;
- memoria, latencia y tamaños medidos;
- informe que distinga hechos, resultados, inferencias y limitaciones.

Al registrar este documento no se descargaron datos, no se consultó TEST v1, no se entrenó ningún modelo y no se modificaron `data/`, el manifiesto, las particiones, `models/` ni el modelo activo de la web.
