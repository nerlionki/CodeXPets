"""Resample whole frames from one generated row; never redraw pet pixels."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'approval/walk-chibi-v8'
OUT = ROOT / 'approval/walk-chibi-v9'
ORDER = [0, 1, 2, 3, 4, 3, 6, 7]
folder = OUT / 'frames/running-right'
folder.mkdir(parents=True, exist_ok=True)
cells = []
provenance = []
for index, original in enumerate(ORDER):
    source = SOURCE / 'frames/running-right' / f'{original:02}.png'
    dest = folder / f'{index:02}.png'
    shutil.copy2(source, dest)
    assert dest.read_bytes() == source.read_bytes()
    cells.append(Image.open(dest).convert('RGBA'))
    provenance.append({'frame': index, 'source_frame': original,
                       'sha256': hashlib.sha256(dest.read_bytes()).hexdigest()})
row = Image.new('RGBA', (1536, 208))
for col, cell in enumerate(cells):
    row.paste(cell, (col*192, 0))
(OUT / 'source').mkdir(exist_ok=True)
row.save(OUT / 'source/running-right.png')
manifest = json.loads((SOURCE / 'frames/frames-manifest.json').read_text(encoding='utf-8'))
right = next(r for r in manifest['rows'] if r['state'] == 'running-right')
right['frames'] = [str((folder / f'{i:02}.png').resolve()) for i in range(8)]
manifest['rows'] = [right]
(OUT / 'frames/frames-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
report = {'ok': True, 'single_generated_family': str(SOURCE), 'source_frame_order': ORDER,
          'frame_provenance': provenance, 'whole_frames_only': True,
          'pixels_redrawn': False, 'pixels_rescaled': False,
          'reason': 'Source frame 5 prematurely changes white dog support; use source frame 3 for the return phase',
          'timing_ms': [120]*7+[220]}
(OUT / 'temporal-assembly.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
(OUT / 'despill.json').write_text(json.dumps({
    'ok': True, 'algorithm': 'temporal-selection-of-already-cleaned-whole-frames',
    'source_report': str(SOURCE / 'despill.json'), 'additional_cleanup_applied': False,
    'alpha_preserved': True}, indent=2), encoding='utf-8')
(OUT / 'BRIEF.md').write_text('''# 垂耳、Q版短腿与连续换脚

本稿保留 v8 同一条带内已检查的耳朵、脸、牵手与Q腿。
仅按独立相位检查建议重采样整帧：0,1,2,3,4,3,6,7。
没有重画或拼接局部肢体，也没有混用其它生成结果；新第5帧使用同一源的第3帧回落姿态。
两只承重顺序为左、左、双脚、右、右、右、双脚、左。
真实客户端时序120ms×7+220ms保持；左行动画由右行逐帧水平镜像产生。
审批通过之前，不更新安装器、本地安装或云端记录。
''', encoding='utf-8')
subprocess.run([sys.executable, str(ROOT / 'tools/preview-mirrored-left.py'),
                '--output', str(OUT.relative_to(ROOT)),
                '--source-frames', str(folder.relative_to(ROOT))], check=True)
for suffix in ['', '-2x']:
    shutil.copy2(OUT / f'running-right-reference{suffix}.gif', OUT / f'running-right{suffix}.gif')
print('Ordered whole-frame walk preview ready')
