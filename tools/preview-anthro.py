"""Prepare approval media from generated strips; do not edit released assets."""
import importlib.util
import hashlib
import json
import argparse
from pathlib import Path
from PIL import Image, ImageDraw
from pet_pipeline_import import SKILL, call

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'approval/anthro-v1'
STATES = ['running-right', 'running-left', 'jumping']

def module(name, script):
    spec = importlib.util.spec_from_file_location(name, SKILL / 'scripts' / script)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

def main():
    global OUT, STATES
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='approval/anthro-v1')
    parser.add_argument('--states', default=','.join(STATES))
    parser.add_argument('--source-dir', default='source')
    parser.add_argument('--reference-cell', help='Register preview width and ground against an approved native cell')
    parser.add_argument('--safe-margin', type=int, default=0, help='Uniformly fit registered rows inside this vertical margin')
    parser.add_argument('--match-reference-height', action='store_true', help='Match the first effect-free body pose to reference height, retaining one shared scale')
    args = parser.parse_args()
    OUT = ROOT / args.output
    STATES = args.states.split(',')
    source_dir = OUT / args.source_dir
    for state in STATES:
        if not (source_dir / f'{state}.png').is_file():
            raise SystemExit(f'Missing generated source: {state}')
    if call('extract_strip_frames.py', '--decoded-dir', source_dir, '--output-dir', OUT / 'raw-frames',
            '--states', ','.join(STATES), '--method', 'stable-slots', '--chroma-key', '#0000FF'):
        raise SystemExit('Extraction failed')
    frame_root = OUT / 'raw-frames'
    if args.reference_cell:
        reg = module('preview_registration', 'assemble_extended_atlas.py')
        reference = Image.open(ROOT / args.reference_cell).convert('RGBA')
        target = reg.cell_geometry(reference)
        reference_width = reference.getbbox()[2] - reference.getbbox()[0]
        registrations = []
        for state in STATES:
            files = sorted((frame_root / state).glob('*.png'))
            cells = [Image.open(p).convert('RGBA') for p in files]
            scale = min(1.0, reference_width / max(c.getbbox()[2]-c.getbbox()[0] for c in cells))
            if args.match_reference_height:
                first_box = cells[0].getbbox()
                reference_box = reference.getbbox()
                scale = min(reference_width / max(c.getbbox()[2]-c.getbbox()[0] for c in cells),
                            (reference_box[3]-reference_box[1]) / (first_box[3]-first_box[1]))
            ground = reg.cell_geometry(cells[0]).bottom
            if args.safe_margin:
                if not 0 < args.safe_margin < min(target.bottom, 208-target.bottom):
                    raise SystemExit('Safe margin must fit around the reference ground')
                # Fit the complete row, including rising effects, with one shared
                # scale. Preserve relative motion and never clip generated art.
                row_top = min(c.getbbox()[1] for c in cells)
                scale = min(scale, (target.bottom-args.safe_margin)/(ground-row_top))
                row_bottom = max(c.getbbox()[3] for c in cells)
                if row_bottom > ground:
                    scale = min(scale, (208-args.safe_margin-target.bottom)/(row_bottom-ground))
            dest = OUT / 'registered-frames' / state
            dest.mkdir(parents=True, exist_ok=True)
            for path, cell in zip(files, cells):
                offset = round((reg.cell_geometry(cell).bottom-ground)*scale)
                geometry = reg.CellGeometry(target.height, target.lower_center_x, target.bottom+offset)
                reg.normalize_cell_to_geometry(cell, geometry, scale).save(dest/path.name)
            registrations.append({'state':state,'scale':scale,'ground':target.bottom,'preserve_vertical_motion':True,'safe_margin':args.safe_margin,'match_reference_height':args.match_reference_height})
        (OUT/'preview-registration.json').write_text(json.dumps(registrations,indent=2),encoding='utf-8')
        frame_root = OUT / 'registered-frames'
    # Copy generated pixels into a diagnostic atlas. No local character drawing.
    raw = Image.new('RGBA', (1536, len(STATES)*208), (0,0,0,0))
    for row, state in enumerate(STATES):
        for column, path in enumerate(sorted((frame_root / state).glob('*.png'))):
            raw.alpha_composite(Image.open(path).convert('RGBA'), (column*192,row*208))
    raw.save(OUT / 'approval-atlas-raw.png')
    raw_hash = hashlib.sha256((OUT / 'approval-atlas-raw.png').read_bytes()).hexdigest()
    hash_path = OUT / 'cleanup-input.sha256'
    cached_hash = hash_path.read_text().strip() if hash_path.exists() else None
    if cached_hash != raw_hash:
        if call('despill_chroma_edges.py', OUT / 'approval-atlas-raw.png', '--output', OUT / 'approval-atlas.png',
                '--chroma-key', '#0000FF', '--json-out', OUT / 'despill.json'):
            raise SystemExit('Preview cleanup failed')
        hash_path.write_text(raw_hash + '\n', encoding='ascii')
    preview = module('pet_preview', 'render_animation_previews.py')
    atlas = Image.open(OUT / 'approval-atlas.png').convert('RGBA')
    rows = []
    for row, state in enumerate(STATES):
        folder = OUT / 'frames' / state
        folder.mkdir(parents=True, exist_ok=True)
        frames = [atlas.crop((c*192,row*208,(c+1)*192,(row+1)*208)) for c in range(len(preview.ROW_DURATIONS[state]))]
        for index, frame in enumerate(frames):
            frame.save(folder / f'{index:02}.png')
        preview.save_preview(frames, preview.ROW_DURATIONS[state], OUT / f'{state}.gif')
        # Enlarged approval media preserves the actual original cell timing.
        preview.save_preview([f.resize((384,416), Image.Resampling.NEAREST) for f in frames],
                             preview.ROW_DURATIONS[state], OUT / f'{state}-2x.gif')
        rows.append({'state':state,'method':'stable-slots','frames':[str((folder/f'{i:02}.png').resolve()) for i in range(len(frames))]})
    key = json.loads((OUT / 'raw-frames/frames-manifest.json').read_text(encoding='utf-8'))['chroma_key']
    (OUT / 'frames/frames-manifest.json').write_text(json.dumps({'ok':True,'chroma_key':key,'rows':rows},indent=2),encoding='utf-8')
    if call('inspect_frames.py', '--frames-root', OUT / 'frames', '--states', ','.join(STATES),
            '--json-out', OUT / 'frame-review.json', '--allow-stable-slots'):
        raise SystemExit('Preview frame inspection failed')
    # Labels and a neutral background belong only to the QA contact sheet.
    sheet = Image.new('RGB', (1536,len(STATES)*238), '#f4efe9')
    draw = ImageDraw.Draw(sheet)
    for row, state in enumerate(STATES):
        draw.text((8,row*238+5),state,fill='#222222')
        sheet.paste(atlas.crop((0,row*208,1536,(row+1)*208)),(0,row*238+26),atlas.crop((0,row*208,1536,(row+1)*208)).getchannel('A'))
    sheet.save(OUT / 'contact-sheet.png')
    print('Approval GIFs and contact sheet ready')

if __name__ == '__main__':
    main()
