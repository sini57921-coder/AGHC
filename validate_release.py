"""CPU-only source/config checks. Does not import the task worker or any model."""
import ast
import hashlib
import importlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
checks = {}
python_files = sorted(ROOT.rglob('*.py'))
for path in python_files:
    ast.parse(path.read_text(encoding='utf-8-sig'), filename=str(path))
checks['python_syntax_files'] = len(python_files)
with tempfile.TemporaryDirectory(dir=ROOT) as temp:
    config = json.loads((ROOT / 'config.example.json').read_text(encoding='utf-8'))
    config['paths'] = {key: './external/' + key for key in config['paths']}
    local = Path(temp) / 'config.json'
    local.write_text(json.dumps(config), encoding='utf-8')
    os.environ['AGHC_CONFIG'] = str(local)
    import release_config
    assert release_config.path('python_service') == (local.parent / 'external/python_service').resolve()
    checks['relative_config_resolution'] = True
    imported = ['release_config', 'input_image', 'ai_adapter', 'frozen35_single', 'clothed_task',
                'body_mesh_task', 'generate_individual_body']
    for name in imported:
        importlib.import_module(name)
    checks['lightweight_imports'] = imported
    checks['torch_not_imported'] = 'torch' not in sys.modules
    assert checks['torch_not_imported']
    assert not (ROOT / 'runs').exists()
    checks['task_worker_not_started'] = True

missing = []
for name in re.findall(r'(?:src|href)="(/static/[^"?#]+)', (ROOT/'static/index.html').read_text(encoding='utf-8')):
    if not (ROOT / name.lstrip('/')).is_file(): missing.append(name)
assert not missing, missing
checks['html_local_references'] = 'all_exist'
for path in (ROOT/'static').glob('*.js'):
    result = subprocess.run(['node', '--check', str(path)], capture_output=True, text=True)
    assert result.returncode == 0, path.name + ': ' + result.stderr
checks['javascript_syntax'] = 'passed'
bad_paths = []
for path in python_files:
    for node in ast.walk(ast.parse(path.read_text(encoding='utf-8-sig'))):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and re.search(r'(?<![A-Za-z])[A-Za-z]:[\\/](?!/)', node.value):
            bad_paths.append(str(path.relative_to(ROOT)))
assert not bad_paths, bad_paths
checks['python_machine_absolute_paths'] = 0
schema = json.loads((ROOT/'config/feature_schema.json').read_text(encoding='utf-8'))
assert schema['feature_count'] == 35 and len(schema['feature_order']) == 35
checks['feature_schema_count'] = 35
checks['gpu_runs'] = 0
checks['inference_validated'] = False
checks['independent_install_validated'] = False
(ROOT / 'validation.json').write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(checks, ensure_ascii=False, indent=2))
