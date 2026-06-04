"""Collect 77 con vàng + trắng vào bulk_v2_out_khanh_10/ với tên batch_01-77.csv"""
import shutil, sys, io, csv
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = Path(r'c:\Users\Admin\Documents\vippro campping')
DEST = BASE / 'bulk_v2_out_khanh_10'

# Order: 35 yellow (theo screenshot), then 42 white
# Format: (display_name, source_batch_file_path)
# source: 't6/batch_XX.csv' or 'k10/batch_XX.csv'

YELLOW = [
    ('Prop Money Inc. _ Impact',          't6/batch_01.csv'),
    ('Keepgo',                             't6/batch_10.csv'),
    ('EngineDIY',                          't6/batch_12.csv'),
    ('ALDKitchen',                         't6/batch_14.csv'),
    ('Hohem Official Store',               't6/batch_15.csv'),
    ('Scarlet Darkness',                   't6/batch_18.csv'),
    ('Maine Garden Products',              't6/batch_21.csv'),
    ('Templar Cross',                      't6/batch_22.csv'),
    ('ANSWR',                              't6/batch_24.csv'),
    ('Trak Racer EU',                      't6/batch_28.csv'),
    ('Typecase',                           't6/batch_91.csv'),
    ('Nicpro',                             't6/batch_30.csv'),
    ('willow.ie',                          't6/batch_31.csv'),
    ('Frizzlife',                          't6/batch_32.csv'),
    ('Procase',                            't6/batch_33.csv'),
    ('Hexgaming.com',                      't6/batch_34.csv'),
    ('Ywigs',                              't6/batch_35.csv'),
    ('Tsarbomba',                          't6/batch_36.csv'),
    ('FigureSkatingStore.com',             't6/batch_40.csv'),
    ('AUKEY',                              't6/batch_42.csv'),
    ('Swad',                               't6/batch_46.csv'),
    ('ECO-WORTHY',                         't6/batch_47.csv'),
    ('Niilight (= Nilight in test6)',      't6/batch_48.csv'),
    ('Yose Power',                         't6/batch_49.csv'),
    ('DOORS',                              't6/batch_50.csv'),
    ('Seagull 1963',                       't6/batch_54.csv'),
    ('Letbricks',                          't6/batch_55.csv'),
    ('Arzopa Official Store',              't6/batch_56.csv'),
    ('Comfier',                            't6/batch_64.csv'),
    ('Floyd',                              't6/batch_65.csv'),
    ('carpuride',                          't6/batch_75.csv'),
    ('KugooEU Scooter',                    't6/batch_76.csv'),
    ('WOLFBOX',                            't6/batch_77.csv'),
    ('Custom Logo creator',                't6/batch_82.csv'),
    ('BUR BUR',                            't6/batch_86.csv'),
]

