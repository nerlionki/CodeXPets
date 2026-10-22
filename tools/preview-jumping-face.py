"""Combine generated upright-ear artwork with existing eyes shifted as pixels."""
import hashlib
import importlib.util
import itertools
import json
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from pet_pipeline_import import RUN, SKILL, call

ROOT = RUN.parents[1]
OUT = ROOT / 'approval/jumping-face-v23'
BASE = ROOT / 'approval/jumping-nose-v22/frames/jumping'
EYES = [
    [(58,122,62,126),(80,110,85,114),(117,126,121,131),(141,126,145,131)],
    [(52,94,55,98),(74,84,78,88),(124,103,128,107),(147,103,150,107)],
    [(45,81,49,84),(68,71,71,74),(125,93,129,97),(148,93,152,97)],
    [(51,94,54,98),(72,84,76,88),(124,103,128,107),(147,103,151,107)],
    [(58,122,62,126),(81,110,85,114),(118,127,121,131),(141,126,145,131)],
]
EARS = [(106,76,133,116),(112,49,138,92),(113,38,140,83),(112,49,138,92),(106,76,133,116)]


def eye_centers(cell, expected):
    a = np.array(cell)
    pts = set(zip(*np.where((a[:,:,:3].max(2)<100)&(a[:,:,3]>128))))
    centers = []
    while pts:
        seed = pts.pop()
        q, group = [seed], [seed]
        while q:
            y,x = q.pop()
            for dy,dx in itertools.product([-1,0,1],repeat=2):
                p = (y+dy,x+dx)
                if p in pts:
                    pts.remove(p)
                    group.append(p)
                    q.append(p)
        ys,xs = zip(*group)
        if 3 <= len(group) <= 40 and max(xs)-min(xs) < 8 and max(ys)-min(ys) < 8:
            centers.append(np.array([np.mean(xs),np.mean(ys)]))
    choices = [(float(sum(np.sum((c-e)**2) for c,e in zip(pair,expected))),pair)
               for pair in itertools.permutations(centers,2) if pair[0][0] < pair[1][0]]
    score, result = min(choices,key=lambda v:v[0])
    assert score < 500, (score,result)
    return np.array(result)


def main():
    status = json.loads((OUT/'status.json').read_text(encoding='utf-8'))
    source = RUN/'final/spritesheet-extended.webp'
    assert hashlib.sha256(source.read_bytes()).hexdigest()==status['baseline_atlas_sha256']
    spec = importlib.util.spec_from_file_location('face_preview',SKILL/'scripts/render_animation_previews.py')
    preview = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(preview)
    generated = OUT/'generated-frames/jumping'
    generated.mkdir(parents=True,exist_ok=True)
    before, after, records = [], [], []
    for col in range(5):
        path = OUT/'frames/jumping'/f'{col:02}.png'
        saved = generated/path.name
        if not saved.exists():
            shutil.copy2(path,saved)
        ear_source = Image.open(saved).convert('RGBA')
        old = Image.open(BASE/path.name).convert('RGBA')
        expected = np.array([[(b[0]+b[2]-1)/2,(b[1]+b[3]-1)/2] for b in EYES[col][2:]])
        detected = eye_centers(ear_source,expected)
        scale = (expected[1,0]-expected[0,0])/(detected[1,0]-detected[0,0])
        assert .75 < scale < 1.3, scale
        translation = expected.mean(0)-scale*detected.mean(0)
        registered = ear_source.transform((192,208),Image.Transform.AFFINE,(1/scale,0,-translation[0]/scale,0,1/scale,-translation[1]/scale),resample=Image.Resampling.BICUBIC)
        new = old.copy()
        ear = EARS[col]
        new.paste(registered.crop(ear),ear[:2])
        a = np.array(old)
        b = np.array(new)
        allowed = np.zeros((208,192),dtype=bool)
        allowed[ear[1]:ear[3],ear[0]:ear[2]] = True
        patches = []
        for index, (x0,y0,x1,y1) in enumerate(EYES[col]):
            box = (x0-1,y0-1,x1+1,y1+1)
            patch = a[box[1]:box[3],box[0]:box[2]].copy()
            ring = patch[:,:,:3].reshape(-1,3)
            light = ring[(ring[:,0]>215)&(ring[:,1]>170)&(ring[:,2]>110)]
            assert len(light), (col,index)
            fill = np.median(light,axis=0).astype(np.uint8)
            b[box[1]:box[3],box[0]:box[2],:3] = fill
            patches.append((box,patch))
            allowed[box[1]-2:box[3],box[0]:box[2]] = True
        for box,patch in patches:
            b[box[1]-2:box[3]-2,box[0]:box[2],:3] = patch[:,:,:3]
        changed = (a!=b).any(2)
        assert not (changed&~allowed).any()
        # Ear is the only location where the sprite's alpha may change.
        alpha_change = a[:,:,3]!=b[:,:,3]
        ear_mask = np.zeros_like(allowed)
        ear_mask[ear[1]:ear[3],ear[0]:ear[2]] = True
        assert not (alpha_change&~ear_mask).any()
        frame = Image.fromarray(b)
        frame.save(path)
        before.append(old)
        after.append(frame)
        records.append({'frame':col,'eye_shift_y':-2,'eyes_per_character':2,'ear_region':ear,'ear_registration_scale':float(scale),'changed_pixels':int(changed.sum())})
    timing = preview.ROW_DURATIONS['jumping']
    preview.save_preview(after,timing,OUT/'jumping.gif')
    preview.save_preview([f.resize((384,416),Image.Resampling.NEAREST) for f in after],timing,OUT/'jumping-2x.gif')
    comparisons = []
    sheet = Image.new('RGB',(960,446),'#f4efe9')
    draw = ImageDraw.Draw(sheet)
    for row,(label,frames) in enumerate([('v22 before',before),('v23 upright ear / wider eye-mouth spacing',after)]):
        draw.text((8,row*223+4),label,fill='#222222')
        for col,frame in enumerate(frames):
            sheet.paste(frame,(col*192,row*223+15),frame)
    sheet.save(OUT/'contact-sheet.png')
    for old,new in zip(before,after):
        c = Image.new('RGBA',(384,208))
        c.paste(old,(0,0))
        c.paste(new,(192,0))
        comparisons.append(c.resize((768,416),Image.Resampling.NEAREST))
    preview.save_preview(comparisons,timing,OUT/'comparison-2x.gif')
    if call('inspect_frames.py','--frames-root',OUT/'frames','--states','jumping','--json-out',OUT/'frame-review.json','--allow-stable-slots'):
        raise SystemExit('Frame validation failed')
    assert hashlib.sha256(source.read_bytes()).hexdigest()==status['baseline_atlas_sha256']
    status['generated_source_states'] = status.pop('states',[])
    status.update(status='awaiting_user_approval',method='Generated upright white left ear only; existing v22 eye pixels moved up two pixels; all pixels outside ear and eye regions unchanged',states=[{'state':'jumping','frames':5,'durations_ms':timing,'bounds':[f.getbbox() for f in after]}],records=records,integrated=False,packaged=False,installed=False,cloud_updated=False,active_atlas_unchanged=True)
    (OUT/'status.json').write_text(json.dumps(status,indent=2),encoding='utf-8')
    print(json.dumps(status,indent=2))


if __name__=='__main__':
    main()
