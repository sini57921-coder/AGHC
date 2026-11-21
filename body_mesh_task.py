from release_config import path as config_path
import hashlib
import json
import math
import os
import subprocess
from pathlib import Path

import numpy as np
from econ_paths import current_econ

BASE = Path(__file__).resolve().parent
ECON = Path(str(config_path('econ_source')))
PYTHON = Path(str(config_path('python_econ')))


def generate(parameter, canonical, original, output, height_cm):
    parameter, canonical, original, output = map(Path, (parameter, canonical, original, output))
    info = json.loads((canonical / "canonical_apose.json").read_text(encoding="utf-8"))
    digest = hashlib.sha256(parameter.read_bytes()).hexdigest()
    if info["source_sha256"] != digest or info["body_model"] != "SMPL-X neutral":
        raise ValueError("same-task SMPL-X parameter binding cannot be verified")
    data = np.load(parameter, allow_pickle=True).item()
    scale = float(np.asarray(data["scale"]).reshape(-1)[0])
    reference = float(info["height_model_units"]) * scale
    factor = float(height_cm) / 100 / reference
    if not all(math.isfinite(v) and v > 0 for v in (scale, reference, factor)):
        raise ValueError("invalid model scale or height")
    output.mkdir(parents=True, exist_ok=True)
    from clothed_task import scale_obj
    canonical_path = canonical / "canonical_apose.obj"
    # Canonical vertices are unscaled SMPL-X coordinates. ECON posed vertices
    # include camera scale; apply it before the shared display scale.
    target = output / "body_canonical_pose_m.obj"
    scale_obj(canonical_path, target, factor * scale)
    return {"body_status": "ok", "body_failure_reason": None,
            "body_canonical_path": str(target), "body_parameter_sha256": digest,
            "body_pose_label": "模型规范姿态（SMPL-X A姿态）", "body_model": "SMPL-X neutral",
            "canonical_height_model_units": info["height_model_units"],
            "econ_camera_scale": scale, "uniform_scale_m_per_econ_unit": factor,
            "body_original_source": str(original)}


def build(task, clothing):
    digest = task.get('run_key') or task['image_sha256'][:16]
    sample = 'upload_' + digest
    source = Path(clothing.get('clothing_source_mesh', '')).parent if clothing.get('clothing_source_mesh') else None
    if source is not None:
        econ = source.parent.parent.parent
    else:
        econ = Path(task['econ_output']) if task.get('econ_output') else current_econ(BASE / 'runs' / digest)
        source = econ / 'output/econ-windows-lowmem/obj'
    parameter = source / f'{sample}_smpl_00.npy'
    original = source / f'{sample}_smpl_00.obj'
    canonical = econ / sample / 'canonical'
    output = BASE / 'static/generated' / task['task_id']
    output.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env['PATH'] = ';'.join(str(PYTHON.parent / x) for x in ('Library/bin', 'bin', 'Scripts', '')) + ';' + env.get('PATH', '')
    env['PYTHONPATH'] = str(ECON) + os.pathsep + env.get('PYTHONPATH', '')
    env['PYTHONUTF8'] = '1'
    command = [str(PYTHON), str(BASE / 'generate_individual_body.py'), str(parameter),
               str(canonical), str(original), str(output), str(task['height_cm'])]
    with (output / 'body_generation.log').open('w', encoding='utf-8') as log:
        process = subprocess.run(command, cwd=ECON, env=env, stdout=log, stderr=subprocess.STDOUT)
    if process.returncode:
        raise RuntimeError((output / 'body_generation.log').read_text(encoding='utf-8', errors='replace')[-1000:])
    result = json.loads((output / 'individual_body_result.json').read_text(encoding='utf-8'))
    result['body_canonical_url'] = f"/static/generated/{task['task_id']}/body_canonical_pose_m.obj"
    result['body_original_url'] = f"/static/generated/{task['task_id']}/body_original_pose_regenerated_m.obj"
    return result
