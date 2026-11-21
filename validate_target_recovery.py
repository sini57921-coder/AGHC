"""CPU-only wiring checks with synthetic inputs; never starts task workers or models."""
import hashlib
import importlib
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch
from PIL import Image

ROOT = Path(__file__).resolve().parent


def main():
    checks = {}
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        config = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
        config["paths"] = {k: (None if k.startswith("cache_") else "external/" + k) for k in config["paths"]}
        file = base / "config.json"
        file.write_text(json.dumps(config), encoding="utf-8")
        os.environ["AGHC_CONFIG"] = str(file)
        import release_config
        release_config._cache = None
        assert release_config.path("camera_assets") == base / "external/camera_assets"
        assert release_config.optional_path("cache_manifest") is None
        import frozen35_single as frozen
        importlib.reload(frozen)
        work = base / "work"; work.mkdir()
        image = base / "synthetic.png"
        Image.new("RGB", (100, 120), (80, 90, 100)).save(image)
        class DetectionStubReached(Exception): pass
        def fake_run(command, **kwargs):
            assert str(command[1]).endswith("detect_camerahmr_people.py")
            raise DetectionStubReached()
        with patch.object(frozen, "HERE", base), patch.object(frozen.subprocess, "run", fake_run):
            try: frozen.feature_for(image, "synthetic", work)
            except DetectionStubReached: checks["missing_optional_cache_reaches_new_image_detector"] = True
        assert checks.get("missing_optional_cache_reaches_new_image_detector")
        from target_selection import candidates_for, prepare_target
        (base / "static").mkdir(); (base / "runs").mkdir()
        digest = hashlib.sha256(image.read_bytes()).hexdigest()
        task = {"task_id":"synthetic_parent", "image_path":str(image), "image_sha256":digest, "run_key":"synthetic", "method_version":frozen.VERSION}
        detector = base / "runs/upload_synthetic_detector"; detector.mkdir()
        row={"source_sha256":digest,"person_candidates":2,"boxes":[[0,0,40,100],[60,0,100,100]],"scores":[0.9,0.9]}
        (detector/"results.json").write_text(json.dumps([row]),encoding="utf-8")
        choices=candidates_for(task,base);assert len(choices)==2
        first=prepare_target(task,choices[0],0,base);second=prepare_target(task,choices[1],1,base)
        assert first["run_key"]!=second["run_key"]
        for selected in (first,second):
            assert selected["target_selection"]["crop_sha256"]==hashlib.sha256(Path(selected["image_path"]).read_bytes()).hexdigest()
        checks["target_id_and_cache_isolation"]=True
        from econ_paths import current_econ,new_econ_attempt
        run=base/"runs"/first["run_key"]
        old=run/"econ";old.mkdir();(old/"old.log").write_text("keep")
        a=new_econ_attempt(run);assert not a.exists();a.mkdir()
        b=new_econ_attempt(run);assert not b.exists();b.mkdir();assert current_econ(run)==b
        assert (old/"old.log").read_text()=="keep"
        checks["attempt_directories_and_pointer"]=True
        first.update(econ_output=str(b),height_cm=170)
        (b/"protocol.json").write_text(json.dumps({"command":["full_inference"]}),encoding="utf-8")
        (b/"inference.log").write_text('AGHC_STAGE_MEMORY '+json.dumps({"error_type":"MemoryError","error":"synthetic allocation failure"}),encoding="utf-8")
        from econ_failure import first_econ_error
        import ai_adapter,clothed_task,body_mesh_task
        error=first_econ_error(b)
        with patch.object(ai_adapter,"predict_image",side_effect=RuntimeError(error)):
            response=ai_adapter.run_ai(str(image))
        assert response["status"]=="failed" and "synthetic allocation failure" in response["failure_reason"]
        checks["first_error_adapter_transmission"]=True
        with patch.object(clothed_task,"BASE",base):
            clothing=clothed_task.build(first)
        assert clothing["clothing_log"]==str(b/"inference.log")
        captured=[]
        def body_stub(command,**kwargs):
            captured.extend(command)
            class Result: returncode=1
            return Result()
        with patch.object(body_mesh_task,"BASE",base),patch.object(body_mesh_task.subprocess,"run",body_stub):
            try:body_mesh_task.build(first,{})
            except RuntimeError:pass
        assert str(b/"output/econ-windows-lowmem/obj"/('upload_'+first["run_key"]+'_smpl_00.npy')) in captured
        checks["body_and_clothing_use_current_attempt"]=True
        checks["gpu_runs"]=0
        checks["model_forward_runs"]=0
        print(json.dumps(checks,ensure_ascii=False,indent=2))


if __name__=="__main__":main()
