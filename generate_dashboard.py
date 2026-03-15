#!/usr/bin/env python3
"""
Research Agents Dashboard Generator
Scans all agent log directories, determines health status, and generates
a self-contained static HTML dashboard.
"""

import re
import html as html_mod
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path("/Users/gtsiamis/Claude")
OUTPUT_FILE = BASE_DIR / "Dashboard" / "index.html"

AGENTS = [
    {"name": "Endure Emails",       "dir": "Endure_emails",        "schedule": "Daily 06:00",   "has_email": True,  "type": "Modern", "color": "#3498db"},
    {"name": "WIDERA",              "dir": "Gmail_Monitoring",      "schedule": "Daily 06:30",   "has_email": True,  "type": "Modern", "color": "#8e44ad"},
    {"name": "AquaBiome Emails",    "dir": "AquaBiome_Emails",      "schedule": "Daily 07:00",   "has_email": True,  "type": "Modern", "color": "#1a8a7d"},
    {"name": "REECOVERY Email Sync","dir": "REECOVERY_Email_Sync",  "schedule": "Daily 07:15",   "has_email": True,  "type": "Modern", "color": "#d35400"},
    {"name": "SINERGIA",            "dir": "SINERGIA",              "schedule": "Daily 07:15",   "has_email": True,  "type": "Modern", "color": "#2980b9"},
    {"name": "Daily Briefing",      "dir": "Daily_Briefing",        "schedule": "Daily 07:57",   "has_email": True,  "type": "Modern", "color": "#27ae60"},
    {"name": "Wolbachia",           "dir": "Wolbachia",             "schedule": "Friday 09:15",  "has_email": True,  "type": "Modern", "color": "#e67e22"},
    {"name": "Insect Microbiome",   "dir": "Insect_Microbiome",     "schedule": "Friday 09:00",  "has_email": True,  "type": "Hybrid", "color": "#9b59b6"},
    {"name": "Literature Wetlands", "dir": "Literature_wetlands",   "schedule": "Monday 09:00",  "has_email": True,  "type": "Modern", "color": "#1abc9c"},
    {"name": "Culturomics",         "dir": "Culturomics",           "schedule": "Tuesday 09:00", "has_email": True,  "type": "Modern", "color": "#e74c3c"},
    {"name": "T6SS",                "dir": "T6SS",                  "schedule": "Monday 09:30",  "has_email": True,  "type": "Hybrid", "color": "#34495e"},
    {"name": "BioDetect LinkedIn",  "dir": "BioDetect-LinkedIn",    "schedule": "Daily 10:00",   "has_email": False, "type": "Modern", "color": "#2c3e50"},
    {"name": "CIRQUA LinkedIn",     "dir": "CIRQUA-LinkedIn",       "schedule": "Daily 08:00",   "has_email": False, "type": "Legacy", "color": "#7f8c8d", "log": "cirqua_cron.log"},
    {"name": "EU Funding",          "dir": "EU_Funding",            "schedule": "Manual",        "has_email": True,  "type": "Legacy", "color": "#95a5a6"},
]

WEEKDAYS = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6}


# ---------------------------------------------------------------------------
# Log parsing
# ---------------------------------------------------------------------------

def parse_log(log_path):
    """Parse cron.log and return a list of run dicts (most recent last)."""
    if not log_path.exists():
        return []

    try:
        text = log_path.read_text(errors="replace")
    except Exception:
        return []

    lines = text.splitlines()
    runs = []
    current = None

    for line in lines:
        if re.match(r"^=+$", line.strip()):
            continue

        start_m = re.search(
            r"(?:started|Started):\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})", line)
        if start_m:
            if current and current.get("end_time"):
                runs.append(current)
            current = {
                "start_time": datetime.strptime(start_m.group(1), "%Y-%m-%d %H:%M:%S"),
                "end_time": None,
                "exit_code": None,
                "output_lines": [],
            }
            continue

        end_m = re.search(
            r"(?:completed|Completed):\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})(?:\s*\(exit code:\s*(\d+)\))?",
            line)
        if end_m and current:
            current["end_time"] = datetime.strptime(end_m.group(1), "%Y-%m-%d %H:%M:%S")
            current["exit_code"] = int(end_m.group(2)) if end_m.group(2) else 0
            current["output"] = "\n".join(current.pop("output_lines"))
            runs.append(current)
            current = None
            continue

        if current is not None:
            current["output_lines"].append(line)

    # Handle a run that started but never completed
    if current:
        current["output"] = "\n".join(current.pop("output_lines"))
        runs.append(current)

    return runs


