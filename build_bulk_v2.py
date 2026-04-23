#!/usr/bin/env python3
"""
build_bulk_v2.py

Generate 6 separate Google Ads bulk upload CSVs matching OFFICIAL Google templates.
Each file imports into Google Ads > Tools & Settings > Bulk actions > Uploads.

Upload order:
  01_campaigns.csv    -> tao 200 camp
  02_ad_groups.csv    -> tao AG-1 cho moi camp
  03_keywords.csv     -> add keywords vao AG
  04_rsa.csv          -> tao RSA
  05_sitelinks.csv    -> tao 3 sitelinks/camp (Row Type=Sitelink)
  06_callouts.csv     -> tao 4 callouts/camp (Row type=Callout extension)

Max CPC bid limit cho Maximize Clicks: KHONG co CSV nao support.
Set tay o UI: chon all camp > Edit > Change bid strategy > tick Max CPC = 0.40

Usage:
  python build_bulk_v2.py batch_200.json
  python build_bulk_v2.py batch_200.json --limit 5
  python build_bulk_v2.py batch_200.json --out-dir out/
"""
import json
import csv
import argparse
import sys
from pathlib import Path

LOCATION_MAP = {
    'Hoa Kỳ':         2840,
    'Canada':         2124,
    'Vương quốc Anh': 2826,
    'Đức':            2276,
    'Úc':             2036,
    'Pháp':           2250,
    'Ý':              2380,
    'Tây Ban Nha':    2724,
}

BIDDING_MAP = {
    'Tối đa lượt nhấn chuột': 'Maximize clicks',
    'Thủ công CPC':            'Manual CPC',
    'Tối đa hóa chuyển đổi':   'Maximize Conversions',
    'Tối đa hóa giá trị chuyển đổi': 'Target ROAS',
}

# Fixed sitelink template (applied to every project, URL = link1 + suffix)
SITELINK_TEMPLATES = [
    {'text': "Today's Top Coupon",    'd1': 'Provide the best coupons',    'd2': 'Rated by the user',             'suffix': '&1'},
    {'text': 'Best Deals Of The Days','d1': 'Sale Up To 60%',              'd2': 'To save your money',            'suffix': ''},
    {'text': 'All Blog',              'd1': 'Save with All Blog coupons',  'd2': 'Discounts and promo codes for', 'suffix': '&2'},
]

CALLOUTS_FIXED = [
    'Rate: 4.93 / 5.0',
    '100% Working Code',
    'All Code Verified',
    'Free Code',
]

HEADLINE_MAX = 30
DESC_MAX = 90
RSA_MIN_HEADLINES = 3
RSA_MIN_DESCS = 2
RSA_MAX_HEADLINES = 15
RSA_MAX_DESCS = 4

FALLBACK_HEADLINES = [
    'Top Coupons Today', 'Save Up To 55% Off', 'Verified Promo Codes',
    'Exclusive Deals Here', 'Hot Discount Today', 'Official Promo Codes',
    'Best Deals Online', 'Shop & Save Today', 'Limited Time Offers',
    'Clearance Sale Now',
]
FALLBACK_DESCS = [
    'Save big with verified coupons. Updated daily for the best deals.',
    'Get top promo codes and exclusive discounts. Tested and working.',
    'Shop smart with hand-picked offers. Fresh codes added every day.',
    'Unlock extra savings with trusted coupon codes. Fast and free to use.',
    'Browse active deals from popular stores. All codes verified by our team.',
]

# Google official headers (from downloaded templates)
CAMPAIGN_HEADERS = [
    'Action', 'Campaign status', 'Campaign', 'Campaign type', 'Networks',
    'Budget', 'Budget type', 'Bid strategy type', 'Language', 'Location',
    'EU political ads',
]

AD_GROUP_HEADERS = [
    'Action', 'Campaign', 'Ad group', 'Status',
]

KEYWORD_HEADERS = [
    'Action', 'Keyword status', 'Campaign', 'Ad group', 'Keyword', 'Match Type',
]

