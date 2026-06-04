"""Tạo folder bulk_v2_out_khanh_78/ với 78 CSV theo order anh đưa"""
import shutil, sys, io, csv, os
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = Path(r'c:\Users\Admin\Documents\vippro campping')

# 78 entries theo order anh paste — (display_name, source: 't6/batch_XX.csv' or 'old10/batch_XX.csv')
ORDER = [
    ('Prop Money Inc. _ Impact',          't6/batch_01.csv'),
    ('Airwallex - Affiliate Program',     't6/batch_05.csv'),
    ('wowangel _ Goaffpro',               't6/batch_06.csv'),
    ('Arccaptain Welder',                 't6/batch_07.csv'),
    ('Sportdirect.ca',                    't6/batch_09.csv'),
    ('Keepgo',                            't6/batch_10.csv'),
    ('EngineDIY',                         't6/batch_12.csv'),
    ('Evolution Power Tools UK',          't6/batch_13.csv'),
    ('ALDKitchen',                        't6/batch_14.csv'),
    ('Hohem Official Store',              't6/batch_15.csv'),
    ("The Agency's Art de Vivre Boutique",'t6/batch_17.csv'),
    ('Transcent',                         't6/batch_19.csv'),
    ('LAYON',                             't6/batch_20.csv'),
    ('Maine Garden Products',             't6/batch_21.csv'),
    ('Templar Cross',                     't6/batch_22.csv'),
    ('ANSWR',                             't6/batch_24.csv'),
    ('Aoocci',                            't6/batch_26.csv'),
    ('poodledstore',                      't6/batch_27.csv'),
    ('Trak Racer EU',                     't6/batch_28.csv'),
    ('Typecase',                          't6/batch_91.csv'),
    ('Adarna House',                      't6/batch_29.csv'),
    ('Nicpro',                            't6/batch_30.csv'),
    ('willow.ie',                         't6/batch_31.csv'),
    ('Frizzlife',                         't6/batch_32.csv'),
    ('Procase',                           't6/batch_33.csv'),
    ('Hexgaming.com',                     't6/batch_34.csv'),
    ('Ywigs',                             't6/batch_35.csv'),
    ('Tsarbomba',                         't6/batch_36.csv'),
    ('Drone-Clone Xperts',                't6/batch_38.csv'),
    ('Dry Bags',                          't6/batch_39.csv'),
    ('FigureSkatingStore.com',            't6/batch_40.csv'),
    ('AUKEY',                             't6/batch_42.csv'),
    ('CANNI Official',                    't6/batch_44.csv'),
    ('Swad',                              't6/batch_46.csv'),
    ('ECO-WORTHY',                        't6/batch_47.csv'),
    ('Nilight',                           't6/batch_48.csv'),
    ('Yose Power',                        't6/batch_49.csv'),
    ('DOORS',                             't6/batch_50.csv'),
    ('Geekvape Store',                    't6/batch_51.csv'),
    ('Ashley Behrndt',                    't6/batch_52.csv'),
    ('Card-Addiction.com',                't6/batch_53.csv'),
    ('Seagull 1963',                      't6/batch_54.csv'),
    ('Letbricks',                         't6/batch_55.csv'),
    ('Arzopa Official Store',             't6/batch_56.csv'),
    ('Youxernet',                         't6/batch_57.csv'),
    ('Pixilated Photo Booth',             't6/batch_60.csv'),
    ('marshydrode',                       't6/batch_61.csv'),
    ('GEPRC',                             't6/batch_63.csv'),
    ('Comfier',                           't6/batch_64.csv'),
    ('Floyd',                             't6/batch_65.csv'),
    ('Modern Abayati',                    't6/batch_66.csv'),
    ('TheHushShop.com',                   't6/batch_68.csv'),
    ('lensmartonline',                    't6/batch_69.csv'),
    ('animota',                           't6/batch_71.csv'),
    ('SJCAM Official Website',            't6/batch_72.csv'),
    ('CharCharms',                        't6/batch_73.csv'),
    ('Shark Wheel Affiliate Program',     't6/batch_74.csv'),
    ('carpuride',                         't6/batch_75.csv'),
    ('KugooEU Scooter',                   't6/batch_76.csv'),
    ('WOLFBOX',                           't6/batch_77.csv'),
    ('sonicred',                          't6/batch_78.csv'),
    ('Rubbit',                            't6/batch_79.csv'),
    ('Life-Space US',                     't6/batch_80.csv'),
    ('SOOTIF.COM',                        't6/batch_81.csv'),
    ('Custom Logo creator',               't6/batch_82.csv'),
    ('PPJoe Pop Protectors',              't6/batch_83.csv'),
    ('Casper Academy',                    't6/batch_84.csv'),
    ('Vaporesso Store',                   't6/batch_85.csv'),
    ('IObit',                             't6/batch_88.csv'),
    ('TheLAShop.com',                     'k10/batch_68.csv'),
    ('Cohorted Beauty',                   'k10/batch_69.csv'),
    ('AmazingCosmetics',                  'k10/batch_70.csv'),
    ('Beauty Affairs',                    'k10/batch_71.csv'),
    ('PetPalsDIY',                        'k10/batch_72.csv'),
    ("HARD'N'HEAVY _ Shopify",            'k10/batch_73.csv'),
    ('herbishh.com',                      'k10/batch_74.csv'),
    ('WONDERFOLD',                        'k10/batch_75.csv'),
    ('Label Land',                        'k10/batch_76.csv'),
]
assert len(ORDER) == 78, f"Expected 78, got {len(ORDER)}"

def resolve(src):
    if src.startswith('t6/'):
        return BASE / 'bulk_v2_out_test6' / src[3:]
    elif src.startswith('k10/'):
        return BASE / 'bulk_v2_out_khanh_10' / src[4:]
    raise ValueError(src)

# Verify
print("=== Verify sources ===")
missing = []
for name, src in ORDER:
    p = resolve(src)
    if not p.exists():
        missing.append((name, str(p)))
if missing:
    print(f"❌ MISSING {len(missing)}:")
    for n, p in missing:
        print(f"  {n}: {p}")
    sys.exit(1)
print(f"✅ All {len(ORDER)} sources exist")

# Create folder
DEST = BASE / 'bulk_v2_out_khanh_78'
if DEST.exists():
    shutil.rmtree(DEST)
DEST.mkdir()

for idx, (name, src) in enumerate(ORDER, 1):
    shutil.copy2(resolve(src), DEST / f'batch_{idx:02d}.csv')

# _index.csv
with open(DEST / '_index.csv', 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f)
    w.writerow(['Batch', 'Project Name', 'Source'])
    for idx, (name, src) in enumerate(ORDER, 1):
        w.writerow([f'batch_{idx:02d}.csv', name, src])

print(f"\n✅ Created {DEST}/ with {len(ORDER)} CSV + _index.csv")
