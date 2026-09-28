import assert from "node:assert/strict";
import test from "node:test";

import { analysisFailureMessage, validateSelectedImage } from "./analysis-input.ts";
import { LatestRequestCoordinator } from "./latest-request.ts";

test("bloquea un segundo envío mientras la primera solicitud sigue activa", () => {
  const coordinator = new LatestRequestCoordinator();
  const first = coordinator.begin();

  assert.ok(first);
  assert.equal(coordinator.begin(), null);
  assert.equal(coordinator.isCurrent(first), true);
  assert.equal(coordinator.finish(first), true);
  assert.ok(coordinator.begin());
});

test("reemplazar la imagen cancela la solicitud y vuelve obsoleta su respuesta", () => {
  const coordinator = new LatestRequestCoordinator();
  const oldRequest = coordinator.begin();
  assert.ok(oldRequest);

  coordinator.replaceSelection();

  assert.equal(oldRequest.controller.signal.aborted, true);
  assert.equal(coordinator.isCurrent(oldRequest), false);
  assert.equal(coordinator.finish(oldRequest), false);

  const newRequest = coordinator.begin();
  assert.ok(newRequest);
  assert.equal(coordinator.isCurrent(newRequest), true);
  assert.equal(coordinator.finish(newRequest), true);
});

test("cancelar impide aplicar una respuesta tardía", () => {
  const coordinator = new LatestRequestCoordinator();
  const request = coordinator.begin();
  assert.ok(request);

  coordinator.cancel();

  assert.equal(request.controller.signal.aborted, true);
  assert.equal(coordinator.isCurrent(request), false);
  assert.equal(coordinator.finish(request), false);
});

test("valida formato y límite de 10 MB antes del envío", () => {
  assert.equal(
    validateSelectedImage({ name: "hoja.jpg", type: "image/jpeg", size: 1_024 }),
    null,
  );
  assert.equal(
    validateSelectedImage({ name: "hoja.txt", type: "text/plain", size: 1_024 }),
    "Selecciona una fotografía JPG o PNG válida.",
  );
  assert.equal(
    validateSelectedImage({
      name: "hoja.png",
      type: "image/png",
      size: 10 * 1024 * 1024 + 1,
    }),
    "La fotografía no puede superar 10 MB.",
  );
});

test("presenta un error específico cuando el backend no está disponible", () => {
  assert.equal(
    analysisFailureMessage(new TypeError("fetch failed")),
    "No se pudo conectar con CaféIA. Comprueba que el backend esté encendido.",
  );
});
