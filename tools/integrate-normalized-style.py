"""Integrate the verified idle-calibrated atlas and refresh local deliverables."""
import hashlib
import json
import shutil
from pathlib import Path
from PIL import Image
from pet_pipeline_import import RUN, call

ROOT = RUN.parents[1]
OUT = ROOT / 'approval/idle-style-unified-v19'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    report = read(OUT / 'style-report.json')
    assert report['ok'] and report['idle_pixel_identical'] and report['all_alpha_pixel_identical']
    source = OUT / 'spritesheet-extended.webp'
    assert hashlib.sha256(source.read_bytes()).hexdigest() == report['sprite_sha256']
    current = RUN / 'final/spritesheet-extended.webp'
    assert hashlib.sha256(current.read_bytes()).hexdigest() in {report['baseline_sha256'], report['sprite_sha256']}
    atlas = Image.open(source).convert('RGBA')
    old = Image.open(OUT / 'baseline.webp').convert('RGBA')
    assert atlas.size == old.size == (1536, 2288)
    assert atlas.getchannel('A').tobytes() == old.getchannel('A').tobytes()
    assert atlas.crop((0, 0, 1536, 208)).tobytes() == old.crop((0, 0, 1536, 208)).tobytes()
    for col in range(8):
        assert atlas.crop((col*192, 416, (col+1)*192, 624)).tobytes() == atlas.crop((col*192, 208, (col+1)*192, 416)).transpose(Image.Transpose.FLIP_LEFT_RIGHT).tobytes()
    if call('validate_atlas.py', source, '--require-v2', '--chroma-key', '#0000FF', '--json-out', OUT / 'validation.json'):
        raise SystemExit('Atlas validation failed')
    previous = RUN / 'qa/final-visual-review.json'
    if not (OUT / 'baseline-visual-review.json').exists():
        shutil.copy2(previous, OUT / 'baseline-visual-review.json')
    for suffix in ['png', 'webp']:
        shutil.copy2(OUT / f'spritesheet-extended.{suffix}', RUN / f'final/spritesheet-extended.{suffix}')
        atlas.crop((0, 0, 1536, 1872)).save(RUN / f'final/spritesheet.{suffix}', **({'lossless': True, 'exact': True} if suffix == 'webp' else {}))
    manifest = read(RUN / 'frames/frames-manifest.json')
    for item in manifest['rows']:
        state = item['state']
        for cell in (OUT / 'frames' / state).glob('*.png'):
            shutil.copy2(cell, RUN / 'frames' / state / cell.name)
            row_path = RUN / 'qa/rows' / state / 'frames' / state / cell.name
            if row_path.parent.exists():
                shutil.copy2(cell, row_path)
        item['style_calibration'] = 'approval/idle-style-unified-v19/style-report.json'
    write(RUN / 'frames/frames-manifest.json', manifest)
    shutil.copy2(OUT / 'validation.json', RUN / 'final/validation-extended.json')
    shutil.copytree(OUT / 'previews', RUN / 'qa/previews', dirs_exist_ok=True)
    if call('inspect_frames.py', '--frames-root', RUN / 'frames', '--json-out', RUN / 'qa/review.json', '--require-components', '--allow-stable-slots'):
        raise SystemExit('Frame validation failed')
    if call('make_contact_sheet.py', current, '--output', RUN / 'qa/contact-sheet-approved.png'):
        raise SystemExit('Contact sheet failed')
    visual = {'ok': True, 'reviewer': 'primary agent static frame comparison and pixel invariants', 'sprite_sha256': report['sprite_sha256'], 'candidate': 'idle-style-unified-v19', 'idle_unchanged': True, 'all_alpha_pixel_identical': True, 'walking_exact_mirror': True, 'review_evidence': str(OUT / 'before-after.png'), 'dynamic_playback_observed': False, 'scope': 'Idle palette and fractional line-weight calibration; tiny detached facial features protected; frame layout, poses and timing retained.', 'limitations': ['Line weights are calibrated by raster measurements; original hand-drawn local variation remains.'], 'installed': False, 'published': False}
    write(previous, visual)
    write(RUN / 'qa/chroma-despill-extended.json', {'ok': True, 'sprite_sha256': report['sprite_sha256'], 'method': 'existing transparent alpha retained pixel-for-pixel; palette calibrated without further chroma keying'})
    status = read(ROOT / 'approval/status.json')
    status['status'] = 'idle_style_unified_local_package'
    status['installed'] = False
    status['packaged'] = False
    status.pop('other_candidate', None)
    status['style_revision'] = {**visual, 'report': 'approval/idle-style-unified-v19/style-report.json'}
    status['cloud_pet']['synchronized'] = False
    status['cloud_pet']['verified_pixel_identical'] = False
    status['packaged_revision']['installed_in_real_codex'] = False
    status['packaged_revision']['spritesheet_sha256'] = report['sprite_sha256']
    status['cleanup_report'] = 'approval/cleanup-20261021.json'
    write(ROOT / 'approval/status.json', status)
    print('Integrated: ' + report['sprite_sha256'])


if __name__ == '__main__':
    main()
