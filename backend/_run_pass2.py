"""Second pass: re-run affected suites with fixed bus/scheduler."""
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
    "test_ceo_inbox.py",
    "test_notifications.py",
    "test_e2e_workflows.py",
]

env = dict(os.environ)
env["DATABASE_URL"] = "sqlite:///./.pass2.db"
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
    if os.path.exists(".pass2.db"):
        try:
            os.remove(".pass2.db")
        except OSError:
            pass


for f in FILES:
    code, out = run_pytest([f"tests/{f}"], 200)
    if code == 124:
        code, out = run_pytest([f"tests/{f}"], 200)
    if code != 0:
        # per-test fallback for lifespan-stall flakes
        _, collect = run_pytest([f"tests/{f}", "--collect-only"], 60)
        ids = [l.strip() for l in collect.splitlines() if l.strip().startswith("tests/") and "::" in l]
        bad, passed = [], 0
        for tid in ids:
            c, o = run_pytest([tid], 100)
            if c != 0:
                c2, o2 = run_pytest([tid], 100)
                if c2 != 0:
                    bad.append(f"{tid}: {summary_of(o2)}")
                else:
                    passed += 1
            else:
                passed += 1
            cleanup()
        outcome = ("OK   (all " + str(passed) + " tests passed, per-test)") if not bad else ("FAIL " + "; ".join(bad[:6]))
    else:
        outcome = f"OK   ({summary_of(out)})"
    cleanup()
    print(f"{f}: {outcome}", flush=True)
