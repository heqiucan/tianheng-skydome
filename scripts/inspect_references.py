"""Archive supplied reference images without changing originals; inspect sizes."""
from pathlib import Path
import argparse
import os
import shutil, json
import tempfile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source-dir', type=Path, default=os.environ.get('TIANHENG_REFERENCE_SOURCE_DIR'),
                    help='Original reference directory containing img/ and PDF sources; '
                         'or set TIANHENG_REFERENCE_SOURCE_DIR.')
parser.add_argument('--clipboard-dir', type=Path,
                    default=os.environ.get('TIANHENG_CLIPBOARD_DIR', tempfile.gettempdir()),
                    help='Directory containing supplied clipboard images; '
                         'or set TIANHENG_CLIPBOARD_DIR (defaults to the system temporary directory).')
args = parser.parse_args()
if args.source_dir is None:
    parser.error('Pass --source-dir or set TIANHENG_REFERENCE_SOURCE_DIR.')
SOURCE = args.source_dir
if not SOURCE.is_dir():
    parser.error('The reference source directory does not exist.')
from PIL import Image, ImageOps, ImageDraw, ImageFont
OUT = ROOT / 'public/references'
for category in ('campus','visual','ui','interaction','sources'):
    (OUT/category).mkdir(parents=True, exist_ok=True)
items = [(p, 'visual' if p.name.startswith('00_') else 'campus', p.name,
          f'用户提供的学校图集 / img/{p.name}') for p in sorted((SOURCE/'img').glob('*'))]
attachments = [
('79e6d7cc-8e47-4b18-af34-d3d4f8d23674','ui','01_day1_reference.png'),
('d37c1cfd-0860-4023-8a5f-b479c8744cc7','campus','11_changxing_annotated.png'),
('e71fc507-6fe1-427e-9b18-da0886460664','visual','01_digital_twin_lighting.png'),
('b38a0cab-17a3-43b7-9160-24396cb8a1a6','visual','02_multidomain_dashboard.png'),
('0e60e78b-5d57-44dd-b328-b685cea0c113','interaction','01_sensor_map_panel.png'),
('b6cbf80c-daa9-416f-88a6-c9b0d2eff18a','interaction','02_incident_routes.png'),
('10155025-4785-4394-a3aa-121c5c8c2e1d','ui','02_situation_layout.png'),
('761d55b8-b38f-477b-8f6d-4d33db3fcf16','visual','03_campus_dashboard.png')]
for identifier,category,name in attachments:
    items.append((args.clipboard_dir/f'codex-clipboard-{identifier}.png',category,name,
                  f'用户提供的参考截图 / {name}'))
items.append((ROOT/'docs/screenshots/day1-workbench.jpg','ui','03_day1_actual.jpg',
              '本项目验收截图 / docs/screenshots/day1-workbench.jpg'))
records=[]
for path,category,name,source_label in items:
    if not path.exists():
        records.append(dict(source=source_label,category=category,missing=True)); continue
    target=OUT/category/name
    if not target.exists(): shutil.copy2(path,target)
    with Image.open(path) as im:
        im.load()
        records.append(dict(file=f'{category}/{name}',source=source_label,width=im.width,height=im.height,ratio=round(im.width/im.height,3),bytes=path.stat().st_size))
for name in ('浙江交院_三维图集.html',):
    shutil.copy2(SOURCE/name,OUT/'sources'/name)
for path in (SOURCE/'pdf原件').glob('*.pdf'):
    shutil.copy2(path,OUT/'sources'/path.name)
(OUT/'inventory.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',16)
for start in range(0,len(records),6):
    sheet=Image.new('RGB',(1200,1050),'#e8edf4'); draw=ImageDraw.Draw(sheet)
    for offset,rec in enumerate(records[start:start+6]):
        if rec.get('missing'): continue
        x=(offset%2)*600;y=(offset//2)*350
        with Image.open(OUT/rec['file']) as im:
            thumb=ImageOps.contain(im.convert('RGB'),(580,295))
            sheet.paste(thumb,(x+10,y+5))
        draw.text((x+10,y+303),rec['file'],font=font,fill='#172235')
        draw.text((x+10,y+327),f"{rec['width']} x {rec['height']} / {rec['ratio']}",font=font,fill='#172235')
    dest=ROOT/f'docs/screenshots/reference-sheet-{start//6+1}.jpg'
    sheet.save(dest,quality=90)
print(json.dumps(records,ensure_ascii=False,indent=2))
