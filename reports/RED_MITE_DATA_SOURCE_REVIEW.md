# Revisión de fuentes públicas para ácaro rojo en hojas de café

**Fecha de corte:** 2026-09-27
**Alcance:** búsqueda documental posterior a `RELIABILITY_AUDIT.md` y `NEXT_EXPERIMENT_PROTOCOL.md`. No se repitieron las auditorías de RoCoLe, no se consultó TEST, no se descargaron imágenes, no se entrenó y no se cambió el modelo activo.

## Conclusión ejecutiva

La fuente más prometedora es el **subconjunto de campo de Xinzhai (Baoshan, Yunnan, China)** asociado al artículo CDMS-YOLO y al depósito [Zenodo 21442135](https://doi.org/10.5281/zenodo.21442135). Es público, el registro declara CC BY 4.0 y el artículo documenta captura propia y revisión experta. Sin embargo, **todavía no es incorporable**: antes hay que comprobar el contenido del ZIP, aislar las 1.021 imágenes propias de las 2.000 tomadas de BarakoBama, conocer cuántas imágenes y plantas independientes corresponden a ácaro rojo, verificar identificadores de planta/sesión y comparar SHA-256 contra RoCoLe y otros repositorios.

La colección ruandesa es relevante y de especie arábica, pero actualmente solo está disponible por solicitud y mezcla fotos de campo, material de Internet y aumentos sin un manifiesto público que separe los originales. BarakoBama y otros proyectos de Roboflow tienen licencia declarada y clase `red_spider_mite`, pero carecen de procedencia biológica, unidades de planta y protocolo de anotación suficientes. Por ello no se consideran datos nuevos verificados.

## Criterios de viabilidad

Una fuente se considera utilizable para el experimento propuesto solo si permite:

1. acceder legalmente a los originales y conservar su atribución;
2. separar originales de copias, redimensionamientos y aumentos;
3. sustentar la etiqueta de ácaro mediante anotación documentada, no mediante el título ni el modelo de CaféIA;
4. agrupar por planta y, si existe, por hoja/sesión para impedir fuga entre particiones;
5. identificar y excluir cualquier solapamiento con RoCoLe;
6. traducir su tarea a las tres categorías de CaféIA sin convertir otras alteraciones en sana ni asumir una etiqueta de imagen a partir de una caja ambigua.

## Fuentes candidatas

### 1. Xinzhai / CDMS-YOLO — candidato prioritario, pendiente de auditoría del archivo

- **Publicación original:** [CDMS-YOLO: An Enhanced YOLOv11 Model with Gated Channel Attention and Dynamic Multiscale Optimization for Coffee Leaf Disease and Pest Detection](https://doi.org/10.3390/app16189199).
- **Datos del autor:** [Zenodo 21442135](https://doi.org/10.5281/zenodo.21442135), “Xinzhai Coffee Plantation Dataset, Baoshan, Yunnan, China”. La consulta de metadatos del registro mostró acceso abierto, licencia **CC BY 4.0**, autor Xiaolong Zhang y un único archivo `data.zip` de 5.166.455.708 bytes. No se descargó.
- **Código de los autores:** [Zenodo 22342586](https://doi.org/10.5281/zenodo.22342586).
- **Especie:** la publicación no identifica de forma inequívoca la especie/cultivar de cada fotografía. Fuentes oficiales describen Xinzhai como zona de café arábica, principalmente Catimor y Typica, pero esto no prueba la identidad de todas las plantas fotografiadas. Debe confirmarlo el manifiesto o los autores.
- **Categorías:** sana, mancha marrón, minador, roya, ácaro rojo, mancha algal, fumagina y antracnosis. Es una tarea de detección; puede haber varias clases en una imagen.
- **Captura y cantidad:** 1.021 JPEG propios, tomados en febrero de 2026 en la plantación Xinzhai con un teléfono IQOO 15, resolución 3072×4096, entre 9:00 y 16:00 y bajo distintos ángulos e iluminaciones. El experimento publicado los mezcla con 2.000 originales seleccionados de BarakoBama y redimensiona todo a 640×640, para 3.021 imágenes.
- **Ácaro en el conjunto mezclado:** 433 imágenes (347/43/43 en train/val/test) y 5.736 instancias anotadas. La tabla publicada no desglosa cuántas proceden de las 1.021 capturas de Xinzhai; por tanto, **433 no es el número de imágenes nuevas disponibles**.
- **Anotación:** para las 1.021 imágenes propias, dos expertos con formación en protección vegetal y visión por computador realizaron la anotación inicial en LabelImg bajo una guía común. Dos expertos en protección vegetal cruzaron las etiquetas y un tercer experto adjudicó desacuerdos. Se marcaron regiones afectadas con cajas, no una única etiqueta exclusiva por hoja.
- **Plantas/sesiones:** no se informa el número de plantas, ni se publican en el artículo identificadores de planta/hoja/sesión. La hora, fecha general, dispositivo y sitio sí están documentados.
- **Relación con RoCoLe:** la captura propia es de otro país, año, dispositivo y probablemente otra especie, por lo que no hay una relación documental con RoCoLe; aun así, falta comparación por hash/perceptual. La parte BarakoBama tiene procedencia incompleta y no puede presumirse independiente de RoCoLe.
- **Compatibilidad:** contiene las tres categorías, pero también otras cinco y etiquetas multiclase por región. Para clasificación de imagen completa habría que fijar antes una política: usar únicamente originales con una sola clase relevante confirmada, conservar el vínculo con la caja original y someter los casos multiclase/ambiguos a revisión experta. No se debe etiquetar como sana una imagen solo porque no tenga caja de las tres clases.
- **Verificación faltante:** inventario interno del ZIP; correspondencia con las 1.021 capturas; originales frente a 640×640; conteos por fuente y clase; unidades de planta; metadatos de sesión; especie/cultivar; licencia incluida en el archivo; hashes; y disponibilidad de imágenes de ácaro suficientes para representar plantas independientes.

### 2. Rwandan Arabica Dataset — relevante, pero no es un dataset público descargable

- **Publicación original:** [An Intelligent System-Based Coffee Plant Leaf Disease Recognition Using Deep Learning Techniques on Rwandan Arabica Dataset](https://doi.org/10.3390/technologies11050116).
- **Repositorio institucional del artículo:** [copia de la publicación en KIU/SMARTIE](https://smartie.kiu.ac.ug/public/assets/publications/ff61646bd4dafb22f511ac36e8e2d092dc735281.pdf). No se localizó un repositorio de datos de los autores.
- **Licencia:** el artículo es abierto bajo CC BY 4.0, pero la declaración de datos dice que se entregarán bajo solicitud. Esto **no concede automáticamente una licencia de reutilización del dataset**; habría que obtener autorización expresa y sus condiciones.
- **Especie y categorías:** *Coffea arabica*; roya, ácaro rojo, minador y sana.
- **Cantidad:** el artículo informa 37.939 imágenes RGB. No separa de forma reproducible cuántas son fotografías originales de campo, imágenes descargadas de Internet o transformaciones. Además documenta rotaciones, volteos, zoom y reescalado como aumento.
- **Muestreo y anotación:** visitas en marzo y junio/julio de 2021; cuatro provincias, diez estaciones de lavado y 150 agricultores (30 en cada uno de cinco distritos, según el texto). Agrónomos conocedores de plagas y enfermedades apoyaron el etiquetado. No se publican por imagen el anotador, el origen Internet/campo ni un protocolo de adjudicación comparable al de Xinzhai.
- **Plantas/sesiones:** los agricultores y campañas no equivalen a conteo de plantas. No se documentan identificadores por planta, hoja o sesión en un manifiesto público.
- **Relación con RoCoLe:** no se declara uso de RoCoLe. Como parte del conjunto procede de Internet y no hay inventario/hashes, el solapamiento no puede descartarse.
- **Compatibilidad:** contiene las tres categorías y agrega minador. Solo sería compatible después de recibir los originales, excluir aumentos/copias y separar minador sin convertirlo en sana.
- **Verificación faltante:** entrega de archivos y licencia, manifiesto de procedencia, originales por clase, identificadores de planta/sesión, separación de material de Internet, hashes y documentación de las etiquetas.

### 3. BarakoBama Coffee Leaf Disease — público, pero sin procedencia suficiente

- **Repositorio:** [proyecto BarakoBama en Roboflow Universe](https://universe.roboflow.com/barakobama/barakobama-coffee-leaf-disease) y [versión 4](https://universe.roboflow.com/barakobama/barakobama-coffee-leaf-disease/dataset/4).
- **Licencia:** CC BY 4.0 declarada en Roboflow.
- **Especie:** no indicada.
- **Categorías:** crecimiento algal, cercospora, minador, roya, ácaro rojo y fumagina; tarea de detección por cajas. No incluye una clase sana documentada.
- **Cantidad:** la página del proyecto presenta 7.535 imágenes fuente. Las versiones generadas no son originales adicionales: por ejemplo, v1 contiene 11.767 imágenes tras generar dos salidas por ejemplo de entrenamiento con volteos y rotaciones. El artículo CDMS-YOLO seleccionó 2.000 imágenes que denomina originales y no preaumentadas de v4.
- **Anotación, plantas y sesiones:** no hay descripción publicada del origen, especie, toma, anotadores, revisión experta, plantas o sesiones.
- **Relación con RoCoLe:** desconocida. La coincidencia temática no demuestra copia, pero la ausencia de procedencia impide descartar solapamiento; se requieren hashes y rastreo de fuente antes de llamarlas nuevas.
- **Compatibilidad:** parcial. Tiene roya y ácaro, no sana, incluye cuatro alteraciones ajenas y usa cajas. No se recomienda incorporarlo al clasificador actual sin resolver procedencia y convertir etiquetas mediante revisión experta.

### 4. Otros proyectos Roboflow con ácaro — no verificables como fuentes originales

Se encontraron, entre otros, [Coffee Leaf Disease de YOLONASV1](https://universe.roboflow.com/yolonasv1/coffee-leaf-disease-o9dbv) (745 imágenes fuente; clases sana, roya y ácaro) y [Coffee leaf disease de CSR](https://universe.roboflow.com/csr-pq8sf/coffee-leaf-disease-jtif1-aptka) (1.391 fuentes; cinco clases). Ambos declaran CC BY 4.0, pero no publican especie, captura, anotadores, plantas/sesiones ni publicación primaria. Sus versiones contienen más imágenes generadas que fuentes. Hasta comparar originales y hashes, son agregados de procedencia desconocida, no nuevas observaciones biológicas.

## Fuentes descartadas o no nuevas

| Fuente | Motivo |
|---|---|
| RoCoLe, sus copias de Kaggle, repositorios que declaran usar RoCoLe y versiones redimensionadas/aumentadas | Es el origen ya auditado del dataset v1; no aporta plantas independientes nuevas. |
| BRACOL, JMuBEN/derivados y CoffeeLeaf-CO v2 | Son útiles para otras alteraciones de café, pero las versiones documentadas revisadas no aportan una clase de ácaro rojo utilizable para este objetivo. |
| Conjuntos de té con `red spider mite` | El huésped es *Camellia sinensis*, no café. No son compatibles para enseñar identificación de hojas de café. |
| Citrus Pest Benchmark | Fotografías de cítricos y especies de ácaros propias de esa tarea; no compatible con el dominio de café. |
| Artículos biológicos sin conjunto de imágenes de hojas etiquetadas | Pueden sustentar contexto agronómico, pero no constituyen datos de entrenamiento. |

## Recomendación concreta

**No incorporar aún ninguna fuente.** Solicitar/auditar primero Xinzhai, porque es la única candidata encontrada que reúne captura de campo, licencia abierta, repositorio de autor y un procedimiento fuerte de revisión de etiquetas.

La acción siguiente es una auditoría de procedencia, sin entrenar:

1. descargar `data.zip` de Zenodo 21442135 en una carpeta externa y excluida del repositorio, por ejemplo `provenance/xinzhai_zenodo_21442135/`;
2. conservar el registro, licencia, cita, checksum del archivo y listado de miembros sin copiar nada a `data/`;
3. identificar si el ZIP contiene solo las 1.021 capturas propias o también las 3.021 mezcladas;
4. producir SHA-256 y hash perceptual de originales y compararlos contra RoCoLe local y BarakoBama, sin abrir ni comparar TEST de CaféIA;
5. contar originales de ácaro por planta/sesión. Si los nombres/metadatos no lo permiten, escribir a los autores antes de particionar;
6. confirmar especie/cultivar, significado de identificadores y si la etiqueta de ácaro fue validada en cada caso;
7. revisar con un experto una muestra estratificada y todos los casos multiclase/ambiguos; no corregir por predicción del modelo;
8. solo si hay suficientes plantas independientes, elaborar un manifiesto candidato separado y someterlo a aprobación antes de ejecutar el protocolo.

Si Xinzhai no permite recuperar unidades de planta o aporta pocas plantas con ácaro, la alternativa recomendada es **captura propia**: al menos una unidad identificada por planta, una o dos caras/fotos por hoja bajo una rúbrica fija, metadatos de sitio/fecha/dispositivo, diagnóstico o confirmación por un profesional competente, doble revisión de etiquetas y deduplicación. Desarrollo y evaluación externa deben provenir de plantas, sesiones y preferiblemente predios distintos.

## Por qué 60 plantas de desarrollo y 30 por clase de evaluación

Son **metas operativas**, no resultados de un cálculo de potencia ni garantías estadísticas.

- TRAIN tiene 67 plantas documentadas con ácaro. Conseguir 60 plantas nuevas aproximadamente duplica las unidades biológicas disponibles para esa clase y cambia la diversidad sin depender de múltiples fotos correlacionadas de las mismas plantas. Es un lote alcanzable para una recolección universitaria y permite reservar fuentes/sesiones, pero no garantiza una mejora ni cubre toda la variabilidad geográfica, estacional o de cultivar.
- Treinta plantas por clase en una evaluación externa permiten un piloto balanceado de 90 unidades y detectar retrocesos grandes. Si se usa una decisión por planta, cada error cambia el recall de esa clase en 3,33 puntos porcentuales.
- En el peor caso binomial, con proporción 0,5, `SE = sqrt(0,25/30) ≈ 0,091`; un intervalo normal aproximado de 95 % tiene margen cercano a ±0,18. Es demasiado ancho para afirmar diferencias pequeñas.
- Como referencia de planificación, alrededor de 96 unidades independientes por clase darían un margen aproximado de ±0,10 en ese peor caso, y unas 385 serían necesarias para ±0,05. La correlación entre varias fotos de una misma planta no reemplaza plantas independientes.

Por tanto, 60/30 sirve como **puerta mínima de factibilidad**: 60 para enriquecer desarrollo y 30 por clase para una comprobación externa piloto. Antes de una afirmación fuerte deben fijarse la diferencia mínima relevante, el intervalo deseado y un cálculo formal de tamaño muestral con datos piloto, además de ampliar sitios, temporadas y cultivares.

## Estado de materiales

- No se descargó ningún dataset ni imagen durante esta revisión.
- No se modificaron `data/`, el manifiesto, las particiones, `models/` ni `experiments/`.
- No se consultaron imágenes, etiquetas, predicciones ni métricas de TEST.
- Cualquier descarga futura debe mantenerse bajo `provenance/` o fuera del repositorio hasta completar licencia, procedencia, duplicados y unidades de agrupación.
