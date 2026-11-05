// Per-1MB map of the image: instruction bytes, defined-data bytes, undefined bytes, function entries.
// @category dp2q
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;

public class DP2QCoverage extends GhidraScript {
    @Override
    public void run() throws Exception {
        Listing l = currentProgram.getListing();
        for (long s = 0x40000000L; s < 0x40E00000L; s += 0x100000) {
            AddressSet set = new AddressSet(toAddr(s), toAddr(s + 0xFFFFF));
            long ins = 0, dat = 0; int fns = 0;
            for (Instruction i : l.getInstructions(set, true)) ins += i.getLength();
            for (Data d : l.getDefinedData(set, true)) dat += d.getLength();
            for (Function f : currentProgram.getFunctionManager().getFunctions(set, true)) fns++;
            println(String.format("%08X code %7d  data %7d  undef %7d  funcs %5d", s, ins, dat,
                0x100000 - ins - dat, fns));
        }
    }
}
