"""Collect individually validated frames and use the bundled atlas/preview pipeline."""
import json
import shutil
import importlib.util
from PIL import Image
from pet_pipeline_import import RUN, call
from pet_pipeline_import import SKILL

STATES = ['idle', 'running-right', 'running-left', 'waving', 'jumping', 'failed', 'waiting', 'running', 'review']
rows = []
for state in STATES:
    source = RUN / 'qa/rows' / state
    report = json.loads((source / 'review.json').read_text(encoding='utf-8-sig'))
    if not report['ok']:
        raise SystemExit(f'{state} has not passed frame validation')
    shutil.copytree(source / 'frames' / state, RUN / 'frames' / state, dirs_exist_ok=True)
    data = json.loads((source / 'frames/frames-manifest.json').read_text(encoding='utf-8-sig'))
    row = data['rows'][0]
    row['frames'] = [str(p.resolve()) for p in sorted((RUN / 'frames' / state).glob('*.png'))]
    rows.append(row)
(RUN / 'frames/frames-manifest.json').write_text(json.dumps({'ok': True, 'chroma_key': data['chroma_key'], 'rows': rows}, indent=2), encoding='utf-8')
# Reuse the bundled registration functions to keep the same ground position
# between states. Preserve the actual airborne offset from stable jump extraction.
spec = importlib.util.spec_from_file_location('pet_registration', SKILL / 'scripts/assemble_extended_atlas.py')
reg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reg)
neutral = Image.open(RUN / 'frames/idle/00.png').convert('RGBA')
target = reg.cell_geometry(neutral)
registration = []
for state in STATES[1:]:
    files = sorted((RUN / 'frames' / state).glob('*.png'))
    cells = [Image.open(p).convert('RGBA') for p in files]
    geometry = reg.CellGeometry(max(reg.cell_geometry(c).height for c in cells), target.lower_center_x, target.bottom)
    scale = reg.normalization_scale(cells, geometry)
    ground = reg.cell_geometry(cells[0]).bottom
    for path, cell in zip(files, cells):
        offset = round((reg.cell_geometry(cell).bottom - ground) * scale) if state == 'jumping' else 0
        pose_target = reg.CellGeometry(geometry.height, geometry.lower_center_x, target.bottom + offset)
        reg.normalize_cell_to_geometry(cell, pose_target, scale).save(path)
    registration.append({'state': state, 'scale': scale, 'ground': target.bottom, 'preserve_jump_offset': state == 'jumping'})
(RUN / 'qa/standard-registration.json').write_text(json.dumps(registration, indent=2), encoding='utf-8')
jobs = [
    ('inspect_frames.py', '--frames-root', RUN / 'frames', '--json-out', RUN / 'qa/review.json', '--require-components', '--allow-stable-slots'),
    ('compose_atlas.py', '--frames-root', RUN / 'frames', '--output', RUN / 'final/spritesheet.png', '--webp-output', RUN / 'final/spritesheet.webp'),
    ('make_contact_sheet.py', RUN / 'final/spritesheet.webp', '--output', RUN / 'qa/contact-sheet.png'),
    ('render_animation_previews.py', '--frames-root', RUN / 'frames', '--output-dir', RUN / 'qa/previews'),
]
for script, *args in jobs:
    if call(script, *args):
        raise SystemExit(f'{script} failed')
