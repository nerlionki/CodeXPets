"""Run the application's bundled pet validators; never generate character pixels."""
import argparse
import datetime
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'animation/pet-run'
SKILL = Path('C:/Program Files/WindowsApps/OpenAI.Codex_26.1013.4894.0_x64__2p2nqsd0c76g0/app/resources/skills/skills/.curated/hatch-pet')

def call(script, *args):
    return subprocess.run([sys.executable, str(SKILL / 'scripts' / script), *map(str, args)], check=False).returncode

def manifest():
    return json.loads((RUN / 'imagegen-jobs.json').read_text(encoding='utf-8-sig'))

def mark(job_id, source):
    data = manifest()
    job = next(j for j in data['jobs'] if j['id'] == job_id)
    job.update(status='complete', source_path=str(source), completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
    (RUN / 'imagegen-jobs.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

def accept(job_id, source, method):
    job = next(j for j in manifest()['jobs'] if j['id'] == job_id)
    target = RUN / job['output_path']
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    if job['kind'] == 'row-strip':
        qa = RUN / 'qa/rows' / job_id
        rc = call('extract_strip_frames.py', '--decoded-dir', RUN / 'decoded', '--output-dir', qa / 'frames', '--states', job_id, '--method', method, '--chroma-key', '#0000FF')
        if rc:
            return rc
        args = ['--frames-root', qa / 'frames', '--json-out', qa / 'review.json', '--states', job_id, '--require-components']
        if method == 'stable-slots':
            args.append('--allow-stable-slots')
        rc = call('inspect_frames.py', *args)
        if rc:
            return rc
    mark(job_id, source)
    return 0

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('job')
    parser.add_argument('source')
    parser.add_argument('--method', default='auto')
    args = parser.parse_args()
    raise SystemExit(accept(args.job, Path(args.source), args.method))
