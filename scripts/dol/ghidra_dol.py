# Ghidra headless script: find xrefs to level-loader strings and decompile callers
from ghidra.app.decompiler import DecompInterface
from ghidra.util.task import ConsoleTaskMonitor

mon = ConsoleTaskMonitor()
decomp = DecompInterface()
decomp.openProgram(currentProgram)

targets = {
    0x8004f7d8: "W%dC%dM%d",
    0x8004f6d0: "LOD%d_Mesh_%d",
    0x8004f648: "Header",
    0x8004f650: "Materials",
    0x8004fa3c: "Collision",
    0x8004fc90: "collision_char",
    0x8004fd4c: "collision_noocclude",
    0x8004c1d8: "Database",
    0x8004c1fc: "Terrain_%d",
}

fm = currentProgram.getFunctionManager()

def func_at(addr):
    f = fm.getFunctionContaining(addr)
    return f

def decompile(f):
    if f is None:
        return ""
    res = decomp.decompileFunction(f, 30, mon)
    if res and res.getDecompiledFunction():
        return res.getDecompiledFunction().getC()
    return ""

for addr, name in sorted(targets.items()):
    a = toAddr(addr)
    refs = getReferencesTo(a)
    print("=" * 70)
    print("%s @ %08x: %d refs" % (name, addr, len(refs)))
    seen = set()
    for r in refs:
        ra = r.getFromAddress()
        f = func_at(ra)
        fn = f.getName() if f else "?"
        print("  ref from %08x in %s" % (ra.getOffset(), fn))
        if f and f.getEntryPoint().getOffset() not in seen:
            seen.add(f.getEntryPoint().getOffset())
            code = decompile(f)
            if code:
                print("  ---- %s ----" % fn)
                print(code[:4000])
                print("  ---- end %s ----" % fn)
