"""Read-only pixel matching of the reported screenshot against shipped cells."""
from pathlib import Path
import json
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'approval/face-lines-audit'
shot = Image.open(OUT/'user-screenshot.png').convert('RGB').crop((20,6,153,113))
a = np.asarray(shot)
mask = (a.max(axis=2)<110) | ((a[:,:,0]>130)&(a[:,:,1]>100)&(a[:,:,1]<235)&(a[:,:,2]<205)&(a[:,:,0]>a[:,:,1]+5)&(a[:,:,1]>a[:,:,2]+10))
ys,xs=np.where(mask)
shot=shot.crop((int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)))
target=np.asarray(shot,dtype=float)
atlas=Image.open(ROOT/'dist/maltese-retriever/spritesheet.webp').convert('RGBA')
counts=[7,8,8,4,5,8,6,6,6,8,8]
results=[]
for r,n in enumerate(counts):
    for c in range(n):
        cell=atlas.crop((c*192,r*208,(c+1)*192,(r+1)*208))
        alpha=cell.getchannel('A').point(lambda v:255 if v>100 else 0)
        bbox=alpha.getbbox()
        if not bbox:continue
        cell=cell.crop(bbox)
        tile=Image.new('RGBA',cell.size,'white');tile.alpha_composite(cell)
        tile=tile.convert('RGB').resize(shot.size,Image.Resampling.LANCZOS)
        pixels=np.asarray(tile,dtype=float)
        mse=float(np.square(pixels-target).mean())
        results.append({'row':r,'column':c,'mse':mse,'bbox':bbox,'tile':tile})
results.sort(key=lambda x:x['mse'])
sheet=Image.new('RGB',(6*176,200),'#f2eee9');draw=ImageDraw.Draw(sheet)
draw.text((8,5),'Reported screenshot',fill='black');sheet.paste(shot,(8,32))
for i,result in enumerate(results[:5],1):
    draw.text((i*176+5,5),f"r{result['row']}c{result['column']} {result['mse']:.1f}",fill='black')
    sheet.paste(result['tile'],(i*176+5,32))
sheet.save(OUT/'match-candidates.png')
summary={'screenshot_crop_size':shot.size,'top_matches':[{k:v for k,v in x.items() if k!='tile'} for x in results[:8]]}
(OUT/'pixel-matches.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps(summary,indent=2))
