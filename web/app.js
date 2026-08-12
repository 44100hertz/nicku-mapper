import * as THREE from "three";
import { OrbitControls } from "three/addons/OrbitControls.js";
import { CSS2DRenderer, CSS2DObject } from "three/addons/CSS2DRenderer.js";
import { parse } from "./parser.js";
import { STYLES, getStyle } from "./styles.js";
import { LEVELS } from "./levels.js";

// Surface any module-level error in the title so headless tests catch it.
window.addEventListener("error", (e) => { document.title = `ERR: ${e.message}`; });
window.addEventListener("unhandledrejection", (e) => {
  document.title = `ERR: ${e.reason?.message || e.reason}`;
});

// ---------------------------------------------------------------------------
// DOM
// ---------------------------------------------------------------------------
const viewport = document.getElementById("viewport");
const statusEl = document.getElementById("status");
const levelSelect = document.getElementById("level-select");
const legendEl = document.getElementById("legend-list");
const legendCountEl = document.getElementById("legend-count");
const infoEl = document.getElementById("info-body");
const infoTitleEl = document.getElementById("info-title");

const $ = (id) => document.getElementById(id);
const tog = {
  points: $("tog-points"),
  links: $("tog-links"),
  paths: $("tog-paths"),
  collision: $("tog-collision"),
  faces: $("tog-faces"),
  cull: $("tog-cull"),
  grid: $("tog-grid"),
  additive: $("tog-additive"),
  collmesh: $("tog-collmesh"),
  collsolid: $("tog-collsolid"),
};

// ---------------------------------------------------------------------------
// Mesh face style (uniform, Gouraud-shaded, Y-tinted)
// ---------------------------------------------------------------------------
// All faces share one base style: the color is tinted a bit by world height
// (cool below, warm above), then Gouraud-lit by the scene lights so each
// face reads with angle-based shading. The only knob is translucent vs
// solid: translucent uses ADDITIVE blending at 25% opacity (half-bright,
// so the X-ray glow doesn't wash out details beneath), which sidesteps
// the classic transparent-sorting artifacts (overlaps get brighter instead
// of z-fighting); solid is a normal opaque surface.
const meshStyle = {
  // Height tint ramp (subtle shift around the base hue, near-constant light)
  tintLow: new THREE.Color(0x2e5f8a), // cool blue, low areas
  tintHigh: new THREE.Color(0x8a6f2e), // warm amber, high areas
  baseLight: new THREE.Color(0xe8ecf4), // material color (vertex colors modulate)
};

// Additive blend factor (opacity of the translucent X-ray shell). Kept at
// half-bright so the overlap glow doesn't wash out the details beneath it.
const MESH_ADDITIVE_OPACITY = 0.25;

// ---------------------------------------------------------------------------
// Three.js scene
// ---------------------------------------------------------------------------
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x161a22);

const camera = new THREE.PerspectiveCamera(
  60,
  viewport.clientWidth / viewport.clientHeight,
  0.01,
  100000
);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(viewport.clientWidth, viewport.clientHeight);
renderer.domElement.style.cursor = "grab";
viewport.appendChild(renderer.domElement);

const labelRenderer = new CSS2DRenderer();
labelRenderer.setSize(viewport.clientWidth, viewport.clientHeight);
labelRenderer.domElement.style.position = "absolute";
labelRenderer.domElement.style.top = "0";
labelRenderer.domElement.style.left = "0";
labelRenderer.domElement.style.pointerEvents = "none";
viewport.appendChild(labelRenderer.domElement);

// Lights
scene.add(new THREE.HemisphereLight(0xbfd4ff, 0x22252c, 1.1));
const dir = new THREE.DirectionalLight(0xffffff, 1.4);
dir.position.set(500, 1000, 300);
scene.add(dir);

// Standard orbit controls: left-drag rotate, right-drag pan, wheel zoom
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.zoomSpeed = 1.5; // wheel zoom stays snappy at close range
controls.zoomToCursor = true; // zoom toward the mouse, not screen center

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
const viewGroup = new THREE.Group();
scene.add(viewGroup);

const state = {
  entities: [],
  byName: new Map(),
  typeMeshes: new Map(), // type -> { boxes: InstancedMesh|null, points: InstancedMesh|null }
  boxInstances: [], // { e, mesh, index } for the y-bottom toggle
  links: [],
  pathLine: null,
  labelObjects: [],
  bounds: null,
  hiddenTypes: new Set(),
  selection: null,
  spawn: null,
  missingLinks: 0,
};

// Collision / mesh geometry (from trb_mesh.py -> web/collision/<level>.json).
// Parented to scene so viewGroup.clear() can't orphan it across level loads.
const collisionGroup = new THREE.Group();
scene.add(collisionGroup);
const selGroup = new THREE.Group();
selGroup.visible = false;
scene.add(selGroup);

// Marker group for user-placed collision markers (press P to place)
const markerGroup = new THREE.Group();
scene.add(markerGroup);
state.markers = [];

// Crosshair preview at camera target (shows where P will place a marker)
const crosshair = new THREE.LineSegments(
  new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(-0.5, 0, 0), new THREE.Vector3(0.5, 0, 0),
    new THREE.Vector3(0, -0.5, 0), new THREE.Vector3(0, 0.5, 0),
    new THREE.Vector3(0, 0, -0.5), new THREE.Vector3(0, 0, 0.5),
  ]),
  new THREE.LineBasicMaterial({ color: 0xff4444, transparent: true, opacity: 0.7, depthTest: false })
);
scene.add(crosshair);

function placeMarker(pos, color = 0xff4444) {
  const sphere = new THREE.Mesh(
    new THREE.SphereGeometry(0.4, 16, 12),
    new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.85, depthTest: true })
  );
  sphere.position.copy(pos);
  markerGroup.add(sphere);
  const div = document.createElement("div");
  div.className = "marker-label";
  div.style.cssText = "color:#ff6666;font-size:11px;font-weight:bold;text-shadow:0 0 4px #000;";
  div.textContent = `${state.markers.length}: ${pos.x.toFixed(1)}, ${pos.y.toFixed(1)}, ${pos.z.toFixed(1)}`;
  const label = new CSS2DObject(div);
  label.position.copy(pos).add(new THREE.Vector3(0, 0.8, 0));
  markerGroup.add(label);
  state.markers.push({ pos: pos.clone(), sphere, label });
  statusEl.textContent = `Marker ${state.markers.length} at (${pos.x.toFixed(1)}, ${pos.y.toFixed(1)}, ${pos.z.toFixed(1)})`;
  console.log(`MARKER ${state.markers.length}: (${pos.x.toFixed(3)}, ${pos.y.toFixed(3)}, ${pos.z.toFixed(3)})`);
}

