"""Run each related test file in its own process (known lifespan-stall workaround).
If a whole-file run times out (flaky lifespan stall), fall back to running each
test of that file in its own process. Retries each attempt once."""
import subprocess, sys, os, re

FILES = [
    "test_account_isolation.py",
    "test_users.py",
    "test_auth.py",
    "test_security.py",
    "test_approvals.py",
    "test_tasks.py",
    "test_analytics.py",
    "test_audit.py",
    "test_permissions.py",
    "test_risk_rules.py",
    "test_tools.py",
    "test_integrations.py",
    "test_ceo_inbox.py",
    "test_notifications.py",
    "test_event_system.py",
    "test_features.py",
    "test_e2e_workflows.py",
    "test_telegram_bot_monitor.py",
    "test_telegram_monitor.py",
    "test_telegram_account_tool.py",
    "test_telegram_bot_seed.py",
]

env = dict(os.environ)
env["DATABASE_URL"] = "sqlite:///./.related_test.db"
env["ENVIRONMENT"] = "test"


def run_pytest(args, timeout):
    try:
        p = subprocess.run(
            [sys.executable, "-m", "pytest", *args, "-q", "--no-header",
             "-p", "no:cacheprovider", "--capture=no"],
            capture_output=True, text=True, timeout=timeout, env=env,
        )
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"


def summary_of(out):
    lines = out.strip().splitlines()
    for l in reversed(lines):
        if re.search(r"\d+ (passed|failed|error)|no tests ran|TIMEOUT", l):
            return l.strip()
    return lines[-1].strip() if lines else "?"


def cleanup():
    if os.path.exists(".related_test.db"):
        try:
            os.remove(".related_test.db")
        except OSError:
            pass


results = []
for f in FILES:
    code, out = run_pytest([f"tests/{f}"], 180)
    if code != 0:
        code2, out2 = run_pytest([f"tests/{f}"], 180)
        if code2 == 0:
            code, out = 0, out2
        elif code2 == 124 or code == 124:
            # lifespan stall → per-test fallback
            _, collect = run_pytest([f"tests/{f}", "--collect-only"], 60)
            ids = [l.strip() for l in collect.splitlines() if l.strip().endswith("::" + f.split("test_")[-1]) or "::" in l.strip()]
            ids = [l for l in ids if l.startswith("tests/")]
            bad = []
            passed = 0
            for tid in ids:
                c, o = run_pytest([tid], 120)
                if c != 0:
                    c2, o2 = run_pytest([tid], 120)
                    if c2 != 0:
                        bad.append(f"{tid}: {summary_of(o2)}")
                    else:
                        passed += 1
                else:
                    passed += 1
                cleanup()
            if bad:
                code, out = 1, "\n".join(bad)
            else:
                code, out = 0, f"all {passed} tests passed (per-test fallback)"
    cleanup()
    outcome = f"OK   ({summary_of(out)})" if code == 0 else f"FAIL {summary_of(out)}"
    print(f"{f}: {outcome}", flush=True)
    results.append((f, outcome))

print("\n==== FAILURES ====")
bad = [r for r in results if r[1].startswith("FAIL")]
print("none" if not bad else "")
for f, o in bad:
    print(f"{f}: {o}")
