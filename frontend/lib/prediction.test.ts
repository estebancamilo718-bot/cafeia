import assert from "node:assert/strict";
import test from "node:test";

import { isPrediction } from "./prediction.ts";

const accepted = {
  status: "classified",
  is_supported_image: true,
  domain_score: 0.82,
  domain_threshold: 0.65,
  message: null,
  category: "coffee___healthy",
  category_label: "Hoja sana",
  score: 0.8,
  scores: [
    { category: "coffee___healthy", label: "Hoja sana", score: 0.8 },
    { category: "coffee___red_spider_mite", label: "Ácaro rojo", score: 0.1 },
    { category: "coffee___rust", label: "Roya", score: 0.1 },
  ],
  is_uncertain: false,
  uncertainty_threshold: 0.7,
};

test("accepts a coherent three-class response", () => {
  assert.equal(isPrediction(accepted), true);
});

test("accepts an outside-domain response without coffee scores", () => {
  assert.equal(
    isPrediction({
      status: "outside_domain",
      is_supported_image: false,
      domain_score: 0.31,
      domain_threshold: 0.65,
      message: "Carga una fotografía de una sola hoja de café.",
      category: null,
      category_label: null,
      score: null,
      scores: [],
      is_uncertain: true,
      uncertainty_threshold: 0.7,
    }),
    true,
  );
});

test("rejects an outside-domain response that leaks a coffee category", () => {
  assert.equal(
    isPrediction({
      ...accepted,
      status: "outside_domain",
      is_supported_image: false,
      message: "Fuera del dominio",
    }),
    false,
  );
});
