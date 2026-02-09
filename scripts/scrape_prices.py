#!/usr/bin/env python3
"""
Scrape bullion prices from Australian precious metal dealers.

Dealers:
  - Ainslie Bullion (ainsliebullion.com.au)
  - ABC Bullion (abcbullion.com.au)
  - Perth Mint (perthmint.com)

Outputs JSON with normalized product data.
"""

import re
import json
import sys
import time
import logging
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from html.parser import HTMLParser

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger(__name__)

TROY_OZ_PER_GRAM = 1 / 31.1035
TROY_OZ_PER_KG = 1000 / 31.1035

# Weight mappings in troy ounces
WEIGHT_MAP = {
    '1/100oz': 0.01,
    '1/10oz': 0.1,
    '1/4oz': 0.25,
    '1/2oz': 0.5,
    '1oz': 1.0,
    '2oz': 2.0,
    '5oz': 5.0,
    '10oz': 10.0,
    '20oz': 20.0,
    '50oz': 50.0,
    '100oz': 100.0,
    '400oz': 400.0,
    '1g': 1 * TROY_OZ_PER_GRAM,
    '2g': 2 * TROY_OZ_PER_GRAM,
    '2.5g': 2.5 * TROY_OZ_PER_GRAM,
    '5g': 5 * TROY_OZ_PER_GRAM,
    '10g': 10 * TROY_OZ_PER_GRAM,
    '20g': 20 * TROY_OZ_PER_GRAM,
    '31.1g': 1.0,  # 1 troy oz
    '37.5g': 37.5 * TROY_OZ_PER_GRAM,
    '50g': 50 * TROY_OZ_PER_GRAM,
    '100g': 100 * TROY_OZ_PER_GRAM,
    '250g': 250 * TROY_OZ_PER_GRAM,
    '500g': 500 * TROY_OZ_PER_GRAM,
    '1kg': TROY_OZ_PER_KG,
    '5kg': 5 * TROY_OZ_PER_KG,
    '15kg': 15 * TROY_OZ_PER_KG,
}


def fetch_url(url, headers=None, timeout=30):
    """Fetch URL content with error handling."""
    hdrs = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) '
                       'Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,'
                  'application/json,*/*;q=0.8',
        'Accept-Language': 'en-AU,en;q=0.9',
    }
    if headers:
        hdrs.update(headers)

    req = Request(url, headers=hdrs)
    try:
        with urlopen(req, timeout=timeout) as resp:
            return resp.read().decode('utf-8', errors='replace')
    except (URLError, HTTPError) as e:
        log.error(f"Failed to fetch {url}: {e}")
        return None


def parse_weight_oz(name):
    """Extract weight in troy ounces from a product name."""
    name_lower = name.lower().strip()

    # Try direct weight matches
    # Match patterns like "1/2oz", "10oz", "1kg", "100g", "37.5g", etc.
    patterns = [
        (r'(\d+/\d+)\s*oz', 'frac_oz'),
        (r'([\d.]+)\s*oz', 'oz'),
        (r'([\d.]+)\s*kg', 'kg'),
        (r'([\d.]+)\s*(?:gram|g\b)', 'g'),
        (r'([\d.]+)\s*(?:tael)', 'tael'),
    ]

    for pattern, unit in patterns:
        m = re.search(pattern, name_lower)
        if m:
            val_str = m.group(1)
            if unit == 'frac_oz':
                parts = val_str.split('/')
                val = float(parts[0]) / float(parts[1])
                return val
            val = float(val_str)
            if unit == 'oz':
                return val
            elif unit == 'kg':
                return val * TROY_OZ_PER_KG
            elif unit == 'g':
                return val * TROY_OZ_PER_GRAM
            elif unit == 'tael':
                return val * 37.5 * TROY_OZ_PER_GRAM

    # Special cases
    if 'maplegram25' in name_lower or 'maplegram 25' in name_lower:
        return 25 * TROY_OZ_PER_GRAM  # 25 x 1g

    return None


