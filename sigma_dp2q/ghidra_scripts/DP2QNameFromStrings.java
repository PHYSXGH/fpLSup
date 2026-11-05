// Propose (dry) or apply names for FUN_ functions from the strings they reference.
// Strings are found through direct references and through literal-pool pointers (one level).
// Rules, in order:
//   self   a log/error string that starts with the function's own name: "Name(): ...", "Name: ...",
//          "E:Name: ...", "I:Name ..." (Milbeaut im_/dd_ style). All self-names in one function must agree.
//   func   a bare C identifier string referenced only by this function, used together with a format
//          string containing %s (the __func__ argument of "[UI]%s: ..." style logs).
// A name claimed by more than one function is not applied (listed as 'dup').
// args: <dry|apply> <out.csv>
// @category dp2q
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import java.io.PrintWriter;
import java.util.*;
import java.util.regex.*;

public class DP2QNameFromStrings extends GhidraScript {
    static final Pattern SELF = Pattern.compile(
        "^(?:--- )?(?:[EIW]:)?([A-Za-z_][A-Za-z0-9_]{4,63})(?:\\(\\))?\\s*[:.]\\s.*", Pattern.DOTALL);
    // Milbeaut driver style: "I:Im_PRO_FF_Start error. ch max value over"
    static final Pattern SELF_ERR = Pattern.compile(
        "^[EIW]:([A-Za-z_][A-Za-z0-9_]{4,63})(?:\\(\\))? error[.!]?\\s.*", Pattern.DOTALL);
    static final Pattern SRC = Pattern.compile("^C:/work/.*/([A-Za-z0-9_]+)\\.(?:c|cpp)$");
    static final Pattern IDENT = Pattern.compile("^[A-Za-z_][A-Za-z0-9_]{4,63}$");
    // words that start messages but are not function names
    static final Set<String> STOP = new HashSet<>(Arrays.asList(
        "Error", "ERROR", "Warning", "WARNING", "Info", "INFO", "Failed", "failed", "Assert", "Debug",
        "DEBUG", "Unknown", "Invalid", "Illegal", "Current", "Status", "Result", "Total", "Start", "Stop",
        "Sensor", "Imager", "System", "Version", "Total", "Value", "State", "Notice", "NOTICE"));

    Map<Address, Set<Function>> strUsers = new HashMap<>();

    String strAt(Address a) {
        Data d = getDataAt(a);
        if (d != null && d.hasStringValue()) return d.getDefaultValueRepresentation().replaceAll("^\"|\"$", "");
        return null;
    }

    // strings referenced by f: direct refs, and refs to pointer data that points at a string
    Map<Address, String> strings(Function f) {
        Map<Address, String> out = new LinkedHashMap<>();
        ReferenceManager rm = currentProgram.getReferenceManager();
        for (Address src : f.getBody().getAddresses(true)) {
            for (Reference r : rm.getReferencesFrom(src)) {
                Address t = r.getToAddress();
                String s = strAt(t);
                if (s == null) {
                    Data d = getDataAt(t);
                    if (d != null && d.isPointer() && d.getValue() instanceof Address p) { t = p; s = strAt(p); }
                }
                if (s != null) out.put(t, s);
            }
        }
        return out;
    }

