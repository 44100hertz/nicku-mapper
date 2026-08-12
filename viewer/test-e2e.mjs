// End-to-end test for the 3D viewer using CDP over a raw WebSocket
// (Node >= 21 has a built-in WebSocket client).
//
//   CHROME=/path/to/chromium node web/test-e2e.mjs
//
// Launches a static server, loads the viewer, waits for a level, then:
//   1. checks entity/box/link stats via window.__nickmapper
//   2. clicks on a named entity near screen center and verifies the
//      info panel shows its name/type
//   3. captures a screenshot to /tmp/nickmapper-shot.png
import { spawn } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const ROOT = new URL("..", import.meta.url).pathname;
const CHROME =
  process.env.CHROME || "/run/current-system/sw/bin/chromium";
const PORT = 8124;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ---------- static server ----------
const server = spawn("python3", ["-m", "http.server", String(PORT)], {
  cwd: ROOT,
  stdio: "ignore",
});
await sleep(600);

// ---------- chrome ----------
const profile = mkdtempSync(join(tmpdir(), "nm-cdp-"));
const chrome = spawn(CHROME, [
  "--headless=new",
  "--password-store=basic",
  "--no-sandbox",
  "--disable-gpu",
  "--enable-unsafe-swiftshader",
  "--use-angle=swiftshader",
  `--user-data-dir=${profile}`,
  "--remote-debugging-port=0",
  "--window-size=1280,800",
  "about:blank",
], { stdio: ["ignore", "ignore", "pipe"] });

const wsUrl = await new Promise((resolve, reject) => {
  let buf = "";
  chrome.stderr.on("data", (d) => {
    buf += d.toString();
    const m = buf.match(/DevTools listening on (ws:\/\/\S+)/);
    if (m) resolve(m[1]);
  });
  setTimeout(() => reject(new Error("chrome did not start: " + buf.slice(0, 500))), 15000);
});

// find the page target
let target;
for (let i = 0; i < 30 && !target; i++) {
  const port = new URL(wsUrl).port;
  const res = await fetch(`http://127.0.0.1:${port}/json/list`);
  const list = await res.json();
  target = list.find((t) => t.type === "page");
  if (!target) await sleep(200);
}
if (!target) throw new Error("no page target");

// ---------- CDP session ----------
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((r) => (ws.onopen = r));

let msgId = 0;
const pending = new Map();
const events = {};
ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  if (msg.id) {
    const p = pending.get(msg.id);
    if (p) {
      pending.delete(msg.id);
      msg.error ? p.reject(new Error(msg.error.message)) : p.resolve(msg.result);
    }
  } else if (events[msg.method]) {
    events[msg.method].forEach((fn) => fn(msg.params));
  }
};
const send = (method, params = {}) =>
  new Promise((resolve, reject) => {
    const id = ++msgId;
    pending.set(id, { resolve, reject });
    ws.send(JSON.stringify({ id, method, params }));
  });
const on = (method, fn) => {
  (events[method] ||= []).push(fn);
};
const evaluate = async (expr) => {
  const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true });
  if (r.exceptionDetails) throw new Error("page exception: " + JSON.stringify(r.exceptionDetails.exception?.description || r.exceptionDetails.text));
  return r.result?.value;
};

await send("Runtime.enable");
await send("Page.enable");
const loaded = new Promise((r) => on("Page.loadEventFired", r));
await send("Page.navigate", { url: `http://127.0.0.1:${PORT}/web/#SpongeBobLevel2` });
await loaded;

// wait for level to finish loading
let status = "";
for (let i = 0; i < 100; i++) {
  status = await evaluate(`document.getElementById("status").textContent`);
  if (status.includes("entities")) break;
  if (status.startsWith("Failed")) throw new Error("load failed: " + status);
  await sleep(200);
}

console.log("status:", status);

// stats
const stats = await evaluate(`({
  entities: window.__nickmapper.entities(),
  boxes: window.__nickmapper.boxes(),
  types: window.__nickmapper.types(),
  labels: window.__nickmapper.labels(),
  links: window.__nickmapper.links(),
  legendRows: document.querySelectorAll(".legend-row").length,
})`);
console.log("stats:", JSON.stringify(stats));

// Pick the closest-to-center entity whose projected point actually raycasts
// to something, then click it. Retries ±2px because CDP rounds click
// coordinates (tiny point entities can otherwise be missed).
async function clickEntity() {
  const target = await evaluate(`(() => {
    const canvas = document.querySelector("#viewport canvas");
    const cx = canvas.clientWidth / 2, cy = canvas.clientHeight / 2;
    const cands = [];
    for (let i = 0; i < window.__nickmapper.entities(); i++) {
      const p = window.__nickmapper.project(i);
      if (!p || !p.visible) continue;
      cands.push({ i, x: p.x, y: p.y, d: (p.x - cx) ** 2 + (p.y - cy) ** 2 });
    }
    cands.sort((a, b) => a.d - b.d);
    for (const c of cands) {
      const hit = window.__nickmapper.pickAt(c.x, c.y);
      if (hit) return c;
    }
    return null;
  })()`);
  if (!target) throw new Error("no clickable entity on screen");
  console.log("clicking entity at", target.x.toFixed(0), target.y.toFixed(0));
  for (let ox = -2; ox <= 2; ox++) {
    for (let oy = -2; oy <= 2; oy++) {
      await send("Input.dispatchMouseEvent", { type: "mousePressed", x: target.x + ox, y: target.y + oy, button: "left", clickCount: 1 });
      await send("Input.dispatchMouseEvent", { type: "mouseReleased", x: target.x + ox, y: target.y + oy, button: "left", clickCount: 1 });
      await sleep(120);
      const title = await evaluate(`document.getElementById("info-title").textContent`);
      if (!title.includes("Nothing")) return target;
    }
  }
  throw new Error("click did not select anything");
}