const selBox = new THREE.LineSegments(
  new THREE.EdgesGeometry(new THREE.BoxGeometry(1, 1, 1)),
  new THREE.LineBasicMaterial({ color: 0xffd400 })
);
selGroup.add(selBox);

const selRing = new THREE.Mesh(
  new THREE.RingGeometry(0.85, 1.15, 40),
  new THREE.MeshBasicMaterial({
    color: 0xffd400,
    side: THREE.DoubleSide,
    transparent: true,
    opacity: 0.85,
    depthWrite: false,
  })
);
selRing.rotation.x = -Math.PI / 2;
selGroup.add(selRing);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function quatFor(e) {
  const o = e.orientation;
  if (o) return new THREE.Quaternion(o.x, o.y, o.z, o.w).normalize();
  return new THREE.Quaternion();
}

function pointRadius(style) {
  const s = style.size || 0.35;
  return Math.max(0.1, Math.min(s * 0.35, 1.5));
}

function rgbStr(col) {
  const c = col.map((v) => Math.round(Math.min(Math.max(v, 0), 1) * 255));
  return `rgb(${c[0]}, ${c[1]}, ${c[2]})`;
}

// Game coordinates: +y points DOWN, and the level is mirrored along z.
// Flipping both (a 180° rotation about the x-axis of the raw data) makes
// the viewer match the in-game layout.
const WY = (y) => -y;
const WZ = (z) => -z;

// Volume/trigger types used to get special treatment; now every box
// renders as edge outlines (solid boxes were dropped entirely).

// These two entity types always get a name label; nothing else does.
const LABEL_TYPES = new Set(["ADanny", "APropTriggerEndLevel"]);

// Hidden by default (legend checkbox starts unchecked).
const DEFAULT_HIDDEN_TYPES = new Set(["AMusicTrigger", "AWorldSectionVolume"]);

// Unit cube's 12 edges (24 vertices) — transformed per box instance.
const unitEdgeVerts = new THREE.EdgesGeometry(new THREE.BoxGeometry(1, 1, 1))
  .attributes.position.array;

// World-space Y for a box center (Position.y is the center of the box).
const boxY = (e) => WY(e.y);

const boxMatrix = (e) =>
  new THREE.Matrix4().compose(
    new THREE.Vector3(e.x, boxY(e), WZ(e.z)),
    quatFor(e),
    new THREE.Vector3(e.w, e.h, e.d)
  );

// ---------------------------------------------------------------------------
// Scene building
// ---------------------------------------------------------------------------
function clearView() {
  const dispose = (o) => {
    if (o.geometry) o.geometry.dispose();
    if (o.material) {
      if (Array.isArray(o.material)) o.material.forEach((m) => m.dispose());
      else o.material.dispose();
    }
    if (o.isCSS2DObject && o.element && o.element.parentNode) {
      o.element.parentNode.removeChild(o.element);
    }
  };
  viewGroup.traverse(dispose);
  collisionGroup.traverse(dispose);
  viewGroup.clear();
  collisionGroup.clear();
  markerGroup.traverse(dispose);
  markerGroup.clear();
  // clear() removed the sub-group; re-parent so loadMeshV2 can fill it.
  // The sub-group's OLD children (the previous level's meshes) survive
  // collisionGroup.clear() — drop them here, or the previous level's mesh
  // keeps rendering under the new level's entities (and shows through for
  // levels whose collision JSON 404s). Their geometries were disposed by
  // the traverse above.
  collisionGroup.add(meshFacesGroup);
  meshFacesGroup.clear();
  collLineGroup.traverse(dispose);
  collLineGroup.clear();
  collSolidGroup.traverse(dispose);
  collSolidGroup.clear();
  selGroup.visible = false;
  state.entities = [];
  state.byName.clear();
  state.typeMeshes.clear();
  state.boxInstances = [];
  state.links = [];
  state.pathLine = null;
  state.labelObjects = [];
  state.hiddenTypes.clear();
  state.selection = null;
  state.spawn = null;
  state.missingLinks = 0;
  state.markers = [];
  infoTitleEl.textContent = "Nothing selected";
  infoEl.innerHTML = "<div class='hint'>Click an entity to inspect it.</div>";
}

function computeBounds(entities) {
  let min = new THREE.Vector3(Infinity, Infinity, Infinity);
  let max = new THREE.Vector3(-Infinity, -Infinity, -Infinity);
  for (const e of entities) {
    const ex = e.w ? e.w / 2 : 0;
    const ey = e.h ? e.h / 2 : 0;
    const ez = e.d ? e.d / 2 : 0;
    const yw = WY(e.y);
    const zw = WZ(e.z);
    min.min(new THREE.Vector3(e.x - ex, yw - ey, zw - ez));
    max.max(new THREE.Vector3(e.x + ex, yw + ey, zw + ez));
  }
  if (min.x === Infinity) {
    min.set(-10, -10, -10);
    max.set(10, 10, 10);
  }
  const center = min.clone().add(max).multiplyScalar(0.5);
  const size = max.clone().sub(min);
  return { min, max, center, size, radius: size.length() / 2 };
}

function addGrid() {
  const r = state.bounds.radius;
  const grid = new THREE.GridHelper(r * 2.2, 22, 0x4a5264, 0x2c323e);
  grid.position.y = state.bounds.min.y - Math.max(r / 25, 1);
  viewGroup.add(grid);

  const axes = new THREE.AxesHelper(Math.max(r / 6, 5));
  axes.position.set(state.bounds.center.x, state.bounds.min.y, state.bounds.center.z);
  viewGroup.add(axes);
}

