---
name: bullion-prices
description: Scrape and compare gold, silver, and platinum bullion prices from Australian dealers (Ainslie Bullion, ABC Bullion, Perth Mint). Generate a static HTML comparison page with sortable tables, filters, and price-per-oz calculations. Use when asked about bullion prices, best deals on gold/silver/platinum bars or coins, or comparing dealers.
---

# Bullion Price Tracker

Scrape live prices from Australian bullion dealers and generate a comparison page.

## Quick Start

```bash
cd skills/bullion-prices

# Full pipeline: scrape + generate site
bash scripts/run.sh

# Or step by step:
python3 scripts/scrape_prices.py -o data/prices.json --pretty
python3 scripts/generate_site.py -i data/prices.json -o site/index.html
```

## Scrapers

### Ainslie Bullion
- Source: `https://ainsliebullion.com.au/Charts`
- Method: HTML scraping (server-rendered price sheet)
- Data: product name, buy price, sell-back price
- ~137 products across gold, silver, platinum

### ABC Bullion
- Source: `https://www.abcbullion.com.au/store/{metal}`
- Method: HTML scraping + embedded JSON price tiers
- Data: product name, buy price, volume pricing
- ~47 products across gold, silver, platinum

### Perth Mint
- Source: `https://www.perthmint.com/api/search/product/node/{id}`
- Method: JSON API (nodes: 1073746517=cast bars, 1073746518=coins, 1073746519=minted bars)
- Data: product name, price, stock status, SKU
- ~76 bullion products

## Site Features

- **Metal tabs**: Gold, Silver, Platinum
- **Sortable columns**: Name, Dealer, Type, Weight, Buy Price, Price/oz, Sell Back, Spread
- **Filters**: Product type (bar/coin/minted/unallocated), dealer, min/max price, weight
- **Best deal highlighting**: Green rows for lowest price/oz in each weight+type category
- **Spread calculation**: Buy vs sell-back spread percentage (where available)

## Data Format

```json
{
  "scraped_at": "ISO timestamp",
  "total_products": 260,
  "products": [{
    "dealer": "Ainslie Bullion",
    "dealer_id": "ainslie",
    "name": "1oz Gold Coin 2026 Kangaroo",
    "metal": "gold",
    "type": "coin",
    "weight_oz": 1.0,
    "buy_price": 7627.39,
    "sell_back_price": 6953.67,
    "price_per_oz": 7627.39,
    "url": "https://...",
    "in_stock": true
  }]
}
```

## Automation

Set up a daily cron job to scrape and regenerate:
```
# In HEARTBEAT.md or via cron tool
cd skills/bullion-prices && bash scripts/run.sh
```

Or deploy `site/index.html` to GitHub Pages for a public comparison page.
