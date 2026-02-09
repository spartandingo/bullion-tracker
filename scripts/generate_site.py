#!/usr/bin/env python3
"""
Generate a static HTML page from scraped bullion price data.

Produces a single index.html with:
  - Tabs for Gold / Silver / Platinum
  - Sortable table (by name, dealer, price, price/oz, weight, type)
  - Filters for product type, dealer, weight range
  - Price per oz highlighting (best deals)
  - Last updated timestamp
"""

import json
import sys
import os
from datetime import datetime, timezone

def fmt_price(val):
    """Format a price value."""
    if val is None:
        return '—'
    return f'${val:,.2f}'

def fmt_weight(oz):
    """Format weight nicely."""
    if oz is None:
        return '—'
    # Common conversions
    if abs(oz - round(oz)) < 0.001 and oz >= 1:
        return f'{int(round(oz))}oz'
    if abs(oz - 0.5) < 0.001:
        return '1/2oz'
    if abs(oz - 0.25) < 0.001:
        return '1/4oz'
    if abs(oz - 0.1) < 0.001:
        return '1/10oz'
    if abs(oz - 0.01) < 0.001:
        return '1/100oz'
    # Convert to grams if small
    grams = oz * 31.1035
    if grams < 31 and abs(grams - round(grams)) < 0.1:
        return f'{int(round(grams))}g'
    if abs(grams - 37.5) < 0.5:
        return '37.5g (tael)'
    if abs(grams - 100) < 1:
        return '100g'
    if abs(grams - 250) < 1:
        return '250g'
    if abs(grams - 500) < 1:
        return '500g'
    if abs(grams - 1000) < 5:
        return '1kg'
    if abs(grams - 5000) < 10:
        return '5kg'
    if abs(grams - 15000) < 50:
        return '15kg'
    return f'{oz:.2f}oz'

def type_label(t):
    """Human-readable type label."""
    return {
        'bar': 'Bar',
        'coin': 'Coin',
        'round': 'Round',
        'minted_bar': 'Minted Bar',
        'unallocated': 'Unallocated',
    }.get(t, t.title())

def generate_html(data, output_path):
    """Generate the static HTML page."""
    products = data['products']
    scraped_at = data.get('scraped_at', '')

    # Parse scraped time
    try:
        dt = datetime.fromisoformat(scraped_at)
        scraped_str = dt.astimezone(timezone.utc).strftime('%d %b %Y %H:%M UTC')
    except:
        scraped_str = scraped_at

    # Group by metal
    metals = ['gold', 'silver', 'platinum']
    metal_products = {m: [] for m in metals}
    for p in products:
        m = p.get('metal', 'gold')
        if m in metal_products:
            metal_products[m].append(p)

    # Get unique values for filters
    all_types = sorted(set(p['type'] for p in products))
    all_dealers = sorted(set(p['dealer'] for p in products))

    # Find best price per oz for each weight/type/metal combo
    best_per_oz = {}
    for p in products:
        key = (p['metal'], p['weight_oz'], p['type'])
        ppo = p.get('price_per_oz')
        if ppo and (key not in best_per_oz or ppo < best_per_oz[key]):
            best_per_oz[key] = ppo

    # Build table rows per metal
    def build_rows(metal_prods, metal):
        rows = []
        for p in sorted(metal_prods, key=lambda x: x.get('price_per_oz') or 999999):
            ppo = p.get('price_per_oz')
            key = (p['metal'], p['weight_oz'], p['type'])
            is_best = ppo and best_per_oz.get(key) == ppo and sum(
                1 for pp in metal_prods
                if pp['weight_oz'] == p['weight_oz'] and pp['type'] == p['type']
            ) > 1

            sell_back = p.get('sell_back_price')
            spread = None
            if sell_back and ppo:
                spread_pct = ((p['buy_price'] - sell_back) / p['buy_price']) * 100
                spread = f'{spread_pct:.1f}%'

            row = {
                'name': p['name'],
                'dealer': p['dealer'],
                'dealer_id': p.get('dealer_id', ''),
                'type': p['type'],
                'type_label': type_label(p['type']),
                'weight_oz': p['weight_oz'],
                'weight_label': fmt_weight(p['weight_oz']),
                'buy_price': p['buy_price'],
                'buy_price_fmt': fmt_price(p['buy_price']),
                'sell_back': sell_back,
                'sell_back_fmt': fmt_price(sell_back),
                'price_per_oz': ppo,
                'price_per_oz_fmt': fmt_price(ppo),
                'spread': spread,
                'url': p.get('url', '#'),
                'in_stock': p.get('in_stock', True),
                'is_best': is_best,
            }
            rows.append(row)
        return rows

    metal_rows = {}
    for m in metals:
        metal_rows[m] = build_rows(metal_products[m], m)

    # Generate HTML
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Australian Bullion Price Tracker</title>
<meta name="description" content="Compare gold, silver and platinum bullion prices from Australian dealers. Updated daily with live prices from Ainslie Bullion, ABC Bullion, and Perth Mint.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root {{
  --bg: #0f1117;
  --bg-card: #1a1d27;
  --bg-hover: #252836;
  --border: #2d3142;
  --text: #e4e4e7;
  --text-muted: #9ca3af;
  --gold: #d4a843;
  --gold-dim: #b8923a;
  --silver: #c0c0c0;
  --platinum: #a8b5c5;
  --green: #22c55e;
  --green-bg: rgba(34, 197, 94, 0.1);
  --red: #ef4444;
  --blue: #3b82f6;
  --tab-active: #d4a843;
}}
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: 'Inter', -apple-system, sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
  line-height: 1.5;
}}
.container {{ max-width: 1400px; margin: 0 auto; padding: 1rem; }}

