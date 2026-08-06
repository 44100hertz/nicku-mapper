#!/usr/bin/env node
// extract-collision.mjs — extract collision wall data from Nicktoons Unite!
// (GC) level .trb files and emit per-level JSON for the 3D viewer.
//
// Source data:  /run/media/samp/.../gcn+wii/extract/nicku-ntsc/P-GNOE/files/Data/<level>/
// Output:       web/collision/<level>.json
//
// Wall records are 5 bytes: (F, X, Z, Y1, Y2)
//   F  type flag (0 = solid main, 1 = boundary/secondary)
//   X  grid column 0..255
//   Z  layer/row byte (mostly 0..4; large values = boundary markers)
//   Y1, Y2  wall vertical span (world y = Y per the verified mapping)
//
// The wall array sits at a per-file 5-byte alignment inside the SECT blob.
// We scan all 5 alignments, pick the one with the most clean records, then
// parse the longest contiguous run at that alignment.
//
// Usage: node extract-collision.mjs [--dir <game Data dir>] [--out web/collision]

import { readFileSync, readdirSync, writeFileSync, mkdirSync, existsSync } from "fs";
import { join } from "path";

const GAME_DATA =
  process.env.GAME_DATA ||
  "/run/media/samp/787be337-88e4-4b95-92f9-45d37615cd02/games/console (other)/gcn+wii/extract/nicku-ntsc/P-GNOE/files/Data";
const OUT_DIR =
  process.env.OUT_DIR || new URL("./web/collision/", import.meta.url).pathname;

// ---------------------------------------------------------------------------
// TSFB container
// ---------------------------------------------------------------------------
function loadSect(path) {
  const d = readFileSync(path);
  if (d.slice(0, 4).toString("latin1") !== "TSFB") return null;
  const hdrxSize = d.readUInt32BE(16);
  const sectStart = hdrxSize + 20;
  if (d.slice(sectStart, sectStart + 4).toString("latin1") !== "TCES") return null;
  const sectSize = d.readUInt32BE(sectStart + 4);
  return d.slice(sectStart + 8, sectStart + 8 + sectSize);
}

// ---------------------------------------------------------------------------
// Wall array detection
// ---------------------------------------------------------------------------
const isWall = (b, o) => {
  const f = b[o], x = b[o + 1], y1 = b[o + 3], y2 = b[o + 4];
  return (f === 0 || f === 1) && !(x === 0 && y1 === 0 && y2 === 0);
};

function findWallRun(sect) {
  // best alignment by clean-record count
  let bestAlign = 0, bestCnt = -1;
  for (let align = 0; align < 5; align++) {
    let cnt = 0;
    for (let k = align; k + 5 <= sect.length; k += 5) {
      if (isWall(sect, k)) cnt++;
    }
    if (cnt > bestCnt) { bestCnt = cnt; bestAlign = align; }
  }
  if (bestCnt < 40) return null;
  // longest contiguous run at that alignment
  let runStart = -1, bestStart = 0, bestLen = 0, cur = 0, curStart = 0;
  for (let k = bestAlign; k + 5 <= sect.length; k += 5) {
    if (isWall(sect, k)) {
      if (cur === 0) curStart = k;
      cur++;
      if (cur > bestLen) { bestLen = cur; bestStart = curStart; }
    } else cur = 0;
  }
  if (bestLen < 40) return null;
  return { start: bestStart, count: bestLen, align: bestAlign };
}

// ---------------------------------------------------------------------------
// Entity-based world-x offset fit (mirrors the python tool's approach)
// ---------------------------------------------------------------------------
function loadEntities(path) {
  if (!existsSync(path)) return [];
  const txt = readFileSync(path, "utf8");
  const out = [];
  const re = /Position\s*=\s*\{\s*(-?\d+(?:\.\d+)?)f?\s*,\s*(-?\d+(?:\.\d+)?)f?\s*,\s*(-?\d+(?:\.\d+)?)f?/g;
  let m;
  while ((m = re.exec(txt))) out.push([+m[1], +m[2], +m[3]]);
  return out;
}

function fitOx(walls, entities) {
  const cols = new Map();
  for (const w of walls) {
    const a = Math.min(w[3], w[4]), b = Math.max(w[3], w[4]);
    if (!cols.has(w[1])) cols.set(w[1], []);
    cols.get(w[1]).push([a, b]);
  }
  if (!entities.length || !cols.size) return 152;
  let best = { hits: 0, ox: 152 };
  for (let ox = 0; ox <= 400; ox += 2) {
    let hits = 0;
    for (const [ex, ey] of entities) {
      const segs = cols.get(Math.round(ex + ox));
      if (!segs) continue;
      for (const [a, b] of segs) {
        if (a - 1 <= ey && ey <= b + 1) { hits++; break; }
      }
    }
    if (hits > best.hits) best = { hits, ox };
  }
  return best.ox;
}

// ---------------------------------------------------------------------------
// main
// ---------------------------------------------------------------------------
mkdirSync(OUT_DIR, { recursive: true });
const levels = readdirSync(GAME_DATA, { withFileTypes: true })
  .filter((e) => e.isDirectory())
  .map((e) => e.name);

let totalWalls = 0;
for (const level of levels) {
  const dir = join(GAME_DATA, level);
  const trbFiles = readdirSync(dir).filter((f) => f.endsWith(".trb"));
  if (!trbFiles.length) continue;
  const parts = [];
  for (const f of trbFiles.sort()) {
    const sect = loadSect(join(dir, f));
    if (!sect) continue;
    const run = findWallRun(sect);
    if (!run) continue;
    const walls = [];
    const seen = new Set();
    for (let i = 0; i < run.count; i++) {
      const o = run.start + i * 5;
      const rec = [sect[o], sect[o + 1], sect[o + 2], sect[o + 3], sect[o + 4]];
      if (!isWall(sect, o)) continue;
      const key = rec.join(",");
      if (seen.has(key)) continue;
      seen.add(key);
      walls.push(rec);
    }
    if (walls.length) {
      parts.push({ file: f, walls });
      totalWalls += walls.length;
    }
  }
  if (!parts.length) continue;
  const ents = findEntityFile(dir);
  const all = parts.flatMap((p) => p.walls);
  const ox = fitOx(all, ents);
  writeFileSync(
    join(OUT_DIR, level + ".json"),
    JSON.stringify({ level, ox, parts })
  );
  console.log(
    `${level}: ${parts.length} part(s), ${all.length} walls, ox=${ox}, hits=${ents.length ? fitScore(all, ents, ox) : "?"}/${ents.length}`
  );
}
console.log(`total walls written: ${totalWalls}`);

function findEntityFile(dir) {
  const files = readdirSync(dir);
  const cand = files.find((f) => f.endsWith("Entities.ini")) ||
               files.find((f) => f.endsWith("Ents.ini"));
  return cand ? loadEntities(join(dir, cand)) : [];
}

function fitScore(walls, ents, ox) {
  const cols = new Map();
  for (const w of walls) {
    if (!cols.has(w[1])) cols.set(w[1], []);
    cols.get(w[1]).push([Math.min(w[3], w[4]), Math.max(w[3], w[4])]);
  }
  let hits = 0;
  for (const [ex, ey] of ents) {
    const segs = cols.get(Math.round(ex + ox));
    if (!segs) continue;
    for (const [a, b] of segs) {
      if (a - 1 <= ey && ey <= b + 1) { hits++; break; }
    }
  }
  return hits;
}