WHITE = [
    ('Plant Paper Inc.',                   'k10/batch_10.csv'),
    ('Sportdirect.ca',                     't6/batch_09.csv'),
    ('Evolution Power Tools UK',           't6/batch_13.csv'),
    ("The Agency's Art de Vivre Boutique", 't6/batch_17.csv'),
    ('Transcent',                          't6/batch_19.csv'),
    ('LAYON',                              't6/batch_20.csv'),
    ('Aoocci',                             't6/batch_26.csv'),
    ('poodledstore',                       't6/batch_27.csv'),
    ('Adarna House',                       't6/batch_29.csv'),
    ('Drone-Clone Xperts',                 't6/batch_38.csv'),
    ('Dry Bags',                           't6/batch_39.csv'),
    ('Hobibear',                           't6/batch_41.csv'),
    ('Geekvape Store',                     't6/batch_51.csv'),
    ('Ashley Behrndt',                     't6/batch_52.csv'),
    ('Card-Addiction.com',                 't6/batch_53.csv'),
    ('Youxernet',                          't6/batch_57.csv'),
    ('Pixilated Photo Booth',              't6/batch_60.csv'),
    ('GEPRC',                              't6/batch_63.csv'),
    ('Modern Abayati',                     't6/batch_66.csv'),
    ('TheHushShop.com',                    't6/batch_68.csv'),
    ('lensmartonline',                     't6/batch_69.csv'),
    ('animota',                            't6/batch_71.csv'),
    ('SJCAM Official Website',             't6/batch_72.csv'),
    ('CharCharms',                         't6/batch_73.csv'),
    ('Shark Wheel Affiliate Program',      't6/batch_74.csv'),
    ('sonicred',                           't6/batch_78.csv'),
    ('Rubbit',                             't6/batch_79.csv'),
    ('Life-Space US',                      't6/batch_80.csv'),
    ('SOOTIF.COM',                         't6/batch_81.csv'),
    ('PPJoe Pop Protectors',               't6/batch_83.csv'),
    ('Casper Academy',                     't6/batch_84.csv'),
    ('Vaporesso Store',                    't6/batch_85.csv'),
    ('TheLAShop.com',                      'k10/batch_01.csv'),
    ('Cohorted Beauty',                    'k10/batch_02.csv'),
    ('AmazingCosmetics',                   'k10/batch_03.csv'),
    ('Beauty Affairs',                     'k10/batch_04.csv'),
    ('PetPalsDIY',                         'k10/batch_05.csv'),
    ("HARD'N'HEAVY _ Shopify",             'k10/batch_06.csv'),
    ('herbishh.com',                       'k10/batch_07.csv'),
    ('WONDERFOLD',                         'k10/batch_08.csv'),
    ('Label Land',                         'k10/batch_09.csv'),
    ('Cardiff, Inc. _ ruelusamcel',        't6/batch_03.csv'),
]

ALL_77 = [('yellow', n, s) for n, s in YELLOW] + [('white', n, s) for n, s in WHITE]
assert len(ALL_77) == 77, f"Expected 77, got {len(ALL_77)}"

def resolve(src):
    if src.startswith('t6/'):
        return BASE / 'bulk_v2_out_test6' / src[3:]
    elif src.startswith('k10/'):
        return BASE / 'bulk_v2_out_khanh_10' / src[4:]
    raise ValueError(src)

# Step 1: Verify all sources exist
print("=== Verify sources ===")
missing = []
for color, name, src in ALL_77:
    p = resolve(src)
    if not p.exists():
        missing.append((name, str(p)))
if missing:
    print(f"❌ MISSING {len(missing)} sources:")
    for n, p in missing:
        print(f"  {n}: {p}")
    sys.exit(1)
print(f"✅ All 77 sources exist")

# Step 2: Copy to tmp folder first (safe atomic-ish)
TMP = BASE / 'bulk_v2_out_khanh_10_NEW'
if TMP.exists():
    shutil.rmtree(TMP)
TMP.mkdir()

for idx, (color, name, src) in enumerate(ALL_77, start=1):
    src_path = resolve(src)
    dst_path = TMP / f'batch_{idx:02d}.csv'
    shutil.copy2(src_path, dst_path)

# Write _index.csv
with open(TMP / '_index.csv', 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f)
    w.writerow(['Batch', 'Color', 'Project Name', 'Source'])
    for idx, (color, name, src) in enumerate(ALL_77, start=1):
        w.writerow([f'batch_{idx:02d}.csv', color, name, src])

print(f"\n✅ Copied 77 files + _index.csv to {TMP}/")

# Step 3: Swap (backup old khanh_10, rename NEW → khanh_10)
OLD_BACKUP = BASE / 'bulk_v2_out_khanh_10_OLD_10files'
if OLD_BACKUP.exists():
    shutil.rmtree(OLD_BACKUP)
shutil.move(str(DEST), str(OLD_BACKUP))
shutil.move(str(TMP), str(DEST))
print(f"✅ Backed up old 10 files → {OLD_BACKUP}/")
print(f"✅ New 77 files now in {DEST}/")
