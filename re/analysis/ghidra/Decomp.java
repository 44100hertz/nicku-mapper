// Decompile functions at given addresses (from args) to C.
// @category NTU
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;

public class Decomp extends GhidraScript {
    @Override
    public void run() throws Exception {
        DecompInterface di = new DecompInterface();
        di.openProgram(currentProgram);
        String[] args = getScriptArgs();
        for (String a : args) {
            long addr = Long.decode(a);
            Function f = currentProgram.getFunctionManager().getFunctionAt(toAddr(addr));
            if (f == null) {
                println("== no function at " + a);
                continue;
            }
            DecompileResults res = di.decompileFunction(f, 120, monitor);
            println("=== " + a + " " + f.getName() + " ===");
            if (res.decompileCompleted()) {
                println(res.getDecompiledFunction().getC());
            } else {
                println("decompile failed: " + res.getErrorMessage());
            }
        }
        di.dispose();
    }
}