/* Header */
header {{
  background: linear-gradient(135deg, #1a1d27 0%, #252836 100%);
  border-bottom: 1px solid var(--border);
  padding: 1.5rem 0;
}}
header .container {{
  display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;
}}
h1 {{
  font-size: 1.5rem; font-weight: 700;
  background: linear-gradient(135deg, var(--gold), #f0d78c);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}}
.updated {{ color: var(--text-muted); font-size: 0.8rem; }}

/* Tabs */
.tabs {{
  display: flex; gap: 0.25rem;
  background: var(--bg-card);
  border-radius: 0.75rem;
  padding: 0.25rem;
  margin: 1rem 0;
  border: 1px solid var(--border);
  width: fit-content;
}}
.tab {{
  padding: 0.6rem 1.5rem;
  border-radius: 0.5rem;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.9rem;
  transition: all 0.2s;
  border: none;
  background: transparent;
  color: var(--text-muted);
}}
.tab:hover {{ background: var(--bg-hover); color: var(--text); }}
.tab.active {{ color: #000; }}
.tab.active[data-metal="gold"] {{ background: var(--gold); }}
.tab.active[data-metal="silver"] {{ background: var(--silver); }}
.tab.active[data-metal="platinum"] {{ background: var(--platinum); }}

/* Filters */
.filters {{
  display: flex; gap: 0.75rem; flex-wrap: wrap; align-items: center;
  margin-bottom: 1rem;
  padding: 1rem;
  background: var(--bg-card);
  border-radius: 0.75rem;
  border: 1px solid var(--border);
}}
.filter-group {{ display: flex; flex-direction: column; gap: 0.25rem; }}
.filter-group label {{
  font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.05em;
  color: var(--text-muted); font-weight: 600;
}}
.filter-group select, .filter-group input {{
  background: var(--bg); border: 1px solid var(--border);
  color: var(--text); padding: 0.4rem 0.6rem;
  border-radius: 0.4rem; font-size: 0.85rem;
  font-family: inherit;
}}
.filter-group select {{ min-width: 130px; }}
.filter-group input {{ width: 100px; }}
.filter-group input::placeholder {{ color: var(--text-muted); }}
.btn-reset {{
  background: transparent; border: 1px solid var(--border);
  color: var(--text-muted); padding: 0.4rem 0.8rem;
  border-radius: 0.4rem; cursor: pointer; font-size: 0.8rem;
  align-self: flex-end; font-family: inherit;
}}
.btn-reset:hover {{ border-color: var(--text-muted); color: var(--text); }}

/* Stats bar */
.stats {{
  display: flex; gap: 1.5rem; flex-wrap: wrap;
  margin-bottom: 1rem; font-size: 0.85rem; color: var(--text-muted);
}}
.stat {{ display: flex; gap: 0.3rem; }}
.stat-val {{ color: var(--text); font-weight: 600; }}

/* Table */
.table-wrap {{
  overflow-x: auto;
  border-radius: 0.75rem;
  border: 1px solid var(--border);
  background: var(--bg-card);
}}
table {{
  width: 100%; border-collapse: collapse;
  font-size: 0.85rem;
}}
thead th {{
  position: sticky; top: 0;
  background: var(--bg-card);
  padding: 0.75rem 0.6rem;
  text-align: left;
  font-weight: 600;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  border-bottom: 2px solid var(--border);
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
}}
thead th:hover {{ color: var(--text); }}
thead th .sort-arrow {{ margin-left: 0.3rem; opacity: 0.4; }}
thead th.sorted .sort-arrow {{ opacity: 1; }}
tbody tr {{
  border-bottom: 1px solid var(--border);
  transition: background 0.15s;
}}
tbody tr:hover {{ background: var(--bg-hover); }}
tbody tr.best-deal {{ background: var(--green-bg); }}
tbody tr.out-of-stock {{ opacity: 0.5; }}
td {{
  padding: 0.6rem;
  white-space: nowrap;
}}
td.name {{ white-space: normal; max-width: 300px; }}
td.name a {{
  color: var(--blue); text-decoration: none;
}}
td.name a:hover {{ text-decoration: underline; }}
td.price {{ text-align: right; font-variant-numeric: tabular-nums; font-weight: 500; }}
td.ppo {{ text-align: right; font-variant-numeric: tabular-nums; font-weight: 600; }}
td.best {{ color: var(--green); }}
td.spread {{ text-align: right; color: var(--text-muted); font-size: 0.8rem; }}
td.dealer {{ color: var(--text-muted); }}
.badge {{
  display: inline-block; padding: 0.15rem 0.4rem;
  border-radius: 0.25rem; font-size: 0.7rem; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.03em;
}}
.badge-bar {{ background: rgba(212,168,67,0.15); color: var(--gold); }}
.badge-coin {{ background: rgba(59,130,246,0.15); color: var(--blue); }}
.badge-minted {{ background: rgba(168,181,197,0.15); color: var(--platinum); }}
.badge-unallocated {{ background: rgba(34,197,94,0.15); color: var(--green); }}
.badge-round {{ background: rgba(192,192,192,0.15); color: var(--silver); }}
.no-results {{
  text-align: center; padding: 3rem 1rem; color: var(--text-muted);
}}

/* Footer */
footer {{
  text-align: center; padding: 2rem 1rem;
  color: var(--text-muted); font-size: 0.75rem;
  border-top: 1px solid var(--border); margin-top: 2rem;
}}
footer a {{ color: var(--gold-dim); text-decoration: none; }}

/* Responsive */
@media (max-width: 768px) {{
  .container {{ padding: 0.5rem; }}
  .filters {{ gap: 0.5rem; padding: 0.75rem; }}
  h1 {{ font-size: 1.2rem; }}
  table {{ font-size: 0.75rem; }}
  td, th {{ padding: 0.4rem 0.3rem; }}
}}

/* Metal panel visibility */
.metal-panel {{ display: none; }}
.metal-panel.active {{ display: block; }}
</style>
</head>
<body>

<header>
  <div class="container">
    <h1>🥇 Australian Bullion Price Tracker</h1>
    <div class="updated">Last updated: {scraped_str}</div>
  </div>
</header>

<div class="container">
  <div class="tabs">
    <button class="tab active" data-metal="gold" onclick="switchTab('gold')">Gold ({len(metal_products['gold'])})</button>
    <button class="tab" data-metal="silver" onclick="switchTab('silver')">Silver ({len(metal_products['silver'])})</button>
    <button class="tab" data-metal="platinum" onclick="switchTab('platinum')">Platinum ({len(metal_products['platinum'])})</button>
  </div>

  <div class="filters">
    <div class="filter-group">
      <label>Type</label>
      <select id="filter-type" onchange="applyFilters()">
        <option value="">All Types</option>
        {''.join(f'<option value="{t}">{type_label(t)}</option>' for t in all_types)}
      </select>
    </div>
    <div class="filter-group">
      <label>Dealer</label>
      <select id="filter-dealer" onchange="applyFilters()">
        <option value="">All Dealers</option>
        {''.join(f'<option value="{d}">{d}</option>' for d in all_dealers)}
      </select>
    </div>
    <div class="filter-group">
      <label>Min Price</label>
      <input type="number" id="filter-min" placeholder="$0" onchange="applyFilters()">
    </div>
    <div class="filter-group">
      <label>Max Price</label>
      <input type="number" id="filter-max" placeholder="No max" onchange="applyFilters()">
    </div>
    <div class="filter-group">
      <label>Weight</label>
      <select id="filter-weight" onchange="applyFilters()">
        <option value="">All Weights</option>
      </select>
    </div>
    <button class="btn-reset" onclick="resetFilters()">Reset</button>
  </div>

  <div class="stats" id="stats"></div>

'''

    # Generate a table for each metal
    for metal in metals:
        rows = metal_rows[metal]
        active = ' active' if metal == 'gold' else ''
        html += f'  <div class="metal-panel{active}" id="panel-{metal}">\n'
        html += '    <div class="table-wrap">\n'
        html += '''    <table id="table-''' + metal + '''">
      <thead>
        <tr>
          <th data-sort="name" onclick="sortTable(this)">Product <span class="sort-arrow">↕</span></th>
          <th data-sort="dealer" onclick="sortTable(this)">Dealer <span class="sort-arrow">↕</span></th>
          <th data-sort="type" onclick="sortTable(this)">Type <span class="sort-arrow">↕</span></th>
          <th data-sort="weight" onclick="sortTable(this)">Weight <span class="sort-arrow">↕</span></th>
          <th data-sort="buy" onclick="sortTable(this)">Buy Price <span class="sort-arrow">↕</span></th>
          <th data-sort="ppo" onclick="sortTable(this)">Price/oz <span class="sort-arrow">↕</span></th>
          <th data-sort="sellback" onclick="sortTable(this)">Sell Back <span class="sort-arrow">↕</span></th>
          <th data-sort="spread" onclick="sortTable(this)">Spread <span class="sort-arrow">↕</span></th>
        </tr>
      </thead>
      <tbody>
'''
        for r in rows:
            best_class = ' best-deal' if r['is_best'] else ''
            stock_class = ' out-of-stock' if not r['in_stock'] else ''
            ppo_class = ' best' if r['is_best'] else ''
            badge_class = f'badge-{r["type"].replace("_", "")}'
            if r['type'] == 'minted_bar':
                badge_class = 'badge-minted'

            spread_val = r['spread'] or '—'

            html += f'''        <tr class="product-row{best_class}{stock_class}" data-dealer="{r['dealer']}" data-type="{r['type']}" data-weight="{r['weight_oz']}" data-buy="{r['buy_price']}" data-ppo="{r['price_per_oz'] or 0}">
          <td class="name"><a href="{r['url']}" target="_blank" rel="noopener">{r['name']}</a></td>
          <td class="dealer">{r['dealer']}</td>
          <td><span class="badge {badge_class}">{r['type_label']}</span></td>
          <td>{r['weight_label']}</td>
          <td class="price">{r['buy_price_fmt']}</td>
          <td class="ppo{ppo_class}">{r['price_per_oz_fmt']}</td>
          <td class="price">{r['sell_back_fmt']}</td>
          <td class="spread">{spread_val}</td>
        </tr>
'''

        html += '''      </tbody>
    </table>
    </div>
  </div>
'''

    html += f'''
  </div>

<footer>
  <p>Data scraped from
    <a href="https://ainsliebullion.com.au/Charts" target="_blank">Ainslie Bullion</a>,
    <a href="https://www.abcbullion.com.au/store" target="_blank">ABC Bullion</a>,
    <a href="https://www.perthmint.com/shop/bullion/" target="_blank">Perth Mint</a>.
    Prices are indicative and may change. Always confirm on the dealer's website before purchasing.
  </p>
  <p style="margin-top:0.5rem">Updated daily. Sorted by price per troy ounce by default.</p>
</footer>

<script>
let currentMetal = 'gold';
let sortState = {{}};

function switchTab(metal) {{
  currentMetal = metal;
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelector(`.tab[data-metal="${{metal}}"]`).classList.add('active');
  document.querySelectorAll('.metal-panel').forEach(p => p.classList.remove('active'));
  document.getElementById('panel-' + metal).classList.add('active');
  updateWeightFilter();
  applyFilters();
}}

function updateWeightFilter() {{
  const select = document.getElementById('filter-weight');
  const panel = document.getElementById('panel-' + currentMetal);
  const rows = panel.querySelectorAll('.product-row');
  const weights = new Set();
  rows.forEach(r => weights.add(r.dataset.weight));
  const sorted = [...weights].sort((a, b) => parseFloat(a) - parseFloat(b));

  const current = select.value;
  select.innerHTML = '<option value="">All Weights</option>';
  sorted.forEach(w => {{
    const label = formatWeight(parseFloat(w));
    select.innerHTML += `<option value="${{w}}">${{label}}</option>`;
  }});
  select.value = current;
}}

function formatWeight(oz) {{
  if (Math.abs(oz - 0.01) < 0.001) return '1/100oz';
  if (Math.abs(oz - 0.1) < 0.001) return '1/10oz';
  if (Math.abs(oz - 0.25) < 0.001) return '1/4oz';
  if (Math.abs(oz - 0.5) < 0.001) return '1/2oz';
  if (oz >= 1 && Math.abs(oz - Math.round(oz)) < 0.01) return Math.round(oz) + 'oz';
  const g = oz * 31.1035;
  if (g < 31 && Math.abs(g - Math.round(g)) < 0.5) return Math.round(g) + 'g';
  if (Math.abs(g - 37.5) < 1) return '37.5g';
  if (Math.abs(g - 100) < 2) return '100g';
  if (Math.abs(g - 250) < 3) return '250g';
  if (Math.abs(g - 500) < 5) return '500g';
  if (Math.abs(g - 1000) < 10) return '1kg';
  if (Math.abs(g - 5000) < 20) return '5kg';
  if (Math.abs(g - 15000) < 50) return '15kg';
  return oz.toFixed(2) + 'oz';
}}

function applyFilters() {{
  const type = document.getElementById('filter-type').value;
  const dealer = document.getElementById('filter-dealer').value;
  const minPrice = parseFloat(document.getElementById('filter-min').value) || 0;
  const maxPrice = parseFloat(document.getElementById('filter-max').value) || Infinity;
  const weight = document.getElementById('filter-weight').value;

  const panel = document.getElementById('panel-' + currentMetal);
  const rows = panel.querySelectorAll('.product-row');
  let visible = 0;
  let lowestPPO = Infinity;
  let bestDeal = '';

  rows.forEach(row => {{
    const matchType = !type || row.dataset.type === type;
    const matchDealer = !dealer || row.dataset.dealer === dealer;
    const price = parseFloat(row.dataset.buy);
    const matchMin = price >= minPrice;
    const matchMax = price <= maxPrice;
    const matchWeight = !weight || row.dataset.weight === weight;

    const show = matchType && matchDealer && matchMin && matchMax && matchWeight;
    row.style.display = show ? '' : 'none';
    if (show) {{
      visible++;
      const ppo = parseFloat(row.dataset.ppo);
      if (ppo > 0 && ppo < lowestPPO) {{
        lowestPPO = ppo;
        bestDeal = row.querySelector('.name a').textContent;
      }}
    }}
  }});

  // Update stats
  const statsEl = document.getElementById('stats');
  let statsHtml = `<div class="stat">Showing: <span class="stat-val">${{visible}}</span> products</div>`;
  if (lowestPPO < Infinity) {{
    statsHtml += `<div class="stat">Best price/oz: <span class="stat-val">${{lowestPPO.toLocaleString('en-AU', {{style:'currency',currency:'AUD'}})}}</span></div>`;
    statsHtml += `<div class="stat">Best deal: <span class="stat-val">${{bestDeal}}</span></div>`;
  }}
  statsEl.innerHTML = statsHtml;
}}

function resetFilters() {{
  document.getElementById('filter-type').value = '';
  document.getElementById('filter-dealer').value = '';
  document.getElementById('filter-min').value = '';
  document.getElementById('filter-max').value = '';
  document.getElementById('filter-weight').value = '';
  applyFilters();
}}

function sortTable(th) {{
  const key = th.dataset.sort;
  const table = th.closest('table');
  const tbody = table.querySelector('tbody');
  const rows = Array.from(tbody.querySelectorAll('.product-row'));

  // Toggle direction
  const id = table.id + '-' + key;
  sortState[id] = sortState[id] === 'asc' ? 'desc' : 'asc';
  const dir = sortState[id] === 'asc' ? 1 : -1;

  // Update visual
  table.querySelectorAll('th').forEach(t => t.classList.remove('sorted'));
  th.classList.add('sorted');
  th.querySelector('.sort-arrow').textContent = dir === 1 ? '↑' : '↓';

  rows.sort((a, b) => {{
    let va, vb;
    switch(key) {{
      case 'name': va = a.querySelector('.name').textContent.trim(); vb = b.querySelector('.name').textContent.trim(); return dir * va.localeCompare(vb);
      case 'dealer': va = a.dataset.dealer; vb = b.dataset.dealer; return dir * va.localeCompare(vb);
      case 'type': va = a.dataset.type; vb = b.dataset.type; return dir * va.localeCompare(vb);
      case 'weight': return dir * (parseFloat(a.dataset.weight) - parseFloat(b.dataset.weight));
      case 'buy': return dir * (parseFloat(a.dataset.buy) - parseFloat(b.dataset.buy));
      case 'ppo': return dir * (parseFloat(a.dataset.ppo) - parseFloat(b.dataset.ppo));
      case 'sellback':
        va = a.querySelector('td:nth-child(7)').textContent.trim();
        vb = b.querySelector('td:nth-child(7)').textContent.trim();
        va = va === '—' ? 0 : parseFloat(va.replace(/[$,]/g, ''));
        vb = vb === '—' ? 0 : parseFloat(vb.replace(/[$,]/g, ''));
        return dir * (va - vb);
      case 'spread':
        va = a.querySelector('td:nth-child(8)').textContent.trim();
        vb = b.querySelector('td:nth-child(8)').textContent.trim();
        va = va === '—' ? 999 : parseFloat(va);
        vb = vb === '—' ? 999 : parseFloat(vb);
        return dir * (va - vb);
      default: return 0;
    }}
  }});

  rows.forEach(r => tbody.appendChild(r));
}}

// Initialize
updateWeightFilter();
applyFilters();
</script>
</body>
</html>'''

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(html)
    print(f'Generated {output_path} ({len(products)} products)')


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Generate bullion price comparison page')
    parser.add_argument('--input', '-i', default='data/prices.json',
                        help='Input JSON file from scraper')
    parser.add_argument('--output', '-o', default='site/index.html',
                        help='Output HTML file')
    args = parser.parse_args()

    with open(args.input) as f:
        data = json.load(f)

    generate_html(data, args.output)


if __name__ == '__main__':
    main()
