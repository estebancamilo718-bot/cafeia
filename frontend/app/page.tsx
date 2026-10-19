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

import { PrivacyConsent } from "../components/privacy-consent";
import { analysisFailureMessage, validateSelectedImage } from "../lib/analysis-input";
import { LatestRequestCoordinator } from "../lib/latest-request";
import { isPrediction, type Prediction } from "../lib/prediction";
import {
  canAnalyzeWithConsent,
  parseStoredPrivacyConsent,
  PRIVACY_CONSENT_STORAGE_KEY,
  type PrivacyConsentChoice,
} from "../lib/privacy-consent";

const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
const GUIDE_BY_CATEGORY: Record<string, string> = {
  coffee___healthy: "guia-sana",
  coffee___rust: "guia-roya",
  coffee___red_spider_mite: "guia-acaro",
};

const GUIDE_CARDS = [
  {
    id: "guia-sana",
    eyebrow: "Hoja sana",
    title: "Aspecto uniforme y buen color",
    image: "/guide/hoja-sana-rocole-c10p12h1.jpg",
    alt: "Hoja de café verde fotografiada en campo, ejemplo de TRAIN anotado como sano en RoCoLe",
    description:
      "Una hoja de referencia para comparar el color, la superficie y la forma general frente a las otras categorías.",
    signs: [
      "Color verde parejo y superficie de aspecto uniforme.",
      "Sin manchas amarillas redondas ni zonas pardas visibles.",
    ],
  },
  {
    id: "guia-roya",
    eyebrow: "Roya del café",
    title: "Revisa el haz y el envés",
    image: "/guide/roya-rocole-c10p27e2.jpg",
    alt: "Envés de una hoja de café con manchas, ejemplo de TRAIN anotado como roya nivel 2 en RoCoLe",
    description:
      "La roya puede mostrar señales distintas en cada cara de la hoja. Revisa el patrón, la forma y la distribución de las manchas.",
    signs: [
      "Puntos o manchas amarillas, especialmente en el envés.",
      "Algunas áreas pueden presentar un centro de color pardo.",
    ],
  },
  {
    id: "guia-acaro",
    eyebrow: "Daño por ácaro rojo",
    title: "Observa el color y la textura",
    image: "/guide/acaro-rojo-rocole-c11p9h2.jpg",
    alt: "Hoja de café con zonas pardas y rojizas, ejemplo de TRAIN anotado como ácaro rojo en RoCoLe",
    description:
      "Esta categoría reúne hojas con cambios de brillo y coloración parda o rojiza. La imagen por sí sola no confirma la causa.",
    signs: [
      "Pérdida de brillo y tonos pardos o rojizos.",
      "Cambios de color más marcados cerca de las nervaduras.",
    ],
  },
] as const;

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

