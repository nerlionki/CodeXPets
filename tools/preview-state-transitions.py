"""Prepare reviewable native state-boundary candidates; never deploy them."""
import hashlib
import importlib.util
import json
from pathlib import Path

from PIL import Image, ImageDraw
from pet_pipeline_import import RUN, SKILL, call

ROOT = RUN.parents[1]
OUT = ROOT / 'approval/state-transitions-v29'
STATES = ['idle','running-right','running-left','waving','jumping','failed','waiting','running','review']
SEATED = ['waving','failed','waiting','running','review']


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, SKILL/'scripts'/filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def main():
    preview = load('transition_preview','render_animation_previews.py')
    extraction = load('transition_components','extract_strip_frames.py')
    source = RUN/'final/spritesheet-extended.webp'
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    atlas = Image.open(source).convert('RGBA')
    idle = [atlas.crop((i*192,0,(i+1)*192,208)) for i in range(6)]
    def geometry(frame):
        groups = extraction.connected_components(frame)
        largest = max(g['area'] for g in groups)
        bodies = [g for g in groups if g['area'] >= max(200,largest*.12)]
        return [min(g['bbox'][0] for g in bodies),min(g['bbox'][1] for g in bodies),
                max(g['bbox'][2] for g in bodies),max(g['bbox'][3] for g in bodies)]
    def scale2(frames):
        return [f.resize((f.width*2,f.height*2),Image.Resampling.NEAREST) for f in frames]
    body = geometry(idle[0])
    sheet = Image.new('RGB',(1536,len(SEATED)*238),'#f4efe9')
    draw = ImageDraw.Draw(sheet)
    records, manifest = [], []
    candidate = atlas.copy()
    for index,state in enumerate(SEATED):
        row = STATES.index(state)
        duration = preview.ROW_DURATIONS[state]
        old = [atlas.crop((i*192,row*208,(i+1)*192,(row+1)*208)) for i in range(len(duration))]
        start_body = geometry(old[0])
        dx = round((body[0]+body[2]-start_body[0]-start_body[2])/2)
        dy = body[3]-start_body[3]
        frames = [idle[0].copy()]
        for frame in old[1:-1]:
            box = frame.getbbox()
            assert 0 <= box[0]+dx and box[2]+dx <= 192
            assert 0 <= box[1]+dy and box[3]+dy <= 208
            shifted = Image.new('RGBA',(192,208))
            shifted.paste(frame,(dx,dy))
            assert shifted.getchannel('A').histogram() == frame.getchannel('A').histogram()
            frames.append(shifted)
        frames.append(idle[0].copy())
        assert len(frames)==len(duration)
        folder = OUT/'frames'/state
        folder.mkdir(parents=True,exist_ok=True)
        for i,frame in enumerate(frames):
            frame.save(folder/f'{i:02}.png')
            candidate.paste(frame,(i*192,row*208))
        manifest.append({'state':state,'method':'stable-slots',
                         'frames':[str((folder/f'{i:02}.png').resolve()) for i in range(len(frames))]})
        preview.save_preview(frames,duration,OUT/f'{state}.gif')
        preview.save_preview(scale2(frames),duration,OUT/f'{state}-2x.gif')
        cycle = idle+frames+frames+idle
        old_cycle = idle+old+old+idle
        times = preview.ROW_DURATIONS['idle']+duration+duration+preview.ROW_DURATIONS['idle']
        preview.save_preview(cycle,times,OUT/f'{state}-transition.gif')
        preview.save_preview(scale2(cycle),times,OUT/f'{state}-transition-2x.gif')
        pairs=[]
        for a,b in zip(old_cycle,cycle):
            pair=Image.new('RGBA',(384,208));pair.paste(a,(0,0));pair.paste(b,(192,0));pairs.append(pair)
        preview.save_preview(scale2(pairs),times,OUT/f'{state}-comparison.gif')
        draw.text((8,index*238+4),f'{state} / revised native frames',fill='#222222')
        for i,frame in enumerate(frames):sheet.paste(frame,(i*192,index*238+25),frame)
        records.append({'state':state,'frame_count':len(frames),'duration_ms':duration,
                        'interior_translation':[dx,dy],'interior_original_pixels_preserved':True,
                        'first_and_last_exact_idle':True,'first_body':geometry(frames[0]),
                        'last_body':geometry(frames[-1]),'scaled':False,'redrawn':False,
                        'native_cycle_count_in_transition_preview':2})
    OUT.mkdir(parents=True,exist_ok=True)
    sheet.save(OUT/'seated-contact-sheet.png')
    candidate.save(OUT/'candidate-atlas.webp',lossless=True,exact=True)
    (OUT/'frames/frames-manifest.json').write_text(json.dumps({'ok':True,'rows':manifest},indent=2),encoding='utf-8')
    if call('inspect_frames.py','--frames-root',OUT/'frames','--states',','.join(SEATED),'--json-out',OUT/'frame-review.json','--allow-stable-slots'):
        raise SystemExit('Frame validation failed')
    if call('validate_atlas.py',OUT/'candidate-atlas.webp','--require-v2','--json-out',OUT/'validation.json'):
        raise SystemExit('Candidate atlas validation failed')
    assert hashlib.sha256(source.read_bytes()).hexdigest()==source_hash
    report={'status':'awaiting_user_approval','baseline_atlas_sha256':source_hash,
            'changed_states':SEATED,'states':records,'native_timing_preserved':True,
            'first_and_last_are_canonical_idle':True,'active_atlas_unchanged':True,
            'installed':False,'packaged':False,'cloud_updated':False,'dynamic_playback_observed':False,
            'remaining_design':'walking candidates handled separately; no seated frames added to walking loop'}
    (OUT/'status.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