RSA_HEADERS = [
    'Action', 'Ad status', 'Campaign', 'Ad group', 'Ad type',
] + [f'Headline {i}' for i in range(1, 16)] + [
    'Description', 'Description 2', 'Description 3', 'Description 4',
    'Final URL',
]

SITELINK_HEADERS = [
    'Row Type', 'Action', 'Asset action', 'Level', 'Campaign',
    'Sitelink text', 'Final URL', 'Description', 'Description 2',
]

CALLOUT_HEADERS = [
    'Row type', 'Action', 'Campaign', 'Callout text',
]


def normalize_list(val):
    if isinstance(val, list):
        return [str(x).strip() for x in val if str(x).strip()]
    if isinstance(val, str):
        return [x.strip() for x in val.split('|') if x.strip()]
    return []


MAX_NAME_WORDS = 6


def sanitize_name(raw):
    """Cat ten camp truoc '/', '|', '-' phan mo ta dau tien, gioi han 6 tu, strip ky tu dac biet cuoi."""
    if not raw:
        return raw
    # Cat tai MOI separator tuan tu (khong break) — tranh truong hop con ',' hoac '|' trong ten
    for sep in (',', '/', '|', ' - ', ' — '):
        if sep in raw:
            raw = raw.split(sep)[0].strip()
    words = raw.split()
    if len(words) > MAX_NAME_WORDS:
        words = words[:MAX_NAME_WORDS]
    name = ' '.join(words).strip()
    # Strip ky tu rac cuoi (dau cach, comma, pipe, ampersand, hash, hash number...)
    return name.rstrip(' ,|&#:.-').strip()


def sanitize_project(p):
    """Neu ten camp bi cat, replace ten GOC trong moi field text (kw/headline/desc) bang ten RUT GON."""
    orig = p.get('name', '')
    new = sanitize_name(orig)
    if new == orig:
        return p
    p['name'] = new
    for key in ('adsKey', 'headlines', 'descriptions'):
        val = p.get(key)
        if isinstance(val, list):
            p[key] = [str(x).replace(orig, new) for x in val]
        elif isinstance(val, str):
            p[key] = val.replace(orig, new)
    return p


def classify_keyword(kw):
    kw = kw.strip()
    if kw.startswith('"') and kw.endswith('"'):
        return kw[1:-1].strip(), 'Phrase match'
    if kw.startswith('[') and kw.endswith(']'):
        return kw[1:-1].strip(), 'Exact match'
    return kw, 'Broad match'


def pick_rsa_texts(project, warnings):
    name = project['name']
    heads = [h for h in normalize_list(project.get('headlines', [])) if len(h) <= HEADLINE_MAX][:RSA_MAX_HEADLINES]
    descs = [d for d in normalize_list(project.get('descriptions', [])) if len(d) <= DESC_MAX][:RSA_MAX_DESCS]
    # Fill headlines den min 5 (an toan hon min 3 cua Google)
    target_heads = max(RSA_MIN_HEADLINES + 2, 5)
    for h in FALLBACK_HEADLINES:
        if len(heads) >= target_heads:
            break
        if h not in heads:
            heads.append(h)
    # Luon fill descs den MAX (4) de khong bao gio dinh loi "need at least 2 descriptions"
    for d in FALLBACK_DESCS:
        if len(descs) >= RSA_MAX_DESCS:
            break
        if d not in descs:
            descs.append(d)
    if len(heads) < RSA_MIN_HEADLINES or len(descs) < RSA_MIN_DESCS:
        warnings.append(f"[{name}] RSA thieu min headlines/descriptions — SKIP RSA")
        return None, None
    return heads, descs


def row_empty(headers):
    return {h: '' for h in headers}


