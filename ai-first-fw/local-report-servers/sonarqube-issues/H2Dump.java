import java.io.*;
import java.nio.charset.StandardCharsets;
import java.sql.*;
import java.time.Instant;
import java.util.*;

/**
 * H2Dump - Read-Only SonarLint Local Database Findings Extractor
 * Connects to IntelliJ IDEA SonarLint H2 database in read-only mode (AUTO_SERVER=TRUE)
 * and dumps local findings to JSON. Zero side-effects on IDE or database.
 */
public class H2Dump {

    public static void main(String[] args) {
        String dbPath = args.length > 0 && !args[0].isEmpty() ? args[0] : findDefaultDbPath();
        if (dbPath.endsWith(".mv.db")) {
            dbPath = dbPath.substring(0, dbPath.length() - 6);
        }

        String outputPath = args.length > 1 && !args[1].isEmpty() ? args[1] : null;

        File dbFile = new File(dbPath + ".mv.db");
        if (!dbFile.exists()) {
            writeResult(outputPath, "{\"status\":\"missing\",\"reason\":\"H2 database file not found: " + escape(dbPath + ".mv.db") + "\",\"knownFindings\":[],\"localOnlyIssues\":[]}");
            return;
        }

        String url = "jdbc:h2:file:" + dbPath + ";AUTO_SERVER=TRUE";

        try {
            Class.forName("org.h2.Driver");
            try (Connection conn = DriverManager.getConnection(url, "sa", "")) {
                conn.setReadOnly(true);

                StringBuilder sb = new StringBuilder(1024 * 1024 * 8);
                sb.append("{\n");
                sb.append("  \"status\": \"ok\",\n");
                sb.append("  \"dbPath\": \"").append(escape(dbPath)).append("\",\n");
                sb.append("  \"timestamp\": \"").append(Instant.now().toString()).append("\",\n");

                // 1. KNOWN_FINDINGS (local analysis findings)
                sb.append("  \"knownFindings\": [\n");
                int knownCount = 0;
                try (Statement stmt = conn.createStatement();
                     ResultSet rs = stmt.executeQuery(
                         "SELECT id, configuration_scope_id, ide_relative_file_path, server_key, rule_key, message, introduction_date, finding_type, line, start_line " +
                         "FROM KNOWN_FINDINGS ORDER BY introduction_date DESC"
                     )) {
                    boolean first = true;
                    while (rs.next()) {
                        if (!first) sb.append(",\n");
                        first = false;
                        sb.append("    {");
                        sb.append("\"id\":\"").append(rs.getString("id")).append("\",");
                        String scope = rs.getString("configuration_scope_id");
                        sb.append("\"scope\":\"").append(escape(scope)).append("\",");
                        sb.append("\"module\":\"").append(extractModule(scope)).append("\",");
                        sb.append("\"file\":\"").append(escape(rs.getString("ide_relative_file_path"))).append("\",");
                        String sk = rs.getString("server_key");
                        sb.append("\"serverKey\":").append(sk == null ? "null" : "\"" + escape(sk) + "\"").append(",");
                        sb.append("\"ruleKey\":\"").append(escape(rs.getString("rule_key"))).append("\",");
                        sb.append("\"message\":\"").append(escape(rs.getString("message"))).append("\",");
                        String intro = rs.getString("introduction_date");
                        sb.append("\"introDate\":").append(intro == null ? "null" : "\"" + escape(intro) + "\"").append(",");
                        int line = rs.getInt("line");
                        if (line <= 0) line = rs.getInt("start_line");
                        sb.append("\"line\":").append(line).append(",");
                        sb.append("\"source\":\"local\"");
                        sb.append("}");
                        knownCount++;
                    }
                } catch (Exception ex) {
                    System.err.println("Warning querying KNOWN_FINDINGS: " + ex.getMessage());
                }
                sb.append("\n  ],\n");

                // 2. LOCAL_ONLY_ISSUES
                sb.append("  \"localOnlyIssues\": [\n");
                int localOnlyCount = 0;
                try (Statement stmt = conn.createStatement();
                     ResultSet rs = stmt.executeQuery(
                         "SELECT id, configuration_scope_id, server_relative_path, rule_key, message, line, start_line, comment " +
                         "FROM LOCAL_ONLY_ISSUES ORDER BY id"
                     )) {
                    boolean first = true;
                    while (rs.next()) {
                        if (!first) sb.append(",\n");
                        first = false;
                        sb.append("    {");
                        sb.append("\"id\":\"").append(rs.getString("id")).append("\",");
                        String scope = rs.getString("configuration_scope_id");
                        sb.append("\"scope\":\"").append(escape(scope)).append("\",");
                        sb.append("\"module\":\"").append(extractModule(scope)).append("\",");
                        sb.append("\"file\":\"").append(escape(rs.getString("server_relative_path"))).append("\",");
                        sb.append("\"ruleKey\":\"").append(escape(rs.getString("rule_key"))).append("\",");
                        sb.append("\"message\":\"").append(escape(rs.getString("message"))).append("\",");
                        String comm = rs.getString("comment");
                        sb.append("\"comment\":").append(comm == null ? "null" : "\"" + escape(comm) + "\"").append(",");
                        int line = rs.getInt("line");
                        if (line <= 0) line = rs.getInt("start_line");
                        sb.append("\"line\":").append(line).append(",");
                        sb.append("\"source\":\"local_only\"");
                        sb.append("}");
                        localOnlyCount++;
                    }
                } catch (Exception ex) {
                    System.err.println("Warning querying LOCAL_ONLY_ISSUES: " + ex.getMessage());
                }
                sb.append("\n  ],\n");

                sb.append("  \"knownCount\": ").append(knownCount).append(",\n");
                sb.append("  \"localOnlyCount\": ").append(localOnlyCount).append("\n");
                sb.append("}\n");

                writeResult(outputPath, sb.toString());
            }
        } catch (Exception e) {
            String err = escape(e.getClass().getName() + ": " + e.getMessage());
            writeResult(outputPath, "{\"status\":\"error\",\"reason\":\"" + err + "\",\"knownFindings\":[],\"localOnlyIssues\":[]}");
        }
    }

