import copy


def resume_allowed(task):
    return (not task.get("force_fresh") and task.get("status") in ("failed", "completed")
            and any(task.get(key) != "ok" for key in ("height_status", "clothing_status", "body_status"))
            and "person_binding_ambiguous" not in (task.get("failure_reason") or ""))


def prepare_resume(task, now):
    old = copy.deepcopy({key:value for key,value in task.items() if key != "attempt_history"})
    task.setdefault("attempt_history", []).append(old)
    preserved = [stage for stage in ("height", "clothing", "body") if task.get(stage+"_status") == "ok"]
    task.update(attempt=old.get("attempt",1)+1, submitted_at=now, status="queued", failure_reason=None,
                preserved_stages=preserved, started_at=None, finished_at=None, queue_time=None,
                end_to_end_time=None, display_time_note=None, timing_scope=None)
    fields={"height":["height_cm","inference_time","height_duration","height_started_at","height_finished_at","feature_source","source","econ_output"],
            "clothing":["obj_url","obj_role","clothing_source_mesh","clothing_duration","clothing_started_at","clothing_finished_at"],
            "body":["body_canonical_url","body_original_url","body_duration","body_started_at","body_finished_at"]}
    for stage in ("height", "clothing", "body"):
        if stage not in preserved:
            task[stage+"_status"]="queued"
            task[stage+"_failure_reason"]=None
            for key in fields[stage]: task.pop(key,None)
    return task