def build_campaign_row(p, warnings):
    name = p['name']
    budget = str(p.get('budget', '')).strip() or '10'
    bidding_vn = p.get('bidding', '').strip()
    bidding_en = BIDDING_MAP.get(bidding_vn, 'Maximize clicks')
    loc_ids = [str(LOCATION_MAP[l]) for l in p.get('targetLocations', []) or [] if l in LOCATION_MAP]
    if not loc_ids:
        warnings.append(f"[{name}] no valid location — SKIP campaign")
        return None
    r = row_empty(CAMPAIGN_HEADERS)
    r['Action'] = 'Add'
    r['Campaign status'] = 'Paused'
    r['Campaign'] = name
    r['Campaign type'] = 'Search'
    r['Networks'] = 'Google search'
    r['Budget'] = budget
    r['Budget type'] = 'Daily'
    r['Bid strategy type'] = bidding_en
    r['Language'] = 'en'
    r['Location'] = ';'.join(loc_ids)
    r['EU political ads'] = 'No'
    return r


def build_ad_group_row(p):
    r = row_empty(AD_GROUP_HEADERS)
    r['Action'] = 'Add'
    r['Campaign'] = p['name']
    r['Ad group'] = 'AG-1'
    r['Status'] = 'Enabled'
    return r


def build_keyword_rows(p):
    rows = []
    for raw in normalize_list(p.get('adsKey', [])):
        txt, mt = classify_keyword(raw)
        if not txt:
            continue
        r = row_empty(KEYWORD_HEADERS)
        r['Action'] = 'Add'
        r['Keyword status'] = 'Enabled'
        r['Campaign'] = p['name']
        r['Ad group'] = 'AG-1'
        r['Keyword'] = txt
        r['Match Type'] = mt
        rows.append(r)
    return rows


def build_rsa_row(p, warnings):
    name = p['name']
    final_url = p.get('link1', '').strip()
    if not final_url:
        warnings.append(f"[{name}] no final URL — SKIP RSA")
        return None
    heads, descs = pick_rsa_texts(p, warnings)
    if not heads:
        return None
    r = row_empty(RSA_HEADERS)
    r['Action'] = 'Add'
    r['Ad status'] = 'Paused'
    r['Campaign'] = name
    r['Ad group'] = 'AG-1'
    r['Ad type'] = 'Responsive search ad'
    for i, h in enumerate(heads, start=1):
        r[f'Headline {i}'] = h
    # First description uses 'Description' (no number), then 'Description 2/3/4'
    desc_cols = ['Description', 'Description 2', 'Description 3', 'Description 4']
    for i, d in enumerate(descs):
        r[desc_cols[i]] = d
    r['Final URL'] = final_url
    return r


def build_sitelink_rows(p, warnings):
    name = p['name']
    base_url = p.get('link1', '').strip()
    if not base_url:
        warnings.append(f"[{name}] no link1 — SKIP sitelinks")
        return []
    rows = []
    for t in SITELINK_TEMPLATES:
        r = row_empty(SITELINK_HEADERS)
        r['Row Type'] = 'Sitelink'
        r['Action'] = 'Add'
        r['Asset action'] = 'Create new'
        r['Level'] = 'Campaign'
        r['Campaign'] = name
        r['Sitelink text'] = t['text']
        r['Final URL'] = base_url + t['suffix']
        r['Description'] = t['d1']
        r['Description 2'] = t['d2']
        rows.append(r)
    return rows


def build_callout_rows(p):
    rows = []
    for text in CALLOUTS_FIXED:
        r = row_empty(CALLOUT_HEADERS)
        r['Row type'] = 'Callout extension'
        r['Action'] = 'add'
        r['Campaign'] = p['name']
        r['Callout text'] = text
        rows.append(r)
    return rows


def write_csv(path, headers, rows):
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        w.writerows(rows)


UNION_HEADERS = [
    'Row Type',
    'Action', 'Campaign status', 'Campaign', 'Campaign type', 'Networks',
    'Budget', 'Budget type', 'Bid strategy type', 'Language', 'Location',
    'EU political ads',
    'Ad group', 'Status',
    'Keyword status', 'Keyword', 'Match Type',
    'Ad status', 'Ad type',
] + [f'Headline {i}' for i in range(1, 16)] + [
    'Description', 'Description 2', 'Description 3', 'Description 4',
    'Final URL',
    'Asset action', 'Level', 'Sitelink text',
    'Callout text',
]


