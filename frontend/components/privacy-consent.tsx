"use client";

import { KeyboardEvent, useEffect, useRef, useState } from "react";

import type { PrivacyConsentChoice } from "../lib/privacy-consent";

const TABS = [
  { id: "consent", label: "Consentimiento" },
  { id: "privacy", label: "Privacidad" },
  { id: "scope", label: "Alcance" },
] as const;

type TabId = (typeof TABS)[number]["id"];

type PrivacyConsentProps = {
  choice: PrivacyConsentChoice;
  open: boolean;
  onAccept: () => void;
  onClose: () => void;
  onDecline: () => void;
};

export function PrivacyConsent({
  choice,
  open,
  onAccept,
  onClose,
  onDecline,
}: PrivacyConsentProps) {
  const [activeTab, setActiveTab] = useState<TabId>("consent");
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;

    const previousFocus = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeButtonRef.current?.focus();

    function handleKeyDown(event: globalThis.KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab" || !dialogRef.current) return;

      const focusable = Array.from(
        dialogRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), a[href], input:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ),
      );
      if (focusable.length === 0) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = previousOverflow;
      previousFocus?.focus();
    };
  }, [open, onClose]);

  if (!open) return null;

  function selectTab(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    let nextIndex = index;
    if (event.key === "ArrowRight") nextIndex = (index + 1) % TABS.length;
    else if (event.key === "ArrowLeft") nextIndex = (index - 1 + TABS.length) % TABS.length;
    else if (event.key === "Home") nextIndex = 0;
    else if (event.key === "End") nextIndex = TABS.length - 1;
    else return;

    event.preventDefault();
    const nextTab = TABS[nextIndex];
    setActiveTab(nextTab.id);
    dialogRef.current
      ?.querySelector<HTMLButtonElement>(`[data-consent-tab="${nextTab.id}"]`)
      ?.focus();
  }

  return (
    <div
      className="consent-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="consent-title"
        aria-describedby="consent-summary"
        className="consent-dialog"
      >
        <header className="consent-header">
          <div className="flex min-w-0 items-center gap-3">
            <span className="consent-shield" aria-hidden="true">
              <svg viewBox="0 0 24 24"><path d="M12 3 5 6v5c0 4.6 2.9 8.3 7 10 4.1-1.7 7-5.4 7-10V6l-7-3Z"/><path d="m9.5 12 1.6 1.6 3.7-4"/></svg>
            </span>
            <div className="min-w-0">
              <p className="consent-brand">CaféIA</p>
              <h2 id="consent-title" className="consent-title">Privacidad y consentimiento</h2>
            </div>
          </div>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={onClose}
            className="consent-close"
            aria-label="Cerrar aviso de privacidad"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18"/></svg>
          </button>
        </header>

        <div role="tablist" aria-label="Información de privacidad" className="consent-tabs">
          {TABS.map((tab, index) => (
            <button
              key={tab.id}
              type="button"
              role="tab"
              id={`tab-${tab.id}`}
              aria-controls={`panel-${tab.id}`}
              aria-selected={activeTab === tab.id}
              tabIndex={activeTab === tab.id ? 0 : -1}
              data-consent-tab={tab.id}
              onClick={() => setActiveTab(tab.id)}
              onKeyDown={(event) => selectTab(event, index)}
              className="consent-tab"
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="consent-content">
          {activeTab === "consent" && (
            <section role="tabpanel" id="panel-consent" aria-labelledby="tab-consent">
              <p className="consent-eyebrow">Tu fotografía, bajo tu control</p>
              <h3 className="consent-heading">Autoriza el análisis antes de enviar una imagen</h3>
              <p id="consent-summary" className="consent-copy">
                Al pulsar “Analizar hoja”, la fotografía seleccionada se envía al backend configurado de CaféIA para ejecutar el modelo. La imagen se procesa en memoria y no se guarda.
              </p>
              <div className="consent-assurances">
                <p><span aria-hidden="true">✓</span>No solicitamos una cuenta ni datos personales.</p>
                <p><span aria-hidden="true">✓</span>No usamos cookies publicitarias ni de analítica.</p>
                <p><span aria-hidden="true">✓</span>Solo guardamos esta decisión en el almacenamiento local del navegador.</p>
              </div>
            </section>
          )}

          {activeTab === "privacy" && (
            <section role="tabpanel" id="panel-privacy" aria-labelledby="tab-privacy">
              <p className="consent-eyebrow">Tratamiento de la imagen</p>
              <h3 className="consent-heading">Un flujo corto y explícito</h3>
              <ol className="privacy-flow">
                <li><span>01</span><div><strong>Selección local</strong><p>La vista previa se crea en tu navegador.</p></div></li>
                <li><span>02</span><div><strong>Envío al backend</strong><p>Solo ocurre cuando pulsas “Analizar hoja”.</p></div></li>
                <li><span>03</span><div><strong>Inferencia en memoria</strong><p>El backend valida la imagen, calcula las puntuaciones y no conserva el archivo.</p></div></li>
              </ol>
              <p className="consent-fine-print">Puedes retirar el consentimiento desde “Privacidad” en el pie de página. Al hacerlo, también se elimina cualquier fotografía seleccionada de la interfaz.</p>
            </section>
          )}

          {activeTab === "scope" && (
            <section role="tabpanel" id="panel-scope" aria-labelledby="tab-scope">
              <p className="consent-eyebrow">Uso responsable</p>
              <h3 className="consent-heading">Qué puede y qué no puede hacer CaféIA</h3>
              <div className="scope-grid">
                <div><strong>Puede comparar</strong><p>Patrones con hoja sana, roya y daño por ácaro rojo.</p></div>
                <div><strong>No puede confirmar</strong><p>Un diagnóstico, la especie de ácaro o que la imagen pertenezca a una hoja de café.</p></div>
              </div>
              <p className="consent-warning">Las puntuaciones no son probabilidades calibradas de acierto. Un resultado alto también puede ser incorrecto.</p>
            </section>
          )}
        </div>

        <footer className="consent-actions">
          <button type="button" onClick={onDecline} className="consent-button is-secondary">
            {choice === "accepted" ? "Retirar consentimiento" : "Continuar sin analizar"}
          </button>
          <button type="button" onClick={onAccept} className="consent-button is-primary">
            {choice === "accepted" ? "Mantener consentimiento" : "Aceptar y continuar"}
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14M14 7l5 5-5 5"/></svg>
          </button>
        </footer>
      </div>
    </div>
  );
}
