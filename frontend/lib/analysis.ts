import { isPrediction, type Prediction } from "./prediction.ts";

export const DEFAULT_CITY = "Ibagué";
export const MAX_CITY_LENGTH = 80;

// Municipios cafeteros sugeridos en el selector; se puede escribir cualquier otro de Colombia.
export const SUGGESTED_CITIES = [
  "Ibagué",
  "Líbano",
  "Planadas",
  "Chinchiná",
  "Manizales",
  "Pereira",
  "Armenia",
  "Popayán",
  "Pitalito",
  "Neiva",
  "Andes",
  "Medellín",
] as const;

export type Location = {
  nombre: string;
  departamento: string | null;
  pais: string;
  latitud: number;
  longitud: number;
  elevacion_m: number | null;
};

export type CurrentWeather = {
  ubicacion: Location;
  hora_local: string;
  temperatura_c: number;
  humedad_relativa_pct: number;
  precipitacion_mm: number;
  fuente: string;
};

export type ForecastDay = {
  fecha: string;
  temperatura_max_c: number | null;
  temperatura_min_c: number | null;
  precipitacion_mm: number | null;
  probabilidad_lluvia_pct: number | null;
  humedad_media_pct: number | null;
};

export type Weather = {
  actual: CurrentWeather;
  pronostico: { ubicacion: Location; dias: ForecastDay[]; fuente: string };
};

export type AgentStep = {
  servidor: string;
  herramienta: string;
  estado: "ok" | "error" | "omitida";
  detalle: string | null;
};

export type Analysis = {
  prediccion: Prediction;
  clima: Weather | null;
  clima_mensaje: string | null;
  pasos: AgentStep[];
};

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isNumberOrNull(value: unknown): boolean {
  return value === null || isFiniteNumber(value);
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isLocation(value: unknown): value is Location {
  return (
    isObject(value) &&
    typeof value.nombre === "string" &&
    (value.departamento === null || typeof value.departamento === "string") &&
    typeof value.pais === "string" &&
    isFiniteNumber(value.latitud) &&
    isFiniteNumber(value.longitud) &&
    isNumberOrNull(value.elevacion_m)
  );
}

function isCurrentWeather(value: unknown): value is CurrentWeather {
  return (
    isObject(value) &&
    isLocation(value.ubicacion) &&
    typeof value.hora_local === "string" &&
    isFiniteNumber(value.temperatura_c) &&
    isFiniteNumber(value.humedad_relativa_pct) &&
    isFiniteNumber(value.precipitacion_mm) &&
    typeof value.fuente === "string"
  );
}

function isForecastDay(value: unknown): value is ForecastDay {
  return (
    isObject(value) &&
    typeof value.fecha === "string" &&
    isNumberOrNull(value.temperatura_max_c) &&
    isNumberOrNull(value.temperatura_min_c) &&
    isNumberOrNull(value.precipitacion_mm) &&
    isNumberOrNull(value.probabilidad_lluvia_pct) &&
    isNumberOrNull(value.humedad_media_pct)
  );
}

function isWeather(value: unknown): value is Weather {
  if (!isObject(value) || !isCurrentWeather(value.actual) || !isObject(value.pronostico)) {
    return false;
  }
  const forecast = value.pronostico;
  return (
    isLocation(forecast.ubicacion) &&
    typeof forecast.fuente === "string" &&
    Array.isArray(forecast.dias) &&
    forecast.dias.every(isForecastDay)
  );
}

function isAgentStep(value: unknown): value is AgentStep {
  return (
    isObject(value) &&
    typeof value.servidor === "string" &&
    typeof value.herramienta === "string" &&
    ["ok", "error", "omitida"].includes(value.estado as string) &&
    (value.detalle === null || typeof value.detalle === "string")
  );
}

export function isAnalysis(payload: unknown): payload is Analysis {
  if (!isObject(payload) || !isPrediction(payload.prediccion)) return false;
  if (!Array.isArray(payload.pasos) || payload.pasos.length === 0 || !payload.pasos.every(isAgentStep)) {
    return false;
  }
  const hasWeather = payload.clima !== null;
  if (hasWeather) {
    // El agente nunca consulta el clima para una imagen rechazada.
    return (
      isWeather(payload.clima) &&
      payload.clima_mensaje === null &&
      payload.prediccion.status !== "outside_domain"
    );
  }
  return typeof payload.clima_mensaje === "string" && payload.clima_mensaje.length > 0;
}

export function normalizeCity(value: string): string {
  return value.trim().replace(/\s+/g, " ").slice(0, MAX_CITY_LENGTH);
}
