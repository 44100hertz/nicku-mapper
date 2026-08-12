// Screenshot a level mesh with the viewer; used to eyeball geometry decodes.
//   CHROME=/path/to/chromium node viewer/shot.mjs [LevelName] [out.png]
import { spawn } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const ROOT = new URL("..", import.meta.url).pathname;
const CHROME = process.env.CHROME || "/run/current-system/sw/bin/chromium";
const PORT = 8125;
const LEVEL = process.argv[2] || "JimmyNeutronLevel1_01";
const OUT = process.argv[3] || "/tmp/nickmapper-mesh.png";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const server = spawn("python3", ["-m", "http.server", String(PORT)], {
  cwd: ROOT, stdio: "ignore",
});
await sleep(600);

const profile = mkdtempSync(join(tmpdir(), "nm-shot-"));
const chrome = spawn(CHROME, [
  "--headless=new",
  "--password-store=basic", "--no-sandbox", "--disable-gpu",
  "--enable-unsafe-swiftshader", "--use-angle=swiftshader",
  `--user-data-dir=${profile}`, "--remote-debugging-port=0",
  "--window-size=1280,800", "about:blank",
], { stdio: ["ignore", "ignore", "pipe"] });

const wsUrl = await new Promise((resolve, reject) => {
  let buf = "";
  chrome.stderr.on("data", (d) => {
    buf += d.toString();
    const m = buf.match(/DevTools listening on (ws:\/\/\S+)/);
    if (m) resolve(m[1]);
  });
  setTimeout(() => reject(new Error("chrome did not start")), 15000);
});

let target;
for (let i = 0; i < 30 && !target; i++) {
  const port = new URL(wsUrl).port;
  const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  target = list.find((t) => t.type === "page");
  if (!target) await sleep(200);
}

const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((r) => (ws.onopen = r));
let msgId = 0;
const pending = new Map();
const events = {};
ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  if (msg.id) {
    const p = pending.get(msg.id);
    if (p) { pending.delete(msg.id); msg.error ? p.reject(new Error(msg.error.message)) : p.resolve(msg.result); }
  } else if (events[msg.method]) events[msg.method].forEach((fn) => fn(msg.params));
};
const send = (method, params = {}) => new Promise((resolve, reject) => {
  const id = ++msgId; pending.set(id, { resolve, reject });
  ws.send(JSON.stringify({ id, method, params }));
});
const on = (method, fn) => { (events[method] ||= []).push(fn); };
const evaluate = async (expr) => {
  const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true });
  if (r.exceptionDetails) throw new Error("page exception: " + (r.exceptionDetails.exception?.description || r.exceptionDetails.text));
  return r.result?.value;
};

await send("Runtime.enable");
await send("Page.enable");
const loaded = new Promise((r) => on("Page.loadEventFired", r));
await send("Page.navigate", { url: `http://127.0.0.1:${PORT}/viewer/#${LEVEL}` });
await loaded;

let status = "";
for (let i = 0; i < 150; i++) {
  status = await evaluate(`document.getElementById("status").textContent`);
  if (status.includes("entities")) break;
  if (status.startsWith("Failed")) break;
  await sleep(200);
}
console.log("status:", status);
// hide overlays so the screenshot is pure mesh geometry
await evaluate(`(() => {
  for (const id of ["tog-points", "tog-links", "tog-paths", "tog-grid"]) {
    const el = document.getElementById(id);
    if (el && el.checked) el.click();
  }
})()`);
await sleep(600);
await sleep(1200); // let the render settle

const info = await evaluate(`(() => {
  const el = document.querySelector("#viewport canvas");
  return {
    canvas: el ? el.width + "x" + el.height : "none",
    status: document.getElementById("status").textContent,
  };
})()`);
console.log("info:", JSON.stringify(info));

const shot = await send("Page.captureScreenshot", { format: "png" });
import { writeFileSync } from "node:fs";
writeFileSync(OUT, Buffer.from(shot.data, "base64"));
console.log("saved", OUT);

chrome.kill();
server.kill();
process.exit(0);
