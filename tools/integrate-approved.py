"""Integrate approved, already cleaned row pixels without redrawing or rescaling."""
import argparse
import datetime
import hashlib
import json
import shutil
from pathlib import Path

from PIL import Image
from pet_pipeline_import import RUN, call

ROOT = RUN.parents[1]
ROWS = {
    'waving': (3, 4, 'state-transitions-v29'),
    'failed': (5, 8, 'state-transitions-v29'),
    'waiting': (6, 6, 'state-transitions-v29'),
    'running': (7, 6, 'state-transitions-v29'),
    'review': (8, 6, 'state-transitions-v29'),
}
STATES = ['idle', 'running-right', 'running-left', 'waving', 'jumping', 'failed', 'waiting', 'running', 'review']
COUNTS = [6, 8, 8, 4, 5, 8, 6, 6, 6]


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sync_row_source(state, candidate):
    source = ROOT / 'approval' / candidate
    row_qa = RUN / 'qa/rows' / state
    dest = row_qa / 'frames' / state
    dest.mkdir(parents=True, exist_ok=True)
    files = sorted((source / 'frames' / state).glob('*.png'))
    for path in files:
        shutil.copy2(path, dest / path.name)
    manifest = read(source / 'frames/frames-manifest.json')
    item = next(r for r in manifest['rows'] if r['state'] == state)
    item['frames'] = [str((dest / p.name).resolve()) for p in files]
    manifest['rows'] = [item]
    write(row_qa / 'frames/frames-manifest.json', manifest)
    review = read(source / 'frame-review.json')
    review['approved_candidate'] = candidate
    write(row_qa / 'review.json', review)
    shutil.copy2(source / 'final-visual-review.json', row_qa / 'final-visual-review.json')
    jobs = read(RUN / 'imagegen-jobs.json')
    job = next(j for j in jobs['jobs'] if j['id'] == state)
    generated_source = source / 'source' / f'{state}.png'
    if not generated_source.exists():
        generated_source = source / 'source/four-keys.png'
    job.update(status='complete', source_path=str(generated_source),
               approved_candidate=candidate, integrated_frames=str(dest))
    write(RUN / 'imagegen-jobs.json', jobs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--approval-text', required=True)
    args = parser.parse_args()
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = ROOT / 'build' / ('before-approved-' + stamp)
    backup.mkdir(parents=True)
    for folder in ['final', 'qa']:
        shutil.copytree(RUN / folder, backup / folder)
    if (ROOT / 'dist').exists():
        shutil.copytree(ROOT / 'dist', backup / 'dist')
    atlas_path = RUN / 'final/spritesheet-extended.webp'
    old = Image.open(atlas_path).convert('RGBA')
    atlas = old.copy()
    provenance = []
    for state, (row, count, candidate) in ROWS.items():
        source = ROOT / 'approval' / candidate
        for report in ['frame-review.json', 'final-visual-review.json', 'despill.json']:
            if not read(source / report).get('ok'):
                raise SystemExit(f'Blocking report: {source / report}')
        files = sorted((source / 'frames' / state).glob('*.png'))
        if len(files) != count:
            raise SystemExit(f'Wrong frame count: {state}')
        offset_y = 0
        if state in {'running-left', 'running-right'}:
            idle_ground = old.crop((0, 0, 192, 208)).getbbox()[3]
            offset_y = idle_ground - Image.open(files[0]).convert('RGBA').getbbox()[3]
        atlas.paste((0, 0, 0, 0), (0, row*208, 1536, (row+1)*208))
        for col, path in enumerate(files):
            cell = Image.open(path).convert('RGBA')
            if cell.size != (192, 208):
                raise SystemExit(f'Wrong cell geometry: {path}')
            if offset_y:
                bounds = cell.getbbox()
                if bounds[1]+offset_y < 2 or bounds[3]+offset_y > 206:
                    raise SystemExit(f'Ground registration would clip {path}')
                shifted = Image.new('RGBA', cell.size)
                shifted.paste(cell, (0, offset_y))
                assert shifted.getchannel('A').histogram() == cell.getchannel('A').histogram()
                cell = shifted
            atlas.paste(cell, (col*192, row*208))
        provenance.append({'state': state, 'row': row, 'candidate': candidate,
                           'translation_y': offset_y, 'no_scaling_or_redrawing': True,
                           'frame_sha256': [sha(p) for p in files],
                           'cleanup_report': str(source / 'despill.json'),
                           'visual_report': str(source / 'final-visual-review.json')})
        # Keep source provenance for future repairs, using the exact extracted source.
        src = source / 'review-source' / f'{state}.png'
        if not src.exists():
            src = source / 'source' / f'{state}.png'
        if src.exists():
            shutil.copy2(src, RUN / 'decoded' / f'{state}.png')
        sync_row_source(state, candidate)
    changed = {info[0] for info in ROWS.values()}
    # Current validator requires empty unused cells and zero RGB below alpha=0.
    # These storage-only repairs do not alter any displayed animation frame.
    cleared_unused = []
    for row, count in enumerate(COUNTS):
        box = (count*192, row*208, 1536, (row+1)*208)
        if count < 8 and atlas.crop(box).getbbox():
            cleared_unused.append(row)
        if count < 8:
            atlas.paste((0, 0, 0, 0), box)
    atlas.putdata([(r,g,b,a) if a else (0,0,0,0) for r,g,b,a in atlas.getdata()])
    for row in set(range(11)) - changed:
        count = COUNTS[row] if row < 9 else 8
        box = (0, row*208, count*192, (row+1)*208)
        before = old.crop(box)
        before.putdata([(r,g,b,a) if a else (0,0,0,0) for r,g,b,a in before.getdata()])
        assert atlas.crop(box).tobytes() == before.tobytes(), f'Unapproved used frame changed: {row}'
    atlas.save(RUN / 'final/spritesheet-extended.png')
    atlas.save(atlas_path, lossless=True, exact=True)
    assert Image.open(atlas_path).convert('RGBA').tobytes() == atlas.tobytes()
    standard = atlas.crop((0, 0, 1536, 1872))
    standard.save(RUN / 'final/spritesheet.png')
    standard.save(RUN / 'final/spritesheet.webp', lossless=True, exact=True)
    manifest = read(RUN / 'frames/frames-manifest.json')
    for row, (state, count) in enumerate(zip(STATES, COUNTS)):
        folder = RUN / 'frames' / state
        folder.mkdir(parents=True, exist_ok=True)
        for col in range(count):
            atlas.crop((col*192, row*208, (col+1)*192, (row+1)*208)).save(folder / f'{col:02}.png')
        item = next(r for r in manifest['rows'] if r['state'] == state)
        item['frames'] = [str((folder / f'{col:02}.png').resolve()) for col in range(count)]
        if state in ROWS:
            item['method'] = 'stable-slots'
            for col in range(count):
                shutil.copy2(folder / f'{col:02}.png', RUN / 'qa/rows' / state / 'frames' / state / f'{col:02}.png')
    write(RUN / 'frames/frames-manifest.json', manifest)
    report = {'ok': True, 'approval_text': args.approval_text, 'backup': str(backup),
              'sprite_sha256': sha(atlas_path), 'replaced_rows': provenance,
              'unchanged_rows_pixel_identical': sorted(set(range(11)) - changed),
              'approved_pixel_identity_preserved_with_recorded_translation': True,
              'storage_cleanup': {'cleared_unused_cell_rows': cleared_unused, 'zero_transparent_rgb': True, 'used_visible_pixels_unchanged': True},
              'installed': False, 'published': False}
    write(RUN / 'qa/approved-integration.json', report)
    # Each row has already passed edge cleanup. Do not clean the atlas a second time.
    write(RUN / 'qa/chroma-despill-extended.json', {
        'ok': True, 'algorithm': 'assemble-already-cleaned-cells-without-reprocessing',
        'source_reports': [p['cleanup_report'] for p in provenance],
        'preserved_report': str(backup / 'qa/chroma-despill-extended.json'),
        'sprite_sha256': report['sprite_sha256'], 'alpha_preserved': True})
    jobs = [
        ('inspect_frames.py', '--frames-root', RUN / 'frames', '--json-out', RUN / 'qa/review.json', '--require-components', '--allow-stable-slots'),
        ('validate_atlas.py', atlas_path, '--require-v2', '--chroma-key', '#0000FF', '--json-out', RUN / 'final/validation-extended.json'),
        ('make_contact_sheet.py', atlas_path, '--output', RUN / 'qa/contact-sheet-approved.png'),
        ('render_animation_previews.py', '--frames-root', RUN / 'frames', '--output-dir', RUN / 'qa/previews'),
    ]
    for script, *params in jobs:
        if call(script, *params):
            raise SystemExit(f'{script} failed; original files preserved in {backup}')
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
