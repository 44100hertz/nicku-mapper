// Find functions referencing GX CP registers (0xCC008000) and dump key ones.
// @category NTU
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSet;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.mem.Memory;

public class FindGX extends GhidraScript {
    @Override
    public void run() throws Exception {
        Listing listing = currentProgram.getListing();
        long target = 0xCC008000L;
        java.util.List<Function> hits = new java.util.ArrayList<>();
        for (Function f : listing.getFunctions(true)) {
            ghidra.program.model.address.AddressSetView body = f.getBody();
            for (Address a : body.getAddresses(true)) {
                Instruction ins = listing.getInstructionAt(a);
                if (ins == null) continue;
                for (int i = 0; i < ins.getNumOperands(); i++) {
                    Object[] refs = ins.getOpObjects(i);
                    for (Object r : refs) {
                        if (r instanceof Address) {
                            long v = ((Address) r).getOffset();
                            if (v >= 0xCC000000L && v <= 0xCC010000L) {
                                hits.add(f);
                                i = 99; break;
                            }
                        }
                    }
                }
            }
        }
        // dedupe
        java.util.LinkedHashSet<Function> uniq = new java.util.LinkedHashSet<>(hits);
        println("functions referencing 0xCC00xxxx: " + uniq.size());
        for (Function f : uniq) {
            println(String.format("  %08x %-40s size=%d", f.getEntryPoint().getOffset(), f.getName(), f.getBody().getNumAddresses()));
        }
    }
}