function addEntities(entities) {
  const byType = new Map();
  for (const e of entities) {
    if (!byType.has(e.type)) byType.set(e.type, []);
    byType.get(e.type).push(e);
  }

  for (const [type, list] of byType) {
    const style = getStyle(type);
    const color = new THREE.Color(...style.col);
    const boxes = list.filter((e) => e.w && e.h && e.d);
    const points = list.filter((e) => !(e.w && e.h && e.d));

    let boxMesh = null;
    let pointMesh = null;
    let boxEdge = null;

    if (boxes.length) {
      boxMesh = new THREE.InstancedMesh(
        new THREE.BoxGeometry(1, 1, 1),
        // Invisible pick proxy: raycasts still work, but only the edge
        // outlines are ever rendered.
        new THREE.MeshLambertMaterial({ color, transparent: true, opacity: 0, depthWrite: false }),
        boxes.length
      );
      // Edge-only outlines: each box's 12 edges (no face triangles).
      const edgePos = new Float32Array(boxes.length * unitEdgeVerts.length);
      const edgeGeo = new THREE.BufferGeometry();
      edgeGeo.setAttribute("position", new THREE.BufferAttribute(edgePos, 3));
      const tmpV = new THREE.Vector3();
      boxes.forEach((e, i) => {
        const m = boxMatrix(e);
        boxMesh.setMatrixAt(i, m);
        const base = i * unitEdgeVerts.length;
        for (let k = 0; k < unitEdgeVerts.length; k += 3) {
          tmpV.set(unitEdgeVerts[k], unitEdgeVerts[k + 1], unitEdgeVerts[k + 2]).applyMatrix4(m);
          const o = base + k;
          edgePos[o] = tmpV.x;
          edgePos[o + 1] = tmpV.y;
          edgePos[o + 2] = tmpV.z;
        }
        state.boxInstances.push({ e, mesh: boxMesh, index: i, edgePos, edgeBase: base, edgeGeo });
      });
      boxMesh.instanceMatrix.needsUpdate = true;
      boxMesh.userData.entities = boxes;
      viewGroup.add(boxMesh);

      boxEdge = new THREE.LineSegments(
        edgeGeo,
        new THREE.LineBasicMaterial({ color })
      );
      viewGroup.add(boxEdge);
    }

    if (points.length) {
      const r = pointRadius(style);
      pointMesh = new THREE.InstancedMesh(
        new THREE.IcosahedronGeometry(1, 0),
        new THREE.MeshBasicMaterial({ color }),
        points.length
      );
      points.forEach((e, i) => {
        const m = new THREE.Matrix4();
        m.compose(
          new THREE.Vector3(e.x, WY(e.y), WZ(e.z)),
          new THREE.Quaternion(),
          new THREE.Vector3(r, r, r)
        );
        pointMesh.setMatrixAt(i, m);
      });
      pointMesh.instanceMatrix.needsUpdate = true;
      pointMesh.userData.entities = points;
      viewGroup.add(pointMesh);
    }

    state.typeMeshes.set(type, {
      boxes: boxMesh,
      points: pointMesh,
      edges: boxEdge,
    });
  }
}

const LINK_KINDS = [
  { key: "target", color: [1, 0.8, 0.5], label: "targets" },
  { key: "parent", color: [0.8, 0.8, 0.8], label: "parents" },
  { key: "next_waypoint", color: [0.0, 0.5, 0.0], label: "waypoints" },
  { key: "respawn_points", color: [0.5, 0.5, 0.5], label: "respawn groups" },
];

function addLinks(entities) {
  let drawn = 0;
  for (const { key, color } of LINK_KINDS) {
    const pos = [];
    for (const e of entities) {
      const v = e[key];
      if (v === undefined || v === null) continue;
      const names = Array.isArray(v) ? v : [v];
      for (const name of names) {
        const t = state.byName.get(name);
        if (t) {
          pos.push(e.x, WY(e.y), WZ(e.z), t.x, WY(t.y), WZ(t.z));
          drawn++;
        } else {
          state.missingLinks++;
        }
      }
    }
    if (pos.length) {
      const geo = new THREE.BufferGeometry();
      geo.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
      const line = new THREE.LineSegments(
        geo,
        new THREE.LineBasicMaterial({ color: new THREE.Color(...color), transparent: true, opacity: 0.85 })
      );
      viewGroup.add(line);
      state.links.push(line);
    }
  }

  // Single RespawnPoint is a position, not a name
  const rp = [];
  for (const e of entities) {
    if (e.respawn_point) {
      rp.push(e.x, WY(e.y), WZ(e.z), e.respawn_point.x, WY(e.respawn_point.y), WZ(e.respawn_point.z));
      drawn++;
    }
  }
  if (rp.length) {
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.Float32BufferAttribute(rp, 3));
    const line = new THREE.LineSegments(
      geo,
      new THREE.LineBasicMaterial({ color: new THREE.Color(0.5, 0.5, 0.3), transparent: true, opacity: 0.85 })
    );
    viewGroup.add(line);
    state.links.push(line);
  }
  return drawn;
}

function addPaths(entities) {
  const pos = [];
  const col = [];
  for (const e of entities) {
    const p = e.path;
    if (!p || p.length < 7) continue;
    for (let i = 0; i + 6 < p.length; i += 7) {
      const nx = p[i + 7];
      if (nx === undefined) break;
      pos.push(p[i], WY(p[i + 1]), WZ(p[i + 2]), nx, WY(p[i + 8]), WZ(p[i + 9]));
      const r = p[i + 4] ?? 0;
      const g = p[i + 5] ?? 0;
      const b = p[i + 6] ?? 0;
      col.push(r, g, b, r, g, b);
    }
  }
  if (!pos.length) return 0;
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  geo.setAttribute("color", new THREE.Float32BufferAttribute(col, 3));
  state.pathLine = new THREE.LineSegments(
    geo,
    new THREE.LineBasicMaterial({ vertexColors: true })
  );
  viewGroup.add(state.pathLine);
  return pos.length / 6;
}

function addLabels(entities) {
  for (const e of entities) {
    if (!LABEL_TYPES.has(e.type)) continue;
    const div = document.createElement("div");
    div.className = "entity-label";
    div.style.borderLeftColor = rgbStr(getStyle(e.type).col);
    div.textContent = e.name || e.type;
    const obj = new CSS2DObject(div);
    obj.position.set(e.x, WY(e.y), WZ(e.z));
    obj.userData.type = e.type;
    viewGroup.add(obj);
    state.labelObjects.push(obj);
  }
}

function frameCamera() {
  const b = state.bounds;
  const r = Math.max(b.radius, 1);
  camera.position.set(b.center.x + r * 1.6, b.center.y + r * 1.2, b.center.z + r * 1.6);
  camera.near = Math.max(0.01, r / 2000);
  camera.far = Math.max(100, r * 200);
  camera.updateProjectionMatrix();
  controls.target.copy(b.center);
  controls.minDistance = Math.max(0.05, r / 100);
  controls.maxDistance = Math.max(100, r * 60);
  controls.update();
}

