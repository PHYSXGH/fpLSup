// Read-only summary of an analysed dp2q project: function counts, Thumb share, seeded names, ram_cfg.
// @category dp2q
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.address.*;
import java.math.BigInteger;

public class DP2QReport extends GhidraScript {
    @Override
    public void run() throws Exception {
        FunctionManager fm = currentProgram.getFunctionManager();
        var tm = currentProgram.getRegister("TMode");
        int total = 0, thumb = 0, named = 0, ram = 0;
        for (Function f : fm.getFunctions(true)) {
            total++;
            BigInteger v = currentProgram.getProgramContext().getValue(tm, f.getEntryPoint(), false);
            if (v != null && v.intValue() == 1) thumb++;
            if (!f.getName().startsWith("FUN_")) named++;
            if (f.getEntryPoint().getOffset() < 0x40000000L) ram++;
        }
        long code = 0;
        for (Instruction i : currentProgram.getListing().getInstructions(true)) code += i.getLength();
        println(String.format("functions %d (thumb %d, named %d, in ram_cfg %d), instruction bytes 0x%X",
            total, thumb, named, ram, code));
        for (MemoryBlock b : currentProgram.getMemory().getBlocks())
            println(String.format("block %s %s..%s", b.getName(), b.getStart(), b.getEnd()));
        for (String n : new String[]{"tk_cre_tsk", "task_BOOT", "task_UI_CTRL", "svc6_stub"}) {
            var syms = currentProgram.getSymbolTable().getGlobalSymbols(n);
            for (var s : syms) {
                Function f = fm.getFunctionAt(s.getAddress());
                int refs = currentProgram.getReferenceManager().getReferenceCountTo(s.getAddress());
                println(String.format("%s @%s body %d bytes, %d refs to it", n, s.getAddress(),
                    f == null ? -1 : f.getBody().getNumAddresses(), refs));
            }
        }
        // the config routine in ram_cfg (runtime 0x01000A58) should now be code that references tk_cre_tsk
        Function cfg = fm.getFunctionContaining(toAddr(0x01000A58L));
        println("ram_cfg 0x01000A58 in function: " + (cfg == null ? "none" : cfg.getName() + " @" + cfg.getEntryPoint()));
    }
}
