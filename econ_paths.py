import json
from pathlib import Path


def current_econ(work):
    work = Path(work)
    pointer = work / "econ_attempt.json"
    return work / json.loads(pointer.read_text(encoding="utf-8"))["directory"] if pointer.exists() else work / "econ"


def new_econ_attempt(work):
    work = Path(work)
    index = 1
    while (work / f"econ_attempt_{index:02d}").exists():
        index += 1
    output = work / f"econ_attempt_{index:02d}"
    # The ECON launcher creates output itself with exist_ok=False.
    (work / "econ_attempt.json").write_text(json.dumps({"directory":output.name,"attempt":index}),encoding="utf-8")
    return output