# ---------------------------------------------------------------------------
# Email status detection
# ---------------------------------------------------------------------------

def detect_email_status(output, has_email):
    if not has_email:
        return "na"
    if not output:
        return "unknown"
    t = output.lower()
    # Check "sent" FIRST — if SMTP succeeded, the draft is just a backup copy
    sent = any(k in t for k in ["email sent", "summary email sent", "summary sent",
                                 "sent via smtp", "send_message", "email delivered"])
    draft = any(k in t for k in ["draft created", "gmail draft", "used gmail draft",
                                  "draft as fallback", "created in gmail"])
    # Exclude "no draft created" false positives
    if draft and "no draft created" in t:
        draft = False
    if sent:
        return "sent"
    if draft:
        return "draft"
    if any(k in t for k in ["email failed", "smtp error", "smtp failed"]):
        return "failed"
    if any(k in t for k in ["posted to linkedin", "linkedin post"]):
        return "na"
    return "unknown"


# ---------------------------------------------------------------------------
# Schedule / health logic
# ---------------------------------------------------------------------------

def get_expected_last_run(schedule, now):
    """Return the datetime when this agent should have most recently run."""
    if schedule == "Manual":
        return None
    parts = schedule.split()
    if parts[0] == "Daily":
        h, m = map(int, parts[1].split(":"))
        expected = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if now < expected:
            expected -= timedelta(days=1)
        return expected
    else:
        day_name = parts[0].lower()
        h, m = map(int, parts[1].split(":"))
        target_wd = WEEKDAYS[day_name]
        days_ago = (now.weekday() - target_wd) % 7
        expected = (now - timedelta(days=days_ago)).replace(
            hour=h, minute=m, second=0, microsecond=0)
        if days_ago == 0 and now < expected:
            expected -= timedelta(days=7)
        return expected


def determine_health(agent, runs, now):
    """Return (status, message) where status is one of:
    healthy, warning, error, overdue, unknown, running."""
    if not runs:
        agent_dir = BASE_DIR / agent["dir"]
        if not agent_dir.exists():
            return "unknown", "Project directory not found"
        return "unknown", "No log data"

    last = runs[-1]

    # Still running (no end time)
    if last.get("end_time") is None and last.get("exit_code") is None:
        return "running", "Currently running"

    output = last.get("output", "")

    # Non-zero exit code
    if last.get("exit_code") is not None and last["exit_code"] != 0:
        if "API Error" in output:
            return "error", "API error"
        if "node: No such file" in output or "env: node" in output:
            return "error", "Node.js not in PATH"
        if "Prompt is too long" in output:
            return "error", "Prompt too long"
        if "Cannot be launched inside another" in output or "CLAUDECODE" in output:
            return "error", "Nested Claude session"
        return "error", f"Exit code {last['exit_code']}"

    # Exit code 0 — check for soft failures
    if agent["has_email"]:
        es = detect_email_status(output, True)
        if es == "draft":
            return "warning", "Email went to draft instead of sending"
        if es == "failed":
            return "error", "Email sending failed"

    t_lower = output.lower()
    has_perm_issue = any(k in t_lower for k in ["permission", "blocked", "needs approval",
                                                 "tool needs permission"])
    # Don't flag if the agent self-corrected the permission issue
    self_fixed = any(k in t_lower for k in ["fixed", "updated", "corrected", "resolved"])
    if has_perm_issue and not self_fixed:
        return "warning", "Permission issues detected"

    # Schedule compliance
    expected = get_expected_last_run(agent["schedule"], now)
    if expected:
        tolerance = timedelta(hours=3)
        if last["start_time"] < expected - tolerance:
            hrs = (now - last["start_time"]).total_seconds() / 3600
            return "overdue", f"Last ran {hrs:.0f}h ago"

    return "healthy", "Running normally"


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

