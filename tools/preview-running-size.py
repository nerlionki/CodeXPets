"""Uniformly resize an existing approved row; never redraw character pixels."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw
from pet_pipeline_import import RUN, SKILL, call

ROOT = RUN.parents[1]
OUT = ROOT / 'approval/running-size-v17'
OUT.mkdir(parents=True, exist_ok=True)
source = RUN / 'final/spritesheet-extended.webp'
atlas = Image.open(source).convert('RGBA')
idle = atlas.crop((0, 0, 192, 208))
before = [atlas.crop((c*192, 7*208, (c+1)*192, 8*208)) for c in range(6)]
boxes = [c.getbbox() for c in before]
idle_box = idle.getbbox()
scale = (idle_box[3]-idle_box[1]) / max(b[3]-b[1] for b in boxes)
ground = boxes[0][3]
frames = []
folder = OUT / 'frames/running'
folder.mkdir(parents=True, exist_ok=True)
for i, (cell, box) in enumerate(zip(before, boxes)):
    size = (round((box[2]-box[0])*scale), round((box[3]-box[1])*scale))
    content = cell.crop(box).resize(size, Image.Resampling.LANCZOS)
    dest = Image.new('RGBA', (192, 208))
    bottom = idle_box[3] + round((box[3]-ground)*scale)
    left = round((idle_box[0]+idle_box[2]-size[0])/2)
    assert left >= 4 and left+size[0] <= 188
    assert bottom-size[1] >= 4 and bottom <= 204
    dest.paste(content, (left, bottom-size[1]))
    # Clear hidden interpolation RGB without altering visible pixels or alpha.
    dest.putdata([(r,g,b,a) if a else (0,0,0,0) for r,g,b,a in dest.getdata()])
    dest.save(folder/f'{i:02}.png')
    frames.append(dest)

spec = importlib.util.spec_from_file_location('size_preview', SKILL/'scripts/render_animation_previews.py')
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)
timing = preview.ROW_DURATIONS['running']
preview.save_preview(frames, timing, OUT/'running.gif')
preview.save_preview([c.resize((384,416), Image.Resampling.NEAREST) for c in frames], timing, OUT/'running-2x.gif')
comparison = []
for old, new in zip(before, frames):
    canvas = Image.new('RGBA', (576,208))
    for x,c in [(0,idle),(192,old),(384,new)]: canvas.paste(c,(x,0))
    comparison.append(canvas.resize((1152,416), Image.Resampling.NEAREST))
preview.save_preview(comparison,timing,OUT/'comparison-2x.gif')
sheet = Image.new('RGB', (1344,240),'#f4efe9')
d = ImageDraw.Draw(sheet)
for col,(label,cell) in enumerate([('idle reference',idle)]+[(f'new running {i}',c) for i,c in enumerate(frames)]):
    d.text((col*192+6,6),label,fill='black')
    sheet.paste(cell,(col*192,26),cell.getchannel('A'))
sheet.save(OUT/'contact-sheet.png')
manifest={'ok':True,'chroma_key':{'hex':'#0000FF','rgb':[0,0,255],'threshold':96},'rows':[{'state':'running','method':'stable-slots','frames':[str((folder/f'{i:02}.png').resolve()) for i in range(6)]}]}
(OUT/'frames/frames-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
report={'ok':True,'source_atlas_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'state':'running','row':7,'uniform_scale':scale,'reference_bbox':idle_box,'before_bboxes':boxes,'after_bboxes':[c.getbbox() for c in frames],'anchor':'idle ground and horizontal center','aspect_ratio_preserved':True,'all_frames_same_scale':True,'pixels_redrawn':False,'timing_ms':timing,'additional_chroma_cleanup':False,'installed':False,'packaged':False,'cloud_updated':False,'status':'awaiting_user_approval'}
(OUT/'size-adjustment.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
if call('inspect_frames.py','--frames-root',OUT/'frames','--states','running','--json-out',OUT/'frame-review.json','--allow-stable-slots'):
    raise SystemExit('Frame checks failed')
print(json.dumps(report,indent=2))
