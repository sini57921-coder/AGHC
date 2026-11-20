from release_config import path as config_path
"""Run the frozen ECON settings once over a fixed independent-image manifest."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("manifest", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    rows = json.loads(a.manifest.read_text(encoding="utf-8"))["samples"]
    a.output.mkdir(parents=True, exist_ok=False)
    inp = a.output / "input"
    inp.mkdir()
    for row in rows:
        src = Path(row["image_path"])
        if hashlib.sha256(src.read_bytes()).hexdigest() != row["source_sha256"]:
            raise ValueError(row["sample_id"])
        shutil.copy2(src, inp / f'{row["sample_id"]}.png')
    project = Path(str(config_path('legacy_project')))
    econ = config_path("econ_source")
    python = Path(str(config_path('python_econ')))
    runtime = a.output / "runtime"
    env = os.environ.copy()
    envroot = python.parent
    env["PATH"] = ";".join(str(envroot / x) for x in ("Library/bin", "bin", "Scripts", "")) + ";" + env.get("PATH", "")
    for key, name in (("TEMP", "t"), ("TMP", "t"), ("CUPY_CACHE_DIR", "c"),
                      ("MPLCONFIGDIR", "m")):
        path = runtime / name
        path.mkdir(parents=True, exist_ok=True)
        env[key] = str(path)
    ascii_temp = Path(os.environ["LOCALAPPDATA"]) / "Temp"
    assert ascii_temp.is_dir() and str(ascii_temp).isascii()
    cache_tag = hashlib.sha1(str(a.output.resolve()).encode("utf-8")).hexdigest()[:12]
    numba_cache = ascii_temp / ("aghn_" + cache_tag)
    numba_cache.mkdir(parents=True, exist_ok=True)
    env.update(TEMP=str(ascii_temp), TMP=str(ascii_temp), TMPDIR=str(ascii_temp),
               NUMBA_CACHE_DIR=str(numba_cache))
    env.update(PYTHONUTF8="1", PYTHONUNBUFFERED="1", PYTHONDONTWRITEBYTECODE="1",
               CUDNN_CONV_WSCAP_DBG="1024",
               U2NET_HOME=str(config_path("u2net_root")),
               TORCH_HOME=str(config_path("torch_cache")),
               HF_HOME=str(econ / "data/hf_cache"), HF_HUB_OFFLINE="1",
               TRANSFORMERS_OFFLINE="1", PYTHONPATH=str(Path(__file__).resolve().parent / "runtime_hooks/u2net_cpu") + ";" + str(config_path("legacy_aghc") / "src") + ";" + str(econ) + ";" + str(Path(__file__).resolve().parent),
               AGHC_REMBG_PROVIDER_LOG=str(a.output / "u2net_provider.jsonl"),
               AGHC_STAGE_MEMORY_LOG=str(a.output / "stage_memory.jsonl"))
    cmd = [str(python), str(config_path("econ_staged_entry")), "-cfg", str(config_path("econ_config")),
           "-gpu", "0", "-in_dir", str(inp), "-out_dir", str(a.output / "output"),
           "-mcube_res", "128", "-loop_smpl", "25", "-novis", "-save_initial"]
    (a.output / "protocol.json").write_text(json.dumps({"samples": [r["sample_id"] for r in rows],
        "command": cmd, "label_blind": True, "one_model_load": True}, indent=2), encoding="utf-8")
    with (a.output / "inference.log").open("w", encoding="utf-8") as log:
        result = subprocess.run(cmd, cwd=econ, env=env, stdout=log, stderr=subprocess.STDOUT)
    print("infer returncode", result.returncode, flush=True)
    for row in rows:
        key = row["sample_id"]
        parameter = a.output / "output/econ-windows-lowmem/obj" / f"{key}_smpl_00.npy"
        if not parameter.is_file():
            print(key, "FAILED_PARAMETER", flush=True)
            continue
        target = a.output / key
        (target / "output/econ-windows-lowmem/obj").mkdir(parents=True)
        shutil.copy2(parameter, target / "output/econ-windows-lowmem/obj" / parameter.name)
        canonical = target / "canonical"
        cmd2 = [str(python), "-m", "aghc.cli", "canonical-body", str(parameter),
                str(econ / "data/smpl_related/models"), str(canonical), "--model-type", "smplx"]
        with (target / "canonical.log").open("w", encoding="utf-8") as log:
            result2 = subprocess.run(cmd2, cwd=econ, env=env, stdout=log, stderr=subprocess.STDOUT)
        print(key, "OK" if result2.returncode == 0 and (canonical / "canonical_apose.json").is_file() else "FAILED_CANONICAL", flush=True)


if __name__ == "__main__":
    main()