def _tag(rows, rt):
    tagged = []
    for r in rows:
        r2 = {h: '' for h in UNION_HEADERS}
        for k, v in r.items():
            if k in r2:
                r2[k] = v
        r2['Row Type'] = rt
        tagged.append(r2)
    return tagged


def build_combined(projects, warnings):
    camp_rows, ag_rows, kw_rows, rsa_rows, sl_rows, co_rows = [], [], [], [], [], []
    for p in projects:
        c = build_campaign_row(p, warnings)
        if not c:
            continue
        camp_rows.append(c)
        ag_rows.append(build_ad_group_row(p))
        kw_rows.extend(build_keyword_rows(p))
        rsa = build_rsa_row(p, warnings)
        if rsa:
            rsa_rows.append(rsa)
        sl_rows.extend(build_sitelink_rows(p, warnings))
        co_rows.extend(build_callout_rows(p))

    co_asset = []
    for r in co_rows:
        r2 = dict(r)
        r2['Asset action'] = 'Create new'
        r2['Level'] = 'Campaign'
        r2['Action'] = 'Add'
        co_asset.append(r2)

    combined = (
        _tag(camp_rows, 'Campaign')
        + _tag(ag_rows, 'Ad group')
        + _tag(kw_rows, 'Keyword')
        + _tag(rsa_rows, 'Ad')
        + _tag(sl_rows, 'Sitelink')
        + _tag(co_asset, 'Callout')
    )
    stats = {
        'camp': len(camp_rows), 'ag': len(ag_rows), 'kw': len(kw_rows),
        'rsa': len(rsa_rows), 'sl': len(sl_rows), 'co': len(co_rows),
        'total': len(combined),
    }
    return combined, stats