// ---------------------------------------------------------------------------
// Loading
// ---------------------------------------------------------------------------
async function loadLevel(dir) {
  statusEl.textContent = `Loading ${dir}…`;
  try {
    const res = await fetch(`../levels/${dir}/Entities.ini`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const text = await res.text();
    const entities = parse(text);

    clearView();
    state.entities = entities;
    for (const e of entities) {
      if (e.name) state.byName.set(e.name, e);
    }
    state.bounds = computeBounds(entities);
    state.spawn = entities.find((e) => e.type === "ADanny") || null;
    for (const t of DEFAULT_HIDDEN_TYPES) state.hiddenTypes.add(t);

    addGrid();
    addEntities(entities);
    const linksDrawn = addLinks(entities);
    const pathSegs = addPaths(entities);
    addLabels(entities);
    const coll = (await loadCollision(dir)) || null;
    const collL = (await loadCollLines(dir)) || null;
    const collTxt =
      collL && collL.meshes
        ? ` · ${collL.meshes} coll meshes · ${collL.lines} edges`
        : "";
    const meshTxt =
      coll && coll.verts
        ? ` · ${coll.verts} mesh verts · ${coll.faces} faces`
        : "";
    frameCamera();
    buildLegend();
    applyToggles();

    const boxes = state.boxInstances.length;
    const points = entities.length - boxes;
    statusEl.textContent =
      `${dir} — ${entities.length} entities · ${boxes} boxes · ${points} points · ` +
      `${linksDrawn} links · ${pathSegs} path segments${collTxt}${meshTxt} · ` +
      `${state.missingLinks} unresolved names · ` +
      `bounds ${state.bounds.size.x.toFixed(0)}×${state.bounds.size.y.toFixed(0)}×${state.bounds.size.z.toFixed(0)}`;
  } catch (err) {
    statusEl.textContent = `Failed to load ${dir}: ${err.message} (serve from the repo root, e.g. python3 -m http.server)`;
  }
}

// ---------------------------------------------------------------------------
// Type legend / filter
// ---------------------------------------------------------------------------
function buildLegend() {
  legendEl.innerHTML = "";
  const entries = [...state.typeMeshes.entries()].map(([type, m]) => {
    const n = (m.boxes?.count ?? 0) + (m.points?.count ?? 0);
    return { type, n, style: getStyle(type) };
  });
  entries.sort((a, b) => b.n - a.n);
  legendCountEl.textContent = `${entries.length} entity types`;

  for (const { type, n, style } of entries) {
    const row = document.createElement("label");
    row.className = "legend-row";

    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = !state.hiddenTypes.has(type);
    cb.addEventListener("change", () => {
      const meshes = state.typeMeshes.get(type);
      if (meshes) {
        if (cb.checked) state.hiddenTypes.delete(type);
        else state.hiddenTypes.add(type);
        applyToggles();
      }
    });

    const dot = document.createElement("span");
    dot.className = "legend-dot";
    dot.style.background = rgbStr(style.col);

    const name = document.createElement("span");
    name.className = "legend-name";
    name.textContent = type;

    const count = document.createElement("span");
    count.className = "legend-count";
    count.textContent = n;

    row.append(cb, dot, name, count);
    legendEl.appendChild(row);
  }
}

$("btn-show-all").addEventListener("click", () => {
  state.hiddenTypes.clear();
  legendEl.querySelectorAll("input").forEach((cb) => (cb.checked = true));
  applyToggles();
});

$("btn-hide-all").addEventListener("click", () => {
  legendEl.querySelectorAll("input").forEach((cb) => (cb.checked = false));
  for (const [type] of state.typeMeshes) state.hiddenTypes.add(type);
  applyToggles();
});

// ---------------------------------------------------------------------------
// Collision / mesh geometry (from trb_mesh.py --web -> web/collision/<level>.json)
// ---------------------------------------------------------------------------
// mesh-v2 format (current): per-mesh display-mesh vertex runs. Each mesh
// carries verts = raw (x, z, y) s16 fixed-point triples at 1/64 scale
// (data.div). The raw y is +y DOWN (game-native; entities are +y up), so in
// the viewer convention (x, -y, -z) the display position is
// (x/div, y/div, -z/div) — the y flips cancel.
//
// Each mesh that decodes also carries faces = the mesh's GX-style INDEXED
// triangle strip: per-record (posIdx, nrmIdx, texIdx) triples from the
// level's 0x98 block, with the pos index first (u8, or u16 for the big
// meshes' 4/5-byte records). Consecutive posIdx walk the strip; the
// repeated-index (degenerate) triangles are the engine's strip-restart
// markers and render as nothing. The solid faces are the strip's real
// triangles. Meshes without faces (undecoded variant formats) render
// nothing.
// Back-face culling for the solid meshes (see applyToggles): with
// THREE.FrontSide, surfaces whose front faces point away from the camera
// (ceiling bottoms from above, outer wall faces, floor undersides) are
// culled, so entities inside buildings show through. The engine's winding
// convention is "front = the side the player sees" (floors up, ceilings
// down), so floors stay visible from above. Default ON (checkbox
// tog-cull is checked); applyToggles syncs this from the checkbox.
let cullBackfaces = true;
// Bump when regenerating collision JSONs to force re-download.
const LOAD_VERSION = 21;

const meshFacesGroup = new THREE.Group();
collisionGroup.add(meshFacesGroup);

// The runtime-dump collision mesh (COLL-LINE) renders as points + triangle
// edges in its own scene-root group so it never touches the visual meshes
// (the past debug pattern). Toggled independently by tog-collmesh.
const collLineGroup = new THREE.Group();
scene.add(collLineGroup);
const COLL_LINE_COLOR = 0x33ffcc;

// Optional solid collision (COLL-SOLID): the same runtime triangles as red
// Lambert surfaces, Gouraud-lit/shaded like the level mesh. Toggled
// independently by tog-collsolid (default off; the cyan lines stay default).
const collSolidGroup = new THREE.Group();
scene.add(collSolidGroup);
const COLL_SOLID_COLOR = 0xff3333;

// Collision classification: GROUND TRUTH from the emulator (s02 savestate,
// DPWorld_Level01_01): the per-mesh coll is a GX-style indexed triangle
// strip. The 0x98 index block walks (posIdx, nrmIdx, texIdx) per strip
// vertex (repeated-index = strip-restart markers); the pos indices point
// into the mesh's s16-fixed-point vertex pool ([x,y,z] triples at 1/div
// scale). Decoded in-code via the same reading as the solid mesh faces.
// (Old "coll quads" 16-byte-s16 reading: DISPROVEN — removed.)
// The per-mesh "coll" footprint arrays exist and the engine links
// OpCODE, but the collision mesh format is UNKNOWN — every 8-bit
// coordinate reading tried so far (u8 triples, (flag,x,y,z) s8 records)
// was an unverified hypothesis (see docs/collision-status.md); the
// footprint decode is a placeholder (origin markers).
// Until the real DOL reader is found, ALL mesh geometry renders uniformly.
const MESH_COLOR = 0x7799aa;  // blue-gray

async function loadCollision(dir) {
  // ?v= busts the HTTP cache — the collision JSON is regenerated often while
  // decoding, and a hard refresh alone doesn't always revalidate it.
  const res = await fetch(`./collision/${dir}.json?v=${LOAD_VERSION}`);
  if (!res.ok) return null;
  const data = await res.json();
  if (data.format === "mesh-v2") {
    const r = loadMeshV2(data);
    return r;
  }
  return null;
}

let collisionManifest = null;
fetch("./collision/manifest.json")
  .then((r) => (r.ok ? r.json() : null))
  .then((m) => (collisionManifest = m))
  .catch(() => {});

// Extracted TRB collision overlay: fetch <level>-coll.json (generated by
// scripts/trb/extract_collision.py) and draw each strip mesh as points +
// deduped strip-triangle edges (the past "connected grid lines" debug look).
async function loadCollLines(dir) {
  const res = await fetch(`./collision/${dir}-coll.json?v=${LOAD_VERSION}`);
  if (!res.ok) return null;
  const data = await res.json();
  if (data.format !== "mesh-v2") return null;
  const div = data.div || 64;
  // facesMode: "triples" (runtime-dump JSONs) = faces are the COMPILED
  // consecutive triangle list (every 3 indices = one real triangle, no
  // strip restarts). The default (mined strips) = a GX-style indexed
  // strip: sliding window with degenerate restarts. The runtime dumps
  // MUST use triples — the strip window would emit phantom "bridge"
  // triangles between the real ones (both correct AND spurious faces).
  const triples = data.facesMode === "triples";
  let meshes = 0;
  let lines = 0;
  for (const part of data.parts || []) {
    for (const m of part.meshes || []) {
      const v = m.verts || [];
      const n = v.length / 3;
      if (n < 2) continue;
      const faces = m.faces || [];
      if (faces.length < 3) continue;
      const pos = new Float32Array(n * 3);
      for (let i = 0, j = 0; i < v.length; i += 3, j += 3) {
        pos[j] = v[i] / div;
        pos[j + 1] = v[i + 2] / div;
        pos[j + 2] = -v[i + 1] / div;
      }
      const ptsGeo = new THREE.BufferGeometry();
      ptsGeo.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
      const pts = new THREE.Points(
        ptsGeo,
        new THREE.PointsMaterial({
          size: 0.25,
          sizeAttenuation: true,
          color: COLL_LINE_COLOR,
          transparent: true,
          opacity: 0.95,
        })
      );
      pts.userData = { type: "coll-line" };
      collLineGroup.add(pts);
      const L = faces.length;
      const edges = new Set();
      const edgeVerts = [];
      // faces = the strip's posIdx column; triangles are CONSECUTIVE triples
      // (a real triangle strip: repeated posIdx = degenerate restart, renders
      // as nothing; winding alternates per triangle).
      const step = triples ? 3 : 1;
      const solidIdx = [];
      for (let i = 0; i < L - 2; i += step) {
        const a = faces[i];
        const b = faces[i + 1];
        const c = faces[i + 2];
        if (a === b || b === c || a === c) continue;
        const tri = triples ? [a, b, c] : i % 2 ? [b, a, c] : [a, b, c];
        solidIdx.push(tri[0], tri[1], tri[2]);
        for (const [u, w] of [
          [tri[0], tri[1]],
          [tri[1], tri[2]],
          [tri[2], tri[0]],
        ]) {
          const k = u < w ? u * 256 + w : w * 256 + u;
          if (edges.has(k)) continue;
          edges.add(k);
          edgeVerts.push(
            pos[u * 3], pos[u * 3 + 1], pos[u * 3 + 2],
            pos[w * 3], pos[w * 3 + 1], pos[w * 3 + 2]
          );
        }
      }
      if (edgeVerts.length) {
        const lgeo = new THREE.BufferGeometry();
        lgeo.setAttribute("position", new THREE.Float32BufferAttribute(edgeVerts, 3));
        const linesObj = new THREE.LineSegments(
          lgeo,
          new THREE.LineBasicMaterial({
            color: COLL_LINE_COLOR,
            transparent: true,
            opacity: 0.9,
          })
        );
        linesObj.userData = { type: "coll-line" };
        collLineGroup.add(linesObj);
        lines += edgeVerts.length / 6;
      }
      // Optional solid render (COLL-SOLID): same triangles as red Lambert
      // surfaces with vertex normals, so the scene lights shade them like
      // the level mesh. DoubleSide so both sides read regardless of winding.
      if (solidIdx.length) {
        const sg = new THREE.BufferGeometry();
        sg.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
        sg.setIndex(new THREE.Uint32BufferAttribute(solidIdx, 1));
        sg.computeVertexNormals();
        const sm = new THREE.Mesh(
          sg,
          new THREE.MeshLambertMaterial({
            color: COLL_SOLID_COLOR,
            side: THREE.DoubleSide,
          })
        );
        sm.userData = { type: "coll-solid" };
        collSolidGroup.add(sm);
      }
      meshes++;
    }
  }
  return { meshes, lines };
}

// Tmp color scratch (allocated once, reused when building per-vertex tint).
const _tint = new THREE.Color();

function loadMeshV2(data) {
  const div = data.div || 64;
  const facePos = [];
  const faceIdx = [];
  const matGroups = {};
  // Per-vertex world-up positions drive both normals and the Y tint.
  const faceRawY = [];
  let minY = Infinity;
  let maxY = -Infinity;
  let vertTotal = 0;
  for (const part of data.parts || []) {
    for (const m of part.meshes || []) {
      const v = m.verts || [];
      const n = v.length / 3;
      if (n < 2) continue;
      vertTotal += n;
      // world positions in the viewer convention (x, -y, -z): the raw
      // triple (x, z, y) is +y DOWN (game-native), so world-up y = -y/div
      // and the viewer's y-flip cancels it: display = (x/div, y/div, -z/div).
      const pos = new Float32Array(n * 3);
      for (let i = 0, j = 0; i < v.length; i += 3, j += 3) {
        const wy = v[i + 2] / div; // world-up y (== display y here)
        pos[j] = v[i] / div;
        pos[j + 1] = wy;
        pos[j + 2] = -v[i + 1] / div;
        if (wy < minY) minY = wy;
        if (wy > maxY) maxY = wy;
      }
      const faces = m.faces;
      if (faces && faces.length >= 3) {
        // Indexed strip: faces[i] = the pool position of strip vertex i.
        // Consecutive triples tile the floors/walls; repeated-index
        // (degenerate) triangles are the strip-restart markers and render
        // as nothing. Winding alternates per triangle (strip convention).
        const fbase = facePos.length / 3;
        for (let i = 0; i < n; i++) {
          facePos.push(pos[i * 3], pos[i * 3 + 1], pos[i * 3 + 2]);
          // Store world-up y per vertex for the height tint applied after
          // a full pass (so the ramp spans the whole level, not one mesh).
          faceRawY.push(pos[i * 3 + 1]);
        }
        const L = faces.length;
        const fstart = faceIdx.length;
        for (let i = 0; i < L - 2; i++) {
          const a = faces[i];
          const b = faces[i + 1];
          const c = faces[i + 2];
          if (a === b || b === c || a === c) continue;
          if (i % 2) faceIdx.push(fbase + b, fbase + a, fbase + c);
          else faceIdx.push(fbase + a, fbase + b, fbase + c);
        }
        const fend = faceIdx.length;
        // Group all faces together — we don't have verified collision
        // classification yet, so everything renders uniformly.
        if (fend > fstart) {
          const key = "mesh";
          if (!matGroups[key]) {
            matGroups[key] = { ranges: [], color: new THREE.Color(MESH_COLOR) };
          }
          matGroups[key].ranges.push([fstart, fend]);
        }
      }
      // Meshes without an indexed strip (undecoded variant formats) render
      // nothing — guessing faces here is exactly what produced the wrong
      // stretched triangles, and the old line fallback is gone.
    }
  }
  let faceCount = 0;
  if (faceIdx.length && facePos.length) {
    // Color array per vertex (faceRawY.length entries)
    const faceColor = new Float32Array(faceRawY.length * 3);
    for (const [mat, grp] of Object.entries(matGroups)) {
      const col = grp.color;
      for (const [s, e] of grp.ranges) {
        // Walk the index buffer to find which vertices this face range uses
        const seen = new Set();
        for (let fi = s; fi < e; fi++) seen.add(faceIdx[fi]);
        for (const vi of seen) {
          faceColor[vi * 3] = col.r;
          faceColor[vi * 3 + 1] = col.g;
          faceColor[vi * 3 + 2] = col.b;
        }
      }
    }

    // Build per-material sub-meshes so each material can be toggled
    const additiveOn = tog.additive && tog.additive.checked;
    const matList = [];
    for (const [mat, grp] of Object.entries(matGroups)) {
      matList.push(mat);
      // Collect all face indices for this material
      const subFaces = [];
      for (const [s, e] of grp.ranges) {
        for (let fi = s; fi < e; fi++) subFaces.push(faceIdx[fi]);
      }
      if (subFaces.length === 0) continue;
      const subGeo = new THREE.BufferGeometry();
      subGeo.setAttribute("position", new THREE.Float32BufferAttribute(facePos, 3));
      subGeo.setAttribute("color", new THREE.Float32BufferAttribute(faceColor, 3));
      subGeo.setIndex(new THREE.Uint32BufferAttribute(subFaces, 1));
      subGeo.computeVertexNormals();
      const lambert = new THREE.MeshLambertMaterial({
        vertexColors: true,
        color: meshStyle.baseLight,
        transparent: additiveOn,
        opacity: additiveOn ? MESH_ADDITIVE_OPACITY : 1,
        blending: additiveOn ? THREE.AdditiveBlending : THREE.NormalBlending,
        side: cullBackfaces ? THREE.FrontSide : THREE.DoubleSide,
        depthWrite: !additiveOn,
        depthTest: true,
      });
      const subMesh = new THREE.Mesh(subGeo, lambert);
      subMesh.userData = { type: "mesh-faces", matKey: mat };
      meshFacesGroup.add(subMesh);
    }
    faceCount = faceIdx.length / 3;

    meshFacesGroup.userData._matGroups = matGroups;
  }

  return { verts: vertTotal, faces: faceCount };
}
// ---------------------------------------------------------------------------
// View toggles
// ---------------------------------------------------------------------------
function applyToggles() {
  const showPoints = tog.points.checked;
  const showLinks = tog.links.checked;
  const showPaths = tog.paths.checked;
  const showCollision = tog.collision.checked;
  const showGrid = tog.grid.checked;

  collisionGroup.visible = showCollision;
  collLineGroup.visible = !!(tog.collmesh && tog.collmesh.checked);
  collSolidGroup.visible = !!(tog.collsolid && tog.collsolid.checked);
  meshFacesGroup.visible = tog.faces.checked;

  // Back-face culling: with FrontSide, surfaces whose front faces point
  // away from the camera (ceiling bottoms from above, outer wall faces,
  // floor undersides) disappear, so entities inside buildings show
  // through. The engine's winding convention is "front = the side the
  // player sees" (floors up, ceilings down), so floors stay visible.
  cullBackfaces = tog.cull.checked;
  const cullSide = cullBackfaces ? THREE.FrontSide : THREE.DoubleSide;
  // Translucent = additive blend at 25% (order-independent, no z-sorting
  // artifacts); solid = opaque, depth-writing. Same Lambert material either
  // way — shading and the Y tint stay on permanently.
  const additiveOn = tog.additive && tog.additive.checked;
  for (const mesh of meshFacesGroup.children) {
    if (mesh.isMesh && mesh.userData.type === "mesh-faces") {
      const m = mesh.material;
      m.side = cullSide;
      m.transparent = additiveOn;
      m.opacity = additiveOn ? MESH_ADDITIVE_OPACITY : 1;
      m.blending = additiveOn ? THREE.AdditiveBlending : THREE.NormalBlending;
      m.depthWrite = !additiveOn;
      m.vertexColors = true;
      m.color.copy(meshStyle.baseLight);
    }
  }

  for (const [type, meshes] of state.typeMeshes) {
    const visible = !state.hiddenTypes.has(type);
    // Boxes are always edge outlines; the solid mesh stays around only as
    // an invisible pick proxy so clicks inside a box still select it.
    if (meshes.boxes) meshes.boxes.visible = visible;
    if (meshes.edges) meshes.edges.visible = visible;
    if (meshes.points) meshes.points.visible = showPoints && visible;
  }
  for (const l of state.links) l.visible = showLinks;
  if (state.pathLine) state.pathLine.visible = showPaths;
  viewGroup.children
    .filter((c) => c.isGridHelper || c.isAxesHelper)
    .forEach((c) => (c.visible = showGrid));

  // Deselect if the selected entity's type just got hidden.
  if (state.selection && state.hiddenTypes.has(state.selection.type)) {
    selectEntity(null);
  }
}

// Collision status legend.
function buildCollLegend() {
  const list = document.getElementById("coll-legend-list");
  if (!list || list.childElementCount) return;
  list.innerHTML = '<span style="color:var(--dim)">' +
    'Collision mesh = the runtime world (s02 savestate, DPWorld_Level01_01)<br>' +
    'dumped from RAM: compiled vertex pool + index list (the actual triangles<br>' +
    'the engine casts against). Verts = the s16 fixed-point coords (x, y, z)<br>' +
    'at 1/64 scale; faces = consecutive triples (no strip restarts).<br>' +
    'Cyan = the real collision surfaces (floors, walls, slopes). The solid<br>' +
    'red toggle renders the same triangles shaded (Lambert), default off.<br>' +
    'Entities may also carry box volumes (AWorldSectionVolume, ADeathZone,<br>' +
    'ABarrier...).' +
    '</span>';
}
buildCollLegend();

// View toggles
for (const id of ["tog-points", "tog-links", "tog-paths", "tog-collision", "tog-collmesh", "tog-collsolid", "tog-faces", "tog-cull", "tog-grid", "tog-additive"]) {
  const el = $(id);
  if (el) el.addEventListener("change", applyToggles);
}

// ---------------------------------------------------------------------------
// Picking
// ---------------------------------------------------------------------------
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();

function pickMeshes() {
  // three.js's raycaster ignores visible=false, so filter manually:
  // hidden types must not be clickable.
  return viewGroup.children.filter((c) => c.isInstancedMesh && c.visible);
}

function pickEntity(event) {
  const rect = renderer.domElement.getBoundingClientRect();
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
  raycaster.setFromCamera(pointer, camera);
  const hits = raycaster.intersectObjects(pickMeshes(), false);
  if (!hits.length) return null;
  const hit = hits[0];
  const list = hit.object.userData.entities;
  return list ? list[hit.instanceId] : null;
}

// Click = select, double-click = fly to it (left button only, so
// right-drag panning doesn't select anything)
let downPos = null;
renderer.domElement.addEventListener("mousedown", (e) => {
  if (e.button !== 0) return;
  downPos = [e.clientX, e.clientY];
});
renderer.domElement.addEventListener("mouseup", (e) => {
  if (e.button !== 0) return;
  if (!downPos) return;
  const dx = e.clientX - downPos[0];
  const dy = e.clientY - downPos[1];
  downPos = null;
  if (dx * dx + dy * dy > 25) return; // it was a drag
  const entity = pickEntity(e);
  selectEntity(entity);
});

renderer.domElement.addEventListener("dblclick", (e) => {
  const entity = pickEntity(e);
  if (entity) {
    selectEntity(entity);
    focusOn(entity);
  }
});

// Hover cursor
let lastHover = 0;
renderer.domElement.addEventListener("mousemove", (e) => {
  const now = performance.now();
  if (now - lastHover < 60) return;
  lastHover = now;
  if (downPos) {
    renderer.domElement.style.cursor = "grabbing";
    return;
  }
  const hit = pickEntity(e);
  renderer.domElement.style.cursor = hit ? "pointer" : "grab";
});

function selectEntity(entity) {
  state.selection = entity;
  if (!entity) {
    selGroup.visible = false;
    infoTitleEl.textContent = "Nothing selected";
    infoEl.innerHTML = "<div class='hint'>Click an entity to inspect it.</div>";
    return;
  }
  const style = getStyle(entity.type);
  if (entity.w && entity.h && entity.d) {
    selBox.scale.set(entity.w, entity.h, entity.d);
    selBox.position.set(entity.x, WY(entity.y), WZ(entity.z));
    selBox.quaternion.copy(quatFor(entity));
    selBox.visible = true;
    selRing.visible = false;
  } else {
    const r = pointRadius(style);
    selRing.scale.setScalar(r);
    selRing.position.set(entity.x, WY(entity.y), WZ(entity.z));
    selRing.visible = true;
    selBox.visible = false;
  }
  selGroup.visible = true;
  fillInfo(entity);
}

function focusOn(entity) {
  const r =
    entity.w && entity.h && entity.d
      ? Math.max(entity.w, entity.h, entity.d) * 1.8
      : pointRadius(getStyle(entity.type)) * 8;
  camera.position.set(entity.x + r, WY(entity.y) + r * 0.7, WZ(entity.z) + r);
  controls.target.set(entity.x, WY(entity.y), WZ(entity.z));
  controls.update();
}

$("btn-focus").addEventListener("click", () => {
  if (state.selection) focusOn(state.selection);
});

$("btn-danny").addEventListener("click", () => {
  if (!state.spawn) {
    statusEl.textContent = "No ADanny entity in this level.";
    return;
  }
  selectEntity(state.spawn);
  focusOn(state.spawn);
});

// ---------------------------------------------------------------------------
// Info panel
// ---------------------------------------------------------------------------
function fillInfo(e) {
  infoTitleEl.textContent = e.name || `#${state.entities.indexOf(e)} (unnamed)`;
  const style = getStyle(e.type);
  const rows = [
    ["type", e.type],
    ["position", fmtVec(e.x, e.y, e.z)],
    ["orientation", e.orientation ? fmtQuat(e.orientation) : "—"],
    ["aabb", e.w ? `${e.w.toFixed(3)} × ${e.h.toFixed(3)} × ${e.d.toFixed(3)}` : "—"],
    ["target", fmtList(e.target)],
    ["parent", e.parent || "—"],
    ["next_waypoint", e.next_waypoint || "—"],
    ["respawn_point", e.respawn_point ? fmtVec(e.respawn_point.x, e.respawn_point.y, e.respawn_point.z) : "—"],
    ["respawn_points", fmtList(e.respawn_points)],
    ["path", e.path ? `${e.path.length / 7} waypoints` : "—"],
  ];
  infoEl.innerHTML =
    `<div class="info-row"><span class="legend-dot" style="background:${rgbStr(style.col)}"></span>` +
    `<span class="info-value">${e.type}</span></div>` +
    rows
      .filter(([, v]) => v !== null && v !== undefined && v !== "—")
      .map(([k, v]) => `<div class="info-row"><span class="info-key">${k}</span><span class="info-value">${v}</span></div>`)
      .join("");
}

const fmtVec = (x, y, z) => `${x.toFixed(3)}, ${y.toFixed(3)}, ${z.toFixed(3)}`;
const fmtQuat = (o) => `${o.x.toFixed(3)}, ${o.y.toFixed(3)}, ${o.z.toFixed(3)}, ${o.w.toFixed(3)}`;
const fmtList = (l) => (Array.isArray(l) && l.length ? l.join(", ") : "—");

// ---------------------------------------------------------------------------
// Level select
// ---------------------------------------------------------------------------
for (const { dir, label } of LEVELS) {
  const opt = document.createElement("option");
  opt.value = dir;
  opt.textContent = label;
  levelSelect.appendChild(opt);
}
levelSelect.addEventListener("change", () => loadLevel(levelSelect.value));

// ---------------------------------------------------------------------------
// Loop / resize
// ---------------------------------------------------------------------------
const clock = new THREE.Clock();
function animate() {
  requestAnimationFrame(animate);
  controls.update(clock.getDelta());
  crosshair.position.copy(controls.target);
  renderer.render(scene, camera);
  labelRenderer.render(scene, camera);
}
animate();

function onResize() {
  const w = viewport.clientWidth;
  const h = viewport.clientHeight;
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h);
  labelRenderer.setSize(w, h);
}
window.addEventListener("resize", onResize);

