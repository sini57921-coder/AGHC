from release_config import path as config_path
import os
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
VSDEV = Path(str(config_path('vsdevcmd')))
PY_ECON = Path(str(config_path('python_econ')))


def main() -> None:
    command = f'call "{VSDEV}" -arch=amd64 -vcvars_ver=14.39 >nul && set'
    loaded = subprocess.run(command, shell=True, capture_output=True)
    loaded.check_returncode()
    env = os.environ.copy()
    for line in loaded.stdout.decode("cp936", errors="replace").splitlines():
        if "=" in line and not line.startswith("="):
            key, value = line.split("=", 1)
            for old_key in list(env):
                if old_key.lower() == key.lower():
                    del env[old_key]
            env[key] = value
    compiler = subprocess.run(["where.exe", "cl.exe"], env=env, capture_output=True, text=True, check=True)
    first = compiler.stdout.splitlines()[0]
    if r"\MSVC\14.39." not in first:
        raise RuntimeError(f"MSVC 14.39 required, found {first}")
    print("ECON_COMPILER", first, flush=True)
    result = subprocess.run([str(PY_ECON), str(HERE / "run_clothed_006_ascii_temp.py"), *sys.argv[1:]], env=env)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
