import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
_cache = None

def settings():
    global _cache
    if _cache is None:
        name = os.environ.get('AGHC_CONFIG')
        if not name:
            raise RuntimeError('请设置AGHC_CONFIG，指向私有config.local.json；勿修改生产配置')
        file = Path(name).resolve()
        _cache = (file.parent, json.loads(file.read_text(encoding='utf-8-sig')))
    return _cache

def path(key):
    base, data = settings()
    value = data['paths'].get(key)
    if not value:
        raise RuntimeError('配置缺项：paths.' + key)
    result = Path(os.path.expandvars(value)).expanduser()
    return result if result.is_absolute() else (base / result).resolve()

OPTIONAL_PATHS = {"cache_manifest", "cache_features", "cache_detector_results", "research_root"}


def optional_path(key):
    _, data = settings()
    return path(key) if data['paths'].get(key) else None


if __name__ == '__main__':
    import sys
    base, data = settings()
    missing = [key for key in data['paths'] if key not in OPTIONAL_PATHS and not path(key).exists()]
    print(json.dumps({'config_loaded': True, 'missing_paths': missing}, ensure_ascii=False))
    if '--python-service' in sys.argv: print(path('python_service'))
