"""Run the bundled one-time cleanup and v2 structural/visual QA artifact steps."""
from pet_pipeline_import import RUN, call

atlas = RUN / 'final/spritesheet-extended.png'
webp = RUN / 'final/spritesheet-extended.webp'
report = RUN / 'qa/chroma-despill-extended.json'
if not report.exists():
    if call('despill_chroma_edges.py', atlas, '--output', atlas, '--webp-output', webp, '--chroma-key', '#0000FF', '--json-out', report):
        raise SystemExit('Bundled chroma cleanup failed')
checks = [
    ('validate_atlas.py', webp, '--json-out', RUN / 'final/validation-extended.json', '--chroma-key', '#0000FF', '--require-v2'),
    ('make_contact_sheet.py', webp, '--output', RUN / 'qa/contact-sheet-extended.png'),
    ('make_direction_qa_sheet.py', webp, '--output', RUN / 'qa/look-directions.png'),
    ('make_direction_blind_qa_sheet.py', webp, '--output', RUN / 'qa/direction-blind-pairs.png', '--answer-key', RUN / 'qa/direction-blind-answer-key.json'),
    ('measure_direction_continuity.py', webp, '--json-out', RUN / 'qa/look-continuity.json'),
]
for script, *args in checks:
    if call(script, *args):
        raise SystemExit(f'{script} failed')
