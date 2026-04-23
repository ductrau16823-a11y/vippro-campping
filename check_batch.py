import csv, re, sys

path = sys.argv[1] if len(sys.argv) > 1 else 'batches/batch_02.csv'
with open(path, 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

bad_kw = []
for i, r in enumerate(rows, start=2):
    if r.get('Row Type') == 'Keyword':
        kw = r.get('Keyword', '')
        if len(kw) > 80:
            bad_kw.append(f'Row {i}: KW len={len(kw)}: {kw!r}')
        if re.search(r'[!@#$%^*()\[\]{}=+|\\;:"<>?/`~]', kw):
            bad_kw.append(f'Row {i}: KW special: {kw!r}')

print(f'Keyword issues: {len(bad_kw)}')
for x in bad_kw[:30]:
    print(x)

bad_url = []
for i, r in enumerate(rows, start=2):
    url = r.get('Final URL', '')
    if url and not url.startswith('http'):
        bad_url.append(f'Row {i}: bad URL: {url!r}')

print(f'URL issues: {len(bad_url)}')
for x in bad_url[:20]:
    print(x)

print('\nSample keywords:')
kws = [r for r in rows if r.get('Row Type') == 'Keyword']
for r in kws[:3]:
    print(f'  {r["Campaign"][:30]} | {r["Keyword"]!r}')
for r in kws[-3:]:
    print(f'  {r["Campaign"][:30]} | {r["Keyword"]!r}')

print('\nSample URLs (Sitelinks):')
sl = [r for r in rows if r.get('Row Type') == 'Sitelink']
for r in sl[:6]:
    print(f'  {r["Campaign"][:25]} | {r["Sitelink text"]!r} -> {r["Final URL"]!r}')

print('\nSample URLs (Ads):')
ads = [r for r in rows if r.get('Row Type') == 'Ad']
for r in ads[:3]:
    print(f'  {r["Campaign"][:25]} -> {r["Final URL"]!r}')
