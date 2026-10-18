const PREDICTION_CATEGORIES = new Set([
  "coffee___healthy",
  "coffee___red_spider_mite",
  "coffee___rust",
]);

const EXPECTED_LABELS: Record<string, string> = {
  coffee___healthy: "Hoja sana",
  coffee___red_spider_mite: "Ácaro rojo",
  coffee___rust: "Roya",
};

type ClassScore = {
  category: string;
  label: string;
  score: number;
};

type PredictionBase = {
  domain_score: number;
  domain_threshold: number;
  is_uncertain: boolean;
  uncertainty_threshold: number;
};

export type CoffeePrediction = PredictionBase & {
  status: "classified" | "uncertain";
  is_supported_image: true;
  message: null;
  category: string;
  category_label: string;
  score: number;
  scores: ClassScore[];
};

export type OutsideDomainPrediction = PredictionBase & {
  status: "outside_domain";
  is_supported_image: false;
  message: string;
  category: null;
  category_label: null;
  score: null;
  scores: [];
};

export type Prediction = CoffeePrediction | OutsideDomainPrediction;

export function isPrediction(payload: unknown): payload is Prediction {
  if (typeof payload !== "object" || payload === null) return false;
  const candidate = payload as Partial<Prediction>;
  if (
    !["classified", "uncertain", "outside_domain"].includes(candidate.status ?? "") ||
    typeof candidate.is_supported_image !== "boolean" ||
    typeof candidate.domain_score !== "number" ||
    !Number.isFinite(candidate.domain_score) ||
    candidate.domain_score < -1 ||
    candidate.domain_score > 1 ||
    typeof candidate.domain_threshold !== "number" ||
    !Number.isFinite(candidate.domain_threshold) ||
    candidate.domain_threshold < -1 ||
    candidate.domain_threshold > 1 ||
    typeof candidate.is_uncertain !== "boolean" ||
    typeof candidate.uncertainty_threshold !== "number" ||
    !Number.isFinite(candidate.uncertainty_threshold) ||
    candidate.uncertainty_threshold !== 0.7 ||
    !Array.isArray(candidate.scores)
  ) {
    return false;
  }

  if (candidate.status === "outside_domain") {
    return (
      candidate.is_supported_image === false &&
      candidate.is_uncertain === true &&
      typeof candidate.message === "string" &&
      candidate.message.length > 0 &&
      candidate.category === null &&
      candidate.category_label === null &&
      candidate.score === null &&
      candidate.scores.length === 0
    );
  }

  if (
    candidate.is_supported_image !== true ||
    candidate.message !== null ||
    typeof candidate.category !== "string" ||
    !PREDICTION_CATEGORIES.has(candidate.category) ||
    typeof candidate.category_label !== "string" ||
    typeof candidate.score !== "number" ||
    !Number.isFinite(candidate.score) ||
    candidate.score < 0 ||
    candidate.score > 1 ||
    candidate.scores.length !== PREDICTION_CATEGORIES.size
  ) {
    return false;
  }

  const returnedCategories = new Set<string>();
  for (const item of candidate.scores) {
    if (
      typeof item !== "object" ||
      item === null ||
      typeof item.category !== "string" ||
      !PREDICTION_CATEGORIES.has(item.category) ||
      typeof item.label !== "string" ||
      item.label !== EXPECTED_LABELS[item.category] ||
      typeof item.score !== "number" ||
      !Number.isFinite(item.score) ||
      item.score < 0 ||
      item.score > 1
    ) {
      return false;
    }
    returnedCategories.add(item.category);
  }

  const selectedScore = candidate.scores.find(
    (item) => item.category === candidate.category,
  )?.score;
  const scoreSum = candidate.scores.reduce((sum, item) => sum + item.score, 0);
  const maximumScore = Math.max(...candidate.scores.map((item) => item.score));
  return (
    returnedCategories.size === PREDICTION_CATEGORIES.size &&
    candidate.category_label === EXPECTED_LABELS[candidate.category] &&
    selectedScore !== undefined &&
    Math.abs(candidate.score - selectedScore) <= 1e-7 &&
    Math.abs(candidate.score - maximumScore) <= 1e-7 &&
    Math.abs(scoreSum - 1) <= 1e-5 &&
    candidate.is_uncertain === (candidate.score < candidate.uncertainty_threshold) &&
    candidate.status === (candidate.is_uncertain ? "uncertain" : "classified")
  );
}