def classify_product_type(name, category_hint=''):
    """Classify product as bar, coin, round, minted, or unallocated."""
    name_lower = name.lower()
    cat_lower = category_hint.lower()

    if any(w in name_lower for w in ['unalloc', 'pool', 'pool allocated']):
        return 'unallocated'
    if any(w in name_lower for w in ['coin', 'kangaroo', 'kookaburra',
                                      'koala', 'lunar', 'britannia',
                                      'eagle', 'maple', 'philharmonic',
                                      'buffalo', 'krugerrand', 'sovereign',
                                      'nugget', 'dragon', 'snake', 'horse',
                                      'emu', 'swan', 'phoenix', 'guardian',
                                      'proclamation', 'olympics',
                                      'rectangular coin']):
        return 'coin'
    if 'coin' in cat_lower:
        return 'coin'
    if any(w in name_lower for w in ['minted', 'tablet']):
        return 'minted_bar'
    if any(w in name_lower for w in ['round']):
        return 'round'
    if any(w in name_lower for w in ['bar', 'bullion', 'cast', 'ingot']):
        return 'bar'

    # Default based on category
    if 'cast' in cat_lower:
        return 'bar'
    if 'minted' in cat_lower:
        return 'minted_bar'

    return 'bar'  # default


def classify_metal(name, section=''):
    """Classify the metal type."""
    name_lower = (name + ' ' + section).lower()
    if 'platinum' in name_lower:
        return 'platinum'
    if 'silver' in name_lower:
        return 'silver'
    if 'palladium' in name_lower:
        return 'palladium'
    return 'gold'


def parse_price(s):
    """Parse a price string to float."""
    if not s:
        return None
    s = s.strip().replace('$', '').replace(',', '').replace(' ', '')
    try:
        return float(s)
    except ValueError:
        return None


# ─── Ainslie Bullion ────────────────────────────────────────────

def scrape_ainslie():
    """Scrape Ainslie Bullion's live price sheet."""
    log.info("Scraping Ainslie Bullion...")
    html = fetch_url('https://ainsliebullion.com.au/Charts')
    if not html:
        return []

    products = []
    current_section = 'gold'  # Track which metal section we're in

    # The page has sections: Gold Products, Silver Products, Platinum Products
    # Each section has cards with product groups

    # Split by metal sections
    # Simple text-based section splitting
    section_boundaries = []
    for label in ['Gold Products', 'Silver Products', 'Platinum Products']:
        idx = html.find(label)
        if idx >= 0:
            section_boundaries.append((label, idx))

    metal_sections = []
    for i, (label, start) in enumerate(section_boundaries):
        end = section_boundaries[i + 1][1] if i + 1 < len(section_boundaries) else len(html)
        metal = label.split()[0].lower()
        metal_sections.append((metal, html[start:end]))

    for metal, section_html in metal_sections:

        # Find product rows: title="NAME" ... sell_price ... buy_price
        product_rows = re.findall(
            r'title="([^"]+)"[^>]*class="col-6 col-md-8 text-truncate".*?'
            r'class="col-3 col-md-2 text-end">([\d.]+)</div>.*?'
            r'class="col-3 col-md-2 text-end">([\d.]+)</div>',
            section_html, re.DOTALL
        )

        for name, sell_back, buy_price in product_rows:
            weight_oz = parse_weight_oz(name)
            if weight_oz is None or weight_oz == 0:
                continue

            buy_f = parse_price(buy_price)
            sell_f = parse_price(sell_back)
            if buy_f is None:
                continue

            product = {
                'dealer': 'Ainslie Bullion',
                'dealer_id': 'ainslie',
                'name': name.strip(),
                'metal': metal,
                'type': classify_product_type(name),
                'weight_oz': round(weight_oz, 4),
                'buy_price': buy_f,
                'sell_back_price': sell_f,
                'price_per_oz': round(buy_f / weight_oz, 2) if weight_oz > 0 else None,
                'url': f'https://ainsliebullion.com.au/Charts',
                'in_stock': True,
            }
            products.append(product)

    log.info(f"  Ainslie: found {len(products)} products")
    return products


# ─── ABC Bullion ────────────────────────────────────────────────

