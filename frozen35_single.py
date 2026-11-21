from release_config import path as config_path, optional_path
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
from econ_failure import first_econ_error
from econ_paths import current_econ, new_econ_attempt

HERE = Path(__file__).resolve().parent
HMR = config_path("camera_assets")
FIT = config_path("frozen_fit")
MANIFEST = optional_path("cache_manifest")
FEATURES = optional_path("cache_features")
CACHE_DETECTOR = optional_path("cache_detector_results")
PY_HMR = config_path("python_service")
PY_FACE = config_path("python_face")
PY_ECON = Path(str(config_path('python_econ')))
TOOLS = config_path("camera_tools")
ORIGINAL_TOOLS = Path(str(config_path('legacy_tools')))
VERSION = "frozen35_full112_clear_only_20261101_v1"


def bound_person(detection, work):
    boxes = detection["boxes"]
    if detection["person_candidates"] == 1:
        return detection, None
    if not boxes:
        raise ValueError("no_person")
    candidates = []
    for i, outer in enumerate(boxes):
        width = outer[2] - outer[0]
        if width <= 0:
            continue
        others = [box for j, box in enumerate(boxes) if j != i]
        if all(
            (max(0, min(outer[2], box[2]) - max(outer[0], box[0]))
             * max(0, min(outer[3], box[3]) - max(outer[1], box[1])))
            / max(1, (box[2] - box[0]) * (box[3] - box[1])) >= 0.95
            and abs((box[0] + box[2] - outer[0] - outer[2]) / 2) <= 0.30 * width
            for box in others
        ):
            candidates.append(i)
    if len(candidates) != 1:
        raise ValueError("person_binding_ambiguous")
    chosen = candidates[0]
    resolved = dict(detection, selected_box=boxes[chosen], selected_score=detection["scores"][chosen])
    path = HERE / "runs" / ("upload_" + work.name + "_binding") / "results.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps([resolved], indent=2), encoding="utf-8")
    return resolved, path.relative_to(HERE / "runs")


