"""Import the orchestration helper without relying on a hyphenated module name."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('pet_pipeline', Path(__file__).with_name('pet-pipeline.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
RUN = module.RUN
call = module.call
SKILL = module.SKILL
