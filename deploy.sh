#!/usr/bin/env bash
# Publish the review screen to Cloudflare Pages. Static only: the page, its three modules
# and the committed out/ folder. Nothing from data/, src/ or the virtual environment is sent.
#   ./deploy.sh            # after `python3 run.py` if out/ changed
set -euo pipefail
cd "$(dirname "$0")"
D="$(mktemp -d)"
cp index.html .nojekyll "$D/"
cp -R web out "$D/"
npx --yes wrangler pages deploy "$D" --project-name money-graph --branch main --commit-dirty=true
rm -rf "$D"
