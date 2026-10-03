"""Table tests for the testbed PreToolUse guard."""

import base64
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import guard  # noqa: E402

HOST = "test.concavoi.com"
B64_HOST = base64.b64encode(f"https://{HOST}/api/lease".encode()).decode()
REPO = os.path.expanduser("~/Projects/lv1-servers")

BLOCKED = [
    # direct calls
    ("curl host", f"curl -s https://{HOST}/demo/__testbed/health"),
    ("wget host", f"wget -qO- https://{HOST}/api/lease"),
    ("absolute curl", f"/usr/bin/curl https://{HOST}/x"),
    ("http port", "curl http://127.0.0.1:23000/api/servers"),
    ("localhost mock port", "curl localhost:23104/amazon/__testbed/stores"),
    ("nc to port", "printf 'GET / HTTP/1.0\\r\\n\\r\\n' | nc localhost 23001"),
    ("admin api path", "curl -X POST $BASE/api/mocks/amazon/rollback"),
    ("runtime api path", "curl $BASE/amazon/__testbed/reset"),
    ("auth header", "curl -H 'X-Auth-Token: abc' $URL"),
    ("call log", "curl $BASE/amazon/log/data"),
    # quoting and expansion tricks
    ("split quotes", "curl https://test.conc'av'oi.com/x"),
    ("double quote split", 'curl "https://test.con""cavoi.com/x"'),
    ("backslash split", "curl https://test.conc\\avoi.com/x"),
    ("ansi-c hex", "curl $'https://test.\\x63oncavoi.com/x'"),
    ("printf octal", "curl $(printf 'test.\\143oncavoi.com')"),
    ("command substitution", f"H=$(echo {HOST}); curl https://$H/"),
    ("bash -c", f"bash -c 'curl https://{HOST}/'"),
    ("env indirection", f"export H={HOST}; curl \"https://$H/api/lease\""),
    ("base64 host", f"curl $(echo {B64_HOST} | base64 -d)"),
    ("hex host", "curl $(echo 746573742e636f6e6361766f692e636f6d | xxd -r -p)"),
    ("reversed host", "curl https://$(echo moc.iovacnoc.tset | rev)/"),
    ("python heredoc urllib",
     "python3 - <<EOF\nimport urllib.request\nurllib.request.urlopen('https://test.concavoi.com/api/lease')\nEOF"),
    ("python string concat", "python3 -c \"import requests; requests.get('https://test.' + 'concavoi' + '.com')\""),
    ("node fetch", f"node -e \"fetch('https://{HOST}/api/lease')\""),
    # secrets
    ("cat testbed.env", "cat ~/.config/lv1-testbed/testbed.env"),
    ("source testbed.env", "source ~/.config/lv1-testbed/testbed.env && echo ok"),
    ("glob config dir", "cat ~/.config/lv1-*/*.env"),
    ("glob config segment", "cat ~/.config/*/testbed.env"),
    ("cd into config", "cd ~/.config && ls"),
    ("grep config dir", "grep -r ADMIN ~/.config/lv1-testbed"),
    ("mcp secrets cat", "cat ~/.mcp/.testbed.env"),
    ("mcp secrets home var", "cat $HOME/.mcp/.wiki.env"),
    ("mcp secrets source", "set -a; . ~/.mcp/.drive.env; set +a"),
    ("mcp dir listing", "ls -la ~/.mcp"),
    ("mcp glob", "cat ~/.m*/.t*.env"),
    ("mcp split quotes", "cat ~/'.m'cp/.testbed.env"),
    ("grep home for secrets", "grep -r TESTBED ~"),
    ("admin password var", "echo $ADMIN_PASSWORD"),
    ("path key var", "echo $PATH_KEY"),
    ("testbed api token", "printenv TESTBED_API_TOKEN"),
    ("testbed path key", "echo ${TESTBED_PATH_KEY}"),
    ("env grep", "env | grep ADMIN"),
    ("printenv dump", "printenv | grep -i token"),
    ("ps environment", "ps eww -ax | grep testbed"),
    # engine
    ("cli run", "cd ~/Projects/lv1-servers/testbed-dev && python3 suite/cli.py run --target amazon"),
    ("cli mocks push", "python3 suite/cli.py mocks push amazon"),
    ("cli validate", "python suite/cli.py --validate cases/x.yaml"),
    ("cli module", "python3 -m suite.cli --list"),
    ("client import", "python3 -c 'from suite.adapters import testbed_client'"),
    ("sync import", "python3 -c 'import suite.commands.sync'"),
]

