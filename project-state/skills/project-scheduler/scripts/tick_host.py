#!/usr/bin/env python3
"""Render the host that fires `project-orchestrator tick` for one project, and check that one fires.

WHY THIS IS A SCRIPT
--------------------
A plugin-only install ships no scheduler (issue #109): the kanban's in-app scheduler and crontab,
the Atomic 47 fan-out Desktop tasks and the cloud scheduler are all somewhere else. So the person
needs a host of their own, and project-scheduler's `host` operation sets one up by talking. The
words of that conversation live in the skill; the artifacts live here, because a launchd plist, a
crontab line or a PowerShell registration that is composed by prose drifts, mis-quotes a path, or
puts a `%` into a crontab (cron reads it as a newline). One renderer, tested, gives every host the
same prompt, and the same prompt is the whole point (docs/AUTOMATION-HOSTS.md: "a host must never
contain a schedule" - it only says one sentence to one skill).

This script never installs anything and never writes the project. `render` prints what would be
installed and the record the skill writes to automation/hosts.json (through project-state) once
the person has said yes. `check` reads that record and the activity log and says whether a host is
installed and when tick last ran.

USAGE
-----
    tick_host.py render --kind desktop|routine|launchd|cron|task-scheduler --project-dir <dir>
                        [--time HH:MM] [--days daily|weekdays] [--claude <path>] [--slug <id>] [--json]
    tick_host.py check  --project-dir <dir> [--no-probe] [--now ISO] [--json]
    tick_host.py prompt --kind <kind> --project-dir <dir>

<dir> is the folder that holds project-state/ (or .project-state/), or the substrate itself.
Standard library only: a plugin-only machine may not have PyYAML.

EXIT CODES
----------
    0  render/prompt printed; check verdict ok
    1  check verdict needs attention (no host, host missing, tick stale or never ran)
    2  usage error (no substrate found, bad time, unknown kind)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import re
import shlex
import shutil
import socket
import subprocess
import sys
from xml.sax.saxutils import escape as xml_escape

KINDS = ("desktop", "routine", "launchd", "cron", "task-scheduler")

# What the headless OS hosts may use. dontAsk denies everything not listed instead of prompting, so an
# unattended run can never park on a permission prompt (AUTOMATION-HOSTS.md, "Unattended runs"). No
# connector is listed: a tick drafts into outbox/queue/ and sends nothing, so it needs no mail or chat
# tool at all. The project-state local server is listed whole; its writes are checked and signed.
ALLOWED_TOOLS = "Read,Glob,Grep,Edit,Write,Skill,Bash(date *),mcp__plugin_project-state_project-state"
BUDGET_USD = "2"

# Expected interval between firings, and how late a tick may be before check calls it stale.
STALE_AFTER_DAYS = {"daily": 2, "weekdays": 4}

WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]


# ── locating the project ────────────────────────────────────────────────────────────────────────────

def find_substrate(project_dir: str) -> tuple[str, str] | None:
    """Return (project_dir, substrate_dir) or None."""
    d = os.path.abspath(os.path.expanduser(project_dir))
    if os.path.basename(d) in ("project-state", ".project-state") and os.path.isfile(os.path.join(d, "manifest.yaml")):
        return os.path.dirname(d), d
    for name in ("project-state", ".project-state"):
        s = os.path.join(d, name)
        if os.path.isfile(os.path.join(s, "manifest.yaml")):
            return d, s
    return None


def slugify(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s or "project"


def manifest_id(substrate: str) -> str | None:
    """Best-effort project id from manifest.yaml without a YAML parser: the `project:` block's `id`, else
    its `name`, else a top-level `id`."""
    try:
        lines = open(os.path.join(substrate, "manifest.yaml"), encoding="utf-8").read().splitlines()
    except OSError:
        return None
    block: dict[str, str] = {}
    inside = False
    for line in lines:
        if re.match(r"^project:\s*$", line):
            inside = True
            continue
        if inside:
            if line and not line[0].isspace():
                break
            m = re.match(r"^  (id|name):\s*['\"]?([A-Za-z0-9._-]+)['\"]?\s*$", line)
            if m:
                block.setdefault(m.group(1), m.group(2))
    if block:
        return block.get("id") or block.get("name")
    for line in lines:
        m = re.match(r"^id:\s*['\"]?([A-Za-z0-9._-]+)", line)
        if m:
            return m.group(1)
    return None


# ── the one prompt every host says ──────────────────────────────────────────────────────────────────

def tick_prompt(kind: str, project_dir: str) -> str:
    """The sentence every plugin-only host says. No quotes, backticks or percent signs, so it survives a
    crontab, a plist string, a POSIX single-quoted argument and a PowerShell single-quoted string."""
    if kind == "desktop":
        where = f"Work in the project folder {project_dir} (change into it first). "
    elif kind == "routine":
        where = "The project is the repository attached to this routine. "
    else:
        where = "The project is the folder this session starts in. "
    # A routine works on a clone, so its drafts reach the person only if it pushes them. Every other
    # host works on the person's own folder and must leave git alone (project-git owns commits).
    ending = ("Then commit only the files this tick wrote under the project-state folder and push them; "
              "send nothing and post nothing." if kind == "routine"
              else "Send nothing, post nothing, commit nothing.")
    return (
        where
        + "Run the project-orchestrator tick routine from the project-state plugin, unattended: nobody is "
        "present, so ask nothing and wait for no one. Read the current time from the system clock (date -u "
        "on a Unix shell) and never infer it from these words. Follow the tick algorithm in that skill: "
        "automation/tasks.yaml is the cadence registry, dispatch only what is due, and each generator drafts "
        f"into outbox/queue/. Record each dispatch, or one quiet entry when nothing is due, as an "
        f"orchestrator.tick event with host set to {kind}. " + ending
    )


# ── schedules ───────────────────────────────────────────────────────────────────────────────────────

def parse_time(t: str) -> tuple[int, int]:
    m = re.fullmatch(r"([01]?\d|2[0-3]):([0-5]\d)", t)
    if not m:
        raise ValueError(f"--time must be HH:MM (24h), got {t!r}")
    return int(m.group(1)), int(m.group(2))


def cron_expr(hour: int, minute: int, days: str) -> str:
    return f"{minute} {hour} * * {'1-5' if days == 'weekdays' else '*'}"


def resolve_claude(given: str | None) -> str:
    if given:
        return os.path.abspath(os.path.expanduser(given))
    found = shutil.which("claude")
    if found:
        return found
    home_bin = os.path.expanduser("~/.local/bin/claude")
    return home_bin


def log_path(kind: str, slug: str) -> str:
    if kind == "launchd":
        return os.path.expanduser(f"~/Library/Logs/project-state/{slug}-tick.log")
    if kind == "task-scheduler":
        return os.path.join("%LOCALAPPDATA%", "project-state", f"{slug}-tick.log")
    return os.path.expanduser(f"~/.local/state/project-state/{slug}-tick.log")


def names(slug: str) -> dict:
    return {
        "desktop": f"project-state-tick-{slug}",
        "routine": f"project-state tick ({slug})",
        "launchd": f"app.project-state.tick.{slug}",
        "cron": f"project-state-tick:{slug}",
        "task-scheduler": f"project-state-tick-{slug}",
    }


def headless_args(claude: str, prompt: str) -> list[str]:
    return [claude, "-p", prompt, "--permission-mode", "dontAsk",
            "--allowedTools", ALLOWED_TOOLS, "--max-budget-usd", BUDGET_USD]


# ── renderers ───────────────────────────────────────────────────────────────────────────────────────

def render_desktop(ctx: dict) -> dict:
    taskid = names(ctx["slug"])["desktop"]
    return {
        "artifact_kind": "Claude Desktop scheduled task",
        "tool": "create_scheduled_task",
        "arguments": {
            "taskId": taskid,
            "title": f"project-state tick: {ctx['slug']}",
            "description": f"Run project-orchestrator tick for {ctx['slug']}: dispatch what is due, draft into the outbox, send nothing.",
            "cronExpression": ctx["cron"],
            "prompt": ctx["prompt"],
        },
        "installed_at_path": os.path.join(os.path.expanduser("~/.claude/scheduled-tasks"), taskid, "SKILL.md"),
        "remove": f"delete_scheduled_task with taskId {taskid}",
        "missed_runs": "Runs while Claude Desktop is open; a run missed while the app was closed runs on next launch. Jittered by several minutes.",
        "first_run": "Run it once now (run_scheduled_task) and approve any permission prompt it raises; approvals are kept for later runs.",
    }


def render_routine(ctx: dict) -> dict:
    return {
        "artifact_kind": "claude.ai routine (cloud)",
        "tool": "the schedule skill (RemoteTrigger create, switched off until a test run succeeds)",
        "arguments": {
            "name": names(ctx["slug"])["routine"],
            "cron_local": ctx["cron"],
            "prompt": ctx["prompt"],
        },
        "requires": [
            "the project is reachable from the cloud: a git repository the routine can clone, with write access so its drafts land",
            "the project-state plugin is installable in the routine's environment",
        ],
        "remove": "delete the routine at https://claude.ai/code/routines",
        "missed_runs": "Runs in the cloud, so a sleeping or closed machine does not matter. A routine cannot see a local folder.",
        "first_run": "Run it once before switching it on and read the run log.",
    }


def render_launchd(ctx: dict) -> dict:
    label = names(ctx["slug"])["launchd"]
    plist_path = os.path.expanduser(f"~/Library/LaunchAgents/{label}.plist")
    hour, minute = ctx["hour"], ctx["minute"]
    if ctx["days"] == "weekdays":
        intervals = "".join(
            f"\n      <dict><key>Weekday</key><integer>{d}</integer><key>Hour</key><integer>{hour}</integer>"
            f"<key>Minute</key><integer>{minute}</integer></dict>" for d in range(1, 6))
        cal = f"<array>{intervals}\n    </array>"
    else:
        cal = f"<dict><key>Hour</key><integer>{hour}</integer><key>Minute</key><integer>{minute}</integer></dict>"
    args = "".join(f"\n      <string>{xml_escape(a)}</string>" for a in headless_args(ctx["claude"], ctx["prompt"]))
    path_env = ":".join([os.path.dirname(ctx["claude"]), "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin"])
    log = log_path("launchd", ctx["slug"])
    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>{xml_escape(label)}</string>
    <key>ProgramArguments</key>
    <array>{args}
    </array>
    <key>WorkingDirectory</key>
    <string>{xml_escape(ctx['project_dir'])}</string>
    <key>EnvironmentVariables</key>
    <dict><key>PATH</key><string>{xml_escape(path_env)}</string></dict>
    <key>StartCalendarInterval</key>
    {cal}
    <key>StandardOutPath</key>
    <string>{xml_escape(log)}</string>
    <key>StandardErrorPath</key>
    <string>{xml_escape(log)}</string>
  </dict>
</plist>
"""
    q = shlex.quote
    return {
        "artifact_kind": "launchd user agent (macOS)",
        "file": plist_path,
        "content": plist,
        "install": [
            f"mkdir -p {q(os.path.dirname(log))}",
            f"launchctl bootstrap gui/$(id -u) {q(plist_path)}",
        ],
        "remove": [f"launchctl bootout gui/$(id -u)/{label}", f"rm {q(plist_path)}"],
        "log": log,
        "missed_runs": "If the Mac is asleep at the time, launchd runs the job when it wakes (missed intervals coalesce into one run). If it is shut down, the run is skipped.",
        "first_run": f"launchctl kickstart gui/$(id -u)/{label}  then read {log}",
    }


