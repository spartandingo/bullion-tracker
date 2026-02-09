#!/bin/bash
# Run the full bullion price pipeline: scrape → generate site
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"

cd "$SKILL_DIR"

echo "=== Scraping bullion prices ==="
python3 scripts/scrape_prices.py -o data/prices.json --pretty

echo ""
echo "=== Generating site ==="
python3 scripts/generate_site.py -i data/prices.json -o site/index.html

echo ""
echo "=== Done ==="
echo "Products: $(python3 -c "import json; print(json.load(open('data/prices.json'))['total_products'])")"
echo "Site: site/index.html"

# If git repo exists and has a gh-pages setup, deploy
if [ -d ".git" ] || [ -d "../../.git" ]; then
    echo ""
    echo "To deploy: push site/index.html to your gh-pages branch or hosting"
fi
