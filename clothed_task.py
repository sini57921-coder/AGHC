from release_config import path as config_path
import hashlib
import json
import math
import shutil
import subprocess
from pathlib import Path

import numpy as np
from econ_paths import current_econ


BASE = Path(__file__).resolve().parent
PY_ECON = Path(str(config_path('python_econ')))


def scale_obj(source: Path, target: Path, factor: float) -> None:
    with source.open(encoding="utf-8") as inp, target.open("w", encoding="utf-8") as out:
        for line in inp:
            if line.startswith("v "):
                parts = line.split()
                xyz = [f"{float(value) * factor:.9f}" for value in parts[1:4]]
                out.write(" ".join(["v", *xyz, *parts[4:]]) + "\n")
            else:
                out.write(line)


def first_error(log: Path) -> str:
    if not log.exists():
        return "ECON did not create an inference log"
    lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
    for line in lines:
        if any(word in line.lower() for word in ("fatal error", "out of memory", "runtimeerror:", "compileexception:")):
            return line.strip()[:500]
    return (lines[-1].strip() if lines else "ECON did not produce a clothed mesh")[:500]


def build(task: dict) -> dict:
    digest = task.get("run_key") or task["image_sha256"][:16]
    sample = "upload_" + digest
    run = BASE / "runs" / digest
    source = Path(task["econ_output"]) if task.get("econ_output") else current_econ(run)
    mesh = source / "output" / "econ-windows-lowmem" / "obj" / f"{sample}_0_full.obj"
    if not mesh.is_file():
        protocol = source / "protocol.json"
        if protocol.is_file() and "-body_only" not in json.loads(protocol.read_text(encoding="utf-8"))["command"]:
            return {"clothing_status": "failed", "clothing_failure_reason": first_error(source / "inference.log"),
                    "clothing_log": str(source / "inference.log"), "obj_url": None, "obj_role": None}
        attempt = BASE / "runs" / "web_tasks" / task["task_id"]
        attempt.mkdir(exist_ok=False)
        manifest = attempt / "manifest.json"
        manifest.write_text(json.dumps({"samples": [{"sample_id": sample, "subject_id": sample,
            "experiment_split": "single_upload", "image_path": task["image_path"],
            "source_sha256": digest}]}), encoding="utf-8")
        source = attempt / "econ_full"
        with (attempt / "clothing_launcher.log").open("w", encoding="utf-8") as log:
            process = subprocess.run([str(PY_ECON), str(BASE / "run_clothed_single.py"),
                                      str(manifest), str(source)], stdout=log, stderr=subprocess.STDOUT)
        mesh = source / "output" / "econ-windows-lowmem" / "obj" / f"{sample}_0_full.obj"
        if process.returncode != 0 or not mesh.is_file():
            return {"clothing_status": "failed", "clothing_failure_reason": first_error(source / "inference.log"),
                    "clothing_log": str(source / "inference.log"), "obj_url": None, "obj_role": None}

    objdir = mesh.parent
    if len(list(objdir.glob(f"{sample}_*_full.obj"))) != 1:
        return {"clothing_status": "failed", "clothing_failure_reason": "ECON target person is ambiguous",
                "obj_url": None, "obj_role": None}

    parameter = objdir / f"{sample}_smpl_00.npy"
    canonical = source / sample / "canonical" / "canonical_apose.json"
    factor = None
    scale_reason = None
    try:
        data = np.load(parameter, allow_pickle=True).item()
        camera_scale = float(np.asarray(data["scale"]).reshape(-1)[0])
        reference = json.loads(canonical.read_text(encoding="utf-8"))
        if reference["source_sha256"] != hashlib.sha256(parameter.read_bytes()).hexdigest():
            raise ValueError("canonical body does not match this task's SMPL-X parameters")
        height = float(reference["height_model_units"]) * camera_scale
        if reference["body_model"] != "SMPL-X neutral" or not math.isfinite(height) or height <= 0:
            raise ValueError("invalid standard-pose body height")
        factor = float(task["height_cm"]) / 100 / height
        if not math.isfinite(factor) or factor <= 0:
            raise ValueError("invalid uniform scale")
    except (OSError, KeyError, TypeError, ValueError) as error:
        scale_reason = f"{type(error).__name__}: {error}"

    display = BASE / "static" / "generated" / task["task_id"]
    display.mkdir(exist_ok=True)
    name = "clothed_original_pose_m.obj" if factor is not None else "clothed_original_pose_model_units.obj"
    target = display / name
    if factor is None:
        shutil.copy2(mesh, target)
    else:
        scale_obj(mesh, target, factor)
    body = objdir / f"{sample}_smpl_00.obj"
    body_target = None
    if body.is_file():
        body_target = display / ("body_original_pose_m.obj" if factor is not None else "body_original_pose_model_units.obj")
        if factor is None:
            shutil.copy2(body, body_target)
        else:
            scale_obj(body, body_target, factor)

    result = {"clothing_status": "ok", "clothing_failure_reason": None,
              "obj_url": f"/static/generated/{task['task_id']}/{name}",
              "obj_role": "same_image_clothed_original_pose", "mesh_pose_state": "original fitted pose",
              "mesh_scale_status": "metric_display" if factor is not None else "unscaled",
              "mesh_scale_reason": scale_reason,
              "mesh_units": "metres from frozen height and same-body A-pose" if factor is not None else "ECON model units",
              "uniform_scale_m_per_model_unit": factor,
              "clothing_source_mesh": str(mesh), "body_display_mesh": str(body_target) if body_target else None}
    (display / "unified_result.json").write_text(json.dumps({"task_id": task["task_id"],
        "image_sha256": digest, "height_cm": task["height_cm"], "height_method_version": task["method_version"],
        **result}, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
