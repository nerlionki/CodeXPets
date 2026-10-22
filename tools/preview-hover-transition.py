"""Join approved idle and hover pixels at a shared ground without redrawing."""
import hashlib
import importlib.util
import json
from pathlib import Path
from PIL import Image, ImageDraw
from pet_pipeline_import import RUN, SKILL, call

ROOT = RUN.parents[1]
OUT = ROOT / 'approval/hover-transition-v26'


def main():
    OUT.mkdir(exist_ok=True)
    folder = OUT/'frames/jumping'
    folder.mkdir(parents=True,exist_ok=True)
    source = RUN/'final/spritesheet-extended.webp'
    atlas = Image.open(source).convert('RGBA')
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    idle = [atlas.crop((c*192,0,(c+1)*192,208)) for c in range(6)]
    old = [atlas.crop((c*192,832,(c+1)*192,1040)) for c in range(5)]
    ground_delta = idle[0].getbbox()[3]-old[0].getbbox()[3]
    new = [idle[0].copy()]
    for i in range(1,4):
        frame = Image.new('RGBA',(192,208))
        bounds = old[i].getbbox()
        assert bounds[1]+ground_delta >= 3 and bounds[3]+ground_delta <= 205
        frame.paste(old[i],(0,ground_delta))
        assert frame.getchannel('A').histogram()==old[i].getchannel('A').histogram()
        # The entire approved airborne cell is translated as a unit.
        crop = frame.crop((0,bounds[1]+ground_delta,192,bounds[3]+ground_delta))
        assert crop.tobytes()==old[i].crop((0,bounds[1],192,bounds[3])).tobytes()
        new.append(frame)
    new.append(idle[0].copy())
    assert new[0].tobytes()==new[-1].tobytes()==idle[0].tobytes()
    spec = importlib.util.spec_from_file_location('hover_preview',SKILL/'scripts/render_animation_previews.py')
    preview = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(preview)
    timing = preview.ROW_DURATIONS['jumping']
    for i,frame in enumerate(new):
        frame.save(folder/f'{i:02}.png')
    preview.save_preview(new,timing,OUT/'jumping.gif')
    preview.save_preview([f.resize((384,416),Image.Resampling.NEAREST) for f in new],timing,OUT/'jumping-2x.gif')
    transition_before = idle+old+idle
    transition_after = idle+new+idle
    transition_timing = preview.ROW_DURATIONS['idle']+timing+preview.ROW_DURATIONS['idle']
    preview.save_preview(transition_after,transition_timing,OUT/'idle-hover-idle.gif')
    preview.save_preview([f.resize((384,416),Image.Resampling.NEAREST) for f in transition_after],transition_timing,OUT/'idle-hover-idle-2x.gif')
    comparisons = []
    for before,after in zip(transition_before,transition_after):
        pair = Image.new('RGBA',(384,208))
        pair.paste(before,(0,0))
        pair.paste(after,(192,0))
        comparisons.append(pair.resize((768,416),Image.Resampling.NEAREST))
    preview.save_preview(comparisons,transition_timing,OUT/'transition-comparison-2x.gif')
    sheet = Image.new('RGB',(1152,446),'#f4efe9')
    draw = ImageDraw.Draw(sheet)
    for row,(label,frames) in enumerate([('idle / v25 hover', [idle[0]]+old),('idle / v26 hover', [idle[0]]+new)]):
        draw.text((8,row*223+3),label,fill='#222222')
        for col,frame in enumerate(frames):
            sheet.paste(frame,(col*192,row*223+15),frame)
    sheet.save(OUT/'contact-sheet.png')
    manifest = {'ok':True,'rows':[{'state':'jumping','method':'stable-slots','frames':[str((folder/f'{i:02}.png').resolve()) for i in range(5)]}]}
    (OUT/'frames/frames-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    if call('inspect_frames.py','--frames-root',OUT/'frames','--states','jumping','--json-out',OUT/'frame-review.json','--allow-stable-slots'):
        raise SystemExit('Frame validation failed')
    assert hashlib.sha256(source.read_bytes()).hexdigest()==source_hash
    report = {'status':'awaiting_user_approval','baseline_atlas_sha256':source_hash,'source_candidate':'jumping-ear-lines-v25','first_and_last_frames_exact_idle_pixels':True,'airborne_frames_pixel_identical_after_translation':True,'airborne_translation_y':ground_delta,'scaling':1,'frame_count':5,'native_timing_ms':timing,'transition_timing_ms':transition_timing,'body_ground':idle[0].getbbox()[3],'before_ground':old[0].getbbox()[3],'notes':['Grounded endpoints return to the actual canonical idle pose; airborne upright ear, facial spacing and stroke corrections retained.','Five native frames remain idle endpoint, rising, apex, descending, idle endpoint. No added native frame or altered playback speed.'],'integrated':False,'packaged':False,'installed':False,'cloud_updated':False,'active_atlas_unchanged':True}
    (OUT/'status.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
