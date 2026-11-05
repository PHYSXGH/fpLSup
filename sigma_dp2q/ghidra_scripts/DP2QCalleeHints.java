// Module hints for unnamed functions: if a FUN_ function calls >= 2 named functions and they all share
// one module prefix (first two '_' parts, e.g. Im_JPEG, dd_hdmac0, System_Func), add a comment
// "module hint: <prefix> (calls a, b, ...)". Names are not changed. OS wrappers/stubs are ignored.
// args: <dry|apply> <out.csv>
// @category dp2q
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import java.io.PrintWriter;
import java.util.*;

public class DP2QCalleeHints extends GhidraScript {
    static String prefix(String n) {
        String base = n.replaceAll("_[0-9a-fA-F]{8}$", "");     // file-rule names: dd_hdmac1_40046482
        String[] p = base.split("_");
        if (p.length < 2) return null;
        return p[0] + "_" + p[1];
    }

    @Override
    public void run() throws Exception {
        String[] a = getScriptArgs();
        boolean apply = a[0].equals("apply");
        Map<String, Integer> byPrefix = new TreeMap<>(); int n = 0;
        try (PrintWriter w = new PrintWriter(a[1])) {
            w.println("addr,name,hint,callees");
            for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
                if (!f.getName().startsWith("FUN_")) continue;
                Set<String> names = new TreeSet<>(); boolean unnamedOrMixed = false;
                for (Function c : f.getCalledFunctions(monitor)) {
                    if (c.isThunk() && c.getThunkedFunction(true) != null) c = c.getThunkedFunction(true);
                    String cn = c.getName();
                    if (cn.startsWith("FUN_") || cn.startsWith("tk_") || cn.startsWith("td_")
                        || cn.startsWith("svc") || cn.startsWith("task_")) continue;
                    names.add(cn);
                }
                if (names.size() < 2) continue;
                Set<String> pre = new TreeSet<>();
                for (String cn : names) { String p = prefix(cn); pre.add(p == null ? "?" : p); }
                if (pre.size() != 1 || pre.contains("?")) continue;
                String p = pre.iterator().next();
                String ev = String.join(" ", names);
                w.printf("%s,%s,%s,%s%n", f.getEntryPoint(), f.getName(true), p, ev);
                byPrefix.merge(p, 1, Integer::sum); n++;
                if (apply) {
                    String c = f.getComment();
                    String h = "module hint: " + p + " (calls " + String.join(", ", names) + ")";
                    if (c == null || !c.contains("module hint:")) f.setComment(c == null ? h : c + "\n" + h);
                }
            }
        }
        println("dp2q hints: " + n + (apply ? " applied" : " (dry)") + " " + byPrefix);
    }
}
