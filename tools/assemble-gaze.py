"""Register gaze against the real idle cell without recentering its headroom."""
from pet_pipeline_import import RUN, SKILL, call
import importlib.util
import json
from PIL import Image

# Omit --neutral-cell: that option recenters even an already registered 192x208
# image in the current bundled helper. Its base-atlas fallback preserves ground.
# The approved seated silhouette is shorter because of its folded legs. Keep
# the already reviewed gaze artwork scale instead of shrinking the heads to
# that pose's total height; only register its feet to the current idle anchor.
spec = importlib.util.spec_from_file_location('pet_gaze', SKILL / 'scripts/assemble_extended_atlas.py')
reg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reg)
neutral = Image.open(RUN / 'frames/idle/00.png').convert('RGBA')
scale = json.loads((RUN / 'qa/look-row-9-registration.json').read_text())['scale']
cells = reg.normalize_cells_to_reference(reg.extract_row_strip_cells(RUN / 'decoded/look-row-9.png', (0, 0, 255), 96), neutral, scale)
reg.validate_normalized_look_cells(cells, 0, 2, 0)
reg.save_registered_row(cells, RUN / 'qa/look-row-9-registered.png')
reg.write_registration_manifest(RUN / 'qa/look-row-9-registration.json', scale)
if call('assemble_extended_atlas.py', '--base-atlas', RUN / 'final/spritesheet.webp', '--registered-row-9', RUN / 'qa/look-row-9-registered.png', '--row-9-registration', RUN / 'qa/look-row-9-registration.json', '--look-row-10', RUN / 'decoded/look-row-10.png', '--chroma-key', '#0000FF', '--chroma-threshold', 96, '--output', RUN / 'final/spritesheet-extended.png', '--webp-output', RUN / 'final/spritesheet-extended.webp', '--manifest-output', RUN / 'final/spritesheet-extended.json'):
    raise SystemExit('Complete gaze assembly failed')
