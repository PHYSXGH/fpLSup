// Export every function: entry, name, namespace, body size, Thumb flag, first 16 bytes (hex), callee count.
// args: <out.tsv>
// @category dp2q
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import java.io.PrintWriter;
import java.math.BigInteger;

public class DP2QExportFuncs extends GhidraScript {
    @Override
    public void run() throws Exception {
        var tm = currentProgram.getRegister("TMode");
        int n = 0;
        try (PrintWriter w = new PrintWriter(getScriptArgs()[0])) {
            w.println("addr\tname\tns\tsize\tthumb\thead\tcallees");
            for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
                BigInteger v = currentProgram.getProgramContext().getValue(tm, f.getEntryPoint(), false);
                byte[] b = new byte[16];
                int got = 0;
                try { got = currentProgram.getMemory().getBytes(f.getEntryPoint(), b); } catch (Exception e) { }
                StringBuilder h = new StringBuilder();
                for (int i = 0; i < got; i++) h.append(String.format("%02x", b[i]));
                w.printf("%s\t%s\t%s\t%d\t%d\t%s\t%d%n", f.getEntryPoint(), f.getName(),
                    f.getParentNamespace().isGlobal() ? "" : f.getParentNamespace().getName(),
                    f.getBody().getNumAddresses(), v != null && v.intValue() == 1 ? 1 : 0, h,
                    f.getCalledFunctions(monitor).size());
                n++;
            }
        }
        println("dp2q export: " + n + " functions");
    }
}
