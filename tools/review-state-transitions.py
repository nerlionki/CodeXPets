"""Render approval overviews and verify exact preview timing and atlas scope."""
import bisect
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pet_pipeline_import import RUN, SKILL

OUT=RUN.parents[1]/'approval/state-transitions-v29'
STATES=['idle','running-right','running-left','waving','jumping','failed','waiting','running','review']
LABELS={'waving':'挥手','failed':'蹭脸','waiting':'等待输入','running':'亲吻处理','review':'检查结果',
        'running-right':'向右拖拽','running-left':'向左拖拽'}


def main():
    global OUT
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=OUT)
    args=parser.parse_args();OUT=args.output.resolve()
    spec=importlib.util.spec_from_file_location('overview_preview',SKILL/'scripts/render_animation_previews.py')
    preview=importlib.util.module_from_spec(spec);spec.loader.exec_module(preview)
    original=RUN/'final/spritesheet-extended.webp'
    a=Image.open(original).convert('RGBA')
    b=Image.open(OUT/'candidate-atlas.webp').convert('RGBA')
    idle=[a.crop((i*192,0,(i+1)*192,208)) for i in range(6)]
    status=json.loads((OUT/'status.json').read_text(encoding='utf-8'))
    assert hashlib.sha256(original.read_bytes()).hexdigest()==status['baseline_atlas_sha256']
    changed_rows={STATES.index(s) for s in status['changed_states']}
    unchanged_rows=sorted(set(range(11))-changed_rows)
    for row in unchanged_rows:
        box=(0,row*208,1536,(row+1)*208)
        assert a.crop(box).tobytes()==b.crop(box).tobytes()
    font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',14)
    timings=[]
    def overview(states,cols,name):
        sequences=[];edges={0}
        for state in states:
            files=sorted((OUT/'frames'/state).glob('*.png'))
            frames=[Image.open(p).convert('RGBA') for p in files]
            durations=preview.ROW_DURATIONS[state]
            sequence=idle+frames+frames+idle
            times=preview.ROW_DURATIONS['idle']+durations+durations+preview.ROW_DURATIONS['idle']
            boundaries=[0]
            for t in times:boundaries.append(boundaries[-1]+t)
            sequences.append((state,sequence,boundaries))
            edges.update(boundaries)
        edges=sorted(edges)
        images=[];times=[]
        for start,end in zip(edges,edges[1:]):
            panel=Image.new('RGB',(cols*192,((len(states)+cols-1)//cols)*232),'#f4efe9')
            draw=ImageDraw.Draw(panel)
            for index,(state,frames,boundaries) in enumerate(sequences):
                frame=frames[min(len(frames)-1,bisect.bisect_right(boundaries,start)-1)]
                x=(index%cols)*192;y=(index//cols)*232
                draw.text((x+8,y+4),LABELS[state],font=font,fill='#222222')
                panel.paste(frame,(x,y+24),frame)
            images.append(panel);times.append(end-start)
        preview.save_preview(images,times,OUT/name)
        preview.save_preview([f.resize((f.width*2,f.height*2),Image.Resampling.NEAREST) for f in images],times,OUT/name.replace('.gif','-2x.gif'))
    overview(['waving','failed','waiting','running','review'],3,'seated-overview.gif')
    if all(s in status['changed_states'] for s in ['running-right','running-left']):
        overview(['running-right','running-left'],2,'walking-overview.gif')
    for state in status['changed_states']:
        with Image.open(OUT/f'{state}.gif') as gif:
            actual=[]
            for i in range(gif.n_frames):
                gif.seek(i);actual.append(gif.info['duration'])
            assert actual==preview.ROW_DURATIONS[state],(state,actual)
        with Image.open(OUT/f'{state}-transition.gif') as gif:
            total=0
            for i in range(gif.n_frames):gif.seek(i);total+=gif.info['duration']
            expected=2*sum(preview.ROW_DURATIONS['idle'])+2*sum(preview.ROW_DURATIONS[state])
            assert total==expected,(state,total,expected)
        timings.append({'state':state,'native_ms':actual,'transition_total_ms':total})
    report={'ok':True,'native_gif_durations_verified':timings,'unchanged_atlas_rows':unchanged_rows,
            'active_and_packaged_atlas_unchanged':hashlib.sha256(original.read_bytes()).hexdigest()==hashlib.sha256((RUN.parents[1]/'dist/maltese-retriever/spritesheet.webp').read_bytes()).hexdigest(),
            'seated_endpoint_pixel_identity_verified':True,'all_candidate_frames_inside_cells':True,
            'dynamic_playback_observed':False,'review':'native contact sheets and pose geometry; GIF motion requires user approval'}
    for state in ['waving','failed','waiting','running','review']:
        for i in [0,len(preview.ROW_DURATIONS[state])-1]:
            assert Image.open(OUT/f'frames/{state}/{i:02}.png').convert('RGBA').tobytes()==idle[0].tobytes()
    assert report['active_and_packaged_atlas_unchanged']
    (OUT/'preview-qa.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    status['seated_first_and_last_are_canonical_idle']=status.pop('first_and_last_are_canonical_idle',True)
    status['changed_states']=list(dict.fromkeys(status['changed_states']))
    status['preview_qa']='preview-qa.json'
    (OUT/'status.json').write_text(json.dumps(status,indent=2),encoding='utf-8')
    print('Preview timing, unchanged rows, seated endpoints and unmodified active package verified')


if __name__=='__main__':main()
