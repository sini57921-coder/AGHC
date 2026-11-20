# -*- coding: utf-8 -*-
"""Frozen 35D single-image height adapter."""
import time
from frozen35_single import VERSION, predict_image

def run_ai(image_path: str, run_key=None, force_fresh=False):
    started = time.monotonic()
    try:
        prediction = predict_image(image_path, run_key=run_key, force_fresh=force_fresh)
        source = prediction.get("source")
        return {"height_cm": prediction["height_cm"], "status":"ok", "failure_reason":None, "method_version":VERSION, "inference_time":round(time.monotonic()-started,3), "feature_source":source, "source":source}
    except Exception as error:
        return {"height_cm":None,"status":"failed","failure_reason":f"{type(error).__name__}: {error}","method_version":VERSION,"inference_time":round(time.monotonic()-started,3)}
