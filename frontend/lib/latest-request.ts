export type RequestTicket = Readonly<{
  requestId: number;
  selectionId: number;
  controller: AbortController;
}>;

/**
 * Coordina una sola petición por fotografía seleccionada.
 *
 * El contador de selección evita que una respuesta tardía se aplique a una
 * fotografía posterior. El bloqueo sincrónico evita dos envíos antes de que
 * React alcance a reflejar el estado `loading` en pantalla.
 */
export class LatestRequestCoordinator {
  private requestSequence = 0;
  private selectionSequence = 0;
  private locked = false;
  private controller: AbortController | null = null;

  begin(): RequestTicket | null {
    if (this.locked) return null;
    this.locked = true;
    const ticket: RequestTicket = {
      requestId: ++this.requestSequence,
      selectionId: this.selectionSequence,
      controller: new AbortController(),
    };
    this.controller = ticket.controller;
    return ticket;
  }

  isCurrent(ticket: RequestTicket): boolean {
    return (
      !ticket.controller.signal.aborted &&
      ticket.requestId === this.requestSequence &&
      ticket.selectionId === this.selectionSequence
    );
  }

  finish(ticket: RequestTicket): boolean {
    if (ticket.requestId !== this.requestSequence) return false;
    this.controller = null;
    this.locked = false;
    return true;
  }

  replaceSelection(): void {
    this.cancel();
    this.selectionSequence += 1;
  }

  cancel(): void {
    this.requestSequence += 1;
    this.controller?.abort();
    this.controller = null;
    this.locked = false;
  }
}
