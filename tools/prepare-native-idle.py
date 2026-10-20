"""Fit the approved bubble effect into Codex's six native idle keyframes.

Only previously generated/supplied artwork is assembled here. No pet or heart
shape is drawn. The installer previews the native timing before installation.
"""
import importlib.util
import json
from pathlib import Path
from PIL import Image
from pet_pipeline_import import RUN, SKILL, call

ROOT = RUN.parents[1]

def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, SKILL / 'scripts' / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

extract = load('pet_extract', 'extract_strip_frames.py')
heart = Image.open(ROOT / 'approval/idle-bubble-v4/heart-raw.png').convert('RGBA')
source = ROOT / 'approval/idle-reference-v3/extracted/idle'
out = RUN / 'qa/rows/idle/frames'
(out / 'idle').mkdir(parents=True, exist_ok=True)
pattern = [[], [(76, 1)], [(51, 1), (76, 1)], [(26, .65), (51, 1), (76, 1)], [(26, .65), (51, 1)], [(26, .35)]]
for index, positions in enumerate(pattern):
    frame = Image.open(source / f'{index:02d}.png').convert('RGBA')
    components = extract.connected_components(frame)
    main = max(components, key=lambda c: c['area'])
    body_parts = [c for c in components if c['bbox'][3] >= main['bbox'][1]]
    body = extract.component_group_image(frame, body_parts, padding=0)
    cell = Image.new('RGBA', (192, 208), (0, 0, 0, 0))
    cell.alpha_composite(body, (min(c['bbox'][0] for c in body_parts), min(c['bbox'][1] for c in body_parts)))
    for center_y, opacity in positions:
        bubble = heart.copy()
        if opacity < 1:
            bubble.putalpha(bubble.getchannel('A').point(lambda a: round(a * opacity)))
        cell.alpha_composite(bubble, ((192 - heart.width) // 2, round(center_y - heart.height / 2)))
    cell.save(out / 'idle' / f'{index:02d}.png')
manifest = {'ok': True, 'chroma_key': {'hex': '#0000FF', 'rgb': [0, 0, 255], 'threshold': 96}, 'rows': [{'state': 'idle', 'method': 'stable-slots', 'frames': [str((out / 'idle' / f'{i:02d}.png').resolve()) for i in range(6)]}]}
(out / 'frames-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
if call('inspect_frames.py', '--frames-root', out, '--json-out', RUN / 'qa/rows/idle/review.json', '--states', 'idle', '--require-components', '--allow-stable-slots'):
    raise SystemExit('Native idle frame validation failed')
record = {'approved_demo': 'approval/idle-bubble-v4/idle-approval-v4.gif', 'demo_frames': 28, 'native_frames': 6, 'native_durations_ms': [280, 110, 110, 140, 140, 320], 'direction': 'bottom-to-top', 'heart_style': 'exact black-outline pink-fill supplied artwork', 'counts': [len(p) for p in pattern], 'note': 'The installer previews the actual native six-frame timing; demo timing is not advertised as identical.'}
(ROOT / 'release/1.0.0/native-idle-adaptation.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
