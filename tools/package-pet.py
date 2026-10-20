"""Package only after the bundled checks and independent visual checks pass."""
import hashlib
import json
import shutil
from pathlib import Path
from PIL import Image
from pet_pipeline_import import RUN, SKILL
import importlib.util

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

for path in [RUN / 'final/validation-extended.json', RUN / 'qa/chroma-despill-extended.json', RUN / 'qa/review.json', RUN / 'qa/direction-blind-validation.json', RUN / 'qa/final-visual-review.json']:
    if not read(path).get('ok'):
        raise SystemExit(f'Blocking QA report: {path}')
semantics = read(RUN / 'qa/direction-semantics.json')
def has_failed_verdict(value):
    if isinstance(value, dict):
        return value.get('verdict') == 'fail' or any(has_failed_verdict(v) for v in value.values())
    return isinstance(value, list) and any(has_failed_verdict(v) for v in value)
if has_failed_verdict(semantics):
    raise SystemExit('Unresolved gaze semantics failure')
request = read(RUN / 'pet_request.json')
package = RUN.parents[1] / 'dist' / 'maltese-retriever'
package.mkdir(parents=True, exist_ok=True)
source = RUN / 'final/spritesheet-extended.webp'
shutil.copy2(source, package / 'spritesheet.webp')
meta = {'id': 'maltese-retriever', 'displayName': '小白和小鸡毛', 'description': '开心的小白和小鸡毛：小鸡毛上下摇尾，黑色描边的粉色爱心像气泡一样向上冒出。', 'spriteVersionNumber': 2, 'spritesheetPath': 'spritesheet.webp'}
(package / 'pet.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
spec = importlib.util.spec_from_file_location('pet_previews', SKILL / 'scripts/render_animation_previews.py')
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)
atlas = Image.open(source).convert('RGBA')
for row, (state, duration) in enumerate(preview.ROW_DURATIONS.items()):
    frames = [atlas.crop((i*192, row*208, (i+1)*192, (row+1)*208)) for i in range(len(duration))]
    preview.save_preview(frames, duration, RUN / 'qa/previews' / f'{state}.gif')
looks = [atlas.crop((i*192,r*208,(i+1)*192,(r+1)*208)) for r in [9,10] for i in range(8)]
preview.save_preview(looks, [180]*16, RUN / 'qa/previews/look-loop.gif')
shutil.make_archive(str(package.parent / 'maltese-retriever-1.0.0'), 'zip', package.parent, package.name)
summary = {'ok': True, 'spriteVersionNumber': 2, 'package': str(package), 'sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'installed': False, 'visual_notes': ['Approved outlined pink bubble artwork adapted to six native idle keyframes; actual timing shown in installer', 'Idle and jumping use visually reviewed stable-slot extraction']}
(RUN / 'qa/run-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(summary, ensure_ascii=True, indent=2))
