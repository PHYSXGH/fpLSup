// How many defined strings are referenced from code, and how many of those code refs come from functions.
// @category dp2q
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;

public class DP2QStrRefs extends GhidraScript {
    @Override
    public void run() throws Exception {
        int strings = 0, referenced = 0, fromFn = 0;
        ReferenceManager rm = currentProgram.getReferenceManager();
        for (Data d : currentProgram.getListing().getDefinedData(true)) {
            if (!d.hasStringValue()) continue;
            strings++;
            boolean r = false, f = false;
            for (Reference ref : rm.getReferencesTo(d.getAddress())) {
                r = true;
                if (getFunctionContaining(ref.getFromAddress()) != null) f = true;
            }
            if (r) referenced++;
            if (f) fromFn++;
        }
        println(String.format("strings %d, referenced %d, referenced from a function %d", strings, referenced, fromFn));
    }
}
