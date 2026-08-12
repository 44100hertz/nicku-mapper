"""nicku-extract — Nicktoons Unite! ISO -> viewer JSON pipeline.

End-to-end: extract the GameCube ISO with WIT (Wiimms ISO Tools), decode the
level meshes + collision worlds, and emit a static data dir the web viewer
loads. The ISO is the ONLY input; nothing else is needed.

    nicku-extract --iso nicktoonsunite.iso --out ./site
    nicku-extract --data files/Data --out ./site     # skip WIT, use a tree
    NICK_ISO=nicktoonsunite.iso nicku-extract --out ./site

Output layout (relative to --out):

    collision/<Level>.json         display meshes (mesh-v2)
    collision/<Level>-coll.json    collision worlds (mesh-v2)
    collision/manifest.json        sorted list of levels with mesh data
    entities/<Level>.ini           entity placements (from *Ents.ini)
    build-info.json                source hash, WIT version, coverage report
"""
import argparse
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

from . import collision, trb


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def find_data_root(path):
    """Normalize a --data path to the files/Data directory.

    Accepts either files/Data itself, or a P-GNOE root (which contains
    files/Data), or a WIT-extract root (which contains P-GNOE/files/Data).
    """
    for cand in (
        os.path.join(path, "files", "Data"),
        os.path.join(path, "P-GNOE", "files", "Data"),
        path,
    ):
        if os.path.isdir(cand):
            return cand
    return None


def run_wit(iso, dest, wit_bin):
    cmd = [wit_bin, "extract", iso, dest]
    log("  wit: " + " ".join(cmd))
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)


def level_dirs(data_root):
    """The level directories: dirs carrying an entity INI file."""
    out = []
    for d in sorted(glob.glob(os.path.join(data_root, "*"))):
        if not os.path.isdir(d):
            continue
        if glob.glob(os.path.join(d, "*Ents.ini")) or \
           glob.glob(os.path.join(d, "*Entities.ini")):
            out.append(d)
    return out


def copy_entities(data_root, out_dir):
    """Copy each level's entity INI to entities/<Level>.ini (name-agnostic:
    *Ents.ini / *Entities.ini, normalizing SB1's SBL1_Ents.ini)."""
    ent_dir = os.path.join(out_dir, "entities")
    os.makedirs(ent_dir, exist_ok=True)
    written = []
    for d in level_dirs(data_root):
        level = os.path.basename(d)
        src = None
        for pat in ("*Ents.ini", "*Entities.ini"):
            m = glob.glob(os.path.join(d, pat))
            if m:
                src = m[0]
                break
        if src:
            dst = os.path.join(ent_dir, level + ".ini")
            shutil.copyfile(src, dst)
            written.append(level)
    return written


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser(prog="nicku-extract", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--iso", help="path to nicktoonsunite.iso (or $NICK_ISO)")
    ap.add_argument("--data", help="pre-extracted files/Data dir (or $NICK_DATA); skips WIT")
    ap.add_argument("--out", default=os.environ.get("NICK_OUT", "./site"),
                    help="output dir (default: ./site or $NICK_OUT)")
    ap.add_argument("--wit", help="path to the wit binary (default: from PATH)")
    ap.add_argument("--keep-temp", action="store_true",
                    help="keep the temporary WIT-extract tree")
    args = ap.parse_args(argv)

    iso = args.iso or os.environ.get("NICK_ISO")
    data = args.data or os.environ.get("NICK_DATA")

    if not iso and not data:
        ap.error("one of --iso / --data (or NICK_ISO / NICK_DATA) is required")

    out_dir = os.path.abspath(args.out)
    os.makedirs(os.path.join(out_dir, "collision"), exist_ok=True)

    tmp = None
    build_info = {"generator": "nicku-extract"}

    if iso:
        if not os.path.exists(iso):
            ap.error(f"ISO not found: {iso}")
        wit_bin = args.wit or shutil.which("wit")
        if not wit_bin:
            ap.error("wit not found on PATH; pass --wit or install wiimms-iso-tools")
        build_info["iso"] = iso
        build_info["iso_sha256"] = sha256(iso)
        try:
            wit_ver = subprocess.run([wit_bin, "--version"], capture_output=True,
                                     text=True, check=True).stdout.splitlines()[0]
        except Exception:
            wit_ver = "unknown"
        build_info["wit"] = wit_ver
        tmp = tempfile.mkdtemp(prefix="nicku-extract-")
        log(f"extracting ISO with wit ({wit_ver})...")
        dest = os.path.join(tmp, "extract")  # must NOT exist (wit creates it)
        run_wit(iso, dest, wit_bin)
        data_root = os.path.join(dest, "P-GNOE", "files", "Data")
    else:
        data_root = find_data_root(os.path.abspath(data))
        if data_root is None:
            ap.error(f"no files/Data found under {data}")
        build_info["data"] = data_root

    # 1) display meshes
    log("decoding display meshes...")
    mesh_levels = trb.extract_meshes(data_root, os.path.join(out_dir, "collision"))

    # 2) collision worlds (Format A then B, structural detection)
    log("decoding collision worlds...")
    coll_levels = {}
    for d in level_dirs(data_root):
        level = os.path.basename(d)
        nta = os.path.join(d, "AssetsAuto.nta")
        if not os.path.exists(nta):
            continue
        world = collision.decode_level(nta, level)
        if world is None:
            log(f"  {level}: no collision resource decoded")
            continue
        outp = os.path.join(out_dir, "collision", level + "-coll.json")
        with open(outp, "w") as f:
            json.dump(world, f, separators=(",", ":"))
        coll_levels[level] = (world["collFormat"], len(world["parts"][0]["meshes"]),
                              len(world["parts"][0]["meshes"][0]["verts"]) // 3)
        log(f"  {level}: {world['collFormat']} -> {os.path.relpath(outp, out_dir)}")

    # 3) entity placements
    log("copying entity INIs...")
    ent_levels = copy_entities(data_root, out_dir)

    # 4) build report
    build_info["levels"] = {
        "mesh": mesh_levels,
        "collision": {k: v[0] for k, v in sorted(coll_levels.items())},
        "entities": sorted(ent_levels),
    }
    build_info["counts"] = {
        "mesh_levels": len(mesh_levels),
        "collision_levels": len(coll_levels),
        "entity_levels": len(ent_levels),
    }
    with open(os.path.join(out_dir, "build-info.json"), "w") as f:
        json.dump(build_info, f, indent=2, sort_keys=True)

    if tmp and not args.keep_temp:
        shutil.rmtree(tmp, ignore_errors=True)

    log(f"done: {build_info['counts']} -> {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
