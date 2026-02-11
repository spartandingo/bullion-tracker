#!/bin/bash
# Full pipeline: scrape, generate site, deploy to gh-pages
set -e

SKILL_DIR="/opt/moltbot/workspace/skills/bullion-prices"
cd "$SKILL_DIR"

echo "=== Scraping bullion prices ==="
python3 scripts/scrape_prices.py -o data/prices.json --pretty

echo ""
echo "=== Generating site ==="
python3 scripts/generate_site.py -i data/prices.json -o site/index.html

TOTAL=$(python3 -c "import json; print(json.load(open('data/prices.json'))['total_products'])")
echo "Products: $TOTAL"

# Save generated file to temp location (survives branch switch)
cp site/index.html /tmp/bullion-index.html

echo ""
echo "=== Committing to main ==="
git add -A
git commit -m "Daily price update $(date +%Y-%m-%d)" || echo "No changes on main"
git push origin main || echo "Main push skipped"

echo ""
echo "=== Deploying to gh-pages ==="
git checkout gh-pages
cp /tmp/bullion-index.html index.html
git add index.html
git commit -m "Daily price update $(date +%Y-%m-%d)" || echo "No changes to commit"
git push origin gh-pages
git checkout main

rm -f /tmp/bullion-index.html

echo ""
echo "=== Done ==="
