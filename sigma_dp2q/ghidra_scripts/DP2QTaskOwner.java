// Assign functions to the task that reaches them. From every task_* entry, walk direct calls and
// function pointers referenced from the body (directly or via one literal-pool word), through thunks.
// The walk does not enter OS wrappers (tk_/td_/svc*) or "hub" functions with more than HUB callers.
// A function reached from exactly one task is "owned" by it; in apply mode owned FUN_/named functions
// are moved into namespace task_<NAME> (names are kept).
// args: <dry|apply> <out.csv> [hub=12]
// @category dp2q
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import java.io.PrintWriter;
import java.util.*;

public class DP2QTaskOwner extends GhidraScript {
    int hub;
    Map<Function, Integer> callers = new HashMap<>();

    Function real(Function f) {
        return f != null && f.isThunk() && f.getThunkedFunction(true) != null ? f.getThunkedFunction(true) : f;
    }

    boolean stop(Function f) {
        String n = f.getName();
        return n.startsWith("tk_") || n.startsWith("td_") || n.startsWith("svc") || n.startsWith("task_")
            || callers.getOrDefault(f, 0) > hub;
    }

    Set<Function> succ(Function f) {
        Set<Function> out = new LinkedHashSet<>();
        for (Function c : f.getCalledFunctions(monitor)) out.add(real(c));
        ReferenceManager rm = currentProgram.getReferenceManager();
        for (Address src : f.getBody().getAddresses(true))
            for (Reference r : rm.getReferencesFrom(src)) {
                if (r.getReferenceType().isCall()) continue;
                Address t = r.getToAddress();
                Function g = getFunctionAt(t);
                if (g == null) {
                    Data d = getDataAt(t);
                    if (d != null && d.isPointer())
                        for (Reference r2 : rm.getReferencesFrom(t)) { g = getFunctionAt(r2.getToAddress()); if (g != null) break; }
                }
                if (g != null && !g.equals(f)) out.add(real(g));
            }
        return out;
    }

    @Override
    public void run() throws Exception {
        String[] a = getScriptArgs();
        boolean apply = a[0].equals("apply");
        hub = a.length > 2 ? Integer.parseInt(a[2]) : 12;
        FunctionManager fm = currentProgram.getFunctionManager();
        List<Function> tasks = new ArrayList<>();
        for (Function f : fm.getFunctions(true)) {
            int n = 0;
            for (Function c : f.getCallingFunctions(monitor)) n++;
            callers.put(f, n);
            if (f.getName().startsWith("task_")) tasks.add(f);
        }
        Map<Function, Set<String>> reach = new HashMap<>();
        Map<String, Integer> size = new TreeMap<>();
        for (Function t : tasks) {
            String tn = t.getName().substring(5);
            Deque<Function> q = new ArrayDeque<>(List.of(t)); Set<Function> seen = new HashSet<>(q);
            while (!q.isEmpty()) {
                monitor.checkCancelled();
                Function f = q.poll();
                reach.computeIfAbsent(f, k -> new TreeSet<>()).add(tn);
                if (f != t && stop(f)) continue;
                for (Function g : succ(f)) if (g != null && seen.add(g)) q.add(g);
            }
            size.put(tn, seen.size());
        }
        Map<String, Integer> owned = new TreeMap<>(); int shared = 0, moved = 0;
        SymbolTable st = currentProgram.getSymbolTable();
        try (PrintWriter w = new PrintWriter(a[1])) {
            w.println("addr,name,owner,tasks");
            for (Map.Entry<Function, Set<String>> e : reach.entrySet()) {
                Function f = e.getKey(); Set<String> ts = e.getValue();
                if (f.getName().startsWith("task_") || stop(f) && callers.getOrDefault(f, 0) > hub) {
                    if (ts.size() > 1) shared++;
                    w.printf("%s,%s,%s,%s%n", f.getEntryPoint(), f.getName(), ts.size() == 1 ? "hub" : "shared", String.join(" ", ts));
                    continue;
                }
                if (ts.size() == 1) {
                    String o = ts.iterator().next();
                    owned.merge(o, 1, Integer::sum);
                    w.printf("%s,%s,%s,%s%n", f.getEntryPoint(), f.getName(), o, o);
                    if (apply && f.getParentNamespace().isGlobal()) {
                        Namespace ns = st.getNamespace("task_" + o, null);
                        if (ns == null) ns = st.createNameSpace(null, "task_" + o, SourceType.ANALYSIS);
                        f.setParentNamespace(ns); moved++;
                    }
                } else {
                    shared++;
                    w.printf("%s,%s,shared,%s%n", f.getEntryPoint(), f.getName(), String.join(" ", ts));
                }
            }
        }
        int total = 0; for (int v : owned.values()) total += v;
        println("dp2q owner: tasks " + tasks.size() + ", reached " + reach.size() + ", owned " + total
            + ", shared " + shared + (apply ? ", moved " + moved : " (dry)"));
        println("owned per task: " + owned);
        println("reach per task: " + size);
    }
}