EMAIL_DISPLAY = {
    "sent":    ("&#10003; Sent",  "email-sent"),
    "draft":   ("&#9888; Draft",  "email-draft"),
    "failed":  ("&#10007; Failed","email-failed"),
    "na":      ("&mdash;",        "email-na"),
    "unknown": ("? Unknown",      "email-unknown"),
}

STATUS_DISPLAY = {
    "healthy": ("Healthy", "badge-healthy"),
    "warning": ("Warning", "badge-warning"),
    "error":   ("Error",   "badge-error"),
    "overdue": ("Overdue", "badge-overdue"),
    "unknown": ("Unknown", "badge-unknown"),
    "running": ("Running", "badge-running"),
}


def build_card(s):
    status_label, status_class = STATUS_DISPLAY.get(s["status"], ("?", "badge-unknown"))
    email_label, email_class = EMAIL_DISPLAY.get(s["email"], ("?", "email-unknown"))

    last_run_str = s["last_run"].strftime("%Y-%m-%d %H:%M") if s["last_run"] else "Never"

    duration_str = ""
    if s["start_time"] and s["end_time"]:
        dur = (s["end_time"] - s["start_time"]).total_seconds()
        if dur < 60:
            duration_str = f"{dur:.0f}s"
        else:
            duration_str = f"{dur/60:.1f}m"
    elif s["start_time"] and not s["end_time"]:
        duration_str = "In progress"
    else:
        duration_str = "&mdash;"

    exit_str = str(s["exit_code"]) if s["exit_code"] is not None else "&mdash;"

    msg_html = ""
    if s["message"]:
        escaped = html_mod.escape(s["message"][:200])
        msg_html = f'<div class="card-message">{escaped}</div>'

    return f"""
        <div class="card" style="border-top: 3px solid {s['color']}">
            <div class="card-header">
                <span class="card-title">{html_mod.escape(s['name'])}</span>
                <span class="badge {status_class}">{status_label}</span>
            </div>
            <div class="card-details">
                <div class="row"><span class="label">Schedule</span><span class="value">{s['schedule']}</span></div>
                <div class="row"><span class="label">Last Run</span><span class="value">{last_run_str}</span></div>
                <div class="row"><span class="label">Duration</span><span class="value">{duration_str}</span></div>
                <div class="row"><span class="label">Exit Code</span><span class="value">{exit_str}</span></div>
                <div class="row"><span class="label">Email</span><span class="value {email_class}">{email_label}</span></div>
                <div class="row"><span class="label">Type</span><span class="value">{s['type']}</span></div>
            </div>
            {msg_html}
        </div>"""


