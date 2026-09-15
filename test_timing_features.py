import os
import re
import subprocess
import sys


def run_interval(value):
    env = os.environ.copy()
    env["DUDAS_INTERVAL_SECONDS"] = value
    code = "import dudas_jump_monitor as m; print(m.INTERVAL_SECONDS); print(m.utc_timestamp_ms())"
    return subprocess.run([sys.executable, "-c", code], env=env, text=True, capture_output=True)


ok = run_interval("0.1")
assert ok.returncode == 0, ok.stderr
assert ok.stdout.splitlines()[0] == "0.1", ok.stdout
assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}\+00:00", ok.stdout.splitlines()[1]), ok.stdout

bad = run_interval("0")
assert bad.returncode != 0
assert "greater than 0" in bad.stderr

bad = run_interval("not-a-number")
assert bad.returncode != 0
assert "positive number" in bad.stderr

print("timing feature tests passed")
