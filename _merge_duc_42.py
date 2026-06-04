"""Merge 4 parts of headlines/descriptions + raw data → entries → merge vào test_6_input.json"""
import json
from pathlib import Path

BASE = Path(r'c:\Users\Admin\Documents\vippro campping')

# Load raw 42
raw = json.loads((BASE / 'duc_42_raw.json').read_text(encoding='utf-8'))

# Load 4 parts of headlines/descriptions
hd_map = {}  # name -> {headlines, descriptions}
for i in range(1, 6):
    part_path = BASE / f'duc_42_hd_part{i}.json'
    if not part_path.exists():
        print(f"MISSING: {part_path}")
        continue
    part = json.loads(part_path.read_text(encoding='utf-8'))
    for item in part:
        hd_map[item['name']] = {
            'headlines': item['headlines'],
            'descriptions': item['descriptions'],
        }

print(f"Loaded H/D for {len(hd_map)} projects")

# Build entries
entries = []
missing = []
for p in raw:
    hd = hd_map.get(p['name'])
    if not hd:
        missing.append(p['name'])
        continue
    entry = {
        'name': p['name'],
        'campaignType': 'Search',
        'link1': p['link1'],
        'adsKey': [f"[{p['key_brand']}]"],  # Exact match format
        'bidding': 'Thủ công CPC',
        'budget': '100',
        'maxCpcLimit': p['max_cpc_parsed'] or '0.40',
        'targetLocations': p['targetLocations'],
        'headlines': hd['headlines'],
        'descriptions': hd['descriptions'],
    }
    entries.append(entry)

print(f"Built {len(entries)} entries")
if missing:
    print(f"MISSING H/D for: {missing}")

# Verify lengths
issues = []
for e in entries:
    for h in e['headlines']:
        if len(h) > 30:
            issues.append(f"[{e['name']}] headline > 30: '{h}' ({len(h)})")
    for d in e['descriptions']:
        if len(d) > 90:
            issues.append(f"[{e['name']}] desc > 90: '{d}' ({len(d)})")
if issues:
    print(f"\n⚠️ {len(issues)} length issues:")
    for i in issues[:20]:
        print(f"  {i}")
else:
    print("\nAll lengths OK")

# Load test_6_input.json
test6_path = BASE / 'test_6_input.json'
test6 = json.loads(test6_path.read_text(encoding='utf-8'))
print(f"\ntest_6_input.json has {len(test6)} entries before merge")

# Check duplicates
existing_names = {e['name'].lower() for e in test6}
new_entries = [e for e in entries if e['name'].lower() not in existing_names]
duplicates = [e['name'] for e in entries if e['name'].lower() in existing_names]
print(f"New entries to add: {len(new_entries)}")
if duplicates:
    print(f"Duplicates skipped: {duplicates}")

# Merge
test6.extend(new_entries)
print(f"After merge: {len(test6)} entries")

# Backup original
backup_path = BASE / 'test_6_input.json.bak'
if not backup_path.exists():
    backup_path.write_text(json.dumps(json.loads((test6_path).read_text(encoding='utf-8')), ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Backed up original to test_6_input.json.bak")

# Write merged
test6_path.write_text(json.dumps(test6, ensure_ascii=False, indent=2), encoding='utf-8')
print(f"Wrote merged test_6_input.json ({len(test6)} entries)")

# Also write separate duc_42_input.json with ONLY new entries (for build_bulk_v2 standalone)
duc_path = BASE / 'duc_42_input.json'
duc_path.write_text(json.dumps(new_entries, ensure_ascii=False, indent=2), encoding='utf-8')
print(f"Wrote duc_42_input.json ({len(new_entries)} entries)")
