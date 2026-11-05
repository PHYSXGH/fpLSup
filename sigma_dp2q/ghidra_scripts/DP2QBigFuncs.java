// List functions whose body is larger than a threshold (default 0x4000 bytes): in this firmware those
// are data blocks that Thumb happens to decode, and they blow up constant propagation / decompiling.
// args: [threshold]
// @category dp2q
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;

public class DP2QBigFuncs extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] a = getScriptArgs();
        long th = a.length > 0 ? Long.decode(a[0]) : 0x4000;
        for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
            long n = f.getBody().getNumAddresses();
            if (n >= th)
                println(String.format("BIG %s %s..%s 0x%X", f.getName(), f.getBody().getMinAddress(),
                    f.getBody().getMaxAddress(), n));
        }
    }
}
