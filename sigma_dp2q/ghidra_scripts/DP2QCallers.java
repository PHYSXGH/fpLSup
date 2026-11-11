// List callers (function + from-addr) of each address argument. @category dp2q
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.*;
public class DP2QCallers extends GhidraScript {
  public void run() throws Exception {
    for (String a : getScriptArgs()) {
      Address t = toAddr(Long.decode(a));
      println("== callers of " + a + " ==");
      for (Reference r : currentProgram.getReferenceManager().getReferencesTo(t)) {
        Function f = getFunctionContaining(r.getFromAddress());
        println("  from " + r.getFromAddress() + "  " + (f!=null?f.getName():"(none)") + "  " + r.getReferenceType());
      }
    }
  }
}
