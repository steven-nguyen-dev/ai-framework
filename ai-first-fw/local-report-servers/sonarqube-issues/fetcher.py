#!/usr/bin/env python3
"""Data fetching and caching engine for SonarQube Issues Explorer.

Sources:
A) PRIMARY (Read-Only): SonarQube Web API at https://sonarqube.anchanto.com (v2026.4).
   - Projects discovered dynamically (jpluger-* live per-area projects).
   - Issues with Clean Code taxonomy facets (Software Qualities, Impact Severities, Statuses).
   - Rule names, descriptions and remediation info (cached locally).
   - Project branches and measures (bugs, vulnerabilities, smells, SQALE debt).

B) SECONDARY (Read-Only): Local IDE SonarLint findings from H2 database
   ~/Library/Caches/JetBrains/IntelliJIdea*/sonarlint/storage/h2/sq-ide.mv.db
   - Extracted via H2Dump Java utility without locking or modifying IDE database.
   - Tagged as 'local' findings in unified dataset.

Pure Python 3 standard library (no pip dependencies required).
"""

from __future__ import annotations

import base64
import glob
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(HERE, "data.json")
RULES_CACHE_FILE = os.path.join(HERE, "rules_cache.json")

def find_theme_dir() -> str:
    candidates = [
        os.path.abspath(os.path.join(HERE, "..", "..", "local-theme")),
        os.path.abspath(os.path.join(HERE, "..", "local-theme")),
        os.path.abspath(os.path.join(HERE, "local-theme")),
    ]
    for c in candidates:
        if os.path.isdir(c):
            return c
    return candidates[0]

THEME_DIR = find_theme_dir()

DEFAULT_SONAR_URL = "https://sonarqube.anchanto.com"


def get_sonar_credentials() -> Tuple[Optional[str], str]:
    """Retrieves SONAR_TOKEN and SONAR_HOST_URL without ever logging or printing the token.
    Checks environment variable, ~/.jpluger-sonar.env, /Users/nguyennguyen.anchanto/.jpluger-sonar.env, and .env.
    """
    token = os.environ.get("SONAR_TOKEN")
    host_url = os.environ.get("SONAR_HOST_URL", DEFAULT_SONAR_URL).rstrip("/")

    if token:
        return token.strip(), host_url

    candidate_files = [
        os.path.expanduser("~/.jpluger-sonar.env"),
        "/Users/nguyennguyen.anchanto/.jpluger-sonar.env",
        os.path.join(HERE, ".env"),
        os.path.join(HERE, "..", ".env"),
    ]

    for path in candidate_files:
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("#") or not line:
                            continue
                        if line.startswith("SONAR_TOKEN="):
                            val = line.split("=", 1)[1].strip().strip("\"'")
                            if val:
                                token = val
                        elif line.startswith("SONAR_HOST_URL="):
                            hval = line.split("=", 1)[1].strip().strip("\"'")
                            if hval:
                                host_url = hval.rstrip("/")
                if token:
                    return token, host_url
            except Exception:
                pass

    return None, host_url


def make_sonar_request(endpoint: str, params: Optional[Dict[str, Any]] = None, timeout: int = 15) -> Dict[str, Any]:
    """Executes a strictly READ-ONLY GET request against the SonarQube Web API."""
    token, host_url = get_sonar_credentials()
    if not token:
        raise RuntimeError("SONAR_TOKEN not found in ~/.jpluger-sonar.env, .env, or environment.")

    url = f"{host_url}{endpoint}"
    if params:
        encoded_params = urllib.parse.urlencode(params, doseq=True)
        url = f"{url}?{encoded_params}"

    auth_bytes = f"{token}:".encode("utf-8")
    auth_header = "Basic " + base64.b64encode(auth_bytes).decode("utf-8")

    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", auth_header)
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "SonarQube-Local-Report-Server/1.0.0")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status != 200:
                raise RuntimeError(f"SonarQube API error: HTTP {response.status}")
            data = response.read().decode("utf-8")
            return json.loads(data)
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"SonarQube API HTTP {e.code} for {endpoint}: {err_msg}")
    except Exception as e:
        raise RuntimeError(f"SonarQube API connection failure for {endpoint}: {e}")


