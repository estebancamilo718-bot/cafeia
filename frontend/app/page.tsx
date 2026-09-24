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

const MAX_FILE_SIZE = 10 * 1024 * 1024;
const ALLOWED_TYPES = new Set(["image/jpeg", "image/png"]);
const ALLOWED_EXTENSIONS = /\.(jpe?g|png)$/i;
const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

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

export default function Home() {
  const inputRef = useRef<HTMLInputElement>(null);
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

  function reset(focusInput = false) {
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
    setError(null);
    setResult(null);

    if (!selected) {
      reset();
      return;
    }
    if (!ALLOWED_TYPES.has(selected.type) || !ALLOWED_EXTENSIONS.test(selected.name)) {
      reset();
      setError("Selecciona una fotografía JPG o PNG válida.");
      return;
    }
    if (selected.size > MAX_FILE_SIZE) {
      reset();
      setError("La fotografía no puede superar 10 MB.");
      return;
    }

    setFile(selected);
    setPreviewUrl(URL.createObjectURL(selected));
  }

  function selectFile(event: ChangeEvent<HTMLInputElement>) {
    useSelectedFile(event.target.files?.[0] ?? null);
  }

  function handleDrag(event: DragEvent<HTMLLabelElement>, active: boolean) {
    event.preventDefault();
    if (!loading) setDragActive(active);
  }

  function handleDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    if (loading) return;
    setDragActive(false);
    useSelectedFile(event.dataTransfer.files?.[0] ?? null);
  }

  async function analyze(event: FormEvent) {
    event.preventDefault();
    if (!file || loading) return;

    setLoading(true);
    setError(null);
    setResult(null);
    const body = new FormData();
    body.append("file", file);

    try {
      const response = await fetch(`${API_URL}/predict`, { method: "POST", body });
      const payload: unknown = await response.json().catch(() => null);
      if (!response.ok) throw new Error(errorMessage(payload));
      setResult(payload as Prediction);
    } catch (reason) {
      setError(
        reason instanceof TypeError
          ? "No se pudo conectar con CaféIA. Comprueba que el backend esté encendido."
          : reason instanceof Error
            ? reason.message
            : "Ocurrió un error inesperado.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <a
        href="#analisis"
        className="sr-only z-50 rounded-lg bg-[#fffdf6] px-4 py-2 font-bold text-[#0d2c22] focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        Ir al análisis
      </a>

      <header className="border-b border-[#163f31]/12 bg-[#fffdf6]/95">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 sm:px-6 lg:px-8">
          <div className="flex items-center gap-2.5">
            <span className="grid h-9 w-9 place-items-center rounded-full bg-[#163f31]" aria-hidden="true">
              <span className="leaf-mark scale-[0.42]" />
            </span>
            <span className="text-xl font-black tracking-[-0.04em] text-[#163f31]">CaféIA</span>
          </div>
          <span className="rounded-full bg-[#dbe5d4] px-3 py-1.5 text-[0.7rem] font-bold tracking-wide text-[#163f31] uppercase sm:text-xs">
            Prototipo académico
          </span>
        </div>
      </header>

      <main id="analisis" className="mx-auto max-w-6xl px-4 py-7 sm:px-6 sm:py-9 lg:px-8 lg:py-10">
        <div className="mb-6 max-w-3xl sm:mb-8">
          <p className="text-xs font-extrabold tracking-[0.18em] text-[#9d4e34] uppercase">Análisis visual orientativo</p>
          <h1 className="mt-2 text-3xl leading-tight font-black tracking-[-0.045em] text-[#163f31] sm:text-4xl">
            Analiza una hoja de café
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-[#455f55] sm:text-base">
            Sube una fotografía clara de una sola hoja. CaféIA comparará la imagen con las categorías hoja sana,
            roya y ácaro rojo.
          </p>
        </div>

        <div className="grid items-start gap-5 md:grid-cols-2 lg:gap-7">
          <section aria-labelledby="upload-title" className="rounded-3xl border border-[#163f31]/12 bg-[#fffdf6] p-4 shadow-[0_16px_50px_rgba(22,63,49,0.08)] sm:p-6">
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
                className={`relative block min-h-64 cursor-pointer overflow-hidden rounded-2xl border-2 border-dashed bg-[#f9f5e9] transition-colors focus-within:ring-3 focus-within:ring-[#d0a24c] focus-within:ring-offset-2 ${
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
                  disabled={loading}
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

              {error && (
                <div role="alert" className="rounded-xl border border-[#a45136]/30 bg-[#f8e9e2] px-4 py-3 text-sm leading-5 text-[#7b3825]">
                  <span className="font-extrabold">No se pudo completar el análisis.</span> {error}
                </div>
              )}

              <button
                type="submit"
                disabled={!file || loading}
                className="w-full rounded-xl bg-[#a45136] px-5 py-3.5 font-extrabold text-white shadow-[0_8px_20px_rgba(119,53,34,0.18)] transition-colors hover:bg-[#873f2a] focus-visible:outline-3 focus-visible:outline-offset-3 focus-visible:outline-[#d0a24c] disabled:cursor-not-allowed disabled:bg-[#b9aaa3] disabled:text-[#fffdf6] disabled:shadow-none"
              >
                {loading ? "Analizando fotografía…" : "Analizar hoja"}
              </button>
            </form>
          </section>

          <section aria-labelledby="result-title" aria-live="polite" aria-busy={loading} className="rounded-3xl border border-[#163f31]/12 bg-[#fffdf6] p-4 shadow-[0_16px_50px_rgba(22,63,49,0.08)] sm:p-6">
            <p className="text-xs font-extrabold tracking-[0.14em] text-[#9d4e34] uppercase">Paso 2</p>

            {loading ? (
              <div className="grid min-h-80 place-items-center py-8 text-center">
                <div>
                  <span className="mx-auto block h-3 w-3 rounded-full bg-[#a45136]" aria-hidden="true" />
                  <h2 id="result-title" className="mt-5 text-2xl font-black text-[#163f31]">Analizando la fotografía</h2>
                  <p className="mt-2 text-sm leading-6 text-[#52675f]">El modelo está calculando las puntuaciones de las tres clases.</p>
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

                <button
                  type="button"
                  onClick={() => reset(true)}
                  className="mt-5 w-full rounded-xl border-2 border-[#163f31] px-5 py-3 font-extrabold text-[#163f31] transition-colors hover:bg-[#163f31] hover:text-white focus-visible:outline-3 focus-visible:outline-offset-3 focus-visible:outline-[#d0a24c]"
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

        <section
          aria-labelledby="evaluation-title"
          className="mt-8 rounded-3xl border border-[#163f31]/12 bg-[#fffdf6] p-5 shadow-[0_16px_50px_rgba(22,63,49,0.06)] sm:p-7"
        >
          <div className="max-w-3xl">
            <p className="text-xs font-extrabold tracking-[0.14em] text-[#9d4e34] uppercase">Resultados medidos</p>
            <h2 id="evaluation-title" className="mt-1 text-2xl font-black tracking-[-0.025em] text-[#163f31]">
              Evaluación del prototipo
            </h2>
            <p className="mt-2 text-sm leading-6 text-[#455f55]">
              Estas cifras describen el conjunto de prueba fijado de 300 imágenes. No son garantías de desempeño para fotografías nuevas.
            </p>
          </div>

          <dl className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-2xl bg-[#f6f0df] p-4">
              <dt className="text-xs font-bold tracking-wide text-[#52675f] uppercase">Imágenes de prueba</dt>
              <dd className="mt-1 text-2xl font-black text-[#163f31]">300</dd>
            </div>
            <div className="rounded-2xl bg-[#f6f0df] p-4">
              <dt className="text-xs font-bold tracking-wide text-[#52675f] uppercase">Accuracy general</dt>
              <dd className="mt-1 text-2xl font-black text-[#163f31]">71,67 %</dd>
            </div>
            <div className="rounded-2xl bg-[#f6f0df] p-4">
              <dt className="text-xs font-bold tracking-wide text-[#52675f] uppercase">F1 macro</dt>
              <dd className="mt-1 text-2xl font-black text-[#163f31]">0,6235</dd>
            </div>
            <div className="rounded-2xl bg-[#f6f0df] p-4">
              <dt className="text-xs font-bold tracking-wide text-[#52675f] uppercase">Cobertura con umbral 0,70</dt>
              <dd className="mt-1 text-2xl font-black text-[#163f31]">52,67 %</dd>
            </div>
          </dl>

          <div className="mt-4 grid gap-4 border-t border-[#163f31]/10 pt-4 text-sm leading-6 text-[#455f55] md:grid-cols-2">
            <p>
              Con el umbral provisional de 0,70 se aceptaron <strong className="text-[#163f31]">158 de 300</strong> predicciones: 140 correctas y 18 incorrectas. La accuracy dentro de ese subconjunto fue 88,61 %.
            </p>
            <p>
              La principal limitación observada fue la clasificación de <strong className="text-[#163f31]">ácaro rojo</strong>. El umbral no está calibrado y tampoco detecta imágenes que no sean hojas de café.
            </p>
          </div>
        </section>
      </main>
    </>
  );
}
