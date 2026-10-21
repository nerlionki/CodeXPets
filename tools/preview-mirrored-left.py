"""Preview a left walk derived by mirroring each approved right-walk cell."""
import hashlib
import importlib.util
import json
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps
from pet_pipeline_import import RUN, SKILL, call

ROOT = RUN.parents[1]

parser = argparse.ArgumentParser()
parser.add_argument('--output', default='approval/walk-left-mirror-v5')
parser.add_argument('--source-frames', help='Already cleaned eight right-walk cells, relative to workspace')
args = parser.parse_args()
OUT = ROOT / args.output
OUT.mkdir(parents=True, exist_ok=True)
atlas_path = RUN / 'final/spritesheet-extended.webp'
atlas = Image.open(atlas_path).convert('RGBA')
assert atlas.size == (1536, 2288)
right = [atlas.crop((i*192, 208, (i+1)*192, 416)) for i in range(8)]
source_files = []
if args.source_frames:
    source_files = sorted((ROOT / args.source_frames).glob('*.png'))
    assert len(source_files) == 8, 'Expected eight cleaned right-walk frames'
    right = [Image.open(p).convert('RGBA') for p in source_files]
    assert all(frame.size == (192, 208) for frame in right)
old_left = [atlas.crop((i*192, 416, (i+1)*192, 624)) for i in range(8)]
left = [ImageOps.mirror(frame) for frame in right]
folder = OUT / 'frames/running-left'
folder.mkdir(parents=True, exist_ok=True)
for index, frame in enumerate(left):
    frame.save(folder / f'{index:02}.png')
    assert ImageOps.mirror(frame).tobytes() == right[index].tobytes()
    assert frame.getchannel('A').histogram() == right[index].getchannel('A').histogram()
manifest = {'ok': True, 'chroma_key': {'hex': '#0000FF', 'rgb': [0, 0, 255], 'threshold': 96},
            'rows': [{'state': 'running-left', 'method': 'stable-slots',
                      'frames': [str((folder / f'{i:02}.png').resolve()) for i in range(8)]}]}
manifest_path = OUT / 'frames/frames-manifest.json'
if manifest_path.exists():
    prior = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    manifest['rows'] = [r for r in prior['rows'] if r['state'] != 'running-left'] + manifest['rows']
(OUT / 'frames/frames-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
if call('inspect_frames.py', '--frames-root', OUT / 'frames', '--states', ','.join(r['state'] for r in manifest['rows']),
        '--json-out', OUT / 'frame-review.json', '--allow-stable-slots'):
    raise SystemExit('Mirrored frames failed inspection')
spec = importlib.util.spec_from_file_location('preview', SKILL / 'scripts/render_animation_previews.py')
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)
durations = preview.ROW_DURATIONS['running-left']
assert durations == preview.ROW_DURATIONS['running-right']
for name, frames in [('running-right-reference', right), ('running-left', left)]:
    preview.save_preview(frames, durations, OUT / f'{name}.gif')
    preview.save_preview([f.resize((384, 416), Image.Resampling.NEAREST) for f in frames],
                         durations, OUT / f'{name}-2x.gif')
sheet = Image.new('RGB', (1536, 3*238), '#f4efe9')
draw = ImageDraw.Draw(sheet)
for row, (label, frames) in enumerate([('right-walk reference', right), ('previous left walk', old_left), ('mirrored left walk', left)]):
    draw.text((8, row*238+5), label, fill='#222222')
    for col, frame in enumerate(frames):
        sheet.paste(frame, (col*192, row*238+25), frame.getchannel('A'))
sheet.save(OUT / 'contact-sheet.png')
report = {'ok': True, 'source_atlas_sha256': hashlib.sha256(atlas_path.read_bytes()).hexdigest(),
          'source_frame_paths': [str(p) for p in source_files],
          'source_frame_sha256': [hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files],
          'source_row': 1, 'derived_state': 'running-left', 'operation': 'horizontal mirror of each cell, same frame order',
          'frames': 8, 'durations_ms': durations,
          'previous_left_was_exact_mirror': all(a.tobytes() == b.tobytes() for a, b in zip(old_left, left)),
          'all_new_left_frames_are_exact_right_mirrors': True,
          'alpha_and_pixel_colors_preserved': True, 'characters_swap_screen_positions': True,
          'installed': False, 'packaged': False, 'cloud_updated': False,
          'status': 'awaiting_user_approval'}
(OUT / 'mirror-validation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
(OUT / 'status.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
if not (OUT / 'BRIEF.md').exists():
    (OUT / 'BRIEF.md').write_text('''# 向左拖拽：逐帧镜像向右动画

用户最新要求继续修复，并指出左右拖拽动画应是镜像。
来源为当前已确认图集的 running-right 八帧。每格仅做水平镜像，帧序、时长、颜色、透明度和步态不变。
不镜像整个条带，避免倒转时间顺序。两只角色的屏幕站位自然对换。
旧左行动画独立绘制，不是该右行动画的精确镜像。
本稿只供 GIF 审批，没有覆盖安装器、本地安装或当前云端宠物。
''', encoding='utf-8')
print(json.dumps(report, indent=2))