ALLOWED = [
    ("ls", "ls -la"),
    ("git status", "git status --short"),
    ("git add", "git add guard/"),
    ("git commit message names host", f"git commit -m 'drop {HOST} calls from cli.py'"),
    ("git commit heredoc message",
     "git commit -m \"$(cat <<'EOF'\nfeat: route __testbed calls via MCP, not cli.py\n\nEOF\n)\""),
    ("git log grep", "git log --oneline --grep concavoi"),
    ("git diff engine", "git diff -- suite/cli.py"),
    ("grep repo for host", f"grep -rn '{HOST}' {REPO}/testbed-dev"),
    ("rg repo for secret name", f"rg -n ADMIN_PASSWORD -g '*.py' {REPO}"),
    ("git grep cli", "git grep -n 'cli.py'"),
    ("unittest", "python -m unittest discover -s suite/tests"),
    ("unittest in dir", f"cd {REPO}/testbed-dev && python3 -m unittest suite.tests.test_guard"),
    ("other config", "cat ~/.config/gh/hosts.yml"),
    ("webpack config", "node webpack.config.js"),
    ("mcp json", "cat .mcp.json"),
    ("lv1-mcp repo", "ls ~/Projects/ai-framework/lv1-mcp/testbed"),
    ("set -e", "set -euo pipefail; echo hi"),
    ("env prefix", "env FOO=1 python3 -c 'print(1)'"),
    ("ps aux", "ps aux | grep python"),
    ("jira id", "echo IA-23001"),
    ("plain python", "python3 -c 'print(2+2)'"),
    ("other host", "curl -s https://example.com"),
]


# Evasions a text guard cannot see. They stay here so a fix shows up as a failing test.
KNOWN_GAPS = [
    ("host split across variables", "A=test.conc; B=avoi.com; curl https://$A$B/"),
    ("host assembled by python chr", "python3 -c \"print(''.join(map(chr,[116,101,115,116])))\""),
    ("host read from a data file", "curl \"https://$(cat host.txt)/\""),
    ("unit test that calls the server", "python -m unittest suite.tests.test_x"),
]


class GuardTable(unittest.TestCase):
    def test_blocked(self):
        for name, cmd in BLOCKED:
            with self.subTest(name=name):
                self.assertIsNotNone(guard.check(cmd, REPO), cmd)

    def test_allowed(self):
        for name, cmd in ALLOWED:
            with self.subTest(name=name):
                self.assertIsNone(guard.check(cmd, REPO), cmd)

    def test_known_gaps_still_pass(self):
        for name, cmd in KNOWN_GAPS:
            with self.subTest(name=name):
                self.assertIsNone(guard.check(cmd, REPO), cmd)

    def test_reason_names_the_mcp_tool(self):
        cases = {
            "python3 suite/cli.py mocks push amazon": "mocks_push",
            "python3 suite/cli.py --validate x.yaml": "suite_validate",
            "python3 suite/cli.py run --target amazon": "run_start",
            "curl $BASE/api/mocks/amazon/rollback": "mocks_rollback",
            "curl $BASE/amazon/__testbed/stores": "stores_get",
            "curl $BASE/api/lease": "lease_status",
            "cat ~/.mcp/.testbed.env": "never returns the values",
        }
        for cmd, tool in cases.items():
            with self.subTest(cmd=cmd):
                self.assertIn(tool, guard.check(cmd, REPO))


class GuardScripts(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = self.dir.name

    def tearDown(self):
        self.dir.cleanup()

    def write(self, name, body, executable=False):
        path = os.path.join(self.root, name)
        with open(path, "w") as fh:
            fh.write(body)
        if executable:
            os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
        return path

    def test_python_script_calling_api(self):
        self.write("probe.py", f"import urllib.request\nurllib.request.urlopen('https://{HOST}/api/lease')\n")
        self.assertIsNotNone(guard.check("python3 probe.py", self.root))

    def test_executable_shell_script(self):
        self.write("probe.sh", "#!/bin/sh\ncurl localhost:23000/api/servers\n", executable=True)
        self.assertIsNotNone(guard.check("./probe.sh", self.root))

    def test_script_calling_another_script(self):
        self.write("inner.sh", "cat ~/.mcp/.testbed.env\n")
        self.write("outer.sh", "bash inner.sh\n")
        self.assertIsNotNone(guard.check("bash outer.sh", self.root))

    def test_clean_script_runs(self):
        self.write("ok.py", "print('hello')\n")
        self.assertIsNone(guard.check("python3 ok.py", self.root))

    def test_unittest_does_not_scan_test_files(self):
        self.write("test_x.py", f"URL = 'https://{HOST}'  # fixture text only\n")
        self.assertIsNone(guard.check("python3 -m unittest test_x", self.root))

    def test_cat_of_doc_is_not_a_script_run(self):
        self.write("README.md", f"Served at https://{HOST}\n")
        self.assertIsNone(guard.check("cat README.md", self.root))


class GuardHook(unittest.TestCase):
    """Runs guard.py as Claude Code would, through stdin and stdout."""

    def run_hook(self, payload):
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "guard.py")
        out = subprocess.run([sys.executable, script], input=json.dumps(payload),
                             capture_output=True, text=True, check=True)
        return out.stdout

    def test_deny_json(self):
        out = json.loads(self.run_hook({"tool_name": "Bash", "cwd": REPO,
                                        "tool_input": {"command": f"curl https://{HOST}"}}))
        self.assertEqual("deny", out["hookSpecificOutput"]["permissionDecision"])

    def test_allow_is_silent(self):
        self.assertEqual("", self.run_hook({"tool_name": "Bash", "tool_input": {"command": "ls"}}))

    def test_other_tools_pass(self):
        self.assertEqual("", self.run_hook({"tool_name": "Edit", "tool_input": {"file_path": "x"}}))


if __name__ == "__main__":
    unittest.main()
