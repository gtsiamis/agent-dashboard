#!/bin/bash
# Research Agents Dashboard - Generator & Deployer
# Regenerates the HTML dashboard and pushes to GitHub Pages
# Called by launchd every hour

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

export PATH="/opt/homebrew/opt/node@22/bin:/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$HOME/npm-global-local/bin"

# Generate the dashboard
/opt/homebrew/bin/python3 generate_dashboard.py

# Push to GitHub Pages
git add index.html
if ! git diff --cached --quiet; then
    git commit -m "Update dashboard $(date '+%Y-%m-%d %H:%M')"
    git push origin main
fi
