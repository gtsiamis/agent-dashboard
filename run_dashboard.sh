#!/bin/bash
# Research Agents Dashboard - Generator & Deployer
# Regenerates the HTML dashboard and pushes to GitHub Pages
# Called by launchd every hour

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

export PATH="/opt/homebrew/opt/node@22/bin:/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$HOME/npm-global-local/bin"

# Generate the dashboard
/opt/homebrew/bin/python3 generate_dashboard.py

# Push to GitHub Pages — but ONLY if something OTHER than the auto-updating
# "Last updated:" timestamp line changed. This stops the every-run no-op deploy
# that was intermittently failing GitHub Pages.
git add index.html
# count changed +/- lines in index.html that are NOT auto-updating cosmetic text.
# Two patterns tick over with wall-clock time every run and must be ignored:
#   - the "Last updated: <ts> (Athens)" subtitle
#   - the per-card "Last ran <N>h ago" relative-time message
changed=$(git diff --cached -U0 -- index.html | grep -E '^[+-]' | grep -vE '^(\+\+\+|---)' | grep -vE 'Last updated:|Last ran .*ago' | grep -c .)
if [ "$changed" -gt 0 ]; then
    git commit -m "Update dashboard $(date '+%Y-%m-%d %H:%M')"
    git push origin main
else
    # only the timestamp changed (or nothing) — discard so we do not trigger a no-op Pages deploy
    git restore --staged index.html 2>/dev/null || git reset -q HEAD index.html
    git checkout -- index.html
fi
