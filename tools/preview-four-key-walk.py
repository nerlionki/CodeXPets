"""Extract one generated four-pose family and sample whole cells for approval."""
import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image
from pet_pipeline_import import SKILL, call

ROOT = Path(__file__).resolve().parents[1]


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, SKILL / 'scripts' / filename)
    obj = importlib.util.module_from_spec(spec)
    sys.modules[name] = obj
    spec.loader.exec_module(obj)
    return obj


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    source = ROOT / args.source
    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)
    extraction = module('four_key_extraction', 'extract_strip_frames.py')
    registration = module('four_key_registration', 'assemble_extended_atlas.py')
    strip = extraction.remove_chroma_background(Image.open(source), (0, 0, 255), 96)
    groups = extraction.component_frame_groups(strip, 4)
    if groups is None:
        raise SystemExit('Four separate pose groups required')
    cells = extraction.extract_stable_slot_frames(strip, 4)
    reference = Image.open(ROOT / 'approval/eye-size-v2/references/idle-cell.png').convert('RGBA')
    target = registration.cell_geometry(reference)
    width = reference.getbbox()[2] - reference.getbbox()[0]
    # Lower-body registration can shift the visible bbox off the cell center.
    # Reserve extra horizontal room before normalization so no outline clips.
    scale = min(1.0, min(width, 164) / max(c.getbbox()[2] - c.getbbox()[0] for c in cells))
    ground = registration.cell_geometry(cells[0]).bottom
    scale = min(scale, (target.bottom - 8) / (ground - min(c.getbbox()[1] for c in cells)))
    excess = max(c.getbbox()[3] for c in cells) - ground
    if excess > 0:
        scale = min(scale, (200 - target.bottom) / excess)
    raw = Image.new('RGBA', (1536, 208))
    for index, cell in enumerate(cells):
        offset = round((registration.cell_geometry(cell).bottom - ground) * scale)
        geometry = registration.CellGeometry(target.height, target.lower_center_x, target.bottom + offset)
        raw.alpha_composite(registration.normalize_cell_to_geometry(cell, geometry, scale), (index * 192, 0))
    raw_path = out / 'four-keys-raw.png'
    raw.save(raw_path)
    digest = hashlib.sha256(raw_path.read_bytes()).hexdigest()
    cache = out / 'cleanup-input.sha256'
    if not cache.exists() or cache.read_text().strip() != digest:
        if call('despill_chroma_edges.py', raw_path, '--output', out / 'four-keys-clean.png',
                '--chroma-key', '#0000FF', '--json-out', out / 'despill.json'):
            raise SystemExit('Cleanup failed')
        cache.write_text(digest + '\n', encoding='ascii')
    clean = Image.open(out / 'four-keys-clean.png').convert('RGBA')
    keys = [clean.crop((i*192, 0, (i+1)*192, 208)) for i in range(4)]
    key_dir = out / 'keys'
    key_dir.mkdir(exist_ok=True)
    for i, key in enumerate(keys):
        key.save(key_dir / f'{i:02}.png')
    order = [1, 2, 3, 0, 1, 2, 3, 0]
    folder = out / 'frames/running-right'
    folder.mkdir(parents=True, exist_ok=True)
    for i, key in enumerate(order):
        keys[key].save(folder / f'{i:02}.png')
    manifest = {'ok': True, 'chroma_key': {'hex': '#0000FF', 'rgb': [0,0,255], 'threshold': 96},
                'rows': [{'state': 'running-right', 'method': 'stable-slots',
                          'frames': [str((folder/f'{i:02}.png').resolve()) for i in range(8)]}]}
    (out / 'frames/frames-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    report = {'single_generated_family': str(source), 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'source_key_order': order, 'timing_ms': [120]*7+[220], 'whole_frames_only': True,
              'scale': scale, 'ground': target.bottom, 'pixels_redrawn': False,
              'component_bounds': [extraction.component_bounds(g) for g in groups]}
    (out / 'temporal-assembly.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    subprocess.run([sys.executable, str(ROOT/'tools/preview-mirrored-left.py'), '--output', str(out.relative_to(ROOT)),
                    '--source-frames', str(folder.relative_to(ROOT))], check=True)
    for suffix in ['', '-2x']:
        shutil.copy2(out/f'running-right-reference{suffix}.gif', out/f'running-right{suffix}.gif')
    print('Four-key family sampled into mirrored native-timing approval media')


if __name__ == '__main__':
    main()