export default function Home() {
  const inputRef = useRef<HTMLInputElement>(null);
  const requestCoordinatorRef = useRef(new LatestRequestCoordinator());
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [result, setResult] = useState<Prediction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [privacyChoice, setPrivacyChoice] = useState<PrivacyConsentChoice>(null);
  const [privacyDialogOpen, setPrivacyDialogOpen] = useState(false);
  const consentAccepted = canAnalyzeWithConsent(privacyChoice);

  const sortedScores = useMemo(
    () => result?.status === "outside_domain" ? [] : result?.scores.slice().sort((a, b) => b.score - a.score) ?? [],
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

  useEffect(() => {
    let storedChoice: PrivacyConsentChoice = null;
    try {
      storedChoice = parseStoredPrivacyConsent(
        window.localStorage.getItem(PRIVACY_CONSENT_STORAGE_KEY),
      );
    } catch {
      // La aplicación sigue funcionando si el navegador bloquea localStorage.
    }
    setPrivacyChoice(storedChoice);
    if (storedChoice === null) setPrivacyDialogOpen(true);
  }, []);

  function savePrivacyChoice(choice: Exclude<PrivacyConsentChoice, null>) {
    try {
      window.localStorage.setItem(PRIVACY_CONSENT_STORAGE_KEY, choice);
    } catch {
      // La decisión permanece durante la sesión aunque no pueda persistirse.
    }
    setPrivacyChoice(choice);
    setPrivacyDialogOpen(false);
  }

  function declinePrivacyConsent() {
    reset();
    savePrivacyChoice("declined");
  }

  function acceptPrivacyConsent() {
    savePrivacyChoice("accepted");
    window.setTimeout(() => inputRef.current?.focus(), 0);
  }

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
    if (!consentAccepted) {
      if (inputRef.current) inputRef.current.value = "";
      setPrivacyDialogOpen(true);
      return;
    }
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
    if (!consentAccepted) {
      setPrivacyDialogOpen(true);
      return;
    }
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
        throw new Error("No pudimos leer el resultado. Inténtalo de nuevo.");
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

  const relatedGuideId = result && result.status !== "outside_domain"
    ? GUIDE_BY_CATEGORY[result.category]
    : undefined;

  return (
    <>
      <a
        href="#analisis"
        className="sr-only z-50 rounded-lg bg-[#fffdf6] px-4 py-2 font-bold text-[#0d2c22] focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        Ir al análisis
      </a>

      <header className="site-header sticky top-0 z-40">
        <div className="mx-auto flex min-h-[4.75rem] max-w-[90rem] items-center justify-between gap-4 px-4 sm:px-6 lg:px-10">
          <a href="#analisis" className="brand-link" aria-label="CaféIA, ir al analizador">
            <img src="/brand/cafeia-mark.svg" alt="" width={46} height={46} className="brand-symbol" />
            <span>
              <span className="brand-wordmark">Café<span>IA</span></span>
              <span className="brand-subtitle">Análisis de hojas de café</span>
            </span>
          </a>

          <nav aria-label="Navegación principal" className="header-nav">
              <a className="nav-link" href="#analisis">Analizar</a>
              <a className="nav-link" href="#guia">Categorías</a>
          </nav>

          <div className="header-actions">
            <button type="button" onClick={() => setPrivacyDialogOpen(true)} className="header-privacy">
              Privacidad
            </button>
            <a href="#analisis" className="header-cta">
              <span className="hidden sm:inline">Analizar una hoja</span>
              <span className="sm:hidden">Analizar</span>
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14M14 7l5 5-5 5" /></svg>
            </a>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[90rem] px-4 py-6 sm:px-6 sm:py-8 lg:px-10 lg:py-10">
        <section id="analisis" aria-labelledby="analysis-title" className="scroll-mt-28 sm:scroll-mt-20">
          <div className="analysis-intro mb-6 sm:mb-8">
            <div className="analysis-hero">
              <div className="max-w-3xl">
                <p className="eyebrow">Clasificación de hojas de café</p>
                <h1 id="analysis-title" className="display-title mt-3">
                  Analiza una hoja de café
                </h1>
                <p className="hero-copy">
                  Sube una fotografía clara de una sola hoja. CaféIA la compara con ejemplos de hoja sana, roya y daño por ácaro rojo.
                </p>
              </div>
              <figure className="hero-photo">
                <img
                  src="/guide/hoja-sana-rocole-c10p12h1.jpg"
                  alt="Hoja de café sana, verde y completa"
                  width={1920}
                  height={1080}
                />
                <span className="hero-photo__shade" aria-hidden="true" />
                <figcaption>
                  <span>Una hoja, una mirada más clara</span>
                  Fotografía con luz natural y la hoja completa
                </figcaption>
              </figure>
            </div>
          </div>

          <div data-analysis-grid className="analysis-grid grid items-stretch gap-5 md:grid-cols-2 lg:gap-6">
            <section aria-labelledby="upload-title" className="tool-card flex flex-col p-4 sm:p-6">
              <div className="section-heading">
                <span className="step-number" aria-hidden="true">01</span>
                <div>
                  <p className="section-kicker">Fotografía de entrada</p>
                  <h2 id="upload-title" className="mt-0.5 text-xl font-extrabold tracking-[-0.02em] text-[#11382b]">Selecciona la hoja</h2>
                </div>
              </div>

              <form onSubmit={analyze} className="mt-5 flex flex-1 flex-col gap-4">
                <p id="upload-help" className="sr-only">
                  Elige un archivo JPG o PNG. Usa buena luz y una hoja enfocada.
                </p>

                {consentAccepted ? (
                  <div className="consent-inline-status" role="status">
                    <span className="consent-inline-icon" aria-hidden="true">
                      <svg viewBox="0 0 24 24"><path d="M12 3 5 6v5c0 4.6 2.9 8.3 7 10 4.1-1.7 7-5.4 7-10V6l-7-3Z"/><path d="m9.5 12 1.6 1.6 3.7-4"/></svg>
                    </span>
                    <p><strong>Permiso activo.</strong> Ya puedes analizar la fotografía seleccionada.</p>
                    <button type="button" onClick={() => setPrivacyDialogOpen(true)}>Revisar</button>
                  </div>
                ) : (
                  <div className="consent-gate" role="status">
                    <span className="consent-gate-icon" aria-hidden="true">
                      <svg viewBox="0 0 24 24"><path d="M12 3 5 6v5c0 4.6 2.9 8.3 7 10 4.1-1.7 7-5.4 7-10V6l-7-3Z"/></svg>
                    </span>
                    <div>
                      <strong>Autoriza el procesamiento de la imagen</strong>
                      <p>Debes aceptar antes de seleccionar y enviar una fotografía.</p>
                    </div>
                    <button type="button" onClick={() => setPrivacyDialogOpen(true)}>Revisar privacidad</button>
                  </div>
                )}

                <label
                  htmlFor="leaf-photo"
                  onDragEnter={(event) => handleDrag(event, true)}
                  onDragOver={(event) => handleDrag(event, true)}
                  onDragLeave={(event) => handleDrag(event, false)}
                  onDrop={handleDrop}
                  aria-disabled={!consentAccepted}
                  className={`upload-zone relative block min-h-64 overflow-hidden transition-all focus-within:ring-3 focus-within:ring-[#285646] focus-within:ring-offset-2 ${
                    consentAccepted ? "cursor-pointer" : "is-disabled cursor-not-allowed"
                  } ${
                    dragActive ? "is-dragging" : ""
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
                    disabled={!consentAccepted}
                    onChange={selectFile}
                  />

                  {previewUrl ? (
                    <div className="relative">
                      <img
                        src={previewUrl}
                        alt="Vista previa de la hoja seleccionada"
                        className="h-64 w-full object-cover sm:h-72"
                      />
                      <div className="absolute inset-x-3 bottom-3 flex items-center justify-between gap-3 rounded-xl bg-[#0d2c22]/88 px-3.5 py-3 text-white shadow-lg backdrop-blur-sm">
                        <span className="min-w-0 truncate text-sm font-semibold">{file?.name}</span>
                        <span className="inline-flex shrink-0 items-center gap-1.5 text-xs font-bold">
                          <svg className="h-4 w-4 fill-none stroke-current stroke-[1.8]" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h4l1.5-2h5L16 7h4v12H4z"/><circle cx="12" cy="13" r="3.5"/></svg>
                          Reemplazar
                        </span>
                      </div>
                    </div>
                  ) : (
                    <div className="grid min-h-64 place-items-center px-6 py-8 text-center sm:min-h-72">
                      <div className="max-w-xs">
                        <svg className="mx-auto h-12 w-12 fill-none stroke-[#285646] stroke-[1.45]" viewBox="0 0 48 48" aria-hidden="true">
                          <rect x="5" y="7" width="38" height="34" rx="7" />
                          <circle cx="31.5" cy="18" r="4" />
                          <path d="m7 34 9.5-10 7 7 5-5 12 12" />
                        </svg>
                        <p className="mt-4 text-base font-extrabold text-[#11382b]">Arrastra una imagen aquí</p>
                        <p className="mt-1.5 text-sm leading-5 text-[#667871]">o haz clic para buscarla en tu equipo</p>
                        <span className="mt-4 inline-flex rounded-md border border-[#c7d2cc] bg-white px-3 py-1.5 text-xs font-bold text-[#285646] shadow-sm">Seleccionar archivo</span>
                      </div>
                    </div>
                  )}
                </label>

                <aside aria-labelledby="photo-tips-title" className="photo-guidance">
                  <div className="flex items-center gap-2">
                    <svg className="h-4 w-4 shrink-0 fill-none stroke-current stroke-2" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.5"/></svg>
                    <h3 id="photo-tips-title" className="text-sm font-extrabold">Para obtener una imagen más útil</h3>
                  </div>
                  <ul className="mt-2 grid gap-x-4 gap-y-1.5 text-sm leading-5 text-[#52655d] sm:grid-cols-2">
                    <li>Una sola hoja completa</li>
                    <li>Luz uniforme y sin filtros</li>
                    <li>Imagen enfocada</li>
                    <li>Haz y envés por separado</li>
                  </ul>
                </aside>

                {error && (
                  <div role="alert" className="error-alert">
                    <svg className="mt-0.5 h-5 w-5 shrink-0 fill-none stroke-current stroke-2" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7v6M12 17h.01"/></svg>
                    <p><span className="font-extrabold">No se pudo completar el análisis.</span> {error}</p>
                  </div>
                )}

                <button
                  type="submit"
                  disabled={!file || loading || !consentAccepted}
                  className="primary-button mt-auto"
                >
                  <span>{loading ? "Analizando fotografía…" : "Analizar hoja"}</span>
                  {!loading && <svg className="h-5 w-5 fill-none stroke-current stroke-2" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14M14 7l5 5-5 5"/></svg>}
                </button>
              </form>
            </section>

            <section aria-labelledby="result-title" aria-live="polite" aria-busy={loading} className="tool-card flex flex-col p-4 sm:p-6">
              <div className="section-heading">
                <span className="step-number" aria-hidden="true">02</span>
                <div>
                  <p className="section-kicker">Lectura del modelo</p>
                  <p className="mt-0.5 text-xl font-extrabold tracking-[-0.02em] text-[#11382b]">Resultado del análisis</p>
                </div>
              </div>

              {loading ? (
                <div className="result-stage">
                  <div className="max-w-sm text-center">
                    <span className="analysis-loader mx-auto" aria-hidden="true" />
                    <h2 id="result-title" className="mt-6 text-2xl font-black tracking-[-0.03em] text-[#11382b]">Analizando la fotografía</h2>
                    <p className="mt-2 text-sm leading-6 text-[#667871]">Estamos comparando la imagen con los patrones de las tres categorías.</p>
                    <p className="mt-3 text-xs leading-5 text-[#71827b]">Si reemplazas la fotografía, esta solicitud se cancelará.</p>
                  </div>
                </div>
              ) : result?.status === "outside_domain" ? (
                <div className="mt-5">
                  <div className="result-summary is-uncertain">
                    <div className="result-summary__status">
                      <span className="result-status-icon" aria-hidden="true">!</span>
                      <span>Imagen fuera del alcance</span>
                    </div>
                    <h2 id="result-title" className="mt-4 text-2xl font-black tracking-[-0.035em] text-[#11382b] sm:text-[1.75rem]">
                      No se pudo confirmar la hoja
                    </h2>
                    <p className="mt-3 text-sm leading-6 text-[#52655d]">{result.message}</p>
                    <p className="mt-4 border-t border-[#b98927]/20 pt-3 text-sm leading-5 text-[#6b511b]">
                      No mostramos una categoría ni puntuaciones porque la imagen no pasó el filtro experimental de dominio. El filtro reduce errores evidentes, pero no reconoce todos los objetos ni garantiza que una imagen aceptada sea café.
                    </p>
                  </div>
                  <div className="mt-5 grid gap-3 sm:grid-cols-2">
                    <button type="button" onClick={() => reset(true)} className="secondary-button">
                      Cargar otra fotografía
                    </button>
                    <a href="#guia" className="text-button">
                      Consultar las tres categorías
                      <svg className="h-4 w-4 fill-none stroke-current stroke-2" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14M14 7l5 5-5 5"/></svg>
                    </a>
                  </div>
                </div>
              ) : result ? (
                <div className="mt-5">
                  <div className={`result-summary ${result.is_uncertain ? "is-uncertain" : "is-accepted"}`}>
                    <div className="result-summary__status">
                      <span className="result-status-icon" aria-hidden="true">
                        {result.is_uncertain ? "?" : "✓"}
                      </span>
                      <span>{result.is_uncertain ? "Revisión recomendada" : "Análisis completado"}</span>
                    </div>
                    <h2 id="result-title" className="mt-4 text-2xl font-black tracking-[-0.035em] text-[#11382b] sm:text-[1.75rem]">
                      {result.is_uncertain
                        ? "Resultado incierto"
                        : `Clasificación orientativa: ${result.category_label}`}
                    </h2>
                    {result.is_uncertain && (
                      <p className="mt-2 text-sm font-bold text-[#52655d]">
                        Categoría más probable: {result.category_label}
                      </p>
                    )}
                    <div className="mt-4 flex items-end justify-between gap-4 border-t border-current/10 pt-4">
                      <div>
                        <p className="text-[0.65rem] font-extrabold tracking-[0.12em] text-[#687a73] uppercase">Puntuación mayor</p>
                        <p className="mt-1 text-3xl leading-none font-black tracking-[-0.04em] text-[#a75236]">{formatScore(result.score)}</p>
                      </div>
                      <span className="text-right text-xs leading-4 text-[#71827b]">Umbral provisional<br />{formatScore(result.uncertainty_threshold)}</span>
                    </div>
                    {result.is_uncertain && (
                      <p className="mt-4 border-t border-[#b98927]/20 pt-3 text-sm leading-5 text-[#6b511b]">
                        La puntuación mayor no alcanzó el umbral provisional de {formatScore(result.uncertainty_threshold)}. Prueba otra foto o solicita revisión humana.
                      </p>
                    )}
                  </div>

                  <div className="mt-6 flex items-center justify-between gap-3">
                    <h3 className="text-sm font-extrabold text-[#11382b]">Puntuaciones por clase</h3>
                    <span className="text-xs text-[#71827b]">Suma total: 100 %</span>
                  </div>
                  <div className="mt-3 space-y-3.5">
                    {sortedScores.map((item) => (
                      <div key={item.category}>
                        <div className="mb-1.5 flex items-center justify-between gap-4 text-sm">
                          <span className="font-semibold text-[#40564e]">{item.label}</span>
                          <span className="font-extrabold tabular-nums text-[#11382b]">{formatScore(item.score)}</span>
                        </div>
                        <div
                          role="progressbar"
                          aria-label={`Puntuación de ${item.label}`}
                          aria-valuemin={0}
                          aria-valuemax={100}
                          aria-valuenow={Math.round(item.score * 100)}
                          className="h-2 overflow-hidden rounded-full bg-[#e4e9e6]"
                        >
                          <div className="score-bar h-full rounded-full" style={{ width: `${Math.max(1, item.score * 100)}%` }} />
                        </div>
                      </div>
                    ))}
                  </div>

                  {!result.is_uncertain && (
                    <p className="mt-5 border-l-2 border-[#55806f] bg-[#f2f6f3] px-4 py-3 text-sm leading-5 text-[#40564e]">
                      Toma esta lectura como un primer punto de comparación. Si notas cambios en el cultivo, revisa varias hojas y consulta a un profesional del café.
                    </p>
                  )}

                  <div className="mt-5 grid gap-3 sm:grid-cols-2">
                    <button type="button" onClick={() => reset(true)} className="secondary-button">
                      Analizar otra fotografía
                    </button>
                    <a href={result.is_uncertain || !relatedGuideId ? "#guia" : `#${relatedGuideId}`} className="text-button">
                      {result.is_uncertain ? "Consultar categorías" : `Ver ficha de ${result.category_label.toLocaleLowerCase("es-CO")}`}
                      <svg className="h-4 w-4 fill-none stroke-current stroke-2" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14M14 7l5 5-5 5"/></svg>
                    </a>
                  </div>
                </div>
              ) : error ? (
                <div className="result-stage">
                  <div className="max-w-sm text-center">
                    <span className="empty-state-icon is-error" aria-hidden="true">!</span>
                    <h2 id="result-title" className="mt-5 text-2xl font-black tracking-[-0.03em] text-[#7b3825]">Análisis no disponible</h2>
                    <p className="mt-2 text-sm leading-6 text-[#667871]">Revisa el mensaje junto al selector y vuelve a intentarlo.</p>
                  </div>
                </div>
              ) : (
                <div className="result-stage">
                  <div className="max-w-sm text-center">
                    <span className="empty-state-icon" aria-hidden="true">
                      <svg className="h-7 w-7 fill-none stroke-current stroke-[1.7]" viewBox="0 0 24 24"><path d="M4 5h16v14H4z"/><path d="m4 15 4.5-4.5 3 3L14 11l6 6"/><circle cx="15.5" cy="8.5" r="1.5"/></svg>
                    </span>
                    <h2 id="result-title" className="mt-5 text-2xl font-black tracking-[-0.03em] text-[#11382b]">Tu resultado aparecerá aquí</h2>
                    <p className="mt-2 text-sm leading-6 text-[#667871]">
                      Selecciona una fotografía y ejecuta el análisis para ver la categoría más probable y sus puntuaciones.
                    </p>
                  </div>
                </div>
              )}

              <div className="model-note mt-auto">
                <svg className="mt-0.5 h-4 w-4 shrink-0 fill-none stroke-current stroke-2" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.5"/></svg>
                <p>Las puntuaciones no son probabilidades calibradas de acierto. CaféIA solo distingue hoja sana, roya y ácaro rojo. El filtro previo de dominio es experimental y no garantiza que toda imagen aceptada corresponda a una hoja de café.</p>
              </div>
            </section>
          </div>
        </section>

        <section id="guia" aria-labelledby="guide-title" className="guide-section mt-16 scroll-mt-28 py-10 sm:mt-20 sm:scroll-mt-20 sm:py-14">
          <div className="max-w-3xl">
              <h2 id="guide-title" className="category-title">
                Explora las hojas por categoría
              </h2>
              <p className="category-subtitle">
                Conoce las tres categorías que CaféIA puede comparar y revisa sus señales visuales habituales.
              </p>
          </div>

          <div className="category-grid">
            {GUIDE_CARDS.map((card) => (
              <article id={card.id} key={card.id} className="guide-card scroll-mt-28 overflow-hidden sm:scroll-mt-20">
                <div className="category-visual">
                  <img src={card.image} alt={card.alt} width={1920} height={1080} loading="lazy" />
                  <span className="category-shade" aria-hidden="true" />
                  <div className="category-heading">
                    <span>Hoja de café</span>
                    <h3>{card.eyebrow}</h3>
                  </div>
                </div>
                <div className="category-content">
                  <p className="category-lead">{card.title}</p>
                  <p className="mt-3 text-sm leading-6 text-[#52655d]">{card.description}</p>

                  <details className="guide-details mt-5 border-t border-[#163f31]/10 pt-4">
                    <summary className="inline-flex min-h-11 cursor-pointer list-none items-center text-sm font-extrabold text-[#285646] hover:text-[#a75236] focus-visible:outline-3 focus-visible:outline-offset-3 focus-visible:outline-[#9d4e34]">
                      Ver detalles
                    </summary>
                    <div className="guide-observation mt-4 text-sm leading-6 text-[#52655d]">
                      <h4>Qué observar</h4>
                      <ul className="guide-signs mt-2 space-y-2">
                        {card.signs.map((sign) => <li key={sign}>{sign}</li>)}
                      </ul>
                      <p className="observation-note">Úsalas como guía de comparación; una fotografía puede no mostrar todas las señales.</p>
                    </div>
                  </details>
                </div>
              </article>
            ))}
          </div>

          <p className="guide-credits">
            Información general: <a href="https://publicaciones.cenicafe.org/" target="_blank" rel="noreferrer">Cenicafé</a>. Fotografías: <a href="https://data.mendeley.com/datasets/c5yvn32dzg/2" target="_blank" rel="noreferrer">RoCoLe v2</a>, licencia <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noreferrer">CC BY 4.0</a>.
          </p>
        </section>
      </main>

      <footer className="site-footer mt-12">
        <div className="mx-auto flex max-w-[90rem] flex-col gap-3 px-4 py-7 text-sm sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-10">
          <div className="flex items-center gap-2.5">
            <img src="/brand/cafeia-mark.svg" alt="" width={34} height={34} className="footer-logo" />
            <span className="font-extrabold tracking-[-0.02em]">CaféIA</span>
          </div>
          <div className="flex flex-col items-start gap-2 sm:items-end">
            <p className="max-w-2xl text-[#c7d5cf] sm:text-right">Clasificación de imágenes en tres categorías de hojas de café. Las puntuaciones sirven como referencia y pueden contener errores.</p>
            <button type="button" onClick={() => setPrivacyDialogOpen(true)} className="footer-privacy-button">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 5 6v5c0 4.6 2.9 8.3 7 10 4.1-1.7 7-5.4 7-10V6l-7-3Z"/></svg>
              Privacidad y consentimiento
            </button>
          </div>
        </div>
      </footer>

      <PrivacyConsent
        choice={privacyChoice}
        open={privacyDialogOpen}
        onAccept={acceptPrivacyConsent}
        onClose={() => setPrivacyDialogOpen(false)}
        onDecline={declinePrivacyConsent}
      />
    </>
  );
}
