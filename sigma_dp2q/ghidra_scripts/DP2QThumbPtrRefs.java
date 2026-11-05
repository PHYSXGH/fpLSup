// Pointers to Thumb code carry bit 0 (e.g. task-table entry 0x4004A27F -> code at 0x4004A27E). Ghidra
// leaves them pointing at the odd address, so the target gets no reference. For every defined pointer
// whose value is odd and whose value-1 starts a Thumb instruction (or function), add a DATA reference
// to value-1 and make it the primary reference.
// @category dp2q
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;

public class DP2QThumbPtrRefs extends GhidraScript {
    @Override
    public void run() throws Exception {
        ReferenceManager rm = currentProgram.getReferenceManager();
        int fixed = 0, fnTargets = 0;
        for (Data d : currentProgram.getListing().getDefinedData(true)) {
            if (!d.isPointer()) continue;
            Object v = d.getValue();
            if (!(v instanceof Address a) || (a.getOffset() & 1) == 0) continue;
            Address t = a.subtract(1);
            Instruction ins = getInstructionAt(t);
            Function f = getFunctionAt(t);
            if (ins == null && f == null) continue;
            for (Reference r : rm.getReferencesFrom(d.getAddress()))
                if (r.getToAddress().equals(a)) rm.delete(r);
            Reference r = rm.addMemoryReference(d.getAddress(), t, RefType.DATA, SourceType.ANALYSIS, 0);
            rm.setPrimary(r, true);
            fixed++;
            if (f != null) fnTargets++;
        }
        println("dp2q thumb ptrs: " + fixed + " references fixed, " + fnTargets + " to function entries");
    }
}