def scrape_abc_store_page(url, metal):
    """Scrape an ABC Bullion store page for products."""
    html = fetch_url(url)
    if not html:
        return []

    products = []

    # Split by product items
    items = re.split(r'<div\s+class="item\s+item-infi\s+col-', html)

    for item_html in items[1:]:  # Skip first (before any product)
        # Get product name from itemprop="name"
        name_match = re.search(
            r'itemprop="name"[^>]*title="([^"]+)"',
            item_html
        )
        if not name_match:
            name_match = re.search(r'<a[^>]*title="([^"]+)"', item_html)
        if not name_match:
            continue
        name = name_match.group(1).strip()

        # Get price from <span class="price">
        price_match = re.search(
            r'class="price"[^>]*>\s*([\d,. ]+)\s*<',
            item_html
        )
        if not price_match:
            continue
        buy_price = parse_price(price_match.group(1))
        if not buy_price:
            continue

        # Get product URL
        link_match = re.search(r'href="(https://www\.abcbullion\.com\.au/store/[^"]+)"', item_html)
        prod_url = link_match.group(1) if link_match else url

        weight_oz = parse_weight_oz(name)
        if weight_oz is None or weight_oz == 0:
            continue

        product = {
            'dealer': 'ABC Bullion',
            'dealer_id': 'abc',
            'name': name,
            'metal': metal,
            'type': classify_product_type(name),
            'weight_oz': round(weight_oz, 4),
            'buy_price': buy_price,
            'sell_back_price': None,
            'price_per_oz': round(buy_price / weight_oz, 2) if weight_oz > 0 else None,
            'url': prod_url,
            'in_stock': True,
        }

        # Try to get volume pricing from embedded JSON
        item_id_match = re.search(r'id="item_(\d+)"', item_html)
        if item_id_match:
            item_id = item_id_match.group(1)
            json_match = re.search(
                rf"item_{item_id}\s*=\s*JSON\.parse\('(\{{[^']*\}})'\)",
                html  # Search full page as scripts may be after the item
            )
            if json_match:
                try:
                    price_data = json.loads(json_match.group(1))
                    tiers = []
                    for tier_key in sorted(price_data.keys(),
                                           key=lambda x: int(x) if x.isdigit() else 999):
                        tier = price_data[tier_key]
                        t_price = parse_price(tier.get('price', ''))
                        if t_price:
                            tiers.append({
                                'min_qty': tier.get('min', 1),
                                'max_qty': tier.get('max'),
                                'price': t_price,
                            })
                    if len(tiers) > 1:
                        product['volume_pricing'] = tiers
                    # Use best price for min qty 1
                    if tiers:
                        product['buy_price'] = tiers[0]['price']
                        product['price_per_oz'] = round(tiers[0]['price'] / weight_oz, 2)
                except json.JSONDecodeError:
                    pass

        products.append(product)

    return products


def scrape_abc():
    """Scrape ABC Bullion store pages."""
    log.info("Scraping ABC Bullion...")
    all_products = []

    pages = [
        ('https://www.abcbullion.com.au/store/gold', 'gold'),
        ('https://www.abcbullion.com.au/store/silver', 'silver'),
        ('https://www.abcbullion.com.au/store/platinum', 'platinum'),
    ]

    for url, metal in pages:
        prods = scrape_abc_store_page(url, metal)
        all_products.extend(prods)
        time.sleep(1)  # Be nice

    log.info(f"  ABC Bullion: found {len(all_products)} products")
    return all_products


# ─── Perth Mint ─────────────────────────────────────────────────

