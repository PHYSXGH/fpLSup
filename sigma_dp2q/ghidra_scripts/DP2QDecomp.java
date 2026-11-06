// Decompile functions to stdout / a file. Each argument is an address (0x...) or a function name, or
// "str:<text>" = every function that references a defined string containing <text>.
// Last argument may be "out=<file>" to write there instead of the log.
// @category dp2q
import ghidra.app.decompiler.*;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import java.io.PrintWriter;
import java.util.*;

public class DP2QDecomp extends GhidraScript {
    @Override
    public void run() throws Exception {
        List<String> args = new ArrayList<>(Arrays.asList(getScriptArgs()));
        PrintWriter out = null;
        if (!args.isEmpty() && args.get(args.size() - 1).startsWith("out=")) {
            out = new PrintWriter(args.remove(args.size() - 1).substring(4));
        }
        Set<Function> fns = new LinkedHashSet<>();
        for (String a : args) {
            if (a.startsWith("str:")) {
                String t = a.substring(4);
                for (Data d : currentProgram.getListing().getDefinedData(true)) {
                    if (!d.hasStringValue() || !d.getDefaultValueRepresentation().contains(t)) continue;
                    // code often points a few bytes into a defined string (stray pointer bytes before it)
                    List<Reference> refs = new ArrayList<>();
                    for (int k = 0; k < Math.min(d.getLength(), 8); k++)
                        for (Reference r : currentProgram.getReferenceManager().getReferencesTo(d.getAddress().add(k))) refs.add(r);
                    for (Reference r : refs) {
                        Function f = getFunctionContaining(r.getFromAddress());
                        if (f != null) fns.add(f);
                        // literal-pool word -> the function that loads it
                        for (Reference r2 : currentProgram.getReferenceManager().getReferencesTo(r.getFromAddress())) {
                            Function g = getFunctionContaining(r2.getFromAddress());
                            if (g != null) fns.add(g);
                        }
                    }
                }
            } else if (a.startsWith("0x")) {
                Function f = getFunctionContaining(toAddr(Long.decode(a)));
                if (f != null) fns.add(f); else println("no function at " + a);
            } else {
                for (Function f : currentProgram.getFunctionManager().getFunctions(true))
                    if (f.getName().equals(a)) fns.add(f);
            }
        }
        DecompInterface di = new DecompInterface();
        di.openProgram(currentProgram);
        for (Function f : fns) {
            DecompileResults r = di.decompileFunction(f, 60, monitor);
            String c = r.decompileCompleted() ? r.getDecompiledFunction().getC() : "// failed: " + r.getErrorMessage();
            String text = "// ===== " + f.getName(true) + " @ " + f.getEntryPoint() + "\n" + c;
            if (out != null) out.println(text); else println(text);
        }
        di.dispose();
        if (out != null) out.close();
        println("dp2q decomp: " + fns.size() + " functions");
    }
}
