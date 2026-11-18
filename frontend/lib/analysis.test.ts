import assert from "node:assert/strict";
import test from "node:test";

import { isAnalysis, normalizeCity } from "./analysis.ts";

const prediction = {
  status: "classified",
  is_supported_image: true,
  domain_score: 0.82,
  domain_threshold: 0.65,
  message: null,
  category: "coffee___rust",
  category_label: "Roya",
  score: 0.8,
  scores: [
    { category: "coffee___healthy", label: "Hoja sana", score: 0.1 },
    { category: "coffee___red_spider_mite", label: "Ácaro rojo", score: 0.1 },
    { category: "coffee___rust", label: "Roya", score: 0.8 },
  ],
  is_uncertain: false,
  uncertainty_threshold: 0.7,
};

const location = {
  nombre: "Ibagué",
  departamento: "Tolima",
  pais: "Colombia",
  latitud: 4.43573,
  longitud: -75.20289,
  elevacion_m: 1047,
};

const weather = {
  actual: {
    ubicacion: location,
    hora_local: "2026-11-16T22:15",
    temperatura_c: 21.4,
    humedad_relativa_pct: 91,
    precipitacion_mm: 0,
    fuente: "Open-Meteo",
  },
  pronostico: {
    ubicacion: location,
    dias: [
      {
        fecha: "2026-11-17",
        temperatura_max_c: 26.4,
        temperatura_min_c: 20,
        precipitacion_mm: 4.3,
        probabilidad_lluvia_pct: null,
        humedad_media_pct: 84,
      },
    ],
    fuente: "Open-Meteo",
  },
};

const steps = [
  { servidor: "cafeia-clasificador", herramienta: "clasificar_hoja", estado: "ok", detalle: null },
  { servidor: "cafeia-clima", herramienta: "clima_actual", estado: "ok", detalle: null },
];

test("accepts an analysis with classification, weather and MCP steps", () => {
  assert.equal(
    isAnalysis({ prediccion: prediction, clima: weather, clima_mensaje: null, pasos: steps }),
    true,
  );
});

test("accepts a diagnosis without weather when the agent explains why", () => {
  assert.equal(
    isAnalysis({
      prediccion: prediction,
      clima: null,
      clima_mensaje: "Open-Meteo no respondió; intenta de nuevo más tarde.",
      pasos: steps,
    }),
    true,
  );
});

test("rejects weather for an image the domain filter rejected", () => {
  const rejected = {
    status: "outside_domain",
    is_supported_image: false,
    domain_score: 0.31,
    domain_threshold: 0.65,
    message: "No pudimos confirmar que la imagen corresponda a una hoja de café.",
    category: null,
    category_label: null,
    score: null,
    scores: [],
    is_uncertain: true,
    uncertainty_threshold: 0.7,
  };
  assert.equal(
    isAnalysis({ prediccion: rejected, clima: weather, clima_mensaje: null, pasos: steps }),
    false,
  );
  assert.equal(
    isAnalysis({
      prediccion: rejected,
      clima: null,
      clima_mensaje: "El agente no consultó el clima porque la imagen fue rechazada.",
      pasos: steps,
    }),
    true,
  );
});

test("rejects responses missing the weather explanation, steps or valid numbers", () => {
  assert.equal(isAnalysis({ prediccion: prediction, clima: null, clima_mensaje: null, pasos: steps }), false);
  assert.equal(isAnalysis({ prediccion: prediction, clima: weather, clima_mensaje: null, pasos: [] }), false);
  assert.equal(
    isAnalysis({
      prediccion: prediction,
      clima: { ...weather, actual: { ...weather.actual, temperatura_c: "21" } },
      clima_mensaje: null,
      pasos: steps,
    }),
    false,
  );
  assert.equal(
    isAnalysis({
      prediccion: prediction,
      clima: weather,
      clima_mensaje: null,
      pasos: [{ ...steps[0], estado: "desconocido" }],
    }),
    false,
  );
});

test("normalizes the city typed by the user", () => {
  assert.equal(normalizeCity("  Santa   Rosa de Cabal "), "Santa Rosa de Cabal");
  assert.equal(normalizeCity("x".repeat(120)).length, 80);
});
