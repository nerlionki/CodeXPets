"""Restore delicate nose ink from existing approved art in ten local regions."""
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from pet_pipeline_import import RUN, SKILL, call

ROOT = RUN.parents[1]
OUT = ROOT / 'approval/jumping-nose-v22'
# Golden nose and white nose, in native-cell coordinates; eyes are outside.
NOSES = [
    [(68, 113, 79, 124), (125, 124, 137, 134)],
    [(62, 87, 74, 97), (132, 101, 144, 111)],
    [(56, 73, 68, 84), (133, 91, 145, 101)],
    [(61, 87, 73, 97), (132, 101, 144, 111)],
    [(68, 114, 79, 125), (125, 124, 137, 134)],
]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    OUT.mkdir(exist_ok=True)
    source = RUN / 'final/spritesheet-extended.webp'
    atlas = Image.open(source).convert('RGBA')
    baseline_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    style = load('nose_style', ROOT / 'tools/normalize-animation-style.py')
    preview = load('nose_preview', SKILL / 'scripts/render_animation_previews.py')
    old_strip = Image.new('RGBA', (960, 208))
    originals = []
    for col in range(5):
        original = Image.open(ROOT / 'approval/hover-tu-v12/frames/jumping' / f'{col:02}.png').convert('RGBA')
        originals.append(original)
        old_strip.paste(original, (col*192, 0))
    original_palette = style.palette(np.array(old_strip))
    target_palette = style.palette(np.array(atlas.crop((0, 0, 1152, 208))))
    frame_dir = OUT / 'frames/jumping'
    frame_dir.mkdir(parents=True, exist_ok=True)
    before, after, details = [], [], []
    for col, original in enumerate(originals):
        cell = atlas.crop((col*192, 832, (col+1)*192, 1040))
        a = np.array(cell)
        original_pixels = np.array(original)
        assert np.array_equal(a[:, :, 3], original_pixels[:, :, 3])
        result = a.copy()
        allowed = np.zeros((208, 192), dtype=bool)
        for character, (x0, y0, x1, y1) in enumerate(NOSES[col]):
            source_fill = original_palette[character+1]
            target_fill = target_palette[character+1]
            rgb = original_pixels[y0:y1, x0:x1, :3].astype(float)
            vector = source_fill-original_palette[0]
            fill = np.clip(((rgb-original_palette[0])*vector).sum(2)/(vector*vector).sum(), 0, 1)
            corrected = target_palette[0] + fill[:, :, None]*(target_fill-target_palette[0])
            result[y0:y1, x0:x1, :3] = np.uint8(np.rint(np.clip(corrected, 0, 255)))
            allowed[y0:y1, x0:x1] = True
        changed = (result != a).any(2)
        assert not (changed & ~allowed).any()
        assert np.array_equal(result[:, :, 3], a[:, :, 3])
        updated = Image.fromarray(result)
        assert updated.getbbox() == cell.getbbox()
        updated.save(frame_dir / f'{col:02}.png')
        before.append(cell)
        after.append(updated)
        details.append({'frame': col, 'nose_regions': NOSES[col], 'changed_pixels': int(changed.sum()), 'black_core_before': int(((a[:, :, :3].max(2)<100)&allowed).sum()), 'black_core_after': int(((result[:, :, :3].max(2)<100)&allowed).sum())})
    durations = preview.ROW_DURATIONS['jumping']
    preview.save_preview(after, durations, OUT / 'jumping.gif')
    preview.save_preview([c.resize((384, 416), Image.Resampling.NEAREST) for c in after], durations, OUT / 'jumping-2x.gif')
    comparison = []
    for a,b in zip(before, after):
        sheet = Image.new('RGBA', (384, 208))
        sheet.paste(a, (0, 0))
        sheet.paste(b, (192, 0))
        comparison.append(sheet.resize((768, 416), Image.Resampling.NEAREST))
    preview.save_preview(comparison, durations, OUT / 'comparison-2x.gif')
    sheet = Image.new('RGB', (960, 446), '#f4efe9')
    draw = ImageDraw.Draw(sheet)
    for row, (label, frames) in enumerate([('before', before), ('after - nose only', after)]):
        draw.text((8, row*223+4), label, fill='#222222')
        for col, cell in enumerate(frames):
            sheet.paste(cell, (col*192, row*223+15), cell)
    sheet.save(OUT / 'contact-sheet.png')
    manifest = {'ok': True, 'rows': [{'state': 'jumping', 'method': 'stable-slots', 'frames': [str(frame_dir / f'{i:02}.png') for i in range(5)]}]}
    (OUT / 'frames/frames-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    if call('inspect_frames.py', '--frames-root', OUT / 'frames', '--states', 'jumping', '--json-out', OUT / 'frame-review.json', '--allow-stable-slots'):
        raise SystemExit('Frame checks failed')
    assert hashlib.sha256(source.read_bytes()).hexdigest() == baseline_hash
    report = {'status': 'awaiting_user_approval', 'source_atlas_sha256': baseline_hash, 'state': 'jumping', 'method': 'Restore original approved pre-thickening nasal ink, remap to current idle colors in ten bounded regions only', 'scale': 1, 'geometry_alpha_and_all_other_pixels_unchanged': True, 'details': details, 'timing_ms': durations, 'integrated': False, 'packaged': False, 'installed': False, 'cloud_updated': False}
    (OUT / 'status.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
