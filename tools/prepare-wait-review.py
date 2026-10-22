"""Prepare only waiting/review approval GIFs; never mutate the active atlas."""
import hashlib
import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from pet_pipeline_import import RUN, SKILL, call

ROOT = RUN.parents[1]
OUT = ROOT / 'approval/anthro-wait-review-v20'
STATES = ['waiting', 'review']


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    global OUT, STATES
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=OUT)
    parser.add_argument('--states', default=','.join(STATES))
    parser.add_argument('--preserve-face-ink', action='store_true', help='Keep generated jumping facial marks delicate during outline calibration')
    args = parser.parse_args()
    OUT = args.output.resolve()
    STATES = args.states.split(',')
    status = json.loads((OUT / 'status.json').read_text(encoding='utf-8'))
    current = RUN / 'final/spritesheet-extended.webp'
    assert hashlib.sha256(current.read_bytes()).hexdigest() == status['baseline_atlas_sha256']
    decoded = OUT / 'decoded-transparent'
    decoded.mkdir(exist_ok=True)
    for state in STATES:
        # Unmix the known blue background before downsampling. The generic
        # post-resize despill can mistake blue-mixed black strokes for white fur.
        source = np.array(Image.open(OUT / 'source' / f'{state}.png').convert('RGBA'), dtype=float)
        rgb = source[:, :, :3]
        excess = np.maximum(0, rgb[:, :, 2]-rgb[:, :, :2].max(2))
        alpha = np.clip(1-excess/255, 0, 1)
        key = (rgb[:, :, 0] < 80) & (rgb[:, :, 1] < 160) & (rgb[:, :, 2] > 180) & (excess > 60)
        alpha[key | (alpha < .025)] = 0
        safe_alpha = np.maximum(alpha, .001)
        foreground = rgb.copy()
        foreground[:, :, 2] -= (1-alpha)*255
        foreground /= safe_alpha[:, :, None]
        rgba = np.concatenate([np.clip(foreground, 0, 255), (alpha*source[:, :, 3])[:, :, None]], axis=2)
        rgba[alpha == 0] = 0
        Image.fromarray(np.uint8(np.rint(rgba))).save(decoded / f'{state}.png')
    subprocess.run([sys.executable, str(ROOT / 'tools/preview-anthro.py'), '--output', str(OUT), '--states', ','.join(STATES), '--source-dir', 'decoded-transparent', '--reference-cell', str(OUT / 'references/idle.png'), '--match-reference-height', '--safe-margin', '4'], check=True)
    calibration = load('wait_review_style', ROOT / 'tools/normalize-animation-style.py')
    preview = load('wait_review_preview', SKILL / 'scripts/render_animation_previews.py')
    reference = np.array(Image.open(OUT / 'references/idle.png').convert('RGBA'))
    target_palette = calibration.palette(reference)
    reference_width = calibration.width(reference)
    records = []
    atlas = Image.new('RGBA', (1536, 416))
    for row, state in enumerate(STATES):
        files = sorted((OUT / 'frames' / state).glob('*.png'))
        count = len(preview.ROW_DURATIONS[state])
        assert len(files) == count
        frames = [Image.open(f).convert('RGBA') for f in files]
        strip = Image.new('RGBA', (count*192, 208))
        for col, frame in enumerate(frames):
            strip.paste(frame, (col*192, 0))
        before = np.array(strip)
        after, measurement = calibration.normalize(before, calibration.palette(before), target_palette, reference_width)
        if args.preserve_face_ink:
            assert state == 'jumping' and count == 5
            # Preserve generated eye, nose and smile weights while calibrating
            # the body outline; no feature is relocated or drawn in this step.
            delicate, _ = calibration.normalize(before, calibration.palette(before), target_palette, calibration.width(before))
            face_boxes = [
                [(48, 99, 97, 140), (110, 112, 158, 151)],
                [(40, 74, 89, 111), (117, 89, 163, 128)],
                [(39, 60, 85, 100), (117, 78, 163, 118)],
                [(40, 74, 89, 111), (117, 89, 163, 128)],
                [(48, 99, 97, 140), (110, 112, 158, 151)],
            ]
            interior = np.array(Image.fromarray(before[:, :, 3]).filter(ImageFilter.MinFilter(7))) > 240
            for col, boxes in enumerate(face_boxes):
                for x0,y0,x1,y1 in boxes:
                    local = interior[y0:y1, col*192+x0:col*192+x1]
                    region = after[y0:y1, col*192+x0:col*192+x1]
                    region[local] = delicate[y0:y1, col*192+x0:col*192+x1][local]
            measurement['facial_marks_not_thickened'] = True
        assert np.array_equal(before[:, :, 3], after[:, :, 3])
        strip = Image.fromarray(after)
        frames = [strip.crop((col*192, 0, (col+1)*192, 208)) for col in range(count)]
        for path, frame in zip(files, frames):
            frame.save(path)
        atlas.paste(strip, (0, row*208))
        preview.save_preview(frames, preview.ROW_DURATIONS[state], OUT / f'{state}.gif')
        preview.save_preview([f.resize((384, 416), Image.Resampling.NEAREST) for f in frames], preview.ROW_DURATIONS[state], OUT / f'{state}-2x.gif')
        with Image.open(OUT / f'{state}.gif') as gif:
            assert gif.n_frames == count and gif.info['loop'] == 0
            durations = []
            for i in range(count):
                gif.seek(i)
                durations.append(gif.info['duration'])
            assert durations == preview.ROW_DURATIONS[state]
        records.append({'state': state, 'frames': count, 'durations_ms': durations, 'bounds': [f.getbbox() for f in frames], 'style': measurement})
    atlas.save(OUT / 'approval-atlas.png')
    sheet = Image.new('RGB', (1536, 476), '#f4efe9')
    draw = ImageDraw.Draw(sheet)
    for row, state in enumerate(STATES):
        draw.text((8, row*238+5), state, fill='#222222')
        strip = atlas.crop((0, row*208, 1536, (row+1)*208))
        sheet.paste(strip, (0, row*238+26), strip)
    sheet.save(OUT / 'contact-sheet.png')
    if call('inspect_frames.py', '--frames-root', OUT / 'frames', '--states', ','.join(STATES), '--json-out', OUT / 'frame-review.json', '--allow-stable-slots'):
        raise SystemExit('Frame validation failed')
    assert hashlib.sha256(current.read_bytes()).hexdigest() == status['baseline_atlas_sha256']
    status.update(status='awaiting_user_approval', states=records, integrated=False, packaged=False, installed=False, cloud_updated=False, active_atlas_unchanged=True)
    (OUT / 'status.json').write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(status, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
