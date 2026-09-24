import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const [uncertainImage, replacementImage, acceptedImage] = process.argv.slice(2);
if (!uncertainImage || !replacementImage || !acceptedImage) {
  throw new Error("Uso: node scripts/verify_frontend.mjs <incierta> <reemplazo> <aceptada>");
}

const edgePath = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const debugPort = 9333;
const profilePath = path.join(os.tmpdir(), `cafeia-edge-${process.pid}`);
const outputDir = path.resolve("reports", "web_ui_verification");
fs.mkdirSync(outputDir, { recursive: true });

const edge = spawn(
  edgePath,
  [
    "--headless=new",
    "--disable-gpu",
    "--no-first-run",
    "--no-default-browser-check",
    `--remote-debugging-port=${debugPort}`,
    `--user-data-dir=${profilePath}`,
    "about:blank",
  ],
  { stdio: "ignore", windowsHide: true },
);

const delay = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

async function waitForDebugTarget() {
  for (let attempt = 0; attempt < 50; attempt += 1) {
    try {
      const response = await fetch(`http://127.0.0.1:${debugPort}/json/list`);
      const targets = await response.json();
      const page = targets.find((target) => target.type === "page");
      if (page?.webSocketDebuggerUrl) return page;
    } catch {
      // Edge todavía está iniciando.
    }
    await delay(100);
  }
  throw new Error("Edge no expuso el puerto de depuración a tiempo");
}

class CdpClient {
  constructor(url) {
    this.socket = new WebSocket(url);
    this.nextId = 1;
    this.pending = new Map();
  }

  async open() {
    await new Promise((resolve, reject) => {
      this.socket.addEventListener("open", resolve, { once: true });
      this.socket.addEventListener("error", reject, { once: true });
    });
    this.socket.addEventListener("message", (event) => {
      const message = JSON.parse(event.data);
      if (!message.id || !this.pending.has(message.id)) return;
      const { resolve, reject } = this.pending.get(message.id);
      this.pending.delete(message.id);
      if (message.error) reject(new Error(message.error.message));
      else resolve(message.result);
    });
  }

  send(method, params = {}) {
    const id = this.nextId;
    this.nextId += 1;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.socket.send(JSON.stringify({ id, method, params }));
    });
  }

  close() {
    this.socket.close();
  }
}

async function evaluate(client, expression) {
  const result = await client.send("Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true,
  });
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.text);
  return result.result.value;
}

async function waitFor(client, expression, description) {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    if (await evaluate(client, expression)) return;
    await delay(100);
  }
  throw new Error(`No se observó el estado esperado: ${description}`);
}

async function setViewport(client, width, height = 1000) {
  await client.send("Emulation.setDeviceMetricsOverride", {
    width,
    height,
    deviceScaleFactor: 1,
    mobile: width < 768,
  });
  await delay(150);
}

async function screenshot(client, filename) {
  const result = await client.send("Page.captureScreenshot", {
    format: "png",
    captureBeyondViewport: false,
  });
  fs.writeFileSync(path.join(outputDir, filename), Buffer.from(result.data, "base64"));
}

async function setFile(client, imagePath) {
  const document = await client.send("DOM.getDocument");
  const input = await client.send("DOM.querySelector", {
    nodeId: document.root.nodeId,
    selector: "#leaf-photo",
  });
  await client.send("DOM.setFileInputFiles", {
    nodeId: input.nodeId,
    files: [path.resolve(imagePath)],
  });
}

async function clickButton(client, text) {
  const clicked = await evaluate(
    client,
    `(() => { const button = [...document.querySelectorAll("button")].find((item) => item.textContent.includes(${JSON.stringify(text)})); if (!button) return false; button.click(); return true; })()`,
  );
  if (!clicked) throw new Error(`No se encontró el botón: ${text}`);
}

let client;
try {
  const target = await waitForDebugTarget();
  client = new CdpClient(target.webSocketDebuggerUrl);
  await client.open();
  await client.send("Page.enable");
  await client.send("DOM.enable");
  await client.send("Network.enable");
  await client.send("Page.navigate", { url: "http://127.0.0.1:3000" });
  await waitFor(client, "document.readyState === 'complete'", "carga inicial");

  const responsive = {};
  for (const width of [390, 768, 1440]) {
    await setViewport(client, width);
    responsive[width] = await evaluate(
      client,
      `(() => { const sections = [...document.querySelectorAll("main > div section")]; const grid = sections[0]?.parentElement; return grid ? getComputedStyle(grid).gridTemplateColumns : null; })()`,
    );
    await screenshot(client, `initial_${width}.png`);
  }

  await setViewport(client, 390);
  await setFile(client, uncertainImage);
  await waitFor(client, `document.body.innerText.includes(${JSON.stringify(path.basename(uncertainImage))})`, "carga de imagen");
  await setFile(client, replacementImage);
  await waitFor(client, `document.body.innerText.includes(${JSON.stringify(path.basename(replacementImage))})`, "reemplazo de imagen");
  await setFile(client, uncertainImage);
  await clickButton(client, "Analizar hoja");
  await waitFor(client, "document.body.innerText.includes('Resultado incierto')", "resultado incierto");
  const uncertainState = await evaluate(
    client,
    `({ title: document.querySelector("#result-title")?.textContent, hasSecondary: document.body.innerText.includes("Categoría más probable:"), exposesInternalId: document.body.innerText.includes("coffee___") })`,
  );
  await screenshot(client, "uncertain_390.png");

  await clickButton(client, "Analizar otra fotografía");
  await setFile(client, acceptedImage);
  await clickButton(client, "Analizar hoja");
  await waitFor(client, "document.body.innerText.includes('Clasificación orientativa:')", "clasificación orientativa");
  const acceptedTitle = await evaluate(client, "document.querySelector('#result-title')?.textContent");
  await setViewport(client, 1440);
  await screenshot(client, "accepted_1440.png");

  await clickButton(client, "Analizar otra fotografía");
  await setFile(client, uncertainImage);
  await client.send("Network.setBlockedURLs", { urls: ["http://127.0.0.1:8000/*"] });
  await clickButton(client, "Analizar hoja");
  await waitFor(
    client,
    "document.body.innerText.includes('No se pudo conectar con CaféIA')",
    "error de conexión",
  );
  const connectionError = await evaluate(
    client,
    "document.body.innerText.includes('Comprueba que el backend esté encendido')",
  );
  await screenshot(client, "connection_error_1440.png");
  await client.send("Network.setBlockedURLs", { urls: [] });

  await evaluate(client, "document.querySelector('#leaf-photo')?.focus()");
  const keyboardLabel = await evaluate(
    client,
    `(() => { const element = document.activeElement; return { id: element?.id, ariaLabel: element?.getAttribute("aria-label") }; })()`,
  );

  const report = {
    url: "http://127.0.0.1:3000",
    responsiveGridColumns: responsive,
    replacementWorked: true,
    uncertainState,
    acceptedTitle,
    connectionError,
    keyboardFocus: keyboardLabel,
    screenshots: fs.readdirSync(outputDir).filter((name) => name.endsWith(".png")).sort(),
  };
  fs.writeFileSync(path.join(outputDir, "browser_checks.json"), `${JSON.stringify(report, null, 2)}\n`);
  console.log(JSON.stringify(report, null, 2));
} finally {
  client?.close();
  edge.kill();
}