def load_rules_cache() -> Dict[str, Any]:
    """Loads cached rule definitions from disk."""
    if os.path.isfile(RULES_CACHE_FILE):
        try:
            with open(RULES_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_rules_cache(cache: Dict[str, Any]) -> None:
    """Saves rule definitions to disk cache."""
    try:
        with open(RULES_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        sys.stderr.write(f"[WARN] Failed to write rules cache: {e}\n")


def fetch_single_rule(rule_key: str) -> Tuple[str, Dict[str, Any]]:
    """Fetches details for a single rule from SonarQube."""
    try:
        data = make_sonar_request("/api/rules/show", {"key": rule_key}, timeout=8)
        rule = data.get("rule", {})
        return rule_key, {
            "name": rule.get("name", rule_key),
            "type": rule.get("type", "CODE_SMELL"),
            "severity": rule.get("severity", "INFO"),
            "cleanCodeAttributeCategory": rule.get("cleanCodeAttributeCategory"),
            "impacts": rule.get("impacts", []),
            "htmlDesc": rule.get("htmlDesc", ""),
            "descriptionSections": rule.get("descriptionSections", []),
            "scope": rule.get("scope", "MAIN"),
        }
    except Exception:
        return rule_key, {
            "name": rule_key,
            "type": "CODE_SMELL",
            "severity": "INFO",
            "cleanCodeAttributeCategory": "CONSISTENT",
            "impacts": [{"softwareQuality": "MAINTAINABILITY", "severity": "INFO"}],
            "htmlDesc": "",
            "descriptionSections": [],
            "scope": "MAIN",
        }


def ensure_rules_cached(rule_keys: List[str]) -> Dict[str, Any]:
    """Ensures all requested rule keys are in the cache, fetching missing ones in parallel."""
    cache = load_rules_cache()
    missing = [rk for rk in set(rule_keys) if rk and rk not in cache]

    if missing:
        sys.stderr.write(f"[*] Caching {len(missing)} rule definitions from SonarQube...\n")
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(fetch_single_rule, missing))
        for rk, rinfo in results:
            cache[rk] = rinfo
        save_rules_cache(cache)

    return cache


def discover_projects() -> List[Dict[str, Any]]:
    """Discovers all live per-area JPluger projects keyed jpluger-*.
    The umbrella 'Jpluger' project was deleted and is excluded.
    """
    data = make_sonar_request("/api/components/search", {"qualifiers": "TRK", "ps": 500})
    components = data.get("components", [])

    jpluger_projects = [
        c for c in components
        if c.get("key", "").startswith("jpluger-") and c.get("key") != "Jpluger"
    ]
    jpluger_projects.sort(key=lambda x: x.get("key", ""))
    return jpluger_projects


def fetch_project_branches(project_key: str) -> List[Dict[str, Any]]:
    """Fetches branches for a project."""
    try:
        data = make_sonar_request("/api/project_branches/list", {"project": project_key}, timeout=8)
        return data.get("branches", [])
    except Exception as e:
        sys.stderr.write(f"[WARN] Could not fetch branches for {project_key}: {e}\n")
        return []


def fetch_project_measures(project_key: str) -> Dict[str, Any]:
    """Fetches key code quality and debt measures for a project."""
    metric_keys = [
        "bugs",
        "vulnerabilities",
        "code_smells",
        "security_hotspots",
        "sqale_index",
        "sqale_rating",
        "reliability_rating",
        "security_rating",
        "ncloc",
        "coverage",
        "duplicated_lines_density",
    ]
    try:
        data = make_sonar_request(
            "/api/measures/component",
            {"component": project_key, "metricKeys": ",".join(metric_keys)},
            timeout=8,
        )
        measures = {}
        comp = data.get("component", {})
        for m in comp.get("measures", []):
            measures[m.get("metric")] = m.get("value")
        return measures
    except Exception as e:
        sys.stderr.write(f"[WARN] Could not fetch measures for {project_key}: {e}\n")
        return {}


def parse_effort_minutes(effort_str: Any) -> int:
    """Parses SonarQube effort representation (e.g. '15min', '2h 30min', '1d') into total minutes."""
    if not effort_str:
        return 0
    if isinstance(effort_str, (int, float)):
        return int(effort_str)

    total = 0
    parts = str(effort_str).strip().split()
    for p in parts:
        p = p.lower()
        if p.endswith("min"):
            num = p[:-3]
            if num.isdigit():
                total += int(num)
        elif p.endswith("h"):
            num = p[:-1]
            if num.isdigit():
                total += int(num) * 60
        elif p.endswith("d"):
            num = p[:-1]
            if num.isdigit():
                total += int(num) * 480
    return total


def format_effort_minutes(minutes: int) -> str:
    """Formats minutes into human-readable SonarQube effort string (e.g. '2h 15min')."""
    if not minutes or minutes <= 0:
        return "0min"
    days = minutes // 480
    rem = minutes % 480
    hours = rem // 60
    mins = rem % 60

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if mins > 0 or not parts:
        parts.append(f"{mins}min")
    return " ".join(parts)


def extract_module_from_path(file_path: str, project_key: str = "") -> str:
    """Extracts logical maven/component module from a file path."""
    if not file_path:
        return project_key or "general"
    clean_path = file_path.replace("\\", "/")
    if clean_path.startswith("jpluger-") and ":" in clean_path:
        clean_path = clean_path.split(":", 1)[1]
    parts = [p for p in clean_path.split("/") if p]
    if "src" in parts:
        idx = parts.index("src")
        if idx > 0:
            return parts[idx - 1]
    if len(parts) > 1:
        return parts[0]
    return project_key or "general"


def fetch_server_issues_for_project(
    project_key: str,
    project_name: str,
    rules_cache: Dict[str, Any],
    max_issues: int = 5000,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Fetches all server issues for a given project with full pagination and facets."""
    all_issues: List[Dict[str, Any]] = []
    facets_summary: Dict[str, Any] = {}
    page_size = 500
    page = 1

    _, host_url = get_sonar_credentials()

    while True:
        params = {
            "projects": project_key,
            "ps": page_size,
            "p": page,
            "facets": "impactSoftwareQualities,impactSeverities,cleanCodeAttributeCategories,severities,statuses,types,rules",
        }
        try:
            data = make_sonar_request("/api/issues/search", params, timeout=20)
        except Exception as e:
            sys.stderr.write(f"[WARN] Error fetching issues for {project_key} p.{page}: {e}\n")
            break

        if not facets_summary and "facets" in data:
            facets_summary = {f.get("property"): f.get("values", []) for f in data["facets"]}

        raw_issues = data.get("issues", [])
        for raw in raw_issues:
            rule_key = raw.get("rule", "")
            rule_meta = rules_cache.get(rule_key, {})
            rule_name = rule_meta.get("name", rule_key)

            impacts = raw.get("impacts", [])
            if not impacts and rule_meta.get("impacts"):
                impacts = rule_meta.get("impacts", [])

            # Primary software quality and impact severity
            software_qualities = [imp.get("softwareQuality") for imp in impacts if imp.get("softwareQuality")]
            if not software_qualities:
                itype = raw.get("type", "CODE_SMELL")
                if itype == "VULNERABILITY" or itype == "SECURITY_HOTSPOT":
                    software_qualities = ["SECURITY"]
                elif itype == "BUG":
                    software_qualities = ["RELIABILITY"]
                else:
                    software_qualities = ["MAINTAINABILITY"]

            primary_quality = software_qualities[0] if software_qualities else "MAINTAINABILITY"

            # Primary severity
            severities = [imp.get("severity") for imp in impacts if imp.get("severity")]
            impact_severity = severities[0] if severities else raw.get("severity", "INFO")

            # Clean component path
            comp = raw.get("component", "")
            file_path = comp.split(":", 1)[1] if ":" in comp else comp

            line = raw.get("line")
            if line is None and "textRange" in raw:
                line = raw["textRange"].get("startLine")
            if line is None:
                line = 1

            effort_str = raw.get("effort", raw.get("debt", "0min"))
            effort_mins = parse_effort_minutes(effort_str)

            issue_key = raw.get("key", "")
            server_link = f"{host_url}/project/issues?id={urllib.parse.quote(project_key)}&open={urllib.parse.quote(issue_key)}"

            normalized = {
                "id": issue_key,
                "key": issue_key,
                "project": project_key,
                "projectName": project_name,
                "branch": raw.get("branch", "main"),
                "rule": rule_key,
                "ruleName": rule_name,
                "message": raw.get("message", ""),
                "filePath": file_path,
                "line": int(line),
                "softwareQuality": primary_quality,
                "softwareQualities": software_qualities,
                "impactSeverity": impact_severity,
                "severity": raw.get("severity", impact_severity),
                "status": raw.get("issueStatus", raw.get("status", "OPEN")),
                "effort": effort_str,
                "effortMinutes": effort_mins,
                "type": raw.get("type", "CODE_SMELL"),
                "cleanCodeAttribute": raw.get("cleanCodeAttribute"),
                "cleanCodeAttributeCategory": raw.get("cleanCodeAttributeCategory"),
                "source": "server",
                "serverUrl": server_link,
                "module": extract_module_from_path(file_path, project_key),
                "creationDate": raw.get("creationDate"),
            }
            all_issues.append(normalized)

        if len(raw_issues) < page_size or len(all_issues) >= max_issues:
            break
        page += 1

    return all_issues, facets_summary


def discover_java_runtime() -> Optional[str]:
    """Finds a working Java runtime, prioritizing IntelliJ's bundled JBR."""
    candidates = [
        "/Applications/IntelliJ IDEA.app/Contents/jbr/Contents/Home/bin/java",
        os.path.expanduser("~/Applications/IntelliJ IDEA.app/Contents/jbr/Contents/Home/bin/java"),
    ]
    for c in candidates:
        if os.path.isfile(c) and os.access(c, os.X_OK):
            return c

    # System java
    if subprocess.call(["command", "-v", "java"], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
        return "java"
    return None


def discover_h2_jar() -> Optional[str]:
    """Finds the H2 JDBC driver jar inside SonarLint plugin installations."""
    base_dirs = [
        "/Users/nguyennguyen.anchanto/Library/Application Support/JetBrains",
        os.path.expanduser("~/Library/Application Support/JetBrains"),
    ]
    for b in base_dirs:
        if os.path.isdir(b):
            matches = glob.glob(f"{b}/**/plugins/sonarlint-intellij/**/h2-*.jar", recursive=True)
            if matches:
                # Prefer the sloop lib or direct lib
                return matches[0]
    return None


def discover_h2_database() -> Optional[str]:
    """Finds the SonarLint local H2 database file without locking."""
    candidates = [
        "/Users/nguyennguyen.anchanto/Library/Caches/JetBrains/IntelliJIdea2026.2/sonarlint/storage/h2/sq-ide.mv.db",
        os.path.expanduser("~/Library/Caches/JetBrains/IntelliJIdea2026.2/sonarlint/storage/h2/sq-ide.mv.db"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c

    # Search dynamically
    base = os.path.expanduser("~/Library/Caches/JetBrains")
    if os.path.isdir(base):
        matches = glob.glob(f"{base}/**/sonarlint/storage/h2/sq-ide.mv.db", recursive=True)
        if matches:
            return matches[0]

    return None


def extract_repo_path(scope: str) -> str:
    """Extracts local repository root path from IntelliJ configuration scope ID."""
    if not scope:
        return ""
    if "/.idea/" in scope:
        return scope.split("/.idea/")[0]
    if ".idea/" in scope:
        return scope.split(".idea/")[0]
    return ""


def fetch_local_ide_findings(rules_cache: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Dumps local findings from IntelliJ's SonarLint H2 database via H2Dump utility.
    Zero modifications, read-only AUTO_SERVER=TRUE connection.
    Gracefully handles absence or failure.
    """
    java_bin = discover_java_runtime()
    h2_jar = discover_h2_jar()
    h2_db = discover_h2_database()

    info_meta = {
        "available": False,
        "java": java_bin,
        "h2Jar": h2_jar,
        "dbPath": h2_db,
        "error": None,
        "count": 0,
    }

    if not java_bin:
        info_meta["error"] = "Java runtime (JBR) not found."
        return [], info_meta

    if not h2_jar:
        info_meta["error"] = "H2 driver jar not found in SonarLint plugin folder."
        return [], info_meta

    if not h2_db or not os.path.isfile(h2_db):
        info_meta["error"] = "SonarLint H2 database not found (IDE might not have run analysis yet)."
        return [], info_meta

    dump_class = os.path.join(HERE, "H2Dump.class")
    if not os.path.isfile(dump_class):
        # Compile H2Dump.java
        javac_bin = java_bin.replace("/bin/java", "/bin/javac")
        if not os.path.isfile(javac_bin):
            javac_bin = "javac"
        try:
            subprocess.run(
                [javac_bin, "-cp", h2_jar, os.path.join(HERE, "H2Dump.java")],
                cwd=HERE,
                check=True,
                capture_output=True,
                timeout=10,
            )
        except Exception as e:
            info_meta["error"] = f"Failed to compile H2Dump.java: {e}"
            return [], info_meta

    # Run H2Dump to temp JSON
    tmp_out = f"/tmp/sq_local_{os.getpid()}_{int(time.time())}.json"
    cp = f"{HERE}:{h2_jar}"
    db_prefix = h2_db[:-6] if h2_db.endswith(".mv.db") else h2_db

    try:
        proc = subprocess.run(
            [java_bin, "-cp", cp, "H2Dump", db_prefix, tmp_out],
            cwd=HERE,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if proc.returncode != 0:
            info_meta["error"] = f"H2Dump failed with code {proc.returncode}: {proc.stderr}"
            return [], info_meta

        if not os.path.isfile(tmp_out):
            info_meta["error"] = "H2Dump did not produce output JSON file."
            return [], info_meta

        with open(tmp_out, "r", encoding="utf-8") as f:
            data = json.load(f)

        if data.get("status") != "ok":
            info_meta["error"] = data.get("reason", "Unknown H2 error")
            return [], info_meta

        raw_known = data.get("knownFindings", [])
        raw_local_only = data.get("localOnlyIssues", [])

        normalized_local: List[Dict[str, Any]] = []

        # Process knownFindings
        for item in raw_known:
            rule_key = item.get("ruleKey", "")
            rule_meta = rules_cache.get(rule_key, {})
            rule_name = rule_meta.get("name", rule_key)

            impacts = rule_meta.get("impacts", [])
            sq_list = [imp.get("softwareQuality") for imp in impacts if imp.get("softwareQuality")]
            primary_sq = sq_list[0] if sq_list else "MAINTAINABILITY"

            sevs = [imp.get("severity") for imp in impacts if imp.get("severity")]
            primary_sev = sevs[0] if sevs else rule_meta.get("severity", "INFO")

            mod = item.get("module", "general")
            file_p = item.get("file", "")

            # Default effort
            effort_str = "15min"
            effort_mins = 15

            repo_p = extract_repo_path(item.get("scope", ""))
            norm = {
                "id": f"local-{item.get('id')}",
                "key": item.get("serverKey") or f"local-{item.get('id')}",
                "project": f"jpluger-{mod}" if not mod.startswith("jpluger-") else mod,
                "projectName": f"Local IDE ({mod})",
                "branch": "local-workspace",
                "rule": rule_key,
                "ruleName": rule_name,
                "message": item.get("message", ""),
                "filePath": file_p,
                "line": int(item.get("line") or 1),
                "softwareQuality": primary_sq,
                "softwareQualities": sq_list or [primary_sq],
                "impactSeverity": primary_sev,
                "severity": primary_sev,
                "status": "OPEN",
                "effort": effort_str,
                "effortMinutes": effort_mins,
                "type": rule_meta.get("type", "CODE_SMELL"),
                "cleanCodeAttribute": rule_meta.get("cleanCodeAttribute"),
                "cleanCodeAttributeCategory": rule_meta.get("cleanCodeAttributeCategory"),
                "source": "local",
                "serverUrl": "",
                "module": mod,
                "repoPath": repo_p,
                "creationDate": item.get("introDate"),
            }
            normalized_local.append(norm)

        # Process local_only
        for item in raw_local_only:
            rule_key = item.get("ruleKey", "")
            rule_meta = rules_cache.get(rule_key, {})
            repo_p = extract_repo_path(item.get("scope", ""))
            norm = {
                "id": f"local-only-{item.get('id')}",
                "key": f"local-only-{item.get('id')}",
                "project": f"jpluger-{item.get('module')}",
                "projectName": f"Local Only ({item.get('module')})",
                "branch": "local-workspace",
                "rule": rule_key,
                "ruleName": rule_meta.get("name", rule_key),
                "message": item.get("message", ""),
                "filePath": item.get("file", ""),
                "line": int(item.get("line") or 1),
                "softwareQuality": "MAINTAINABILITY",
                "softwareQualities": ["MAINTAINABILITY"],
                "impactSeverity": "INFO",
                "severity": "INFO",
                "status": "OPEN",
                "effort": "15min",
                "effortMinutes": 15,
                "type": "CODE_SMELL",
                "source": "local",
                "serverUrl": "",
                "module": item.get("module", "general"),
                "repoPath": repo_p,
                "creationDate": None,
            }
            normalized_local.append(norm)

        info_meta["available"] = True
        info_meta["count"] = len(normalized_local)
        return normalized_local, info_meta

    except Exception as ex:
        info_meta["error"] = str(ex)
        return [], info_meta
    finally:
        if os.path.isfile(tmp_out):
            try:
                os.remove(tmp_out)
            except Exception:
                pass


def fetch_all(force: bool = False) -> Dict[str, Any]:
    """Fetches full live dataset from SonarQube Server and Local H2 findings.
    Persists to data.json.
    """
    sys.stderr.write("[*] Discovering live SonarQube projects...\n")
    raw_projects = discover_projects()
    project_keys = [p["key"] for p in raw_projects]
    sys.stderr.write(f"[*] Discovered {len(raw_projects)} JPluger projects.\n")

    # Fetch branches and measures for each project
    projects_meta = []
    for p in raw_projects:
        pkey = p["key"]
        pname = p.get("name", pkey)
        branches = fetch_project_branches(pkey)
        measures = fetch_project_measures(pkey)
        projects_meta.append({
            "key": pkey,
            "name": pname,
            "description": p.get("description", ""),
            "branches": [b.get("name") for b in branches],
            "mainBranch": next((b.get("name") for b in branches if b.get("isMain")), "main"),
            "measures": measures,
        })

    # Fetch server issues for all projects
    sys.stderr.write("[*] Fetching live issues from SonarQube Server...\n")
    rules_cache = load_rules_cache()
    all_server_issues: List[Dict[str, Any]] = []
    facets_by_project: Dict[str, Any] = {}

    for p in projects_meta:
        pkey = p["key"]
        pname = p["name"]
        issues, pfacets = fetch_server_issues_for_project(pkey, pname, rules_cache)
        if issues:
            all_server_issues.extend(issues)
            facets_by_project[pkey] = pfacets
            sys.stderr.write(f"  ➜ {pkey}: {len(issues)} issues\n")

    # Collect all rule keys and ensure rule cache is warm
    rule_keys = [iss["rule"] for iss in all_server_issues]
    rules_cache = ensure_rules_cached(rule_keys)

    # Enrich server issues with full rule metadata
    for iss in all_server_issues:
        rk = iss.get("rule")
        if rk in rules_cache:
            rm = rules_cache[rk]
            iss["ruleName"] = rm.get("name", rk)

    # Fetch local IDE findings from H2 database
    sys.stderr.write("[*] Checking local IntelliJ SonarLint findings (Source B)...\n")
    local_issues, local_meta = fetch_local_ide_findings(rules_cache)
    if local_meta["available"]:
        sys.stderr.write(f"  ➜ Local findings loaded: {len(local_issues)} findings\n")
    else:
        sys.stderr.write(f"  ➜ Local findings status: {local_meta.get('error', 'Unavailable')}\n")

    # Combine issues
    combined_issues = all_server_issues + local_issues

    # Compute global statistics
    total_issues = len(combined_issues)
    server_count = len(all_server_issues)
    local_count = len(local_issues)

    quality_counts = {"SECURITY": 0, "RELIABILITY": 0, "MAINTAINABILITY": 0}
    severity_counts = {"BLOCKER": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}
    status_counts = {"OPEN": 0, "CONFIRMED": 0, "ACCEPTED": 0, "FALSE_POSITIVE": 0}
    total_effort_minutes = 0

    for iss in combined_issues:
        sq = iss.get("softwareQuality", "MAINTAINABILITY")
        quality_counts[sq] = quality_counts.get(sq, 0) + 1

        sev = iss.get("impactSeverity", "INFO")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

        st = iss.get("status", "OPEN")
        status_counts[st] = status_counts.get(st, 0) + 1

        total_effort_minutes += iss.get("effortMinutes", 0)

    repo_paths = sorted(list(set(i.get("repoPath") for i in combined_issues if i.get("repoPath"))))

    dataset = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "epoch": time.time(),
        "projects": projects_meta,
        "repoPaths": repo_paths,
        "issues": combined_issues,
        "totalIssues": total_issues,
        "serverCount": server_count,
        "localCount": local_count,
        "qualityCounts": quality_counts,
        "severityCounts": severity_counts,
        "statusCounts": status_counts,
        "totalEffortMinutes": total_effort_minutes,
        "totalEffortFormatted": format_effort_minutes(total_effort_minutes),
        "localMeta": local_meta,
        "rulesCache": rules_cache,
    }

    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(dataset, f)
        sys.stderr.write(f"[*] Successfully saved dataset to {DATA_FILE} ({total_issues} total issues)\n")
    except Exception as e:
        sys.stderr.write(f"[WARN] Failed to write data.json: {e}\n")

    return dataset


def extract_data_from_html(html_content: str) -> Optional[Dict[str, Any]]:
    """Extracts embedded JSON data from a static HTML report."""
    idx = html_content.find("REPORT_DATA")
    if idx == -1:
        return None
    brace_idx = html_content.find("{", idx)
    if brace_idx == -1:
        return None
    try:
        decoder = json.JSONDecoder()
        obj, _ = decoder.raw_decode(html_content, brace_idx)
        return obj
    except Exception:
        pass

    end_target = html_content.find("activeFilters", brace_idx)
    if end_target != -1:
        close_brace = html_content.rfind("}", brace_idx, end_target)
        if close_brace > brace_idx:
            try:
                return json.loads(html_content[brace_idx:close_brace + 1])
            except Exception:
                pass

    return None


def normalize_dataset(raw_data: Any) -> Dict[str, Any]:
    """Normalizes any dataset (current or legacy SonarQube export) into standard schema."""
    if not raw_data:
        return {"issues": [], "projects": [], "totalIssues": 0}

    if isinstance(raw_data, list):
        issues_raw = raw_data
        projects_raw = []
        rules_cache = {}
        local_meta = None
        timestamp = None
        epoch = None
    elif isinstance(raw_data, dict):
        issues_raw = raw_data.get("issues") or raw_data.get("data") or raw_data.get("findings") or []
        projects_raw = raw_data.get("projects") or []
        rules_cache = raw_data.get("rulesCache") or {}
        local_meta = raw_data.get("localMeta")
        timestamp = raw_data.get("timestamp")
        epoch = raw_data.get("epoch")
    else:
        return {"issues": [], "projects": [], "totalIssues": 0}

    normalized_issues: List[Dict[str, Any]] = []

    for iss in issues_raw:
        if not isinstance(iss, dict):
            continue

        file_path = iss.get("filePath") or iss.get("file") or iss.get("path") or ""
        if not file_path and iss.get("component"):
            comp = iss["component"]
            file_path = comp.split(":", 1)[1] if ":" in comp else comp

        project_key = (
            iss.get("project")
            or iss.get("projectKey")
            or (iss.get("component", "").split(":")[0] if ":" in iss.get("component", "") else "general")
        )

        module_name = iss.get("module") or extract_module_from_path(file_path, project_key)

        # Software quality normalization (handling legacy type BUG/VULNERABILITY/CODE_SMELL)
        sq = (iss.get("softwareQuality") or "").upper()
        if not sq:
            itype = (iss.get("type") or "").upper()
            if itype in ("VULNERABILITY", "SECURITY_HOTSPOT"):
                sq = "SECURITY"
            elif itype == "BUG":
                sq = "RELIABILITY"
            else:
                sq = "MAINTAINABILITY"
        if sq not in ("SECURITY", "RELIABILITY", "MAINTAINABILITY"):
            sq = "MAINTAINABILITY"

        # Severity normalization (handling legacy CRITICAL/MAJOR/MINOR)
        sev = (iss.get("impactSeverity") or iss.get("severity") or "INFO").upper()
        if sev == "CRITICAL":
            sev = "HIGH"
        elif sev == "MAJOR":
            sev = "MEDIUM"
        elif sev == "MINOR":
            sev = "LOW"
        if sev not in ("BLOCKER", "HIGH", "MEDIUM", "LOW", "INFO"):
            sev = "INFO"

        # Status normalization
        st = (iss.get("status") or iss.get("issueStatus") or "OPEN").upper()
        if st in ("REOPENED", "OPEN"):
            st = "OPEN"
        elif st in ("WONTFIX", "ACCEPTED"):
            st = "ACCEPTED"
        elif st in ("FALSE-POSITIVE", "FALSE_POSITIVE"):
            st = "FALSE_POSITIVE"
        elif st in ("CONFIRMED",):
            st = "CONFIRMED"
        else:
            st = "OPEN"

        line = iss.get("line")
        if line is None and "textRange" in iss and isinstance(iss["textRange"], dict):
            line = iss["textRange"].get("startLine")
        if line is None:
            line = 1

        rule_key = iss.get("rule") or iss.get("ruleKey") or "unknown"
        rule_name = iss.get("ruleName") or rules_cache.get(rule_key, {}).get("name", rule_key)

        effort_str = iss.get("effort") or iss.get("debt") or "0min"
        effort_mins = iss.get("effortMinutes")
        if effort_mins is None:
            effort_mins = parse_effort_minutes(effort_str)

        normalized_issues.append({
            "id": iss.get("id") or iss.get("key") or f"{project_key}-{file_path}-{line}",
            "key": iss.get("key") or iss.get("id") or "",
            "project": project_key,
            "projectName": iss.get("projectName", project_key),
            "branch": iss.get("branch", "main"),
            "rule": rule_key,
            "ruleName": rule_name,
            "message": iss.get("message") or iss.get("msg") or "",
            "filePath": file_path,
            "line": int(line),
            "softwareQuality": sq,
            "softwareQualities": [sq],
            "impactSeverity": sev,
            "severity": iss.get("severity", sev),
            "status": st,
            "effort": effort_str,
            "effortMinutes": int(effort_mins),
            "type": iss.get("type", "CODE_SMELL"),
            "cleanCodeAttribute": iss.get("cleanCodeAttribute"),
            "cleanCodeAttributeCategory": iss.get("cleanCodeAttributeCategory"),
            "source": iss.get("source") or ("local" if iss.get("isLocal") else "server"),
            "serverUrl": iss.get("serverUrl", ""),
            "module": module_name,
            "repoPath": iss.get("repoPath") or extract_repo_path(iss.get("scope", "")),
            "creationDate": iss.get("creationDate"),
        })

    # Projects
    if not projects_raw:
        pkeys = sorted(list(set(i["project"] for i in normalized_issues if i["project"])))
        projects_raw = [{"key": k, "name": k, "branches": ["main"], "mainBranch": "main"} for k in pkeys]

    repo_paths = (raw_data.get("repoPaths") if isinstance(raw_data, dict) else None) or sorted(list(set(i.get("repoPath") for i in normalized_issues if i.get("repoPath"))))
    srv_count = sum(1 for i in normalized_issues if i.get("source") == "server")
    loc_count = sum(1 for i in normalized_issues if i.get("source") == "local")

    return {
        "timestamp": timestamp or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "epoch": epoch or int(time.time()),
        "projects": projects_raw,
        "repoPaths": repo_paths,
        "issues": normalized_issues,
        "totalIssues": len(normalized_issues),
        "serverCount": srv_count,
        "localCount": loc_count,
        "qualityCounts": {
            "SECURITY": sum(1 for i in normalized_issues if i.get("softwareQuality") == "SECURITY"),
            "RELIABILITY": sum(1 for i in normalized_issues if i.get("softwareQuality") == "RELIABILITY"),
            "MAINTAINABILITY": sum(1 for i in normalized_issues if i.get("softwareQuality") == "MAINTAINABILITY"),
        },
        "severityCounts": {
            "BLOCKER": sum(1 for i in normalized_issues if i.get("impactSeverity") == "BLOCKER"),
            "HIGH": sum(1 for i in normalized_issues if i.get("impactSeverity") == "HIGH"),
            "MEDIUM": sum(1 for i in normalized_issues if i.get("impactSeverity") == "MEDIUM"),
            "LOW": sum(1 for i in normalized_issues if i.get("impactSeverity") == "LOW"),
            "INFO": sum(1 for i in normalized_issues if i.get("impactSeverity") == "INFO"),
        },
        "statusCounts": {
            "OPEN": sum(1 for i in normalized_issues if i.get("status") == "OPEN"),
            "CONFIRMED": sum(1 for i in normalized_issues if i.get("status") == "CONFIRMED"),
            "ACCEPTED": sum(1 for i in normalized_issues if i.get("status") == "ACCEPTED"),
            "FALSE_POSITIVE": sum(1 for i in normalized_issues if i.get("status") == "FALSE_POSITIVE"),
        },
        "rulesCache": rules_cache,
        "localMeta": local_meta,
    }


def load_export_file(file_path: str) -> Optional[Dict[str, Any]]:
    """Loads an export file (.html or .json), extracts data, and normalizes it."""
    if not os.path.isfile(file_path):
        return None
    try:
        if file_path.endswith(".html") or file_path.endswith(".htm"):
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            raw = extract_data_from_html(content)
            if raw:
                return normalize_dataset(raw)
        else:
            with open(file_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            return normalize_dataset(raw)
    except Exception as e:
        sys.stderr.write(f"[WARN] Error reading export file {file_path}: {e}\n")
    return None


def load_cached_data() -> Optional[Dict[str, Any]]:
    """Loads cached data from data.json or falls back to any existing export file."""
    if os.path.isfile(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
                return normalize_dataset(raw)
        except Exception:
            pass

    # Fallback to reading an existing export file if data.json is missing
    candidates = [
        os.path.join(HERE, "report.html"),
        os.path.join(HERE, "sonarqube-issues.html"),
        os.path.join(HERE, "sonarqube-issues-report.html"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            data = load_export_file(c)
            if data and data.get("issues"):
                return data

    return None


def generate_static_report(output_name: str = "report.html") -> str:
    """Generates a 100% self-contained static HTML report by inlining CSS and data."""
    template_path = os.path.join(HERE, "template.html")
    if not os.path.isfile(template_path):
        raise FileNotFoundError(f"template.html not found in {HERE}")

    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Read dataset
    data = load_cached_data()
    if not data:
        data = fetch_all()

    json_str = json.dumps(data)
    html = html.replace("__REPORT_DATA_JSON__", json_str)

    # Inline theme.css if available
    theme_css_file = os.path.join(THEME_DIR, "theme.css")
    theme_css_content = ""
    if os.path.isfile(theme_css_file):
        try:
            with open(theme_css_file, "r", encoding="utf-8") as tf:
                theme_css_content = tf.read()
        except Exception:
            pass

    if theme_css_content:
        # Replace <link rel="stylesheet" href="/theme/theme.css"> with inlined style
        link_pattern = re.compile(r'<link\s+rel="stylesheet"\s+href="[^"]*theme\.css"[^>]*>', re.IGNORECASE)
        inline_style = f"<style>\n/* Inlined local-theme.css */\n{theme_css_content}\n</style>"
        html = link_pattern.sub(inline_style, html)

    target_path = os.path.join(HERE, output_name)
    with open(target_path, "w", encoding="utf-8") as f:
        f.write(html)

    # Also generate sonarqube-issues.html offline export
    export_alias = os.path.join(HERE, "sonarqube-issues.html")
    with open(export_alias, "w", encoding="utf-8") as f:
        f.write(html)

    return target_path


if __name__ == "__main__":
    if "--static" in sys.argv or "--export" in sys.argv:
        p = generate_static_report()
        print(f"✔ Generated static report: {p}")
    else:
        d = fetch_all()
        print(f"✔ Fetched {d.get('totalIssues')} issues across {len(d.get('projects', []))} projects.")
