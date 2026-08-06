// test-meshv2.mjs — validate the REAL loadMeshV2 from app.js in Node:
// loads the vendored three.module.js, extracts the function source, runs it
// against the mesh-v2 JSONs, and checks the built geometry (index bounds,
// counts, no NaN positions). No browser needed.
import * as THREE from "./vendor/three.module.js";
import { readFileSync } from "node:fs";

const collisionGroup = new THREE.Group();
const meshFacesGroup = new THREE.Group();
const meshLinesGroup = new THREE.Group();

const app = readFileSync("web/app.js", "utf8");
const start = app.indexOf("function loadMeshV2(data) {");
if (start < 0) throw new Error("loadMeshV2 not found");
// extract by brace counting
let depth = 0, end = start;
for (let i = start; i < app.length; i++) {
  if (app[i] === "{") depth++;
  else if (app[i] === "}") {
    depth--;
    if (depth === 0) { end = i + 1; break; }
  }
}
const src = app.slice(start, end);
const loadMeshV2 = new Function(
  "THREE", "collisionGroup", "meshLinesGroup", "meshFacesGroup", "state",
  "MESH_COLORS", "MESH_STRIP_GAP",
  `return (${src});`
)(
  THREE, collisionGroup, meshLinesGroup, meshFacesGroup,
  { collisionLines: [] },
  [[0.5, 0.5, 0.5]], 270
);

let ok = true;
const files = [
  "web/collision/SpongeBobLevel1.json",
  "web/collision/dannyphantomlevel1.json",
  "web/collision/TimmyTurnerLevel1.json",
  "web/collision/JimmyNeutronLevel1_01.json",
  "web/collision/SpongeBobLevel2.json",
];
for (const f of files) {
  const data = JSON.parse(readFileSync(f, "utf8"));
  const res = loadMeshV2(data);
  const faceMeshes = [], lineMeshes = [];
  for (const g of [collisionGroup, meshFacesGroup, meshLinesGroup]) {
    for (const c of g.children) {
      if (c.isMesh) faceMeshes.push(c);
      else if (c.isLineSegments) lineMeshes.push(c);
    }
  }
  let tris = 0, segs = 0;
  for (const m of faceMeshes) {
    const idx = m.geometry.getIndex();
    if (idx) tris += idx.count / 3;
    const pos = m.geometry.attributes.position;
    for (let i = 0; i < pos.count * 3; i++) {
      if (!Number.isFinite(pos.array[i])) { console.log(`NaN in ${f}`); ok = false; }
    }
  }
  for (const l of lineMeshes) segs += l.geometry.attributes.position.count / 2;
  // index bounds
  for (const m of faceMeshes) {
    const idx = m.geometry.getIndex();
    if (!idx) continue;
    const nPos = m.geometry.attributes.position.count;
    for (let i = 0; i < idx.count; i++) {
      if (idx.getX(i) >= nPos) { console.log(`OOB index in ${f}`); ok = false; }
    }
  }
  const name = f.split("/").pop().padEnd(38);
  const match = tris === res.faces && segs === res.segments;
  console.log(
    `${name} res={verts:${res.verts}, faces:${res.faces}, segments:${res.segments}}` +
    `  built: ${tris} tris, ${segs} segs  ${match ? "OK" : "MISMATCH!"}`
  );
  if (!match) ok = false;
  for (const g of [collisionGroup, meshFacesGroup, meshLinesGroup]) g.children.length = 0;
}
console.log(ok ? "\nALL OK" : "\nFAILURES");
process.exit(ok ? 0 : 1);