    private static String findDefaultDbPath() {
        String home = System.getProperty("user.home", "/Users/nguyennguyen.anchanto");
        if (home.contains(".antigravity")) {
            home = "/Users/nguyennguyen.anchanto";
        }
        File cacheDir = new File(home, "Library/Caches/JetBrains");
        if (cacheDir.isDirectory()) {
            File[] files = cacheDir.listFiles();
            if (files != null) {
                for (File f : files) {
                    if (f.getName().startsWith("IntelliJIdea")) {
                        File db = new File(f, "sonarlint/storage/h2/sq-ide.mv.db");
                        if (db.exists()) {
                            return new File(f, "sonarlint/storage/h2/sq-ide").getAbsolutePath();
                        }
                    }
                }
            }
        }
        return home + "/Library/Caches/JetBrains/IntelliJIdea2026.2/sonarlint/storage/h2/sq-ide";
    }

    private static String extractModule(String scope) {
        if (scope == null) return "unknown";
        int idx = scope.lastIndexOf("misc.xml_");
        if (idx >= 0) {
            return escape(scope.substring(idx + 9));
        }
        int slash = scope.lastIndexOf('/');
        if (slash >= 0) {
            return escape(scope.substring(slash + 1));
        }
        return escape(scope);
    }

    private static String escape(String s) {
        if (s == null) return "";
        StringBuilder sb = new StringBuilder(s.length() + 16);
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '\\': sb.append("\\\\"); break;
                case '"': sb.append("\\\""); break;
                case '\b': sb.append("\\b"); break;
                case '\f': sb.append("\\f"); break;
                case '\n': sb.append("\\n"); break;
                case '\r': sb.append("\\r"); break;
                case '\t': sb.append("\\t"); break;
                default:
                    if (c < ' ') {
                        String t = "000" + Integer.toHexString(c);
                        sb.append("\\u").append(t.substring(t.length() - 4));
                    } else {
                        sb.append(c);
                    }
            }
        }
        return sb.toString();
    }

    private static void writeResult(String outputPath, String content) {
        if (outputPath == null || outputPath.equals("-")) {
            System.out.println(content);
        } else {
            try (FileOutputStream fos = new FileOutputStream(outputPath);
                 OutputStreamWriter osw = new OutputStreamWriter(fos, StandardCharsets.UTF_8);
                 BufferedWriter bw = new BufferedWriter(osw)) {
                bw.write(content);
            } catch (IOException e) {
                System.err.println("Failed to write output to " + outputPath + ": " + e.getMessage());
                System.out.println(content);
            }
        }
    }
}
