"""Render actual v2 atlas playback for installer and final visual QA."""
import importlib.util
from PIL import Image
from pet_pipeline_import import RUN, SKILL

spec = importlib.util.spec_from_file_location('pet_previews', SKILL / 'scripts/render_animation_previews.py')
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)
atlas = Image.open(RUN / 'final/spritesheet-extended.webp').convert('RGBA')
for row, (state, durations) in enumerate(preview.ROW_DURATIONS.items()):
    frames = [atlas.crop((i*192,row*208,(i+1)*192,(row+1)*208)) for i in range(len(durations))]
    preview.save_preview(frames, durations, RUN / 'qa/previews' / f'{state}.gif')
looks = [atlas.crop((i*192,r*208,(i+1)*192,(r+1)*208)) for r in [9,10] for i in range(8)]
preview.save_preview(looks, [180]*16, RUN / 'qa/previews/look-loop.gif')
print('Rendered native atlas previews')