def generate_html(statuses, now):
    counts = {"healthy": 0, "warning": 0, "error": 0, "other": 0}
    for s in statuses:
        if s["status"] in counts:
            counts[s["status"]] += 1
        elif s["status"] in ("overdue",):
            counts["error"] += 1
        else:
            counts["other"] += 1

    cards_html = "\n".join(build_card(s) for s in statuses)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Research Agents Dashboard</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0d1117;
            color: #c9d1d9;
            min-height: 100vh;
        }}
        .header {{
            background: #161b22;
            border-bottom: 1px solid #30363d;
            padding: 24px 32px;
        }}
        .header h1 {{
            font-size: 24px;
            color: #f0f6fc;
            margin-bottom: 4px;
        }}
        .subtitle {{ color: #8b949e; font-size: 14px; }}
        .stats-bar {{
            display: flex;
            gap: 32px;
            margin-top: 16px;
            flex-wrap: wrap;
        }}
        .stat {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .stat-dot {{
            width: 12px; height: 12px;
            border-radius: 50%;
        }}
        .stat-label {{ color: #8b949e; font-size: 14px; }}
        .stat-value {{ font-weight: 600; font-size: 20px; }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
            gap: 16px;
            padding: 24px 32px;
        }}
        .card {{
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 20px;
            transition: border-color 0.2s;
        }}
        .card:hover {{ border-color: #58a6ff; }}
        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 14px;
        }}
        .card-title {{ font-size: 15px; font-weight: 600; color: #f0f6fc; }}
        .badge {{
            display: inline-block;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
            white-space: nowrap;
        }}
        .badge-healthy {{ background: #238636; color: #fff; }}
        .badge-warning {{ background: #9e6a03; color: #fff; }}
        .badge-error   {{ background: #da3633; color: #fff; }}
        .badge-overdue {{ background: #da3633; color: #fff; }}
        .badge-unknown {{ background: #484f58; color: #8b949e; }}
        .badge-running {{ background: #1f6feb; color: #fff; }}
        .card-details {{ font-size: 13px; }}
        .card-details .row {{
            display: flex;
            justify-content: space-between;
            padding: 5px 0;
            border-bottom: 1px solid #21262d;
        }}
        .card-details .row:last-child {{ border-bottom: none; }}
        .label {{ color: #8b949e; }}
        .value {{ color: #c9d1d9; font-weight: 500; }}
        .email-sent    {{ color: #3fb950; }}
        .email-draft   {{ color: #d29922; }}
        .email-failed  {{ color: #f85149; }}
        .email-na      {{ color: #484f58; }}
        .email-unknown {{ color: #8b949e; }}
        .card-message {{
            margin-top: 10px;
            padding: 8px 12px;
            background: #0d1117;
            border-radius: 6px;
            font-size: 12px;
            color: #8b949e;
            line-height: 1.4;
        }}
        .footer {{
            text-align: center;
            padding: 24px;
            color: #484f58;
            font-size: 12px;
            border-top: 1px solid #21262d;
            margin-top: 8px;
        }}
        @media (max-width: 600px) {{
            .header {{ padding: 16px; }}
            .grid {{ padding: 16px; grid-template-columns: 1fr; }}
            .stats-bar {{ gap: 16px; }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Research Agents Dashboard</h1>
        <p class="subtitle">Last updated: {now.strftime("%Y-%m-%d %H:%M")} (Athens)</p>
        <div class="stats-bar">
            <div class="stat">
                <div class="stat-dot" style="background:#3fb950"></div>
                <span class="stat-value">{counts['healthy']}</span>
                <span class="stat-label">Healthy</span>
            </div>
            <div class="stat">
                <div class="stat-dot" style="background:#d29922"></div>
                <span class="stat-value">{counts['warning']}</span>
                <span class="stat-label">Warning</span>
            </div>
            <div class="stat">
                <div class="stat-dot" style="background:#f85149"></div>
                <span class="stat-value">{counts['error']}</span>
                <span class="stat-label">Error</span>
            </div>
            <div class="stat">
                <div class="stat-dot" style="background:#484f58"></div>
                <span class="stat-value">{counts['other']}</span>
                <span class="stat-label">Unknown</span>
            </div>
        </div>
    </div>
    <div class="grid">
{cards_html}
    </div>
    <div class="footer">
        Research Agents Dashboard &middot; George Tsiamis
    </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    now = datetime.now()
    statuses = []

    for agent in AGENTS:
        custom_log = agent.get("log")
        if custom_log:
            log_path = BASE_DIR / agent["dir"] / custom_log
        else:
            log_path = BASE_DIR / agent["dir"] / "logs" / "cron.log"
        runs = parse_log(log_path)
        status, message = determine_health(agent, runs, now)
        last = runs[-1] if runs else None

        email = detect_email_status(
            last.get("output", "") if last else "", agent["has_email"])

        statuses.append({
            "name":       agent["name"],
            "dir":        agent["dir"],
            "schedule":   agent["schedule"],
            "type":       agent["type"],
            "color":      agent["color"],
            "has_email":  agent["has_email"],
            "status":     status,
            "message":    message,
            "email":      email,
            "last_run":   last["start_time"] if last else None,
            "start_time": last["start_time"] if last else None,
            "end_time":   last.get("end_time") if last else None,
            "exit_code":  last.get("exit_code") if last else None,
        })

    dashboard_html = generate_html(statuses, now)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(dashboard_html)
    print(f"Dashboard generated: {OUTPUT_FILE}")
    print(f"  Healthy: {sum(1 for s in statuses if s['status']=='healthy')}")
    print(f"  Warning: {sum(1 for s in statuses if s['status']=='warning')}")
    print(f"  Error:   {sum(1 for s in statuses if s['status'] in ('error','overdue'))}")


if __name__ == "__main__":
    main()
