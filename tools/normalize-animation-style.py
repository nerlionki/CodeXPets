"""Calibrate existing sprites to idle without changing frame registration or timing."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'animation/pet-run'
OUT = ROOT / 'approval/idle-style-unified-v19'
STATES = ['idle', 'running-right', 'running-left', 'waving', 'jumping', 'failed', 'waiting', 'running', 'review', 'look-row-9', 'look-row-10']
COUNTS = [6, 8, 8, 4, 5, 8, 6, 6, 6, 8, 8]


def skeleton(mask):
    a = np.pad(mask, 1).astype(np.uint8)
    for _ in range(40):
        changed = False
        for phase in range(2):
            p = [a[:-2, 1:-1], a[:-2, 2:], a[1:-1, 2:], a[2:, 2:], a[2:, 1:-1], a[2:, :-2], a[1:-1, :-2], a[:-2, :-2]]
            n = sum(p)
            t = sum((p[i] == 0) & (p[(i + 1) % 8] == 1) for i in range(8))
            if phase == 0:
                c = (p[0]*p[2]*p[4] == 0) & (p[2]*p[4]*p[6] == 0)
            else:
                c = (p[0]*p[2]*p[6] == 0) & (p[0]*p[4]*p[6] == 0)
            remove = (a[1:-1, 1:-1] == 1) & (n >= 2) & (n <= 6) & (t == 1) & c
            changed |= bool(remove.any())
            a[1:-1, 1:-1][remove] = 0
        if not changed:
            break
    return a[1:-1, 1:-1].astype(bool)


def palette(a):
    rgb = a[:, :, :3].astype(float)
    r, g, b = rgb.transpose(2, 0, 1)
    opaque = a[:, :, 3] > 245
    masks = [opaque & (r < 55) & (g < 55) & (b < 55),
             opaque & (r > 180) & (g > 140) & (g-b > 25) & (r-g < 75),
             opaque & (rgb.min(2) > 210) & (rgb.max(2)-rgb.min(2) < 20),
             opaque & (r > 170) & (r-g > 65) & (r-b > 50)]
    colors = [np.median(rgb[m], axis=0) for m in masks[:3]]
    red = rgb[masks[3]]
    centers = np.array([red[np.argmin(red[:, 1])], red[np.argmax(red[:, 1])]])
    for _ in range(12):
        labels = ((red[:, None, :]-centers[None, :, :])**2).sum(2).argmin(1)
        centers = np.array([np.median(red[labels == i], axis=0) if (labels == i).any() else centers[i] for i in range(2)])
    colors.extend(centers[np.argsort(centers[:, 1])])
    return np.array(colors)


def width(a):
    mask = (a[:, :, :3].max(2) < 100) & (a[:, :, 3] > 128)
    sk = skeleton(mask)
    return float(mask.sum()/max(1, sk.sum()))


def small_feature_mask(a):
    """Keep tiny eye dots, noses and mouth marks at their approved dimensions."""
    dark = (a[:, :, :3].max(2) < 110) & (a[:, :, 3] > 160)
    seen = np.zeros(dark.shape, dtype=bool)
    protect = np.zeros(dark.shape, dtype=bool)
    height, width_ = dark.shape
    for y, x in zip(*np.where(dark)):
        if seen[y, x]:
            continue
        points, pending = [], [(int(y), int(x))]
        seen[y, x] = True
        while pending:
            cy, cx = pending.pop()
            points.append((cy, cx))
            for dy in [-1, 0, 1]:
                for dx in [-1, 0, 1]:
                    ny, nx = cy+dy, cx+dx
                    if 0 <= ny < height and 0 <= nx < width_ and dark[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        pending.append((ny, nx))
        if len(points) <= 90:
            ys, xs = zip(*points)
            protect[max(0, min(ys)-1):max(ys)+2, max(0, min(xs)-1):max(xs)+2] = True
    return protect


def normalize(a, source, target, reference_width):
    rgb = a[:, :, :3].astype(float)
    vectors = source[1:] - source[0]
    relative = rgb - source[0]
    t = np.clip(np.einsum('hwc,kc->hwk', relative, vectors) / (vectors*vectors).sum(1), 0, 1)
    projection = source[0] + t[:, :, :, None]*vectors
    error = ((rgb[:, :, None, :]-projection)**2).sum(3)
    labels = error.argmin(2)
    fill = np.take_along_axis(t, labels[:, :, None], axis=2)[:, :, 0]
    # Preserve the original antialias coverage and silhouette; adjust only the ink
    # inside it. A bounded fractional one-pixel dilation/erosion calibrates weight.
    ink = 1-fill
    ink[a[:, :, 3] == 0] = 0
    before_width = width(a)
    delta = float(np.clip((reference_width-before_width)/2, -.45, .85))
    layer = Image.fromarray(np.uint8(np.rint(ink*255)))
    filtered = np.array(layer.filter(ImageFilter.MaxFilter(3) if delta > 0 else ImageFilter.MinFilter(3)), dtype=float)/255
    adjusted = ink*(1-abs(delta)) + filtered*abs(delta)
    # Avoid turning barely visible edge pixels into a dark halo.
    adjusted[a[:, :, 3] < 180] = ink[a[:, :, 3] < 180]
    protect = small_feature_mask(a)
    adjusted[protect] = ink[protect]
    corrected = target[0] + (1-adjusted[:, :, None])*(target[1:][labels]-target[0])
    result = a.copy()
    result[:, :, :3] = np.uint8(np.clip(np.rint(corrected), 0, 255))
    result[a[:, :, 3] == 0, :3] = 0
    return result, {'line_width_before': before_width, 'line_width_after': width(result), 'fractional_ink_adjustment': delta, 'small_facial_features_protected': True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    baseline = OUT / 'baseline.webp'
    source = baseline if baseline.exists() else RUN / 'final/spritesheet-extended.webp'
    old = Image.open(source).convert('RGBA')
    rows = [np.array(old.crop((0, i*208, 1536, (i+1)*208))) for i in range(11)]
    target = palette(rows[0])
    ref_width = width(rows[0])
    if not args.apply:
        print(json.dumps({'idle_palette': target.tolist(), 'rows': [{'state': s, 'palette': palette(a).tolist(), 'width': width(a)} for s,a in zip(STATES, rows)]}, indent=2))
        return
    OUT.mkdir(parents=True, exist_ok=True)
    if not baseline.exists():
        baseline.write_bytes(source.read_bytes())
    atlas = old.copy()
    reports = []
    for row, (state, count, original) in enumerate(zip(STATES, COUNTS, rows)):
        if row == 0:
            adjusted = original.copy()
            record = {'unchanged': True}
        elif row == 2:
            # Apply once to the right walk, then retain the exact original mirror.
            adjusted = np.zeros_like(original)
            for col in range(8):
                adjusted[:, col*192:(col+1)*192] = np.array(atlas.crop((col*192, 208, (col+1)*192, 416)))[:, ::-1]
            record = {'exact_mirror_of_right': True}
        else:
            adjusted, record = normalize(original, palette(original), target, ref_width)
        assert np.array_equal(original[:, :, 3], adjusted[:, :, 3]), state
        atlas.paste(Image.fromarray(adjusted), (0, row*208))
        frame_dir = OUT / 'frames' / state
        frame_dir.mkdir(parents=True, exist_ok=True)
        for col in range(count):
            cell = atlas.crop((col*192, row*208, (col+1)*192, (row+1)*208))
            cell.save(frame_dir / f'{col:02}.png')
        reports.append({'state': state, 'palette_before': palette(original).tolist(), **record})
    assert atlas.crop((0, 0, 1536, 208)).tobytes() == old.crop((0, 0, 1536, 208)).tobytes()
    atlas.save(OUT / 'spritesheet-extended.png')
    atlas.save(OUT / 'spritesheet-extended.webp', lossless=True, exact=True)
    # Reuse native playback timing rather than creating new animation phases.
    from pet_pipeline_import import SKILL
    spec = importlib.util.spec_from_file_location('style_previews', SKILL / 'scripts/render_animation_previews.py')
    preview = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(preview)
    for state, durations in preview.ROW_DURATIONS.items():
        cells = [Image.open(OUT / 'frames' / state / f'{i:02}.png').convert('RGBA') for i in range(len(durations))]
        preview.save_preview(cells, durations, OUT / 'previews' / f'{state}.gif')
    sheet = Image.new('RGB', (6*192, 11*208), '#dedee3')
    for row, count in enumerate(COUNTS):
        for side, im in enumerate([old, atlas]):
            for sample, col in enumerate([0, min(2, count-1), count-1]):
                cell = im.crop((col*192, row*208, (col+1)*192, (row+1)*208))
                sheet.paste(cell, ((side*3+sample)*192, row*208), cell)
    sheet.save(OUT / 'before-after.png')
    report = {'ok': True, 'method': 'user-authorized Python palette and fractional ink calibration', 'baseline_sha256': hashlib.sha256(baseline.read_bytes()).hexdigest(), 'sprite_sha256': hashlib.sha256((OUT / 'spritesheet-extended.webp').read_bytes()).hexdigest(), 'idle_pixel_identical': True, 'all_alpha_pixel_identical': True, 'frame_counts': COUNTS, 'idle_palette': target.tolist(), 'idle_line_width': ref_width, 'rows': reports, 'installed': False, 'published': False}
    (OUT / 'style-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
