import os, struct, json

EXTRACT = os.environ.get("NICK_EXTRACT", "")

fn = os.path.join(EXTRACT, "nicku-ntsc", "P-GNOE", "files", "Data", "SpongeBobLevel1", "SBWorld_Detail_Level01_01.trb")
d = open(fn, "rb").read()
hdrx_size = struct.unpack_from(">I", d, 0x10)[0]
n = struct.unpack_from(">I", d, 0x18)[0]
sect = hdrx_size + 20 + 8
p = 0x20
sizes = []
for i in range(n):
    sizes.append(struct.unpack_from(">I", d, p)[0]); p += 16
chunk0 = d[sect:sect+sizes[0]]
W = len(chunk0) // 2
print(f"chunk0: {len(chunk0)} bytes, {W} words")

s16 = struct.unpack(">%dh" % W, chunk0[:W*2])
u16 = struct.unpack(">%dH" % W, chunk0[:W*2])
W4 = len(chunk0) // 4
f32 = struct.unpack(">%df" % W4, chunk0[:W4*4])

def suffix_run_scan(view, stride_words, min_entries, valid_fn, smooth_fn, label):
    """For each phase p of stride S: L = view[p::S]; find longest suffix run where
    every element is valid and every consecutive pair is smooth. Candidate pool start
    (in bytes) = (p + (len(L)-runlen)*S)*2."""
    cands = []
    for ph in range(stride_words):
        L = view[ph::stride_words]
        nL = len(L)
        if nL < min_entries:
            continue
        # build good[] in one pass
        run = 0
        best_run, best_end = 0, -1
        prev = L[0]
        for k in range(1, nL):
            v = L[k]
            ok = valid_fn(v) and smooth_fn(v, prev)
            if ok:
                run += 1
                if run > best_run:
                    best_run = run
                    best_end = k
            else:
                run = 0
            prev = v
        if best_end >= 0 and best_run >= min_entries:
            start_word = ph + (best_end - best_run + 1) * stride_words
            cands.append((best_run, start_word*2, ph, label))
    return cands

# --- POS pool scans ---
min_pos = 2336
pos_cands = []
# s16 view: valid |v|<20000, smooth |dv|<256
pos_cands += suffix_run_scan(s16, 3, min_pos, lambda v: abs(v) < 20000, lambda v, p: abs(v-p) < 256, "s16x3")
pos_cands += suffix_run_scan(s16, 4, min_pos, lambda v: abs(v) < 20000, lambda v, p: abs(v-p) < 256, "s16x3+pad(8)")
pos_cands += suffix_run_scan(s16, 6, min_pos, lambda v: abs(v) < 20000, lambda v, p: abs(v-p) < 256, "s16x3+pad(12)")
pos_cands += suffix_run_scan(s16, 8, min_pos, lambda v: abs(v) < 20000, lambda v, p: abs(v-p) < 256, "s16x3+pad(16)")
pos_cands += suffix_run_scan(u16, 3, min_pos, lambda v: v < 40000, lambda v, p: abs(v-p) < 256, "u16x3")
pos_cands += suffix_run_scan(u16, 4, min_pos, lambda v: v < 40000, lambda v, p: abs(v-p) < 256, "u16x3+pad(8)")
pos_cands += suffix_run_scan(u16, 6, min_pos, lambda v: v < 40000, lambda v, p: abs(v-p) < 256, "u16x3+pad(12)")
# f32: valid |v|<200 (world units), smooth |dv|<30
pos_cands += suffix_run_scan(f32, 3, min_pos, lambda v: abs(v) < 200, lambda v, p: abs(v-p) < 30, "f32x3(12)")
pos_cands += suffix_run_scan(f32, 4, min_pos, lambda v: abs(v) < 200, lambda v, p: abs(v-p) < 30, "f32x4(16)")

pos_cands.sort(reverse=True)
print("=== POS candidates (run, byte_off, phase, layout) top 25 ===")
for c in pos_cands[:25]:
    print("  ", c)
