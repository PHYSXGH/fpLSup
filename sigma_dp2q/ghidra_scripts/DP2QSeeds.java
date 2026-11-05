// Apply extra seeds to an existing dp2q program before re-analysis.
// CSV addr,name,mode : T = Thumb function, A = ARM function, P = 32-bit pointer data. name may be empty.
// args: <seeds.csv>
// @category dp2q
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.data.PointerDataType;
import ghidra.program.model.lang.Register;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.SourceType;
import java.math.BigInteger;
import java.nio.file.*;

public class DP2QSeeds extends GhidraScript {
    @Override
    public void run() throws Exception {
        Register tmode = currentProgram.getRegister("TMode");
        int fn = 0, ptr = 0, skip = 0, conflict = 0;
        for (String line : Files.readAllLines(Paths.get(getScriptArgs()[0]))) {
            line = line.trim();
            if (line.isEmpty() || line.startsWith("#")) continue;
            String[] f = line.split(",", -1);
            Address ad = toAddr(Long.decode(f[0]) & ~1L);
            String name = f[1].trim(), mode = f[2].trim();
            if (mode.equals("P")) {
                try {
                    clearListing(ad, ad.add(3));
                    createData(ad, PointerDataType.dataType);
                    ptr++;
                } catch (Exception e) { conflict++; println("pointer " + ad + " skipped: " + e.getMessage()); }
                continue;
            }
            if (getFunctionAt(ad) != null) { skip++; continue; }
            Instruction at = getInstructionContaining(ad);
            if (at != null && !at.getAddress().equals(ad)) { skip++; continue; }  // mid-instruction
            try {
                if (at == null) {                      // undefined bytes: set mode and disassemble
                    currentProgram.getProgramContext().setValue(tmode, ad, ad,
                        BigInteger.valueOf(mode.equals("T") ? 1 : 0));
                    disassemble(ad);
                }                                      // else keep the mode Ghidra already chose
                Function g = createFunction(ad, name.isEmpty() ? null : name);
                if (g != null) fn++; else skip++;
            } catch (Exception e) {
                conflict++;
                if (conflict <= 20) println("seed " + ad + " skipped: " + e.getMessage());
            }
        }
        println("dp2q seeds: " + fn + " functions, " + ptr + " pointers, " + skip + " skipped, " + conflict + " conflicts");
    }
}
