"""Normalize only the existing white character's body ink; preserve all geometry."""
import hashlib
import argparse
import importlib.util
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from pet_pipeline_import import RUN, SKILL, call

ROOT = RUN.parents[1]
SOURCE = ROOT / 'approval/jumping-face-v23/frames/jumping'
OUT = ROOT / 'approval/jumping-body-lines-v24'
# Body includes outstretched arms; separate face exclusions protect all features.
BODY = [(105,143,183,202),(96,99,190,168),(96,89,190,158),(96,99,190,168),(105,143,183,202)]
FACE = [(110,112,157,148),(114,87,162,125),(115,76,163,115),(114,87,162,125),(110,112,157,148)]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name,path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def local_distance(seed, radius):
    """Exact Euclidean distance to existing pixels within a bounded radius."""
    h,w = seed.shape
    padded = np.pad(seed,radius)
    result = np.full((h,w),np.inf)
    for dy in range(-radius,radius+1):
        for dx in range(-radius,radius+1):
            d = dx*dx+dy*dy
            if d > radius*radius:
                continue
            nearby = padded[radius+dy:radius+dy+h,radius+dx:radius+dx+w]
            result[nearby] = np.minimum(result[nearby],d)
    return np.sqrt(result)


def main():
    global SOURCE, OUT, BODY
    parser = argparse.ArgumentParser()
    parser.add_argument('--part', choices=['body','ear'], default='body')
    args = parser.parse_args()
    ear_mode = args.part == 'ear'
    if ear_mode:
        SOURCE = ROOT / 'approval/jumping-body-lines-v24/frames/jumping'
        OUT = ROOT / 'approval/jumping-ear-lines-v25'
        BODY = [(106,76,142,118),(112,49,146,94),(113,38,147,85),(112,49,146,94),(106,76,142,118)]
    OUT.mkdir(exist_ok=True)
    (OUT/'frames/jumping').mkdir(parents=True,exist_ok=True)
    style = load('body_style',ROOT/'tools/normalize-animation-style.py')
    preview = load('body_preview',SKILL/'scripts/render_animation_previews.py')
    current = RUN/'final/spritesheet-extended.webp'
    baseline_hash = hashlib.sha256(current.read_bytes()).hexdigest()
    before,after,reports = [],[],[]
    target_width = 3.2 if ear_mode else 3.5
    for col in range(5):
        old = Image.open(SOURCE/f'{col:02}.png').convert('RGBA')
        a = np.array(old)
        rgb = a[:,:,:3].astype(float)
        alpha = a[:,:,3]
        white = (rgb.min(2)>210)&(rgb.max(2)-rgb.min(2)<25)&(alpha>200)
        gold = (rgb[:,:,0]>140)&(rgb[:,:,1]-rgb[:,:,2]>20)&(rgb[:,:,0]-rgb[:,:,1]>8)&(alpha>200)
        dw = local_distance(white,7)
        dg = local_distance(gold,7)
        ink = (rgb.max(2)<110)&(alpha>128)
        centerline = style.skeleton(ink)
        distance = local_distance(centerline,5)
        edge_distance = local_distance(alpha<128,6)
        allowed = np.zeros((208,192),dtype=bool)
        x0,y0,x1,y1 = BODY[col]
        allowed[y0:y1,x0:x1] = True
        fx0,fy0,fx1,fy1 = FACE[col]
        allowed[fy0:fy1,fx0:fx1] = False
        allowed &= (dw<=6)&(dw<dg)&~((dw<5)&(dg<5))&(alpha>0)&((distance<=4)|(edge_distance<=4.5))
        # Resample ink around the original stroke centerline. Alpha remains
        # identical, preserving the complete hand-drawn silhouette and tu pose.
        inner_ink = np.clip(target_width/2+.5-distance,0,1)
        # Existing alpha supplies the continuous outer contour even where the
        # old dark core was faint or interrupted by prior edge cleanup.
        outer_ink = np.clip(target_width+1-edge_distance,0,1)
        coverage = np.maximum(inner_ink,outer_ink)
        corrected = 253 + coverage[:,:,None]*(np.array([4,3,3])-253)
        result = a.copy()
        result[allowed,:3] = np.uint8(np.rint(corrected[allowed]))
        changed = (result!=a).any(2)
        assert not (changed&~allowed).any()
        assert np.array_equal(result[:,:,3],a[:,:,3])
        assert np.array_equal(result[fy0:fy1,fx0:fx1],a[fy0:fy1,fx0:fx1])
        new = Image.fromarray(result)
        assert new.getbbox()==old.getbbox()
        new.save(OUT/'frames/jumping'/f'{col:02}.png')
        before.append(old)
        after.append(new)
        reports.append({'frame':col,'changed_pixels':int(changed.sum()),'target_stroke_width':target_width,'region':BODY[col],'face_pixel_identical':True,'alpha_pixel_identical':True,'changes_confined_to_requested_ink_region':True})
    timing = preview.ROW_DURATIONS['jumping']
    preview.save_preview(after,timing,OUT/'jumping.gif')
    preview.save_preview([f.resize((384,416),Image.Resampling.NEAREST) for f in after],timing,OUT/'jumping-2x.gif')
    comparisons=[]
    sheet=Image.new('RGB',(960,446),'#f4efe9')
    draw=ImageDraw.Draw(sheet)
    labels = ('v24 before','v25 left ear / forehead stroke calibration') if ear_mode else ('v23 before','v24 white body stroke calibration')
    for row,(label,frames) in enumerate(zip(labels,[before,after])):
        draw.text((8,row*223+4),label,fill='#222222')
        for col,frame in enumerate(frames):
            sheet.paste(frame,(col*192,row*223+15),frame)
    sheet.save(OUT/'contact-sheet.png')
    for old,new in zip(before,after):
        c=Image.new('RGBA',(384,208))
        c.paste(old,(0,0))
        c.paste(new,(192,0))
        comparisons.append(c.resize((768,416),Image.Resampling.NEAREST))
    preview.save_preview(comparisons,timing,OUT/'comparison-2x.gif')
    manifest={'ok':True,'rows':[{'state':'jumping','method':'stable-slots','frames':[str((OUT/'frames/jumping'/f'{i:02}.png').resolve()) for i in range(5)]}]}
    (OUT/'frames/frames-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    if call('inspect_frames.py','--frames-root',OUT/'frames','--states','jumping','--json-out',OUT/'frame-review.json','--allow-stable-slots'):
        raise SystemExit('Frame checks failed')
    assert hashlib.sha256(current.read_bytes()).hexdigest()==baseline_hash
    report={'status':'awaiting_user_approval','baseline_atlas_sha256':baseline_hash,'source_candidate':'jumping-body-lines-v24' if ear_mode else 'jumping-face-v23','part':args.part,'method':'Normalize only requested white-character ink regions around existing stroke centerlines and alpha contour; preserve alpha and all other pixels','frames':reports,'timing_ms':timing,'integrated':False,'packaged':False,'installed':False,'cloud_updated':False}
    (OUT/'status.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
