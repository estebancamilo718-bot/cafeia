"use client";

import {
  ChangeEvent,
  DragEvent,
  FormEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { analysisFailureMessage, validateSelectedImage } from "../lib/analysis-input";
import { LatestRequestCoordinator } from "../lib/latest-request";

const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
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

const GUIDE_BY_CATEGORY: Record<string, string> = {
  coffee___healthy: "guia-sana",
  coffee___rust: "guia-roya",
  coffee___red_spider_mite: "guia-acaro",
};

const GUIDE_CARDS = [
  {
    id: "guia-sana",
    eyebrow: "Hoja sana",
    title: "Una referencia, no un certificado",
    image: "/guide/hoja-sana-rocole-c10p12h1.jpg",
    alt: "Hoja de café verde fotografiada en campo, ejemplo de TRAIN anotado como sano en RoCoLe",
    description:
      "En RoCoLe, esta fotografía está anotada como sana. Sirve para comparar la apariencia general con las otras dos categorías del prototipo.",
    signs: [
      "Tejido predominantemente verde y sin las señales habituales de roya o daño por ácaro descritas en esta guía.",
      "El color, el brillo y la forma pueden variar por edad, nutrición, luz y otras condiciones que CaféIA no distingue.",
    ],
    sourceTitle: "Síntomas visuales de deficiencias nutricionales en café (Cenicafé, Avance 478)",
    sourceUrl: "https://publicaciones.cenicafe.org/index.php/avances_tecnicos/article/view/302",
    photoId: "C10P12H1.jpg",
    originalLabel: "sana",
  },
  {
    id: "guia-roya",
    eyebrow: "Roya del café",
    title: "Observa ambas caras de la hoja",
    image: "/guide/roya-rocole-c10p27e2.jpg",
    alt: "Envés de una hoja de café con manchas, ejemplo de TRAIN anotado como roya nivel 2 en RoCoLe",
    description:
      "La roya es una enfermedad foliar. El ejemplo pertenece a la categoría roya del proyecto y conserva su anotación original verificada.",
    signs: [
      "En el envés pueden aparecer manchas redondeadas amarillas con aspecto de polvillo; en el haz suelen verse amarillas y lisas.",
      "Algunas manchas desarrollan un centro pardo. Otras afectaciones pueden parecerse, por lo que la fotografía no confirma un diagnóstico.",
    ],
    sourceTitle: "Enfermedades foliares del cafeto (Cenicafé, Avance 106)",
    sourceUrl: "https://publicaciones.cenicafe.org/index.php/avances_tecnicos/article/view/2069",
    photoId: "C10P27E2.jpg",
    originalLabel: "roya, nivel 2",
  },
  {
    id: "guia-acaro",
    eyebrow: "Daño por ácaro rojo",
    title: "Una categoría especialmente difícil",
    image: "/guide/acaro-rojo-rocole-c11p9h2.jpg",
    alt: "Hoja de café con zonas pardas y rojizas, ejemplo de TRAIN anotado como ácaro rojo en RoCoLe",
    description:
      "RoCoLe denomina esta categoría ácaro rojo. Su documentación no confirma la especie, así que CaféIA tampoco la identifica.",
    signs: [
      "Cenicafé describe como señales habituales la pérdida de brillo y la coloración parda o rojiza, a veces más marcada junto a las nervaduras.",
      "Estos cambios pueden ser más visibles en hojas viejas y persistir aunque ya no se observen ácaros; por sí solos no confirman la causa.",
    ],
    sourceTitle: "La arañita roja del cafeto (Cenicafé, Avance 22)",
    sourceUrl: "https://publicaciones.cenicafe.org/index.php/avances_tecnicos/article/view/2157",
    photoId: "C11P9H2.jpg",
    originalLabel: "ácaro rojo",
  },
] as const;

type ClassScore = {
  category: string;
  label: string;
  score: number;
};

type Prediction = {
  category: string;
  category_label: string;
  score: number;
  scores: ClassScore[];
  is_uncertain: boolean;
  uncertainty_threshold: number;
};

function formatScore(value: number) {
  return value.toLocaleString("es-CO", {
    style: "percent",
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
}

function errorMessage(payload: unknown): string {
  if (typeof payload === "object" && payload !== null && "detail" in payload) {
    const detail = (payload as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
  }
  return "No pudimos analizar la fotografía. Intenta de nuevo.";
}

function isPrediction(payload: unknown): payload is Prediction {
  if (typeof payload !== "object" || payload === null) return false;
  const candidate = payload as Partial<Prediction>;
  if (
    typeof candidate.category !== "string" ||
    !PREDICTION_CATEGORIES.has(candidate.category) ||
    typeof candidate.category_label !== "string" ||
    typeof candidate.score !== "number" ||
    !Number.isFinite(candidate.score) ||
    candidate.score < 0 ||
    candidate.score > 1 ||
    typeof candidate.is_uncertain !== "boolean" ||
    typeof candidate.uncertainty_threshold !== "number" ||
    !Number.isFinite(candidate.uncertainty_threshold) ||
    candidate.uncertainty_threshold !== 0.7 ||
    !Array.isArray(candidate.scores) ||
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
    candidate.is_uncertain === (candidate.score < candidate.uncertainty_threshold)
  );
}

export default function Home() {
  const inputRef = useRef<HTMLInputElement>(null);
  const requestCoordinatorRef = useRef(new LatestRequestCoordinator());
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [result, setResult] = useState<Prediction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [dragActive, setDragActive] = useState(false);

  const sortedScores = useMemo(
    () => result?.scores.slice().sort((a, b) => b.score - a.score) ?? [],
    [result],
  );

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  useEffect(() => {
    return () => requestCoordinatorRef.current.cancel();
  }, []);

  function reset(focusInput = false) {
    requestCoordinatorRef.current.replaceSelection();
    setFile(null);
    setPreviewUrl(null);
    setResult(null);
    setError(null);
    setLoading(false);
    setDragActive(false);
    if (inputRef.current) {
      inputRef.current.value = "";
      if (focusInput) inputRef.current.focus();
    }
  }

  function useSelectedFile(selected: File | null) {
    requestCoordinatorRef.current.replaceSelection();
    setLoading(false);
    setError(null);
    setResult(null);

    if (!selected) {
      reset();
      return;
    }
    const validationError = validateSelectedImage(selected);
    if (validationError) {
      reset();
      setError(validationError);
      return;
    }

    setFile(selected);
    setPreviewUrl(URL.createObjectURL(selected));
  }

  function selectFile(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0] ?? null;
    event.target.value = "";
    useSelectedFile(selected);
  }

  function handleDrag(event: DragEvent<HTMLLabelElement>, active: boolean) {
    event.preventDefault();
    setDragActive(active);
  }

  function handleDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragActive(false);
    useSelectedFile(event.dataTransfer.files?.[0] ?? null);
  }

  async function analyze(event: FormEvent) {
    event.preventDefault();
    if (!file) return;

    const requestTicket = requestCoordinatorRef.current.begin();
    if (!requestTicket) return;
    setLoading(true);
    setError(null);
    setResult(null);
    const body = new FormData();
    body.append("file", file);

    try {
      const response = await fetch(`${API_URL}/predict`, {
        method: "POST",
        body,
        signal: requestTicket.controller.signal,
      });
      const payload: unknown = await response.json().catch(() => null);
      if (!response.ok) throw new Error(errorMessage(payload));
      if (!isPrediction(payload)) {
        throw new Error("El backend devolvió una respuesta de predicción inesperada.");
      }
      if (requestCoordinatorRef.current.isCurrent(requestTicket)) {
        setResult(payload);
      }
    } catch (reason) {
      if (requestCoordinatorRef.current.isCurrent(requestTicket)) {
        setError(analysisFailureMessage(reason));
      }
    } finally {
      if (requestCoordinatorRef.current.finish(requestTicket)) {
        setLoading(false);
      }
    }
  }

  const relatedGuideId = result ? GUIDE_BY_CATEGORY[result.category] : undefined;

  return (
    <>
      <a
        href="#analisis"
        className="sr-only z-50 rounded-lg bg-[#fffdf6] px-4 py-2 font-bold text-[#0d2c22] focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        Ir al análisis
      </a>

      <header className="sticky top-0 z-40 border-b border-[#163f31]/12 bg-[#fffdf6]/92 shadow-[0_1px_18px_rgba(22,63,49,0.04)] backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 py-2.5 sm:px-6 lg:px-8">
          <a href="#analisis" className="flex items-center gap-2.5 rounded-md focus-visible:outline-3 focus-visible:outline-offset-3 focus-visible:outline-[#9d4e34]" aria-label="CaféIA, ir al analizador">
            <span className="grid h-9 w-9 place-items-center rounded-full bg-[#163f31]" aria-hidden="true">
              <span className="leaf-mark scale-[0.42]" />
            </span>
            <span>
              <span className="block text-xl leading-none font-black tracking-[-0.04em] text-[#163f31]">CaféIA</span>
              <span className="mt-0.5 hidden text-[0.65rem] font-bold tracking-wide text-[#60756d] sm:block">Asistente para hojas de café</span>
            </span>
          </a>
          <nav aria-label="Navegación principal" className="order-3 flex w-full items-center gap-1 overflow-x-auto pb-0.5 sm:order-2 sm:w-auto sm:pb-0">
            <a className="nav-link" href="#analisis">Analizar</a>
            <a className="nav-link" href="#guia">Guía visual</a>
          </nav>
          <span className="order-2 rounded-full bg-[#dbe5d4] px-3 py-1.5 text-[0.65rem] font-bold tracking-wide text-[#163f31] uppercase sm:order-3 sm:text-xs">
            Prototipo académico
          </span>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-7 sm:px-6 sm:py-9 lg:px-8 lg:py-10">
        <section id="analisis" aria-labelledby="analysis-title" className="scroll-mt-28 sm:scroll-mt-20">
          <div className="analysis-intro mb-6 overflow-hidden rounded-3xl border border-[#163f31]/10 px-5 py-5 sm:mb-8 sm:px-7 sm:py-6">
            <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
              <div className="max-w-3xl">
                <p className="text-xs font-extrabold tracking-[0.18em] text-[#9d4e34] uppercase">Agente IA para hojas de café</p>
                <h1 id="analysis-title" className="mt-2 text-3xl leading-tight font-black tracking-[-0.045em] text-[#163f31] sm:text-4xl">
                  Analiza una hoja de café
                </h1>
                <p className="mt-3 max-w-2xl text-sm leading-6 text-[#455f55] sm:text-base">
                  Sube una fotografía clara de una sola hoja. CaféIA la compara de forma orientativa con hoja sana, roya y daño por ácaro rojo.
                </p>
              </div>
              <p className="w-fit shrink-0 rounded-full border border-[#163f31]/12 bg-[#fffdf6]/80 px-3 py-2 text-xs font-extrabold text-[#52675f]">
                3 categorías · Resultado orientativo
              </p>
            </div>
          </div>

          <div data-analysis-grid className="grid items-start gap-5 md:grid-cols-2 lg:gap-7">
            <section aria-labelledby="upload-title" className="tool-card rounded-3xl border border-[#163f31]/12 bg-[#fffdf6] p-4 sm:p-6">
              <div className="mb-4 flex items-start justify-between gap-4">
                <div>
                  <p className="text-xs font-extrabold tracking-[0.14em] text-[#9d4e34] uppercase">Paso 1</p>
                  <h2 id="upload-title" className="mt-1 text-xl font-black text-[#163f31]">Selecciona una fotografía</h2>
                </div>
                <span className="shrink-0 rounded-lg bg-[#f6f0df] px-2.5 py-1 text-xs font-bold text-[#52675f]">JPG o PNG</span>
              </div>

              <form onSubmit={analyze} className="space-y-4">
                <p id="upload-help" className="sr-only">
                  Archivos JPG o PNG de hasta 10 MB. Usa buena luz y una hoja enfocada.
                </p>
                <label
                  htmlFor="leaf-photo"
                  onDragEnter={(event) => handleDrag(event, true)}
                  onDragOver={(event) => handleDrag(event, true)}
                  onDragLeave={(event) => handleDrag(event, false)}
                  onDrop={handleDrop}
                  className={`relative block min-h-64 cursor-pointer overflow-hidden rounded-2xl border-2 border-dashed bg-[#f9f5e9] transition-colors focus-within:ring-3 focus-within:ring-[#9d4e34] focus-within:ring-offset-2 ${
                    dragActive ? "border-[#9d4e34] bg-[#f3e6d7]" : "border-[#163f31]/30 hover:border-[#163f31]/60"
                  }`}
                >
                  <input
                    ref={inputRef}
                    id="leaf-photo"
                    className="absolute inset-0 z-10 h-full w-full cursor-pointer opacity-0 disabled:cursor-not-allowed"
                    type="file"
                    aria-label={file ? "Reemplazar fotografía de la hoja" : "Seleccionar fotografía de una hoja de café"}
                    aria-describedby="upload-help"
                    accept=".jpg,.jpeg,.png,image/jpeg,image/png"
                    onChange={selectFile}
                  />

                  {previewUrl ? (
                    <div>
                      <img
                        src={previewUrl}
                        alt="Vista previa de la hoja seleccionada"
                        className="h-64 w-full object-cover sm:h-72"
                      />
                      <div className="flex items-center justify-between gap-3 border-t border-[#163f31]/10 bg-[#fffdf6] px-4 py-3">
                        <span className="min-w-0 truncate text-sm font-bold text-[#163f31]">{file?.name}</span>
                        <span className="shrink-0 text-xs font-extrabold text-[#9d4e34]">Reemplazar</span>
                      </div>
                    </div>
                  ) : (
                    <div className="grid min-h-64 place-items-center px-6 py-8 text-center sm:min-h-72">
                      <div>
                        <span className="mx-auto grid h-12 w-12 place-items-center rounded-full bg-[#dbe5d4] text-2xl font-light text-[#163f31]" aria-hidden="true">+</span>
                        <p className="mt-4 font-extrabold text-[#163f31]">Selecciona o arrastra una imagen</p>
                        <p className="mt-1 text-sm leading-5 text-[#52675f]">Máximo 10 MB. Usa buena luz y una hoja enfocada.</p>
                      </div>
                    </div>
                  )}
                </label>

                <aside aria-labelledby="photo-tips-title" className="rounded-xl bg-[#edf3e9] px-4 py-3">
                  <h3 id="photo-tips-title" className="text-sm font-extrabold text-[#163f31]">Para una foto más útil</h3>
                  <ul className="mt-1 grid gap-x-4 gap-y-1 text-sm leading-5 text-[#455f55] sm:grid-cols-2">
                    <li>• Enfoca una sola hoja completa.</li>
                    <li>• Usa luz pareja, sin filtros.</li>
                    <li>• Evita dedos y fondos dominantes.</li>
                    <li>• Fotografía haz y envés por separado.</li>
                  </ul>
                </aside>

                {error && (
                  <div role="alert" className="rounded-xl border border-[#a45136]/30 bg-[#f8e9e2] px-4 py-3 text-sm leading-5 text-[#7b3825]">
                    <span className="font-extrabold">No se pudo completar el análisis.</span> {error}
                  </div>
                )}

                <button
                  type="submit"
                  disabled={!file || loading}
                  className="w-full rounded-xl bg-[#a45136] px-5 py-3.5 font-extrabold text-white shadow-[0_8px_20px_rgba(119,53,34,0.18)] transition-colors hover:bg-[#873f2a] focus-visible:outline-3 focus-visible:outline-offset-3 focus-visible:outline-[#9d4e34] disabled:cursor-not-allowed disabled:bg-[#b9aaa3] disabled:text-[#fffdf6] disabled:shadow-none"
                >
                  {loading ? "Analizando fotografía…" : "Analizar hoja"}
                </button>
              </form>
            </section>

            <section aria-labelledby="result-title" aria-live="polite" aria-busy={loading} className="tool-card rounded-3xl border border-[#163f31]/12 bg-[#fffdf6] p-4 sm:p-6">
              <p className="text-xs font-extrabold tracking-[0.14em] text-[#9d4e34] uppercase">Paso 2</p>

              {loading ? (
                <div className="grid min-h-80 place-items-center py-8 text-center">
                  <div>
                    <span className="mx-auto block h-3 w-3 rounded-full bg-[#a45136]" aria-hidden="true" />
                    <h2 id="result-title" className="mt-5 text-2xl font-black text-[#163f31]">Analizando la fotografía</h2>
                    <p className="mt-2 text-sm leading-6 text-[#52675f]">El modelo está calculando las puntuaciones de las tres clases.</p>
                    <p className="mt-2 text-xs leading-5 text-[#52675f]">Puedes reemplazar la fotografía; esta solicitud se cancelará.</p>
                  </div>
                </div>
              ) : result ? (
                <div className="mt-1">
                  <div className={`rounded-2xl border p-4 ${result.is_uncertain ? "border-[#d0a24c]/60 bg-[#fbf4df]" : "border-[#163f31]/15 bg-[#edf3e9]"}`}>
                    <h2 id="result-title" className="text-2xl font-black tracking-[-0.025em] text-[#163f31] sm:text-3xl">
                      {result.is_uncertain
                        ? "Resultado incierto"
                        : `Clasificación orientativa: ${result.category_label}`}
                    </h2>
                    {result.is_uncertain && (
                      <p className="mt-2 text-sm font-bold text-[#455f55]">
                        Categoría más probable: {result.category_label}
                      </p>
                    )}
                    <p className="mt-1 text-3xl font-black text-[#a45136]">{formatScore(result.score)}</p>
                    {result.is_uncertain && (
                      <p className="mt-2 text-sm leading-5 text-[#6b511b]">
                        La puntuación mayor no alcanzó el umbral provisional de {formatScore(result.uncertainty_threshold)}. Prueba otra foto o solicita revisión humana.
                      </p>
                    )}
                  </div>

                  <h3 className="mt-6 text-sm font-extrabold text-[#163f31]">Puntuaciones por clase</h3>
                  <div className="mt-3 space-y-4">
                    {sortedScores.map((item) => (
                      <div key={item.category}>
                        <div className="mb-1.5 flex items-center justify-between gap-4 text-sm">
                          <span className="font-bold text-[#344f45]">{item.label}</span>
                          <span className="font-black text-[#163f31]">{formatScore(item.score)}</span>
                        </div>
                        <div
                          role="progressbar"
                          aria-label={`Puntuación de ${item.label}`}
                          aria-valuemin={0}
                          aria-valuemax={100}
                          aria-valuenow={Math.round(item.score * 100)}
                          className="h-2.5 overflow-hidden rounded-full bg-[#dbe5d4]"
                        >
                          <div className="h-full rounded-full bg-[#a45136]" style={{ width: `${Math.max(1, item.score * 100)}%` }} />
                        </div>
                      </div>
                    ))}
                  </div>

                  {!result.is_uncertain && (
                    <p className="mt-5 rounded-xl bg-[#edf3e9] px-4 py-3 text-sm leading-5 text-[#344f45]">
                      Este resultado es orientativo. Si observas daños o síntomas, solicita revisión de una persona experta.
                    </p>
                  )}

                  <a
                    href={result.is_uncertain || !relatedGuideId ? "#guia" : `#${relatedGuideId}`}
                    className="mt-4 inline-flex min-h-11 items-center rounded-lg font-extrabold text-[#7b3825] underline decoration-2 underline-offset-4 focus-visible:outline-3 focus-visible:outline-offset-3 focus-visible:outline-[#9d4e34]"
                  >
                    {result.is_uncertain ? "Consultar las tres categorías" : `Ver la ficha de ${result.category_label.toLocaleLowerCase("es-CO")}`}
                  </a>

                  <button
                    type="button"
                    onClick={() => reset(true)}
                    className="mt-4 w-full rounded-xl border-2 border-[#163f31] px-5 py-3 font-extrabold text-[#163f31] transition-colors hover:bg-[#163f31] hover:text-white focus-visible:outline-3 focus-visible:outline-offset-3 focus-visible:outline-[#9d4e34]"
                  >
                    Analizar otra fotografía
                  </button>
                </div>
              ) : error ? (
                <div className="grid min-h-80 place-items-center py-8 text-center">
                  <div>
                    <h2 id="result-title" className="text-2xl font-black text-[#7b3825]">Análisis no disponible</h2>
                    <p className="mt-2 max-w-sm text-sm leading-6 text-[#52675f]">Revisa el mensaje junto al selector y vuelve a intentarlo.</p>
                  </div>
                </div>
              ) : (
                <div className="grid min-h-80 place-items-center py-8 text-center">
                  <div>
                    <span className="mx-auto block h-px w-14 bg-[#d0a24c]" aria-hidden="true" />
                    <h2 id="result-title" className="mt-5 text-2xl font-black text-[#163f31]">Aquí verás el resultado</h2>
                    <p className="mt-2 max-w-sm text-sm leading-6 text-[#52675f]">
                      Selecciona una fotografía y pulsa “Analizar hoja” para obtener las tres puntuaciones.
                    </p>
                  </div>
                </div>
              )}

              <p className="mt-5 border-t border-[#163f31]/10 pt-4 text-xs leading-5 text-[#52675f]">
                Las puntuaciones no son probabilidades calibradas de acierto. CaféIA solo distingue hoja sana, roya y ácaro rojo; no comprueba si la fotografía pertenece a una hoja de café ni sustituye una evaluación experta.
              </p>
            </section>
          </div>
        </section>

        <section id="guia" aria-labelledby="guide-title" className="guide-section mt-14 scroll-mt-28 rounded-[2rem] px-4 py-8 sm:mt-16 sm:scroll-mt-20 sm:px-7 sm:py-10">
          <div className="max-w-3xl">
            <p className="text-xs font-extrabold tracking-[0.16em] text-[#9d4e34] uppercase">Guía visual educativa</p>
            <h2 id="guide-title" className="mt-2 text-3xl font-black tracking-[-0.04em] text-[#163f31] sm:text-4xl">
              Conoce las hojas de café
            </h2>
            <p className="mt-3 text-sm leading-6 text-[#455f55] sm:text-base">
              Compara señales habituales y aprende qué observa el prototipo. Las fotografías son ejemplos reales de TRAIN con anotación original verificada; no son diagnósticos ni muestran todas las variaciones posibles.
            </p>
          </div>

          <div className="mt-7 grid items-start gap-5 lg:grid-cols-3">
            {GUIDE_CARDS.map((card) => (
              <article id={card.id} key={card.id} className="guide-card scroll-mt-28 overflow-hidden rounded-3xl border border-[#163f31]/12 bg-[#fffdf6] shadow-[0_16px_50px_rgba(22,63,49,0.08)] sm:scroll-mt-20">
                <img src={card.image} alt={card.alt} width={1920} height={1080} loading="lazy" className="aspect-[16/10] w-full object-cover" />
                <div className="p-5 sm:p-6">
                  <p className="text-xs font-extrabold tracking-[0.14em] text-[#9d4e34] uppercase">{card.eyebrow}</p>
                  <h3 className="mt-1 text-xl font-black text-[#163f31]">{card.title}</h3>
                  <p className="mt-3 text-sm leading-6 text-[#455f55]">{card.description}</p>

                  <details className="guide-details mt-5 border-t border-[#163f31]/10 pt-4">
                    <summary className="inline-flex min-h-11 cursor-pointer list-none items-center rounded-lg border-2 border-[#163f31] px-4 py-2 text-sm font-extrabold text-[#163f31] hover:bg-[#163f31] hover:text-white focus-visible:outline-3 focus-visible:outline-offset-3 focus-visible:outline-[#9d4e34]">
                      Ver detalles
                    </summary>
                    <div className="mt-4 text-sm leading-6 text-[#455f55]">
                      <h4 className="font-extrabold text-[#163f31]">Señales visuales habituales</h4>
                      <ul className="mt-2 space-y-2">
                        {card.signs.map((sign) => <li key={sign}>• {sign}</li>)}
                      </ul>
                      <p className="mt-4 rounded-xl bg-[#f6f0df] px-3 py-2.5 text-xs leading-5">
                        <strong className="text-[#163f31]">Fuente del texto:</strong>{" "}
                        <a href={card.sourceUrl} target="_blank" rel="noreferrer" className="font-bold text-[#7b3825] underline underline-offset-2">
                          {card.sourceTitle}
                        </a>. Texto resumido y contextualizado para esta guía.
                      </p>
                      <p className="mt-3 text-xs leading-5">
                        <strong className="text-[#163f31]">Fotografía:</strong> {card.photoId}, partición TRAIN; anotación original “{card.originalLabel}”. RoCoLe v2, Jorge Parraga-Alava, Kevin Cusme, Angélica Loor y Esneider Santander,{" "}
                        <a href="https://data.mendeley.com/datasets/c5yvn32dzg/2" target="_blank" rel="noreferrer" className="font-bold text-[#7b3825] underline underline-offset-2">CC BY 4.0</a>.
                      </p>
                    </div>
                  </details>
                </div>
              </article>
            ))}
          </div>

          <p className="mt-5 rounded-2xl border border-[#d0a24c]/50 bg-[#fff9e9] px-5 py-4 text-sm leading-6 text-[#5e4b23]">
            Las explicaciones de Cenicafé describen información agronómica general. Las etiquetas de RoCoLe solo indican la categoría asignada a cada fotografía; en particular, “ácaro rojo” no identifica una especie concreta en la documentación del dataset.
          </p>
        </section>
      </main>

      <footer className="mt-10 border-t border-[#163f31]/12 bg-[#163f31] px-4 py-6 text-center text-sm leading-6 text-[#f6f0df]">
        CaféIA es un prototipo académico de tres clases. No reemplaza la revisión de una persona experta.
      </footer>
    </>
  );
}