def scrape_perth_mint():
    """Scrape Perth Mint using their product API."""
    log.info("Scraping Perth Mint...")

    # Category node IDs for bullion
    categories = [
        (1073746517, 'cast_bars'),
        (1073746518, 'coins'),
        (1073746519, 'minted_bars'),
    ]

    products = []
    seen_skus = set()

    for node_id, cat_name in categories:
        url = f'https://www.perthmint.com/api/search/product/node/{node_id}?pageSize=200'
        data_str = fetch_url(url, headers={'Accept': 'application/json'})
        if not data_str:
            continue

        try:
            data = json.loads(data_str)
        except json.JSONDecodeError:
            log.error(f"  Failed to parse Perth Mint API response for node {node_id}")
            continue

        result = data.get('result', {})
        items = result.get('products', [])
        log.info(f"  Perth Mint {cat_name}: {len(items)} items")

        for item in items:
            title = item.get('title', '') or item.get('description', '')
            if not title:
                continue

            # Skip archived/unavailable
            if item.get('isArchived') or item.get('isNoLongerAvailable'):
                continue

            # Skip duplicates
            sku = item.get('skuItemNumber', '')
            if sku in seen_skus:
                continue
            seen_skus.add(sku)

            # Get price
            prices = item.get('prices') or {}
            adj_price = prices.get('adjustedPrice') or {}
            buy_price = adj_price.get('price')
            if not buy_price:
                base_price = prices.get('basePrice') or {}
                buy_price = base_price.get('price')

            if not buy_price:
                continue

            # Only include bullion (skip collector coins)
            item_type = item.get('type', '')
            if item_type != 'Bullion':
                continue

            # Determine metal from title and category
            metal = classify_metal(title, item.get('category', ''))

            weight_oz = parse_weight_oz(title)
            if weight_oz is None or weight_oz == 0:
                continue

            # Determine product type
            category = item.get('category', '')
            prod_type = classify_product_type(title, category)

            product = {
                'dealer': 'Perth Mint',
                'dealer_id': 'perth_mint',
                'name': title.strip(),
                'metal': metal,
                'type': prod_type,
                'weight_oz': round(weight_oz, 4),
                'buy_price': buy_price,
                'sell_back_price': None,
                'price_per_oz': round(buy_price / weight_oz, 2) if weight_oz > 0 else None,
                'url': item.get('link', 'https://www.perthmint.com/shop/bullion/'),
                'in_stock': item.get('canAddToCart', False) and not item.get('isOutOfStock', False),
                'sku': sku,
            }

            products.append(product)

        time.sleep(1)

    log.info(f"  Perth Mint: found {len(products)} products")
    return products


# ─── Main ───────────────────────────────────────────────────────

def scrape_all():
    """Scrape all dealers and return combined data."""
    all_products = []

    scrapers = [
        scrape_ainslie,
        scrape_abc,
        scrape_perth_mint,
    ]

    for scraper in scrapers:
        try:
            products = scraper()
            all_products.extend(products)
        except Exception as e:
            log.error(f"Error in {scraper.__name__}: {e}", exc_info=True)

    # Add metadata
    result = {
        'scraped_at': datetime.now(timezone.utc).isoformat(),
        'total_products': len(all_products),
        'dealers': list(set(p['dealer'] for p in all_products)),
        'products': all_products,
    }

    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Scrape Australian bullion prices')
    parser.add_argument('--output', '-o', default='-',
                        help='Output file (default: stdout)')
    parser.add_argument('--dealer', choices=['ainslie', 'abc', 'perth_mint', 'all'],
                        default='all', help='Which dealer to scrape')
    parser.add_argument('--pretty', action='store_true',
                        help='Pretty-print JSON output')
    args = parser.parse_args()

    if args.dealer == 'all':
        result = scrape_all()
    else:
        scraper_map = {
            'ainslie': scrape_ainslie,
            'abc': scrape_abc,
            'perth_mint': scrape_perth_mint,
        }
        products = scraper_map[args.dealer]()
        result = {
            'scraped_at': datetime.now(timezone.utc).isoformat(),
            'total_products': len(products),
            'dealers': [args.dealer],
            'products': products,
        }

    indent = 2 if args.pretty else None

    if args.output == '-':
        json.dump(result, sys.stdout, indent=indent, ensure_ascii=False)
        print()
    else:
        import os
        os.makedirs(os.path.dirname(args.output) or '.', exist_ok=True)
        with open(args.output, 'w') as f:
            json.dump(result, f, indent=indent, ensure_ascii=False)
        log.info(f"Wrote {result['total_products']} products to {args.output}")


if __name__ == '__main__':
    main()