def render_cron(ctx: dict) -> dict:
    marker = names(ctx["slug"])["cron"]
    log = log_path("cron", ctx["slug"])
    cmd = " ".join(shlex.quote(a) for a in headless_args(ctx["claude"], ctx["prompt"]))
    line = f"{ctx['cron']} cd {shlex.quote(ctx['project_dir'])} && {cmd} >> {shlex.quote(log)} 2>&1 # {marker}"
    # cron turns an unescaped % into a newline; nothing we render should contain one, but a path might.
    line = line.replace("%", r"\%")
    return {
        "artifact_kind": "crontab line (Linux)",
        "content": line,
        "install": [f"mkdir -p {shlex.quote(os.path.dirname(log))}",
                    f"( crontab -l 2>/dev/null; echo {shlex.quote(line)} ) | crontab -"],
        "remove": [f"crontab -l | grep -v {shlex.quote('# ' + marker)} | crontab -"],
        "log": log,
        "missed_runs": "cron does not catch up: a run due while the machine is off or asleep is skipped, and the next firing is the next one. A systemd user timer with Persistent=true does catch up, if the person prefers one.",
        "first_run": f"run the command after the time fields by hand once, then read {log}",
    }


def ps_single(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def render_task_scheduler(ctx: dict) -> dict:
    name = names(ctx["slug"])["task-scheduler"]
    claude = ctx["claude"]
    argv = headless_args(claude, ctx["prompt"])[1:]
    arg_str = " ".join(f'"{a}"' if (" " in a or "(" in a) else a for a in argv)
    trigger = (f"New-ScheduledTaskTrigger -Weekly -DaysOfWeek {','.join(WEEKDAY_NAMES)} -At {ctx['time']}"
               if ctx["days"] == "weekdays" else f"New-ScheduledTaskTrigger -Daily -At {ctx['time']}")
    script = "\n".join([
        f"$action = New-ScheduledTaskAction -Execute {ps_single(claude)} -Argument {ps_single(arg_str)} -WorkingDirectory {ps_single(ctx['project_dir'])}",
        f"$trigger = {trigger}",
        "$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1)",
        f"Register-ScheduledTask -TaskName {ps_single(name)} -Action $action -Trigger $trigger -Settings $settings "
        f"-Description {ps_single('project-state tick for ' + ctx['slug'] + ': drafts only, sends nothing')}",
    ])
    return {
        "artifact_kind": "Windows Task Scheduler task (PowerShell)",
        "content": script,
        "install": ["run the four lines above in PowerShell as the person (not as Administrator)"],
        "remove": [f"Unregister-ScheduledTask -TaskName {ps_single(name)} -Confirm:$false"],
        "missed_runs": "StartWhenAvailable runs a missed task as soon as possible after the machine is back.",
        "first_run": f"Start-ScheduledTask -TaskName {ps_single(name)}",
    }


RENDERERS = {"desktop": render_desktop, "routine": render_routine, "launchd": render_launchd,
             "cron": render_cron, "task-scheduler": render_task_scheduler}


def context(args) -> dict:
    found = find_substrate(args.project_dir)
    if not found:
        raise LookupError(f"no project-state/manifest.yaml under {args.project_dir}")
    project_dir, substrate = found
    hour, minute = parse_time(args.time)
    slug = slugify(args.slug or manifest_id(substrate) or os.path.basename(project_dir))
    ctx = {"project_dir": project_dir, "substrate": substrate, "slug": slug, "hour": hour, "minute": minute,
           "time": f"{hour:02d}:{minute:02d}", "days": args.days, "cron": cron_expr(hour, minute, args.days),
           "claude": resolve_claude(getattr(args, "claude", None))}
    ctx["prompt"] = tick_prompt(args.kind, project_dir)
    return ctx


def record_for(ctx: dict, kind: str, artifact: dict) -> dict:
    return {
        "id": f"tick-{kind}",
        "phase": "tick",
        "kind": kind,
        "name": names(ctx["slug"])[kind],
        "schedule": {"cron": ctx["cron"], "days": ctx["days"], "clock": "machine-local" if kind != "routine" else "the routine's own"},
        "machine": None if kind == "routine" else socket.gethostname(),
        "artifact": artifact.get("file") or artifact.get("installed_at_path"),
        "installed_at": None,
        "installed_by": None,
        "status": "active",
    }


# ── check ───────────────────────────────────────────────────────────────────────────────────────────

def read_hosts(substrate: str) -> list[dict]:
    p = os.path.join(substrate, "automation", "hosts.json")
    try:
        data = json.load(open(p, encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [h for h in data.get("hosts", []) if isinstance(h, dict)]


def parse_ts(s) -> dt.datetime | None:
    if not isinstance(s, str):
        return None
    try:
        t = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def last_ticks(substrate: str) -> dict:
    """The newest orchestrator.tick of any kind, and the newest one that dispatched something."""
    out = {"last_tick": None, "last_tick_host": None, "last_dispatch": None, "ticks": 0}
    p = os.path.join(substrate, "logs", "activity.ndjson")
    try:
        lines = open(p, encoding="utf-8").read().splitlines()
    except OSError:
        return out
    for line in lines:
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if not isinstance(e, dict) or e.get("event") != "orchestrator.tick":
            continue
        ts = parse_ts(e.get("ts") or e.get("timestamp"))
        if ts is None:
            continue
        out["ticks"] += 1
        if out["last_tick"] is None or ts > out["last_tick"]:
            out["last_tick"], out["last_tick_host"] = ts, e.get("host") or e.get("actor_role")
        if e.get("dispatched") is not False and e.get("id"):
            if out["last_dispatch"] is None or ts > out["last_dispatch"]:
                out["last_dispatch"] = ts
    return out


def probe(h: dict) -> str:
    """installed | missing | unverifiable — what this machine can see of a recorded host."""
    kind, name = h.get("kind"), h.get("name") or ""
    here = socket.gethostname()
    if kind != "routine" and h.get("machine") and h["machine"] != here:
        return "unverifiable"  # recorded on another machine
    try:
        if kind == "desktop":
            p = h.get("artifact") or os.path.join(os.path.expanduser("~/.claude/scheduled-tasks"), name, "SKILL.md")
            return "installed" if os.path.isfile(os.path.expanduser(p)) else "missing"
        if kind == "launchd":
            p = h.get("artifact") or os.path.expanduser(f"~/Library/LaunchAgents/{name}.plist")
            if not os.path.isfile(os.path.expanduser(p)):
                return "missing"
            if platform.system() != "Darwin":
                return "unverifiable"
            r = subprocess.run(["launchctl", "print", f"gui/{os.getuid()}/{name}"], capture_output=True, text=True, timeout=10)
            return "installed" if r.returncode == 0 else "missing"
        if kind == "cron":
            if not shutil.which("crontab"):
                return "unverifiable"
            r = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=10)
            return "installed" if f"# {name}" in r.stdout else "missing"
        if kind == "task-scheduler":
            if platform.system() != "Windows":
                return "unverifiable"
            r = subprocess.run(["schtasks", "/Query", "/TN", name], capture_output=True, text=True, timeout=10)
            return "installed" if r.returncode == 0 else "missing"
    except (OSError, subprocess.SubprocessError):
        return "unverifiable"
    return "unverifiable"  # routine: only claude.ai (or RemoteTrigger list) can say


def check(substrate: str, now: dt.datetime, do_probe: bool = True) -> dict:
    hosts = [h for h in read_hosts(substrate) if h.get("status", "active") == "active" and h.get("phase", "tick") == "tick"]
    for h in hosts:
        h["probe"] = probe(h) if do_probe else "not-probed"
    t = last_ticks(substrate)
    problems = []
    if not hosts:
        problems.append("no host is recorded for tick: nothing runs it unless someone does, by hand")
    for h in hosts:
        if h["probe"] == "missing":
            problems.append(f"{h.get('kind')} host {h.get('name')} is recorded but not installed on this machine")
    if hosts:
        days = min(STALE_AFTER_DAYS.get((h.get("schedule") or {}).get("days"), 2) for h in hosts)
        if t["last_tick"] is None:
            problems.append("tick has never logged a run")
        elif (now - t["last_tick"]).total_seconds() > days * 86400:
            age = (now - t["last_tick"]).days
            problems.append(f"tick last ran {age} day(s) ago, longer than its host's schedule allows")
    verdict = "ok" if not problems else ("no-host" if not hosts else "attention")
    return {
        "substrate": substrate,
        "verdict": verdict,
        "hosts": hosts,
        "last_tick": t["last_tick"].strftime("%Y-%m-%dT%H:%M:%SZ") if t["last_tick"] else None,
        "last_tick_host": t["last_tick_host"],
        "last_dispatch": t["last_dispatch"].strftime("%Y-%m-%dT%H:%M:%SZ") if t["last_dispatch"] else None,
        "ticks_logged": t["ticks"],
        "problems": problems,
    }


# ── cli ─────────────────────────────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("render", "prompt"):
        p = sub.add_parser(name)
        p.add_argument("--kind", required=True, choices=KINDS)
        p.add_argument("--project-dir", required=True)
        p.add_argument("--time", default="07:15")
        p.add_argument("--days", default="daily", choices=["daily", "weekdays"])
        p.add_argument("--claude")
        p.add_argument("--slug")
        p.add_argument("--json", action="store_true")
    c = sub.add_parser("check")
    c.add_argument("--project-dir", required=True)
    c.add_argument("--no-probe", action="store_true")
    c.add_argument("--now")
    c.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.cmd == "check":
        found = find_substrate(args.project_dir)
        if not found:
            print(f"no project-state/manifest.yaml under {args.project_dir}", file=sys.stderr)
            return 2
        now = parse_ts(args.now) if args.now else dt.datetime.now(dt.timezone.utc)
        r = check(found[1], now, do_probe=not args.no_probe)
        if args.json:
            print(json.dumps(r, indent=2))
        else:
            print(f"verdict: {r['verdict']}")
            for h in r["hosts"]:
                print(f"  host: {h.get('kind')} {h.get('name')} ({(h.get('schedule') or {}).get('cron')}) - {h['probe']}")
            print(f"  last tick: {r['last_tick'] or 'never'}" + (f" by {r['last_tick_host']}" if r["last_tick_host"] else ""))
            print(f"  last dispatch: {r['last_dispatch'] or 'never'}")
            for p in r["problems"]:
                print(f"  problem: {p}")
        return 0 if r["verdict"] == "ok" else 1

    try:
        ctx = context(args)
    except (LookupError, ValueError) as e:
        print(str(e), file=sys.stderr)
        return 2
    if args.cmd == "prompt":
        print(ctx["prompt"])
        return 0
    art = RENDERERS[args.kind](ctx)
    out = {"kind": args.kind, "project_dir": ctx["project_dir"], "slug": ctx["slug"], "cron": ctx["cron"],
           "artifact": art, "record": record_for(ctx, args.kind, art)}
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print(f"# {art['artifact_kind']} for {ctx['slug']} - fires {ctx['cron']} (machine-local time)")
        for k in ("file", "tool"):
            if k in art:
                print(f"{k}: {art[k]}")
        if "content" in art:
            print("\n" + art["content"])
        if "arguments" in art:
            print(json.dumps(art["arguments"], indent=2))
        for k in ("install", "remove"):
            if k in art:
                v = art[k]
                print(f"\n{k}:")
                for line in (v if isinstance(v, list) else [v]):
                    print(f"  {line}")
        print(f"\nmissed runs: {art['missed_runs']}")
        print(f"first run: {art['first_run']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