// Keyboard: P = place marker at camera target, M = print all markers to console
window.addEventListener("keydown", (e) => {
  if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT") return;
  if (e.key === "p" || e.key === "P") {
    placeMarker(controls.target.clone());
  }
  if (e.key === "m" || e.key === "M") {
    console.log("=== MARKERS ===");
    state.markers.forEach((m, i) => {
      console.log(`  ${i}: (${m.pos.x.toFixed(3)}, ${m.pos.y.toFixed(3)}, ${m.pos.z.toFixed(3)})`);
    });
    if (state.markers.length === 0) console.log("  (none)");
  }
});

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------
// Allow deep-linking: http://host/web/#SpongeBobLevel2
// Optional debug flags: &cam=x,y,z = set camera position (e.g. top-down:
// 0,60,0.1), &tgt=x,y,z.
const _q = location.hash.split("&").slice(1);
const _get = (k) => {
  const e = _q.find((s) => s.startsWith(k + "="));
  return e ? e.slice(k.length + 1) : null;
};
const camPos = _get("cam") ? _get("cam").split(",").map(Number) : null;
const camTgt = _get("tgt") ? _get("tgt").split(",").map(Number) : null;
const initial = location.hash.slice(1).split("&")[0];
const initialLevel = LEVELS.some((l) => l.dir === initial) ? initial : LEVELS[0].dir;
levelSelect.value = initialLevel;
loadLevel(initialLevel);

