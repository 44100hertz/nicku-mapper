// JS port of parser.lua — parses Nicktoons: Unite! Entities.ini files.
// Deliberately keeps the quirks of the original Lua implementation:
//  * entities is a FLAT list; nested "Entity { ... }" blocks are pushed as
//    siblings of their parents (links between them come from ParentName)
//  * the "previous token" heuristic decides when a '{' opens an entity
//  * only the first three numbers of Position/AABBDimensions/RespawnPoint
//    are kept (the 4th element is always a scale of 1.0)
//
// One addition vs parser.lua: Orientation quaternions are captured so the
// 3D viewer can rotate boxes correctly.

const parsenums = (line) => (line.match(/[0-9.\-]+/g) || []).map(Number);

const parsefns = {
  Type(line, e) {
    // Entity type declarations are bare identifiers ("Type = APropDoor;").
    // Some entities also carry a *property* named Type with a quoted string
    // value ("Type = \"empty\";") — ignore those so they don't clobber the
    // entity's real type. (The original Lua parser has this bug.)
    const m = line.match(/Type = (.+);/);
    if (m && !m[1].startsWith('"')) e.type = m[1];
  },
  Position(line, e) {
    const n = parsenums(line);
    [e.x, e.y, e.z] = n;
  },
  Orientation(line, e) {
    const n = parsenums(line);
    e.orientation = { x: n[0], y: n[1], z: n[2], w: n[3] };
  },
  AABBDimensions(line, e) {
    const n = parsenums(line);
    [e.w, e.h, e.d] = n;
  },
  RespawnPoint(line, e) {
    const n = parsenums(line);
    e.respawn_point = { x: n[0], y: n[1], z: n[2] };
  },
  Path(line, e) {
    // 7 floats per waypoint: x, y, z, scale, r, g, b
    e.path = parsenums(line);
  },
  Name(line, e) {
    const m = line.match(/Name = "(.+)"/);
    if (m) e.name = m[1];
  },
  Target(line, e) {
    const m = line.match(/Target = "(.+)"/);
    if (m) e.target = [m[1]];
  },
  ParentName(line, e) {
    const m = line.match(/ParentName = "(.+)"/);
    if (m) e.parent = m[1];
  },
  NextWaypoint(line, e) {
    const m = line.match(/NextWaypoint = "(.+)"/);
    if (m) e.next_waypoint = m[1];
  },
  ExtraTargets(line, e) {
    const quoted = [...line.matchAll(/"(.+?)"/g)].map((m) => m[1]);
    if (quoted.length) e.target = (e.target || []).concat(quoted);
  },
  RespawnPoints(line, e) {
    e.respawn_points = [...line.matchAll(/"(.+?)"/g)].map((m) => m[1]);
  },
};

export function parse(data) {
  const entities = [];
  let ptoken;
  for (const line of data.split("\n")) {
    const token = line.match(/\S+/)?.[0];
    if (token === "{" && ptoken === "Entity") entities.push({});
    const fn = parsefns[token];
    if (fn && entities.length) fn(line, entities[entities.length - 1]);
    ptoken = token;
  }
  return entities;
}
