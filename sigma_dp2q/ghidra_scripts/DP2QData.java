// Mark repetitive regions (from tools/data_regions.py: CSV start,end exclusive) as byte arrays so
// auto-analysis does not disassemble them. Functions starting inside a region are removed first.
// args: <regions.csv>
// @category dp2q
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.data.*;
import ghidra.program.model.listing.*;
import java.nio.file.*;

public class DP2QData extends GhidraScript {
    @Override
    public void run() throws Exception {
        int regions = 0, removed = 0;
        for (String line : Files.readAllLines(Paths.get(getScriptArgs()[0]))) {
            line = line.trim();
            if (line.isEmpty() || line.startsWith("#")) continue;
            String[] f = line.split(",");
            Address a = toAddr(Long.decode(f[0])), b = toAddr(Long.decode(f[1]) - 1);
            AddressSet set = new AddressSet(a, b);
            for (Function fn : currentProgram.getFunctionManager().getFunctions(set, true)) {
                removeFunction(fn); removed++;
            }
            clearListing(set);
            int len = (int) (b.subtract(a) + 1);
            createData(a, new ArrayDataType(ByteDataType.dataType, len, 1));
            createLabel(a, String.format("data_rep_%08X", a.getOffset()), true);
            regions++;
        }
        println("dp2q data: " + regions + " regions marked, " + removed + " functions removed");
    }
}