// pick a visible entity near screen center, click it, check info panel
await clickEntity();
const info = await evaluate(`({
  title: document.getElementById("info-title").textContent,
  selectedName: window.__nickmapper.selectName(),
  selectedType: window.__nickmapper.selectType(),
  infoText: document.getElementById("info-body").innerText,
  markerVisible: window.__nickmapper.markerVisible(),
  markerParented: window.__nickmapper.markerParented(),
})`);
console.log("selection:", JSON.stringify(info));
if (!info.title) throw new Error("info panel did not populate");
if (!info.markerVisible || !info.markerParented) throw new Error("selection marker not rendered/parented");

// switch level, click again — marker must survive the viewGroup clear
await evaluate(`(() => {
  const sel = document.getElementById("level-select");
  sel.value = "TimmyTurnerLevel1";
  sel.dispatchEvent(new Event("change"));
})()`);
for (let i = 0; i < 100; i++) {
  const s = await evaluate(`document.getElementById("status").textContent`);
  if (s.includes("TimmyTurnerLevel1 —")) break;
  await sleep(200);
}
const click2 = await clickEntity();
const after2 = await evaluate(`({ t: document.getElementById("info-title").textContent, mv: window.__nickmapper.markerVisible(), mp: window.__nickmapper.markerParented() })`);
console.log("after level switch:", JSON.stringify(after2));
if (!after2.mv || !after2.mp) throw new Error("selection marker lost after level switch");

// toggle a type off via legend checkbox and confirm no errors, then restore
await evaluate(`(() => {
  const cb = document.querySelector(".legend-row input");
  cb.checked = false;
  cb.dispatchEvent(new Event("change"));
})()`);
await sleep(200);
await evaluate(`(() => {
  const cb = document.querySelector(".legend-row input");
  cb.checked = true;
  cb.dispatchEvent(new Event("change"));
})()`);
await sleep(200);

// Boxes always render as edge outlines; the solid mesh is only an
// invisible pick proxy.
const wf = await evaluate(`({
  normalEdges: window.__nickmapper.edgesVisible(),
  volumeEdges: window.__nickmapper.volumeEdgesVisible(),
  pickable: window.__nickmapper.pickAt(${click2.x}, ${click2.y}) !== null,
})`);
console.log("edge defaults:", JSON.stringify(wf));
if (wf.normalEdges !== true || wf.volumeEdges !== false) throw new Error("edge defaults wrong (volume should be hidden)");
if (!wf.pickable) throw new Error("boxes not pickable in outline mode");

// Box volumes use the engine AABB convention (AABBDimensions = half-extents,
// Position.y = top of the box): rendered center = (x, -y+h, -z), size = 2×dims.
const boxConv = await evaluate(`(() => {
  const N = window.__nickmapper;
  for (let i = 0; i < N.entities(); i++) {
    const b = N.boxAt(i);
    if (!b) continue;
    const [x, y, z, w, h, d] = b.raw;
    return {
      center: b.center.map((v) => v.toFixed(3)),
      size: b.size.map((v) => v.toFixed(3)),
      expCenter: [x, -y + h, -z].map((v) => v.toFixed(3)),
      expSize: [w * 2, h * 2, d * 2].map((v) => v.toFixed(3)),
    };
  }
  return null;
})()`);
console.log("box convention:", JSON.stringify(boxConv));
if (
  !boxConv ||
  JSON.stringify(boxConv.center) !== JSON.stringify(boxConv.expCenter) ||
  JSON.stringify(boxConv.size) !== JSON.stringify(boxConv.expSize)
)
  throw new Error("box volume does not match engine AABB convention: " + JSON.stringify(boxConv));

// Labels: only ADanny and APropTriggerEndLevel, unconditionally
const labelTypes = await evaluate(`window.__nickmapper.labelTypes()`);
console.log("label types:", JSON.stringify(labelTypes));
if (labelTypes.some((t) => !["ADanny", "APropTriggerEndLevel"].includes(t)))
  throw new Error("unexpected label types: " + labelTypes);

