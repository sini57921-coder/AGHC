import json
from pathlib import Path


def first_econ_error(directory):
    directory = Path(directory)
    log = directory / "inference.log"
    if log.exists():
        lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
        for line in lines:
            if line.startswith("AGHC_STAGE_MEMORY "):
                try:
                    record = json.loads(line.split(" ", 1)[1])
                    if record.get("error"):
                        return "ECON " + record.get("error_type", "error") + ": " + record["error"] + "；日志：" + str(log)
                except (ValueError, KeyError):
                    pass
        for line in lines:
            if any(token in line for token in ("MemoryError:", "RuntimeError:", "CUDA out of memory", "fatal   :")):
                return "ECON: " + line.strip() + "；日志：" + str(log)
    return "ECON必需产物未生成；日志：" + str(log)
