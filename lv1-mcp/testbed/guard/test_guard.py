"""Table tests for the testbed PreToolUse guard."""

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
CWD = os.path.expanduser("~")

BLOCKED = [
    # key files
    ("cat key file", "cat ~/.mcp/.testbed.env"),
    ("source key file", "set -a; . $HOME/.mcp/.testbed.env; set +a"),
    ("key file after cd", "cd ~/.mcp && cat .testbed.env"),
    ("config dir listing", "ls ~/.config/lv1-testbed/"),
    ("config dir bare", "cat ~/.config/lv1-testbed"),
    ("config dir quoted", "ls '~/.config/lv1-testbed'"),
    ("config file", "cat ~/.config/lv1-testbed/testbed.env"),
    ("key file split quotes", "cat ~/.mcp/.test'bed.env'"),
    # mock server host, admin API, ports
    ("curl host", f"curl -s https://{HOST}/demo/health"),
    ("wget host", f"wget -qO- https://{HOST}/"),
    ("split quotes", "curl https://test.conc'av'oi.com/x"),
    ("double quote split", 'curl "https://test.con""cavoi.com/x"'),
    ("backslash split", "curl https://test.conc\\avoi.com/x"),
    ("ansi-c hex", "curl $'https://test.\\x63oncavoi.com/x'"),
    ("printf octal", "curl $(printf 'test.\\143oncavoi.com')"),
    ("command substitution", f"curl $(echo https://{HOST}/)"),
    ("bash -c", f"bash -c 'curl https://{HOST}/'"),
    ("python heredoc", f"python3 - <<EOF\nimport urllib.request\nurllib.request.urlopen('https://{HOST}/')\nEOF"),
    ("node fetch", f"node -e \"fetch('https://{HOST}/')\""),
    ("admin content", "curl $BASE/api/content/amazon"),
    ("admin mocks", "curl -X POST $BASE/api/mocks/amazon/rollback"),
    ("admin lease", "curl $BASE/api/lease"),
    ("admin servers", "curl $BASE/api/servers"),
    ("runtime api", "curl $BASE/amazon/__testbed/reset"),
    ("port low end", "curl http://127.0.0.1:23000/x"),
    ("port high end", "curl localhost:23103/x"),
    ("port nc", "printf 'GET / HTTP/1.0\\r\\n\\r\\n' | nc localhost 23001"),
    # engine
    ("cli run", "cd ~/Projects/lv1-servers/testbed-dev && python3 suite/cli.py run --target amazon"),
    ("cli full path", "python3 ~/Projects/lv1-servers/testbed-dev/suite/cli.py --list"),
    ("cli from suite dir", "cd suite && python cli.py --validate x.yaml"),
    ("cli uv run", "uv run python suite/cli.py run"),
    ("cli executed", "./suite/cli.py run"),
    ("cli module", "python3 -m suite.cli --list"),
    ("client import", "python3 -c 'from suite.adapters import testbed_client'"),
    # mock data
    ("cat mock data", "cat ~/.local/share/lv1-testbed/amazon/stores.json"),
    ("write mock data", "echo '{}' > $HOME/.local/share/lv1-testbed/amazon/stores.json"),
    ("rm mock data", "rm -rf /Users/x/.local/share/lv1-testbed"),
    ("mock data bare", "ls ~/.local/share/lv1-testbed"),
]

ALLOWED = [
    ("ls", "ls -la"),
    ("wiki host", "curl -s https://wiki.concavoi.com/api/articles"),
    ("drive host", "curl -s https://drive.concavoi.com/health"),
    ("other host", "curl -s https://example.com"),
    ("testbed-dev results", "ls ~/.config/lv1-testbed-dev/results"),
    ("testbed-mcp", "ls ~/.config/lv1-testbed-mcp"),
    ("repo testbed-dev dir", "ls ~/Projects/lv1-servers/testbed-dev/results"),
    ("read zshrc", "sed -n 1p ~/.zshrc"),
    ("cat zshrc", "cat ~/.zshrc"),
    ("other mcp secret", "cat ~/.mcp/.wiki.env"),
    ("ls local share", "ls ~/.local/share"),
    ("ls local", "ls ~/.local"),
    ("local bin", "ls ~/.local/bin"),
    ("other config", "cat ~/.config/gh/hosts.yml"),
    ("env dump", "env | sort"),
    ("printenv", "printenv HOME"),
    ("ps environment", "ps eww -ax"),
    ("read engine source", "cat suite/cli.py"),
    ("git diff engine", "git diff -- suite/cli.py"),
    ("port out of range", "curl localhost:23104/x"),
    ("port inside number", "echo IA-123000"),
    ("plain python", "python3 -c 'print(2+2)'"),
    ("git status", "git status --short"),
]


class GuardTable(unittest.TestCase):
    def test_blocked(self):
        for name, cmd in BLOCKED:
            with self.subTest(name=name):
                self.assertIsNotNone(guard.check(cmd, CWD), cmd)

    def test_allowed(self):
        for name, cmd in ALLOWED:
            with self.subTest(name=name):
                self.assertIsNone(guard.check(cmd, CWD), cmd)

    def test_reason_names_rule_and_route(self):
        reason = guard.check("curl $BASE/api/lease", CWD)
        self.assertIn("mock admin API", reason)
        self.assertIn("lease_status", reason)


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

    def test_python_script_calling_host(self):
        self.write("probe.py", f"import urllib.request\nurllib.request.urlopen('https://{HOST}/')\n")
        self.assertIsNotNone(guard.check("python3 probe.py", self.root))

    def test_executable_shell_script(self):
        self.write("probe.sh", "#!/bin/sh\ncurl localhost:23000/x\n", executable=True)
        self.assertIsNotNone(guard.check("./probe.sh", self.root))

    def test_clean_script_runs(self):
        self.write("ok.py", "print('hello')\n")
        self.assertIsNone(guard.check("python3 ok.py", self.root))

    def test_unittest_does_not_scan_test_files(self):
        self.write("test_x.py", f"URL = 'https://{HOST}'  # fixture text only\n")
        self.assertIsNone(guard.check("python3 -m unittest test_x", self.root))

    def test_file_that_is_only_read_is_not_scanned(self):
        self.write("notes.md", f"Served at https://{HOST}\n")
        self.assertIsNone(guard.check("cat notes.md", self.root))
        self.assertIsNone(guard.check("sed -n 1p notes.md", self.root))


class GuardHook(unittest.TestCase):
    """Runs guard.py as Claude Code would, through stdin and stdout."""

    def run_hook(self, payload):
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "guard.py")
        out = subprocess.run([sys.executable, script], input=json.dumps(payload),
                             capture_output=True, text=True, check=True)
        return out.stdout

    def test_deny_json(self):
        out = json.loads(self.run_hook({"tool_name": "Bash", "cwd": CWD,
                                        "tool_input": {"command": f"curl https://{HOST}"}}))
        self.assertEqual("deny", out["hookSpecificOutput"]["permissionDecision"])

    def test_allow_is_silent(self):
        self.assertEqual("", self.run_hook({"tool_name": "Bash", "tool_input": {"command": "ls"}}))

    def test_other_tools_pass(self):
        self.assertEqual("", self.run_hook({"tool_name": "Edit", "tool_input": {"file_path": "x"}}))


if __name__ == "__main__":
    unittest.main()
