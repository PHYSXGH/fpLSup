// Rename functions from a CSV addr,name[,comment]. An empty name restores the default FUN_ name.
// args: <renames.csv>
// @category dp2q
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.SourceType;
import java.nio.file.*;

public class DP2QRename extends GhidraScript {
    @Override
    public void run() throws Exception {
        int n = 0;
        for (String line : Files.readAllLines(Paths.get(getScriptArgs()[0]))) {
            line = line.trim();
            if (line.isEmpty() || line.startsWith("#")) continue;
            String[] f = line.split(",", 3);
            Function fn = getFunctionAt(toAddr(Long.decode(f[0])));
            if (fn == null) { println("no function at " + f[0]); continue; }
            if (f[1].isEmpty()) fn.setName(null, SourceType.DEFAULT);
            else fn.setName(f[1], SourceType.USER_DEFINED);
            fn.setComment(f.length > 2 ? f[2] : null);
            n++;
        }
        println("dp2q rename: " + n);
    }
}
