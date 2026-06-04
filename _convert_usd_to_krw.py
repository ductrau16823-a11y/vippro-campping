"""Convert CPC + Budget từ USD → KRW trong bulk_v2_out_khanh_78/ (multiply 1300)"""
import csv, shutil, sys, io
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = Path(r'c:\Users\Admin\Documents\vippro campping')
SRC = BASE / 'bulk_v2_out_khanh_78'
BACKUP = BASE / 'bulk_v2_out_khanh_78_USD_backup'
RATE = 1300

# Backup
if BACKUP.exists():
    shutil.rmtree(BACKUP)
shutil.copytree(SRC, BACKUP)
print(f"✅ Backup: {BACKUP}/")

def to_krw(val):
    """USD string → KRW int string. Empty → empty."""
    s = str(val).strip()
    if not s:
        return ''
    try:
        krw = round(float(s) * RATE)
        return str(krw)
    except:
        return s

# Columns to convert
CONVERT_COLS = ['Budget', 'Maximum CPC bid limit', 'Max CPC']

stats = {'files': 0, 'cells_converted': 0}
for f in sorted(SRC.glob('batch_*.csv')):
    rows = []
    with open(f, 'r', encoding='utf-8-sig', newline='') as fp:
        reader = csv.DictReader(fp)
        fieldnames = reader.fieldnames
        for row in reader:
            for col in CONVERT_COLS:
                if col in row and row[col].strip():
                    new = to_krw(row[col])
                    if new != row[col]:
                        row[col] = new
                        stats['cells_converted'] += 1
            rows.append(row)
    with open(f, 'w', encoding='utf-8-sig', newline='') as fp:
        w = csv.DictWriter(fp, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    stats['files'] += 1

print(f"\n✅ Converted {stats['files']} files | {stats['cells_converted']} cells × 1300 → KRW")

# Verify sample
print("\n=== Verify sample (Prop Money + Nilight) ===")
for fname in ['batch_01.csv', 'batch_36.csv', 'batch_78.csv']:
    p = SRC / fname
    with open(p, 'r', encoding='utf-8-sig') as f:
        camp = ''
        for row in csv.DictReader(f):
            if row.get('Row Type') == 'Campaign':
                camp = row['Campaign']
                print(f"\n[{fname}] {camp}")
                print(f"  Budget: {row.get('Budget','')} KRW")
                print(f"  Max CPC limit: {row.get('Maximum CPC bid limit','') or '(empty - Manual CPC)'}")
            elif row.get('Row Type') == 'Keyword':
                print(f"  Keyword CPC: {row.get('Max CPC','')} KRW")