    @Override
    public void run() throws Exception {
        String[] a = getScriptArgs();
        boolean apply = a[0].equals("apply");
        List<Function> fns = new ArrayList<>();
        Map<Function, Map<Address, String>> fs = new HashMap<>();
        for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
            monitor.checkCancelled();
            Map<Address, String> m = strings(f);
            if (m.isEmpty()) continue;
            fns.add(f); fs.put(f, m);
            for (Address s : m.keySet()) strUsers.computeIfAbsent(s, k -> new HashSet<>()).add(f);
        }
        Map<Function, String[]> prop = new LinkedHashMap<>();   // name, rule, evidence
        for (Function f : fns) {
            if (!f.getName().startsWith("FUN_")) continue;
            Map<Address, String> m = fs.get(f);
            Set<String> self = new TreeSet<>(); String selfEv = null;
            boolean fmtS = false; List<String> idents = new ArrayList<>(); Set<String> srcs = new TreeSet<>();
            for (Map.Entry<Address, String> e : m.entrySet()) {
                String s = e.getValue();
                Matcher mm = SELF.matcher(s);
                if (!mm.matches()) mm = SELF_ERR.matcher(s);
                if (mm.matches() && !STOP.contains(mm.group(1))
                        && (mm.group(1).contains("_") || mm.group(1).matches(".*[a-z][A-Z].*"))
                        && !s.contains(mm.group(1) + "() failed") && !s.contains(mm.group(1) + " failed")) {
                    self.add(mm.group(1)); if (selfEv == null) selfEv = s;
                }
                if (s.contains("%s")) fmtS = true;
                Matcher sm = SRC.matcher(s);
                if (sm.matches()) srcs.add(sm.group(1).toLowerCase());
                if (IDENT.matcher(s).matches() && strUsers.get(e.getKey()).size() == 1
                        && (s.contains("_") || s.matches(".*[a-z][A-Z].*"))) idents.add(s);
            }
            if (self.size() == 1) prop.put(f, new String[]{self.iterator().next(), "self", selfEv});
            else if (fmtS && idents.size() == 1) prop.put(f, new String[]{idents.get(0), "func", idents.get(0)});
            else if (idents.size() == 1 && idents.get(0).contains("_")
                    && !idents.get(0).matches("[A-Z0-9_]+"))   // ALL_CAPS = object/enum names (IM_PRC4, RES_LOW)
                prop.put(f, new String[]{idents.get(0), "func1", idents.get(0)});
            else if (srcs.size() == 1) {
                String src = srcs.iterator().next();
                prop.put(f, new String[]{src + "_" + f.getEntryPoint(), "file", src + ".c"});
            }
        }
        if (a[0].equals("dump")) {                     // every FUN_ without a proposal: its strings
            try (PrintWriter w = new PrintWriter(a[1])) {
                for (Function f : fns)
                    if (f.getName().startsWith("FUN_") && !prop.containsKey(f))
                        for (Map.Entry<Address, String> e : fs.get(f).entrySet())
                            w.printf("%s\t%d\t%s%n", f.getEntryPoint(), strUsers.get(e.getKey()).size(),
                                e.getValue().replace("\n", "\\n").replace("\t", " "));
            }
            println("dp2q names: dumped strings of unnamed functions");
            return;
        }
        Map<String, Integer> count = new HashMap<>();
        for (String[] p : prop.values()) count.merge(p[0], 1, Integer::sum);
        Set<String> existing = new HashSet<>();
        for (Function f : currentProgram.getFunctionManager().getFunctions(true)) existing.add(f.getName());
        int applied = 0, dup = 0; Map<String, Integer> byRule = new TreeMap<>();
        try (PrintWriter w = new PrintWriter(a[1])) {
            w.println("addr,old,new,rule,status,evidence");
            for (Map.Entry<Function, String[]> e : prop.entrySet()) {
                Function f = e.getKey(); String[] p = e.getValue();
                String status = count.get(p[0]) > 1 || existing.contains(p[0]) ? "dup" : "ok";
                if (status.equals("ok")) {
                    byRule.merge(p[1], 1, Integer::sum);
                    if (apply) {
                        f.setName(p[0], SourceType.ANALYSIS);
                        f.setComment((f.getComment() == null ? "" : f.getComment() + "\n")
                            + "name from string (" + p[1] + "): " + p[2]);
                        applied++;
                    }
                } else dup++;
                w.printf("%s,%s,%s,%s,%s,\"%s\"%n", f.getEntryPoint(), f.getName().equals(p[0]) ? "FUN_" : f.getName(),
                    p[0], p[1], status, p[2].replace("\"", "'").replace("\n", "\\n"));
            }
        }
        println("dp2q names: functions with strings " + fns.size() + ", proposals " + prop.size()
            + " " + byRule + ", dup " + dup + (apply ? ", applied " + applied : " (dry run)"));
    }
}
