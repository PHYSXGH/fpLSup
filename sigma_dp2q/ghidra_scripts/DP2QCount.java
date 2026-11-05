// Print the function count as "dp2q count: N" (used by the pipeline to iterate analysis).
// @category dp2q
import ghidra.app.script.GhidraScript;

public class DP2QCount extends GhidraScript {
    @Override
    public void run() throws Exception {
        println("dp2q count: " + currentProgram.getFunctionManager().getFunctionCount());
    }
}
