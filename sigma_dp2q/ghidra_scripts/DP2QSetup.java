// Pre-analysis setup for a dp2 Quattro image imported raw at 0x40000000 (ARM:LE:32:v7).
// - maps the boot-copied config block (image SRC..SRC+LEN) at 0x01000000 as its own initialized block
// - creates labelled functions from a seeds CSV: addr,name,mode   (mode T = Thumb, A = ARM)
// args: <seeds.csv> [src=0x40C40628] [len=0x79C8]
// @category dp2q
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.lang.*;
import ghidra.program.model.symbol.SourceType;
import java.math.BigInteger;
import java.nio.file.*;
import java.util.*;

public class DP2QSetup extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] a = getScriptArgs();
        Path seeds = Paths.get(a[0]);
        long src = a.length > 1 ? Long.decode(a[1]) : 0x40C40628L;
        int len = a.length > 2 ? Integer.decode(a[2]) : 0x79C8;

        Memory mem = currentProgram.getMemory();
        AddressSpace sp = currentProgram.getAddressFactory().getDefaultAddressSpace();
        byte[] buf = new byte[len];
        mem.getBytes(sp.getAddress(src), buf);
        MemoryBlock b = mem.createInitializedBlock("ram_cfg", sp.getAddress(0x01000000L),
            new java.io.ByteArrayInputStream(buf), len, monitor, false);
        b.setRead(true); b.setWrite(true); b.setExecute(true);
        b.setComment(String.format("copy of image 0x%X..+0x%X (boot-time copy, inferred)", src, len));
        mem.getBlock(sp.getAddress(0x40000000L)).setName("image");

        Register tmode = currentProgram.getRegister("TMode");
        int n = 0;
        for (String line : Files.readAllLines(seeds)) {
            line = line.trim();
            if (line.isEmpty() || line.startsWith("#")) continue;
            String[] f = line.split(",");
            Address ad = sp.getAddress(Long.decode(f[0]) & ~1L);
            boolean thumb = f.length > 2 && f[2].trim().equals("T");
            currentProgram.getProgramContext().setValue(tmode, ad, ad,
                BigInteger.valueOf(thumb ? 1 : 0));
            disassemble(ad);
            Function fn = getFunctionAt(ad);
            if (fn == null) fn = createFunction(ad, f[1].trim());
            else fn.setName(f[1].trim(), SourceType.USER_DEFINED);
            if (fn != null) n++;
        }
        println("dp2q setup: ram_cfg mapped, " + n + " seeded functions");
    }
}