// AMusicTrigger + AWorldSectionVolume hidden by default: legend checkboxes
// unchecked, meshes invisible, and hidden boxes are NOT clickable
const vis = await evaluate(`(() => {
  const legend = [...document.querySelectorAll(".legend-row")].map((r) => ({
    name: r.querySelector(".legend-name").textContent,
    checked: r.querySelector("input").checked,
  }));
  const wrong = legend.filter((r) =>
    ["AMusicTrigger", "AWorldSectionVolume"].includes(r.name) ? r.checked : !r.checked
  );
  let probe = null;
  for (let i = 0; i < window.__nickmapper.entities(); i++) {
    if (window.__nickmapper.entityType(i) !== "AWorldSectionVolume") continue;
    const p = window.__nickmapper.project(i);
    if (!p || !p.visible) continue;
    const hit = window.__nickmapper.pickAt(p.x, p.y);
    probe = hit ? hit.type : null;
    break;
  }
  return { wrong, probe };
})()`);
console.log("hidden defaults:", JSON.stringify(vis));
if (vis.wrong.length) throw new Error("legend visibility wrong: " + JSON.stringify(vis.wrong));
if (vis.probe === "AWorldSectionVolume") throw new Error("hidden box is still clickable");

// Jump to Danny: selects ADanny and moves the camera to it
await evaluate(`document.getElementById("btn-danny").click()`);
await sleep(300);
const dj = await evaluate(`({
  type: window.__nickmapper.selectType(),
  dist: window.__nickmapper.camDist(),
  marker: window.__nickmapper.markerVisible(),
})`);
console.log("jump to danny:", JSON.stringify(dj));
if (dj.type !== "ADanny") throw new Error("Jump to Danny did not select ADanny");
if (dj.dist > 100) throw new Error("camera did not fly to Danny");

console.log("type toggle OK, page title:", await evaluate("document.title"));

// Collision walls: loaded, visible, and toggleable (also must survive level switches)
const coll = await evaluate(`({
  visible: window.__nickmapper.collisionVisible(),
  parented: window.__nickmapper.collisionParented(),
  status: document.getElementById("status").textContent,
})`);
console.log("collision:", JSON.stringify(coll));
if (coll.visible !== true || coll.parented !== true) throw new Error("collision not rendered/parented");
if (!/mesh verts/.test(coll.status)) throw new Error("collision not loaded: " + coll.status);
await evaluate(`(() => {
  const cb = document.getElementById("tog-collision");
  cb.checked = false;
  cb.dispatchEvent(new Event("change"));
})()`);
await sleep(200);
if ((await evaluate(`window.__nickmapper.collisionVisible()`)) !== false)
  throw new Error("collision toggle failed");
await evaluate(`(() => {
  const cb = document.getElementById("tog-collision");
  cb.checked = true;
  cb.dispatchEvent(new Event("change"));
})()`);
await sleep(200);

// Mesh faces: solid strip faces, on by default; lines overlay off by default
const faces = await evaluate(`({
  visible: window.__nickmapper.meshFacesVisible(),
  cb: document.getElementById("tog-faces").checked,
})`);
console.log("faces:", JSON.stringify(faces));
if (faces.cb !== true) throw new Error("faces toggle should default checked");
if (faces.visible !== true) throw new Error("faces not visible by default");
await evaluate(`(() => {
  const cb = document.getElementById("tog-faces");
  cb.checked = false;
  cb.dispatchEvent(new Event("change"));
})()`);
await sleep(200);
if ((await evaluate(`window.__nickmapper.meshFacesVisible()`)) !== false)
  throw new Error("faces toggle failed");
await evaluate(`(() => {
  const cb = document.getElementById("tog-faces");
  cb.checked = true;
  cb.dispatchEvent(new Event("change"));
})()`);
await sleep(200);

// OrbitControls: left-drag should rotate the camera
const qBefore = await evaluate(`window.__nickmapper.cameraQuat()`);
await send("Input.dispatchMouseEvent", { type: "mousePressed", x: 500, y: 300, button: "left", clickCount: 1 });
await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: 620, y: 330, button: "left", buttons: 1 });
await send("Input.dispatchMouseEvent", { type: "mouseReleased", x: 620, y: 330, button: "left", clickCount: 1 });
await sleep(300);
const qAfter = await evaluate(`window.__nickmapper.cameraQuat()`);
if (JSON.stringify(qBefore) === JSON.stringify(qAfter)) throw new Error("left-drag did not rotate camera");
console.log("orbit rotate OK");

// Wheel should zoom the camera toward the target
const dBefore = await evaluate(`window.__nickmapper.camDist()`);
await send("Input.dispatchMouseEvent", { type: "mouseWheel", x: 500, y: 300, deltaX: 0, deltaY: -300 });
await sleep(300);
const dAfter = await evaluate(`window.__nickmapper.camDist()`);
if (!(dAfter < dBefore)) throw new Error("wheel did not zoom in");
console.log("orbit zoom OK:", dBefore.toFixed(1), "->", dAfter.toFixed(1));

// screenshot
const shot = await send("Page.captureScreenshot", { format: "png" });
writeFileSync("/tmp/nickmapper-shot.png", Buffer.from(shot.data, "base64"));
console.log("screenshot: /tmp/nickmapper-shot.png");

chrome.kill();
server.kill();
process.exit(0);
