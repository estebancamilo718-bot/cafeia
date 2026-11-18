import type { AgentStep, Weather } from "../lib/analysis";

type AgentPanelProps = {
  weather: Weather | null;
  weatherMessage: string | null;
  steps: AgentStep[];
};

const STEP_ICON: Record<AgentStep["estado"], string> = {
  ok: "✓",
  error: "!",
  omitida: "–",
};

const STEP_LABEL: Record<AgentStep["estado"], string> = {
  ok: "Respondió",
  error: "Sin datos",
  omitida: "No consultada",
};

function formatNumber(value: number | null, unit: string) {
  if (value === null) return "—";
  return `${value.toLocaleString("es-CO", { maximumFractionDigits: 1 })}${unit}`;
}

function formatDay(isoDate: string) {
  const date = new Date(`${isoDate}T12:00:00`);
  if (Number.isNaN(date.getTime())) return isoDate;
  const text = date.toLocaleDateString("es-CO", { weekday: "short", day: "numeric", month: "short" });
  return text.charAt(0).toLocaleUpperCase("es-CO") + text.slice(1);
}

export function AgentPanel({ weather, weatherMessage, steps }: AgentPanelProps) {
  const location = weather?.actual.ubicacion;

  return (
    <div className="mt-6 space-y-4">
      <section aria-labelledby="weather-title" className="rounded-xl border border-[#163f31]/12 bg-[#f6f8f4] p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[0.65rem] font-extrabold tracking-[0.12em] text-[#687a73] uppercase">Sensor ambiental · MCP</p>
            <h3 id="weather-title" className="mt-1 text-base font-extrabold text-[#11382b]">
              {location
                ? `Clima en ${location.nombre}${location.departamento ? `, ${location.departamento}` : ""}`
                : "Clima de la zona"}
            </h3>
          </div>
          <svg className="h-6 w-6 shrink-0 fill-none stroke-[#285646] stroke-[1.6]" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M7 18h10a4 4 0 0 0 .4-8 6 6 0 0 0-11.6 1.5A3.3 3.3 0 0 0 7 18Z" />
          </svg>
        </div>

        {weather ? (
          <>
            <dl className="mt-3 grid grid-cols-3 gap-2 text-center">
              <div className="rounded-lg bg-white px-2 py-2.5">
                <dt className="text-[0.68rem] font-bold text-[#687a73]">Temperatura</dt>
                <dd className="mt-0.5 text-lg font-black text-[#11382b]">{formatNumber(weather.actual.temperatura_c, " °C")}</dd>
              </div>
              <div className="rounded-lg bg-white px-2 py-2.5">
                <dt className="text-[0.68rem] font-bold text-[#687a73]">Humedad</dt>
                <dd className="mt-0.5 text-lg font-black text-[#11382b]">{formatNumber(weather.actual.humedad_relativa_pct, " %")}</dd>
              </div>
              <div className="rounded-lg bg-white px-2 py-2.5">
                <dt className="text-[0.68rem] font-bold text-[#687a73]">Lluvia ahora</dt>
                <dd className="mt-0.5 text-lg font-black text-[#11382b]">{formatNumber(weather.actual.precipitacion_mm, " mm")}</dd>
              </div>
            </dl>

            <div className="mt-3 overflow-x-auto">
              <table className="w-full min-w-[18rem] text-left text-xs text-[#40564e]">
                <caption className="sr-only">Pronóstico de los próximos días</caption>
                <thead>
                  <tr className="text-[#687a73]">
                    <th scope="col" className="py-1.5 font-bold">Día</th>
                    <th scope="col" className="py-1.5 font-bold">Máx / mín</th>
                    <th scope="col" className="py-1.5 font-bold">Lluvia</th>
                    <th scope="col" className="py-1.5 font-bold">Prob.</th>
                    <th scope="col" className="py-1.5 font-bold">Humedad</th>
                  </tr>
                </thead>
                <tbody>
                  {weather.pronostico.dias.map((day) => (
                    <tr key={day.fecha} className="border-t border-[#163f31]/10">
                      <th scope="row" className="py-1.5 font-semibold">{formatDay(day.fecha)}</th>
                      <td className="py-1.5 tabular-nums">
                        {formatNumber(day.temperatura_max_c, "°")} / {formatNumber(day.temperatura_min_c, "°")}
                      </td>
                      <td className="py-1.5 tabular-nums">{formatNumber(day.precipitacion_mm, " mm")}</td>
                      <td className="py-1.5 tabular-nums">{formatNumber(day.probabilidad_lluvia_pct, " %")}</td>
                      <td className="py-1.5 tabular-nums">{formatNumber(day.humedad_media_pct, " %")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <p className="mt-3 text-xs leading-5 text-[#687a73]">
              Datos de{" "}
              <a href="https://open-meteo.com/" target="_blank" rel="noreferrer" className="font-bold text-[#285646] underline">
                Open-Meteo
              </a>{" "}
              (CC BY 4.0). Son contexto del cultivo: CaféIA no calcula un riesgo de enfermedad a partir del clima.
            </p>
          </>
        ) : (
          <p className="mt-3 text-sm leading-6 text-[#52655d]">{weatherMessage}</p>
        )}
      </section>

      <section aria-labelledby="agent-steps-title" className="rounded-xl border border-[#163f31]/12 p-4">
        <h3 id="agent-steps-title" className="text-sm font-extrabold text-[#11382b]">Cómo trabajó el agente</h3>
        <p className="mt-1 text-xs leading-5 text-[#687a73]">
          CaféIA consultó sus sensores mediante MCP (Model Context Protocol).
        </p>
        <ol className="mt-3 space-y-2">
          {steps.map((step, index) => (
            <li key={`${step.servidor}-${step.herramienta}-${index}`} className="flex items-start gap-2.5 text-sm">
              <span
                aria-hidden="true"
                className={`mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full text-[0.7rem] font-black ${
                  step.estado === "ok"
                    ? "bg-[#dcebe2] text-[#285646]"
                    : step.estado === "error"
                      ? "bg-[#f6e1d9] text-[#a75236]"
                      : "bg-[#e9ecea] text-[#687a73]"
                }`}
              >
                {STEP_ICON[step.estado]}
              </span>
              <div className="min-w-0">
                <p className="text-[#40564e]">
                  <code className="font-mono text-[0.78rem] font-bold text-[#11382b]">{step.servidor}</code>
                  {" → "}
                  <code className="font-mono text-[0.78rem] text-[#11382b]">{step.herramienta}</code>
                  <span className="sr-only">: </span>
                  <span className="ml-2 text-xs font-bold text-[#687a73]">{STEP_LABEL[step.estado]}</span>
                </p>
                {step.detalle && <p className="text-xs leading-5 text-[#687a73]">{step.detalle}</p>}
              </div>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
