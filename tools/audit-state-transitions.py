"""Render real native state boundaries for review without changing artwork."""
import hashlib
import importlib.util
import json
from pathlib import Path
from PIL import Image, ImageDraw
from pet_pipeline_import import RUN, SKILL

ROOT=RUN.parents[1]
OUT=ROOT/'approval/state-transition-audit-v27'
STATES=['idle','running-right','running-left','waving','jumping','failed','waiting','running','review']


def module(name,filename):
    spec=importlib.util.spec_from_file_location(name,SKILL/'scripts'/filename)
    result=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def main():
    OUT.mkdir(exist_ok=True)
    preview=module('audit_previews','render_animation_previews.py')
    extract=module('audit_components','extract_strip_frames.py')
    source=RUN/'final/spritesheet-extended.webp'
    atlas=Image.open(source).convert('RGBA')
    idle=[atlas.crop((i*192,0,(i+1)*192,208)) for i in range(6)]
    def geometry(frame):
        components=extract.connected_components(frame)
        largest=max(c['area'] for c in components)
        bodies=[c for c in components if c['area']>=max(200,largest*.12)]
        x0=min(c['bbox'][0] for c in bodies)
        y0=min(c['bbox'][1] for c in bodies)
        x1=max(c['bbox'][2] for c in bodies)
        y1=max(c['bbox'][3] for c in bodies)
        return {'bbox':[x0,y0,x1,y1],'width':x1-x0,'height':y1-y0,'ground':y1,'center_x':(x0+x1)/2}
    reference=geometry(idle[0])
    sheet=Image.new('RGB',(960,8*238),'#f4efe9')
    draw=ImageDraw.Draw(sheet)
    reports=[]
    for row,state in enumerate(STATES[1:]):
        index=STATES.index(state)
        count=len(preview.ROW_DURATIONS[state])
        frames=[atlas.crop((i*192,index*208,(i+1)*192,(index+1)*208)) for i in range(count)]
        if state=='jumping':
            frames=[Image.open(ROOT/'approval/hover-transition-v26/frames/jumping'/f'{i:02}.png').convert('RGBA') for i in range(count)]
        durations=preview.ROW_DURATIONS['idle']+preview.ROW_DURATIONS[state]+preview.ROW_DURATIONS['idle']
        sequence=idle+frames+idle
        preview.save_preview(sequence,durations,OUT/f'{state}-transition.gif')
        preview.save_preview([f.resize((384,416),Image.Resampling.NEAREST) for f in sequence],durations,OUT/f'{state}-transition-2x.gif')
        first,last=geometry(frames[0]),geometry(frames[-1])
        reports.append({'state':state,'first':first,'last':last,'first_ground_delta':first['ground']-reference['ground'],'last_ground_delta':last['ground']-reference['ground'],'first_width_ratio':first['width']/reference['width'],'last_width_ratio':last['width']/reference['width'],'first_exact_idle':frames[0].tobytes()==idle[0].tobytes(),'last_exact_idle':frames[-1].tobytes()==idle[0].tobytes(),'native_durations_ms':preview.ROW_DURATIONS[state]})
        draw.text((8,row*238+4),f'{state} | idle / entry / middle / exit / idle',fill='#222222')
        for col,frame in enumerate([idle[0],frames[0],frames[len(frames)//2],frames[-1],idle[0]]):
            sheet.paste(frame,(col*192,row*238+25),frame)
    sheet.save(OUT/'boundary-contact-sheet.png')
    look_sheet=Image.new('RGB',(1536,2*238),'#f4efe9')
    ld=ImageDraw.Draw(look_sheet)
    looks=[]
    for i in range(16):
        row,col=9+i//8,i%8
        frame=atlas.crop((col*192,row*208,(col+1)*192,(row+1)*208))
        looks.append(frame)
        ld.text((col*192+5,(i//8)*238+4),f'{i*22.5:g} degrees',fill='#222222')
        look_sheet.paste(frame,(col*192,(i//8)*238+25),frame)
    look_sheet.save(OUT/'look-contact-sheet.png')
    preview.save_preview(idle+looks+idle,preview.ROW_DURATIONS['idle']+[180]*16+preview.ROW_DURATIONS['idle'],OUT/'look-transition.gif')
    report={'atlas_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'idle_body_geometry':reference,'body_geometry_excludes_detached_hearts':True,'states':reports,'looks':[{'degree':i*22.5,**geometry(f)} for i,f in enumerate(looks)],'native_timing_preserved':True,'audit_only_artwork_unchanged':True,'dynamic_playback_observed':False}
    (OUT/'measurements.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
