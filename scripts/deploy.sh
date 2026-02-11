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

echo ""
echo "=== Deploying to gh-pages ==="
git checkout gh-pages
git checkout main -- site/index.html
cp site/index.html .
git add index.html
git commit -m "Daily price update $(date +%Y-%m-%d)" || echo "No changes to commit"
git push origin gh-pages
git checkout main

echo ""
echo "=== Done ==="