def build_and_write_combined(projects, out_dir, idx, total_chunks):
    warnings = []
    rows, stats = build_combined(projects, warnings)
    fname = f"batch_{idx:02d}.csv"
    write_csv(out_dir / fname, UNION_HEADERS, rows)
    print(f"  [{idx}/{total_chunks}] {fname}: {stats['camp']} camp, {stats['kw']} kw, {stats['sl']} SL, {stats['co']} CO -> {stats['total']} rows")
    if warnings:
        (out_dir / f"batch_{idx:02d}_warnings.txt").write_text('\n'.join(warnings), encoding='utf-8')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('input')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--out-dir', default='bulk_v2_out')
    ap.add_argument('--chunks', type=int, default=0,
                    help='Chia thanh N file rieng (VD --chunks 10 cho 200 camp -> 10 file, 20 camp/file)')
    args = ap.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        print(f"Not found: {in_path}", file=sys.stderr)
        sys.exit(1)

    data = json.loads(in_path.read_text(encoding='utf-8'))
    if args.limit > 0:
        data = data[:args.limit]

    # Sanitize: rut gon ten camp co '/' hoac qua dai, replace trong moi field
    renamed = []
    for p in data:
        before = p.get('name', '')
        sanitize_project(p)
        if p.get('name') != before:
            renamed.append((before, p['name']))
    if renamed:
        print(f"Renamed {len(renamed)} camp(s):")
        for b, a in renamed:
            print(f"  {b!r} -> {a!r}")

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    if args.chunks > 0:
        import math
        per = math.ceil(len(data) / args.chunks)
        print(f"Chunk mode: {len(data)} camp / {args.chunks} files = {per} camp/file")
        for idx in range(args.chunks):
            start = idx * per
            chunk = data[start:start+per]
            if not chunk:
                break
            build_and_write_combined(chunk, out, idx+1, args.chunks)
        return

    warnings = []
    camp_rows, ag_rows, kw_rows, rsa_rows, sl_rows, co_rows = [], [], [], [], [], []

    for p in data:
        c = build_campaign_row(p, warnings)
        if not c:
            continue
        camp_rows.append(c)
        ag_rows.append(build_ad_group_row(p))
        kw_rows.extend(build_keyword_rows(p))
        rsa = build_rsa_row(p, warnings)
        if rsa:
            rsa_rows.append(rsa)
        sl_rows.extend(build_sitelink_rows(p, warnings))
        co_rows.extend(build_callout_rows(p))

    write_csv(out / '01_campaigns.csv', CAMPAIGN_HEADERS, camp_rows)
    write_csv(out / '02_ad_groups.csv', AD_GROUP_HEADERS, ag_rows)
    write_csv(out / '03_keywords.csv',  KEYWORD_HEADERS,  kw_rows)
    write_csv(out / '04_rsa.csv',       RSA_HEADERS,      rsa_rows)
    write_csv(out / '05_sitelinks.csv', SITELINK_HEADERS, sl_rows)
    write_csv(out / '06_callouts.csv',  CALLOUT_HEADERS,  co_rows)
    (out / 'warnings.txt').write_text('\n'.join(warnings), encoding='utf-8')

    # --- Combined single CSV (ALL IN ONE) ---
    # Union of all headers, Row Type column distinguishes entity type.
    union_headers = [
        'Row Type',
        # campaign cols
        'Action', 'Campaign status', 'Campaign', 'Campaign type', 'Networks',
        'Budget', 'Budget type', 'Bid strategy type', 'Language', 'Location',
        'EU political ads',
        # ad group cols
        'Ad group', 'Status',
        # keyword cols
        'Keyword status', 'Keyword', 'Match Type',
        # rsa cols
        'Ad status', 'Ad type',
    ] + [f'Headline {i}' for i in range(1, 16)] + [
        'Description', 'Description 2', 'Description 3', 'Description 4',
        'Final URL',
        # sitelink cols
        'Asset action', 'Level', 'Sitelink text',
        # callout cols
        'Callout text',
    ]

    def tag(rows, rt):
        tagged = []
        for r in rows:
            r2 = {h: '' for h in union_headers}
            for k, v in r.items():
                if k in r2:
                    r2[k] = v
            r2['Row Type'] = rt
            tagged.append(r2)
        return tagged

    combined = []
    combined += tag(camp_rows, 'Campaign')
    combined += tag(ag_rows,   'Ad group')
    combined += tag(kw_rows,   'Keyword')
    combined += tag(rsa_rows,  'Ad')
    combined += tag(sl_rows,   'Sitelink')
    # Callout in combined CSV: use 'Callout' (asset style) not 'Callout extension' (old format)
    # Also add Asset action='Create new' + Level='Campaign' so Google parses as asset
    co_asset_rows = []
    for r in co_rows:
        r2 = dict(r)
        r2['Asset action'] = 'Create new'
        r2['Level'] = 'Campaign'
        r2['Action'] = 'Add'
        co_asset_rows.append(r2)
    combined += tag(co_asset_rows, 'Callout')

    write_csv(out / 'all_in_one.csv', union_headers, combined)

    print(f"Output dir: {out}/")
    print(f"  01_campaigns.csv  : {len(camp_rows):4d} rows ({len(camp_rows)} camp)")
    print(f"  02_ad_groups.csv  : {len(ag_rows):4d} rows ({len(ag_rows)} AG)")
    print(f"  03_keywords.csv   : {len(kw_rows):4d} rows (avg {len(kw_rows)//max(len(camp_rows),1)} kw/camp)")
    print(f"  04_rsa.csv        : {len(rsa_rows):4d} rows ({len(rsa_rows)} RSA)")
    print(f"  05_sitelinks.csv  : {len(sl_rows):4d} rows ({len(sl_rows)//3} camp x 3 SL)")
    print(f"  06_callouts.csv   : {len(co_rows):4d} rows ({len(co_rows)//4} camp x 4 CO)")
    print(f"  all_in_one.csv    : {len(combined):4d} rows (combined 6 types)")
    print(f"  warnings.txt      : {len(warnings)} warnings")


if __name__ == '__main__':
    main()
