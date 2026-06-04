"""Extract 42 dự án Đức từ cached Sheet → duc_42_raw.json"""
import json
import re

CACHED = r'C:\Users\Admin\.claude\projects\c--Users-Admin-Documents-vippro-campping\169a8119-d7d4-4bde-8785-9cd142843c52\tool-results\mcp-claude_ai_Google_Drive-read_file_content-1780456317838.txt'

# Map country code → VN name (chỉ những country có trong LOCATION_MAP của build_bulk_v2)
CC_TO_VN = {
    'US': 'Hoa Kỳ', 'CA': 'Canada', 'UK': 'Vương quốc Anh', 'GB': 'Vương quốc Anh',
    'DE': 'Đức', 'AU': 'Úc', 'FR': 'Pháp', 'IT': 'Ý', 'ES': 'Tây Ban Nha',
    'BE': 'Bỉ', 'NL': 'Hà Lan', 'AT': 'Áo', 'SE': 'Thụy Điển', 'CH': 'Thụy Sĩ',
    'FI': 'Phần Lan', 'IE': 'Ireland', 'NO': 'Na Uy', 'DK': 'Đan Mạch',
    'NZ': 'New Zealand', 'PT': 'Bồ Đào Nha',
}

def parse_row(line):
    if not line.strip().startswith('|'):
        return None
    parts = line.strip().strip('|').split('|')
    return [p.strip().replace(r'\_', '_').replace(r'\&', '&') for p in parts]

def parse_tier(t):
    # 'UK (2,400)' → 'UK'
    m = re.match(r'\s*([A-Z]{2,3})\s*\(', t)
    return m.group(1) if m else None

def parse_cpc(s):
    # '$0.34' → '0.34', '$1.913' → '1.91'
    s = s.strip()
    if not s: return None
    m = re.search(r'(\d+(?:\.\d+)?)', s)
    if not m: return None
    val = float(m.group(1))
    # Round to 2 decimal
    return f"{val:.2f}"

with open(CACHED, 'r', encoding='utf-8') as f:
    content = json.load(f)['fileContent']

projects = []
for line in content.split('\n'):
    r = parse_row(line)
    if not r or len(r) < 32: continue
    if r[0] in ('network', ':-:') or not r[1] or r[1] == ':-:': continue
    if r[30].strip() != 'Đức': continue

    name = r[1].strip()
    link_web = r[2].strip()
    aff_link = r[5].strip()
    danh_muc = r[4].strip()
    key_brand = r[22].strip() or name.lower()
    max_cpc_raw = r[27].strip()

    # parse Tier1 locations
    tier_cells = [r[10+i] for i in range(10)]
    locations_vn = []
    seen = set()
    for t in tier_cells:
        cc = parse_tier(t)
        if not cc: continue
        vn = CC_TO_VN.get(cc)
        if vn and vn not in seen:
            seen.add(vn)
            locations_vn.append(vn)

    # Link ưu tiên aff_link, fallback link_web
    link1 = aff_link if aff_link else link_web

    # Max CPC parse
    max_cpc = parse_cpc(max_cpc_raw)

    projects.append({
        'name': name,
        'link_web': link_web,
        'link1': link1,
        'danh_muc': danh_muc,
        'key_brand': key_brand,
        'max_cpc_raw': max_cpc_raw,
        'max_cpc_parsed': max_cpc,
        'targetLocations': locations_vn,
    })

with open(r'c:\Users\Admin\Documents\vippro campping\duc_42_raw.json', 'w', encoding='utf-8') as f:
    json.dump(projects, f, ensure_ascii=False, indent=2)

print(f"Extracted {len(projects)} projects")
print(f"Written to duc_42_raw.json")

# Check locations have any project with 0 locations
zero = [p for p in projects if not p['targetLocations']]
print(f"\nProjects with 0 valid locations: {len(zero)}")
for p in zero:
    print(f"  - {p['name']}")