// Debug camera override (hash flags) after the level loads.
if (camPos || camTgt) {
  const _apply = () => {
    if (camPos) camera.position.set(camPos[0], camPos[1], camPos[2]);
    if (camTgt) controls.target.set(camTgt[0], camTgt[1], camTgt[2]);
    controls.update();
  };
  if (state.bounds) _apply();
  else setTimeout(() => { if (state.bounds) _apply(); else _apply(); }, 1500);
}

// Test/debug hooks (used by headless smoke tests; harmless otherwise)
window.__nickmapper = {
  entities: () => state.entities.length,
  boxes: () => state.boxInstances.length,
  types: () => state.typeMeshes.size,
  labels: () => state.labelObjects.length,
  links: () => state.links.length,
  status: () => statusEl.textContent,
  bounds: () => state.bounds && {
    min: state.bounds.min.toArray(),
    max: state.bounds.max.toArray(),
  },
  // Screen-space projection of an entity's origin (for automated click tests)
  project: (i) => {
    const e = state.entities[i];
    if (!e) return null;
    const v = new THREE.Vector3(e.x, WY(e.y), WZ(e.z)).project(camera);
    const w = renderer.domElement.clientWidth;
    const h = renderer.domElement.clientHeight;
    return { x: ((v.x + 1) / 2) * w, y: ((1 - v.y) / 2) * h, visible: v.z < 1 };
  },
  selectName: () => (state.selection && state.selection.name) || null,
  selectType: () => (state.selection && state.selection.type) || null,
  markerVisible: () => selGroup.visible,
  markerParented: () => !!selGroup.parent && selGroup.parent.type === "Scene",
  edgesVisible: () => {
    for (const [type, m] of state.typeMeshes) {
      if (m.edges && !state.hiddenTypes.has(type)) return m.edges.visible;
    }
    return null;
  },
  volumeEdgesVisible: () => {
    const m = state.typeMeshes.get("AWorldSectionVolume");
    return m && m.edges ? m.edges.visible : null;
  },
  labelCount: () => state.labelObjects.length,
  labelTypes: () => [...new Set(state.labelObjects.map((o) => o.userData.type))],
  entityType: (i) => (state.entities[i] && state.entities[i].type) || null,
  spawnType: () => (state.spawn && state.spawn.type) || null,
  collisionVisible: () => collisionGroup.visible,
  collisionParented: () => collisionGroup.parent === scene,
  meshFacesVisible: () => meshFacesGroup.visible,
  camPos: () => camera.position.toArray(),
  camTarget: () => controls.target.toArray(),
  pickAt: (x, y) => {
    const rect = renderer.domElement.getBoundingClientRect();
    pointer.x = ((x - rect.left) / rect.width) * 2 - 1;
    pointer.y = -((y - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(pointer, camera);
    const hits = raycaster.intersectObjects(pickMeshes(), false);
    if (!hits.length) return null;
    const list = hits[0].object.userData.entities;
    return list ? { type: list[hits[0].instanceId].type, name: list[hits[0].instanceId].name } : null;
  },
  cameraQuat: () => camera.quaternion.toArray(),
  cameraTopDown: () => {
    const b = state.bounds;
    if (!b) return null;
    const d = b.radius * 2.4;
    camera.position.set(b.center.x, b.center.y + d, b.center.z + 0.01);
    camera.up.set(0, 1, 0);
    camera.lookAt(b.center.x, b.center.y, b.center.z);
    controls.update();
    return [b.center.x, b.center.y, d, b.radius];
  },
  camDist: () => camera.position.distanceTo(controls.target),
};
