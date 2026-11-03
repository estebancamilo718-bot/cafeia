# Consentimiento por visita y mensaje de rechazo

**Fecha:** 2026-11-02  
**Entrenamiento realizado:** ninguno  
**Uso de TEST:** ninguno  
**Modelo web reemplazado:** no

## Cambios

- El permiso para procesar una fotografía se mantiene únicamente en memoria durante la carga actual de la página.
- CaféIA no guarda la decisión en cookies, `localStorage` ni `sessionStorage`.
- Al recargar, volver a abrir la página o restaurarla desde la memoria de navegación, el permiso vuelve a solicitarse.
- Una decisión persistida por versiones anteriores se elimina y no evita el nuevo aviso.
- Rechazar o cerrar el aviso permite consultar la página, pero mantiene deshabilitados la selección y el análisis de fotografías.
- El rechazo del filtro se expresa en lenguaje común: CaféIA no pudo confirmar una hoja de café que pueda analizar. No se afirma que la planta definitivamente no sea café, porque el filtro puede rechazar hojas válidas.

## Modelo y precisión

El clasificador y el filtro permanecen intactos:

- clasificador: `models/mobilenet_finetuned_epoch6.pt`, SHA-256 `4ab4e52fc3d417fe5fb126ff1e5b346f080c55ffa80232cffd5d6e6622e46c94`;
- filtro: `models/coffee_domain_guard.pt`, SHA-256 `8060ef83e4a018d6a49e22fc5b59162f4ec6cbba90482e27d7896c79106d90e7`;
- umbral de incertidumbre: `0.70`;
- umbral del filtro: `0.6497240662574768`.

No se declara una mejora de precisión de las tres clases. El candidato de ajuste más profundo mejora el F1 macro medio de VAL, pero presenta variación y retrocesos por clase entre semillas, y no es directamente compatible con el filtro activo. La evidencia disponible no justifica reemplazar los pesos de producción. La comparación completa permanece en `reports/MOBILENET_DEPTH_EXPERIMENT_RESULTS.md`.

## Verificación ejecutada

- Backend: `23 passed`.
- Frontend: `14 passed`.
- Compilación optimizada de Next.js: correcta, incluido TypeScript.
- Navegador Chromium: consentimiento visible a 390, 768 y 1440 px; rechazo mantiene bloqueado el selector; aceptación lo habilita; después de recargar vuelve el diálogo, se deshabilita el selector y se elimina la antigua decisión persistida.
- Flujo real: carga, reemplazo durante una petición, resultado incierto, clasificación aceptada, desconexión y retirada del permiso.
- Imagen externa `Fury_01.jpg`: `outside_domain`, `is_supported_image=false`, categoría nula y `scores=[]`; no se expuso una clasificación de café.

El resultado estructurado del navegador está en `reports/web_ui_verification/browser_checks.json`. Las capturas generadas permanecen excluidas de Git.

## Límite que continúa

El filtro reduce errores evidentes, pero no es un detector universal de café. Una imagen aceptada aún puede no ser una hoja de café y una hoja válida puede ser rechazada. Mejorar la clasificación de fotografías nuevas requiere datos independientes y etiquetados de las tres clases, especialmente de ácaro rojo; no puede lograrse de forma fiable cambiando solo el texto, el umbral o entrenando indefinidamente sobre las mismas particiones.
