// Set up memory blocks for the NTU GC main.dol (raw import).
// @category NTU
import ghidra.app.script.GhidraScript;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.address.Address;
import java.io.File;
import java.nio.file.Files;

public class SetupMemory extends GhidraScript {
    @Override
    public void run() throws Exception {
        println("lang: " + currentProgram.getLanguage().getLanguageID());
        var fm = currentProgram.getMemory();
        for (MemoryBlock b : fm.getBlocks()) {
            fm.removeBlock(b, monitor);
        }
        long[][] sections = {
            {0x100, 0x80003100L, 0x3A0},
            {0x4A0, 0x800034A0L, 0x3EFE0},
            {0x3F480, 0x80042480L, 0x74AC0},
            {0xB3F40, 0x800B6F40L, 0x315C0},
            {0xE5500, 0x80195620L, 0x1520},
            {0xE6A20, 0x80197C40L, 0x1DE0},
        };
        byte[] data = java.nio.file.Files.readAllBytes(java.nio.file.Paths.get("/tmp/main_fixed.dol"));
        String[] names = {".text0", ".text1", ".text7", ".text8", ".text9", ".text10"};
        for (int i = 0; i < sections.length; i++) {
            int foff = (int) sections[i][0];
            long ram = sections[i][1];
            int size = (int) sections[i][2];
            byte[] chunk = new byte[size];
            System.arraycopy(data, foff, chunk, 0, size);
            MemoryBlock block = fm.createInitializedBlock(
                names[i], toAddr(ram), new java.io.ByteArrayInputStream(chunk), size, monitor, false);
            block.setRead(true); block.setWrite(true); block.setExecute(true);
            println("created " + names[i] + " @ " + Long.toHexString(ram) + " size " + Integer.toHexString(size));
        }
        fm.createUninitializedBlock(".data", toAddr(0x800E8500L), 0xAD120, false);
        // entry point from DOL header
        int ep = ((data[0x19C] & 0xFF) << 24) | ((data[0x19D] & 0xFF) << 16) |
                 ((data[0x19E] & 0xFF) << 8) | (data[0x19F] & 0xFF);
        println("entry: " + Integer.toHexString(ep));
        currentProgram.getSymbolTable().createLabel(toAddr(ep & 0xFFFFFFFFL), "entry", ghidra.program.model.symbol.SourceType.USER_DEFINED);
    }
}
