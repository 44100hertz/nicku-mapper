#!/usr/bin/env python3
"""Disassemble the NTU GC main.dol with capstone (PPC big-endian).

Usage:
    python3 re_dol.py FUNC_ADDR [--len N]   # disassemble one function
    python3 re_dol.py --xrefs STRING_ADDR   # find lis+addi/ori refs to an address
    python3 re_dol.py --strings "WorldMesh" # find strings + disasm refs to each

Requires: nix-shell -p python3Packages.capstone  (capstone 5.x)
"""
import os
import re
import struct
import sys

try:
    from capstone import Cs, CS_ARCH_PPC, CS_MODE_BIG_ENDIAN, CS_MODE_32
    from capstone.ppc import PPC_OP_REG, PPC_OP_IMM
except ImportError:
    print("capstone not installed; run: nix-shell -p python3Packages.capstone")
    sys.exit(2)

from dol import Dol, R13_BASE, R2_BASE

md = Cs(CS_ARCH_PPC, CS_MODE_BIG_ENDIAN | CS_MODE_32)
md.detail = True


def decode(ins):
    """Return (type, rD, rA, rB, imm) or None for the common forms."""
    ops = ins.operands
    mnem = ins.mnemonic
    if not ops:
        return None
    if mnem == "lis":
        return ("lis", ops[0].reg, None, None, ops[0].imm)
    if mnem in ("addi", "addic", "addic.", "subi", "subic"):
        rD, rA = ops[0].reg, ops[1].reg
        imm = ops[2].imm if len(ops) > 2 else 0
        return ("addi", rD, rA, None, imm)
    if mnem == "addis":
        rD, rA = ops[0].reg, ops[1].reg
        imm = ops[2].imm if len(ops) > 2 else 0
        return ("addis", rD, rA, None, imm)
    if mnem in ("ori", "oris"):
        rA = ops[0].reg
        rB = ops[1].reg
        imm = ops[2].imm if len(ops) > 2 else 0
        return (mnem, rA, rB, None, imm)
    if mnem.startswith("lwz") or mnem.startswith("lbz") or mnem.startswith("lhz"):
        rD, rA = ops[0].reg, ops[1].reg
        imm = ops[2].imm if len(ops) > 2 else 0
        return (mnem, rD, rA, None, imm)
    if mnem.startswith("stw") or mnem.startswith("stb"):
        rD, rA = ops[0].reg, ops[1].reg
        imm = ops[2].imm if len(ops) > 2 else 0
        return (mnem, rD, rA, None, imm)
    if mnem.startswith("b") and mnem not in ("bne", "beq", "blt", "bgt", "ble", "bge", "bns", "bso", "bl", "b", "bclr", "bcctr", "bnelr", "beqlr"):
        # branches (incl. bl) — capstone gives ins.operands[0].imm as target
        if ops[0].type == PPC_OP_IMM:
            return ("branch", None, None, None, ops[0].imm)
    return None


def disasm_range(dol, addr, n=0x400):
    """Disassemble a range; returns list of (addr, mnemonic, op_str)."""
    b = dol.read(addr, n)
    if b is None:
        print("address 0x%08x not in text sections" % addr)
        return []
    out = []
    for ins in md.disasm(b, addr):
        out.append((ins.address, ins.mnemonic, ins.op_str))
    return out


def find_xrefs(dol, target, window=4):
    """Find instructions computing 'target' via lis+addi/ori (any register
    scheme, incl. SDA r13/r2). Returns list of (addr, how, reg)."""
    hits = []
    for s in dol.sections:
        data = s["data"]
        base = s["ram"]
        for i in range(0, len(data) - 4, 4):
            insn = struct.unpack(">I", data[i:i + 4])[0]
            a = base + i
            regmap = {}
            # single-scan: collect all lis/addis over the whole section once
        # do it in two passes: first collect lis/addis, then match
        regs = {}
        for i in range(0, len(data) - 4, 4):
            insn = struct.unpack(">I", data[i:i + 4])[0]
            a = base + i
            try:
                ins = next(md.disasm(data[i:i + 4], a))
            except StopIteration:
                continue
            d = decode(ins)
            if not d:
                continue
            t, rd, ra, rb, imm = d
            if t == "lis":
                regs[rd] = (a, (imm << 16) & 0xFFFFFFFF, "lis")
            elif t in ("addi", "addis"):
                if ra in regs:
                    saddr, hi, how = regs[ra]
                    val = (hi + imm) & 0xFFFFFFFF
                    if val == target:
                        hits.append((a, "lis+%s" % t, None, saddr))
                    del regs[ra]
            elif t == "ori":
                if rb in regs:
                    saddr, hi, how = regs[rb]
                    val = (hi | imm) & 0xFFFFFFFF
                    if val == target:
                        hits.append((a, "lis+ori", None, saddr))
                    del regs[rb]
            elif t in ("lwz", "lbz", "lhz", "stw"):
                # SDA: lwz rD, imm(r13) -> addr = R13_BASE + sign(imm)
                if ra in (13, 2):
                    base_reg = R13_BASE if ra == 13 else R2_BASE
                    val = (base_reg + imm) & 0xFFFFFFFF
                    if val == target:
                        hits.append((a, "sda lwz", rd, None))
            elif t == "addi" and ra in (13, 2) and rd not in (0,):
                # addi rX, r13, imm  (SDA address materialization)
                base_reg = R13_BASE if ra == 13 else R2_BASE
                val = (base_reg + imm) & 0xFFFFFFFF
                if val == target:
                    hits.append((a, "sda addi", rd, None))
    return hits


def find_u32_refs(dol, target):
    """Find u32 constants equal to target (pointer tables/vtables)."""
    hits = []
    for s in dol.sections:
        data = s["data"]
        base = s["ram"]
        for i in range(0, len(data) - 4, 4):
            v = struct.unpack(">I", data[i:i + 4])[0]
            if v == target:
                hits.append(base + i)
    return hits


def disasm_function(dol, addr, n=0x2000):
    b = dol.read(addr, n)
    if b is None:
        print("not in text")
        return
    print("; function @ 0x%08x" % addr)
    for ins in md.disasm(b, addr):
        d = decode(ins)
        annot = ""
        if d and d[0] in ("addi", "addis", "ori") and d[3] in (13, 2):
            base = R13_BASE if d[3] == 13 else R2_BASE
            val = (base + d[4]) & 0xFFFFFFFF
            cs = dol.cstring(val)
            if cs:
                annot = "  ; -> 0x%08x \"%s\"" % (val, cs[:60])
        print("  0x%08x: %-10s %s%s" % (ins.address, ins.mnemonic, ins.op_str, annot))


if __name__ == "__main__":
    dol = Dol.load()
    args = sys.argv[1:]
    if "--strings" in args:
        needle = args[args.index("--strings") + 1]
        for addr, s in dol.find_string(needle):
            print("== string 0x%08x: %r" % (addr, s))
            for a, how, reg, extra in find_xrefs(dol, addr):
                print("   xref 0x%08x (%s)" % (a, how))
    elif "--xrefs" in args:
        target = int(args[args.index("--xrefs") + 1], 0)
        print("xrefs to 0x%08x (instruction refs):" % target)
        for a, how, reg, extra in find_xrefs(dol, target):
            print("  0x%08x  %s" % (a, how))
        print("u32 pointer refs:")
        for a in find_u32_refs(dol, target):
            print("  0x%08x (u32)" % a)
    else:
        addr = int(args[0], 0)
        n = 0x2000
        if "--len" in args:
            n = int(args[args.index("--len") + 1], 0)
        disasm_function(dol, addr, n)
