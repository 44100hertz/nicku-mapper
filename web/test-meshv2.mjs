// test-meshv2.mjs — validate the REAL loadMeshV2 from app.js in Node:
// loads the vendored three.module.js, extracts the function source, runs it
// against the mesh-v2 JSONs, and checks the built geometry (index bounds,
// counts, no NaN positions). No browser needed.
import * as THREE from "./vendor/three.module.js";
import { readFileSync } from "node:fs";

const collisionGroup = new THREE.Group();
const meshFacesGroup = new THREE.Group();

const app = readFileSync("web/app.js", "utf8");
function extractFn(name, prefix) {
  const start = app.indexOf(prefix);
  if (start < 0) throw new Error(`${name} not found`);
  let depth = 0, end = start;
  for (let i = start; i < app.length; i++) {
    if (app[i] === "{") depth++;
    else if (app[i] === "}") {
      depth--;
      if (depth === 0) { end = i + 1; break; }
    }
  }
  return app.slice(start, end);
}
const src = extractFn("loadMeshV2", "function loadMeshV2(data) {");
const _THREE = THREE;
const tog = { additive: { checked: true } };
const meshStyle = {
  tintLow: new THREE.Color(0x2e5f8a),
  tintHigh: new THREE.Color(0x8a6f2e),
  baseLight: new THREE.Color(0xe8ecf4),
};
const _tint = new THREE.Color();
const MESH_ADDITIVE_OPACITY = 0.5;
const loadMeshV2 = new Function(
  "THREE", "collisionGroup", "meshFacesGroup", "state",
  "cullBackfaces", "tog", "meshStyle", "_tint", "MESH_ADDITIVE_OPACITY",
  `return (${src});`
)(
  THREE, collisionGroup, meshFacesGroup,
  {},
  true, tog, meshStyle, _tint, MESH_ADDITIVE_OPACITY
);

// mirror app.js module scope: the sub-group lives inside collisionGroup
collisionGroup.add(meshFacesGroup);

let ok = true;
const files = [
  "web/collision/SpongeBobLevel1.json",
  "web/collision/dannyphantomlevel1.json",
  "web/collision/TimmyTurnerLevel1.json",
  "web/collision/JimmyNeutronLevel1_01.json",
  "web/collision/SpongeBobLevel2.json",
];
for (let fi = 0; fi < files.length; fi++) {
  if (fi > 0) {
    // simulate a level switch: clearView() clears collisionGroup, and the
    // fixed version re-parents the sub-groups afterwards (regression guard:
    // if they stay orphaned, the mesh renders nothing and toggles are dead)
    collisionGroup.clear();
    collisionGroup.add(meshFacesGroup);
  }
  const f = files[fi];
  const data = JSON.parse(readFileSync(f, "utf8"));
  const res = loadMeshV2(data);
  const faceMeshes = [];
  for (const g of [collisionGroup, meshFacesGroup]) {
    for (const c of g.children) {
      if (c.isMesh) faceMeshes.push(c);
    }
  }
  let tris = 0;
  for (const m of faceMeshes) {
    const idx = m.geometry.getIndex();
    if (idx) tris += idx.count / 3;
    const pos = m.geometry.attributes.position;
    for (let i = 0; i < pos.count * 3; i++) {
      if (!Number.isFinite(pos.array[i])) { console.log(`NaN in ${f}`); ok = false; }
    }
    // Gouraud shading relies on smooth per-vertex normals.
    const nrm = m.geometry.attributes.normal;
    if (!nrm) { console.log(`no normals in ${f}`); ok = false; }
    else if (nrm.count !== pos.count) { console.log(`normal count != pos in ${f}`); ok = false; }
  }
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
  const match = tris === res.faces;
  console.log(
    `${name} res={verts:${res.verts}, faces:${res.faces}}` +
    `  built: ${tris} tris  ${match ? "OK" : "MISMATCH!"}`
  );
  if (!match) ok = false;
  // parenting checks (the orphan bug: clearView() used to drop these)
  if (meshFacesGroup.parent !== collisionGroup) {
    console.log(`GROUPS ORPHANED after ${f}`);
    ok = false;
  }
  for (const g of [collisionGroup, meshFacesGroup]) g.children.length = 0;
}
console.log(ok ? "\nALL OK" : "\nFAILURES");
process.exit(ok ? 0 : 1);