def feature_for(image, digest, work, force_fresh=False):
    cache_ready = not force_fresh and all(path is not None and path.is_file() for path in (MANIFEST, FEATURES, CACHE_DETECTOR))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))["samples"] if cache_ready else []
    known = next((row for row in manifest if row["source_sha256"] == digest), None)
    if known:
        detector = next((row for row in json.loads(CACHE_DETECTOR.read_text(encoding="utf-8"))
                         if row["sample_id"] == known["sample_id"]), None)
        if detector is None or detector["person_candidates"] != 1:
            raise ValueError("person_binding_ambiguous")
        row = next((row for row in json.loads(FEATURES.read_text(encoding="utf-8"))
                    if row["sample_id"] == known["sample_id"]), None)
        if row and "body28" in row:
            return row["body28"], row["ratios"], "same_image_cache"

    sample = "upload_" + work.name
    manifest_path = work / "manifest.json"
    manifest_path.write_text(json.dumps({"samples": [{"sample_id": sample, "subject_id": sample,
        "experiment_split": "independent", "image_path": str(image), "source_sha256": digest}]}), encoding="utf-8")
    log = work / "frontend.log"
    def run(command):
        with log.open("a", encoding="utf-8") as stream:
            stream.write("COMMAND " + " ".join(map(str, command)) + "\n")
            stream.flush()
            result = subprocess.run([str(x) for x in command], stdout=stream, stderr=subprocess.STDOUT,
                                    env={**os.environ, "PYTHONUTF8": "1", "PYTHONPATH": str(ORIGINAL_TOOLS) + os.pathsep + os.environ.get("PYTHONPATH", "")})
        if result.returncode:
            text = log.read_text(encoding="utf-8", errors="replace").rsplit("COMMAND ", 1)[-1]
            errors = [line.strip() for line in text.splitlines()
                      if any(token in line for token in ("Error:", "Exception:", "fatal   :"))]
            cause = errors[-1] if errors else f"frontend exit {result.returncode}"
            raise RuntimeError(f"{cause}; see {log}")
    detector, fov, body, reflection = [sample + suffix for suffix in
        ("_detector", "_fov", "_body", "_reflection")]
    common = ["--manifest", manifest_path, "--expected-inputs", "1"]
    if not (HERE / "runs" / detector / "results.json").exists():
        run([PY_HMR, TOOLS / "detect_camerahmr_people.py", "--output", detector, *common])
    detection = json.loads((HERE / "runs" / detector / "results.json").read_text(encoding="utf-8"))[0]
    detection, resolved_path = bound_person(detection, work)
    detector_results = str(resolved_path) if resolved_path else detector + "/results.json"
    if not (HERE / "runs" / fov / "completion.json").exists():
        run([PY_HMR, TOOLS / "run_camerahmr_pilot.py", "--stage", "fov", "--output", fov, *common])
    if not (HERE / "runs" / body / "completion.json").exists():
        run([PY_HMR, TOOLS / "run_camerahmr_pilot.py", "--stage", "body", "--output", body,
             "--box-rule", "detector_full_height", "--detector-results", detector_results,
             "--fov-output", fov, *common])
    if not (HERE / "runs" / reflection / "features.json").exists():
        run([PY_HMR, TOOLS / "run_camerahmr_reflection_diagnostic.py", "--output", reflection,
             "--manifest", manifest_path, "--expected-inputs", "1", "--base-parameters", body])
    face_dir = work / "face"
    if not (face_dir / "features.json").exists():
        run([PY_FACE, ORIGINAL_TOOLS / "extract_baracca5_face.py", "--manifest", manifest_path,
             "--detector", HERE / "runs" / detector_results, "--output", face_dir])
    econ = current_econ(work)
    if not (econ / sample / "canonical/canonical_apose.json").exists():
        econ = new_econ_attempt(work)
        run([PY_ECON, HERE / "run_clothed_single.py", manifest_path, econ])
    canonical = econ / sample / "canonical/canonical_apose.json"
    parameter = econ / sample / "output/econ-windows-lowmem/obj" / (sample + "_smpl_00.npy")
    if not parameter.is_file() or not canonical.is_file():
        raise RuntimeError(first_econ_error(econ))
    import torch
    beta = np.asarray(np.load(parameter, allow_pickle=True).item()["betas"].detach().cpu()).reshape(-1)[:10]
    hmr = json.loads((HERE / "runs" / reflection / "features.json").read_text(encoding="utf-8"))[0]
    if hmr["status"] != "OK":
        raise ValueError("CameraHMR_output_unavailable")
    body28 = [json.loads(canonical.read_text(encoding="utf-8"))["height_model_units"],
              *beta.tolist(), hmr["canonical_height_model_units"], *hmr["betas"]]
    ratios = json.loads((face_dir / "features.json").read_text(encoding="utf-8"))[0]["ratios"]
    return body28, ratios, "fresh_same_image"

def predict_image(image_path, run_key=None, force_fresh=False):
    image = Path(image_path)
    digest = hashlib.sha256(image.read_bytes()).hexdigest()
    work = HERE / "runs" / (run_key or digest[:16])
    work.mkdir(parents=True, exist_ok=True)
    body28, ratios, source = feature_for(image, digest, work, force_fresh=force_fresh)
    frozen = json.loads(FIT.read_text(encoding="utf-8"))
    face = ratios if ratios is not None else frozen["face_medians"]
    values = np.r_[body28, face, float(ratios is not None)]
    fit = frozen["fit"]
    height = float((values - fit["center"]) / fit["spread"] @ np.asarray(fit["coefficients"]) + fit["offset"])
    if values.shape != (35,) or not np.isfinite(height):
        raise ValueError("invalid_frozen35_output")
    result = {"height_cm": height, "method_version": VERSION, "source": source, "image_sha256": digest,
              "run_key": work.name, "force_fresh": force_fresh, "econ_output": str(current_econ(work))}
    (work / "direct_prediction.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(predict_image(sys.argv[1]), ensure_ascii=False))
