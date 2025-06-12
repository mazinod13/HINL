import json
import os
from django.conf import settings
from .models import Script

def load_symbols_from_json():
    json_path = os.path.join(settings.BASE_DIR, 'cms', 'static', 'cms', 'symbol_script_map.json')
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    for entry in data:
        Script.objects.update_or_create(
            symbol=entry["Symbol"],
            defaults={
                "script_name": entry["Script"],
                "sector": entry["Sector"],
            }
        )

# views.py (or utils.py)

from .models import EntrySheet

# module-level cache for the global suffix
_global_suffix = None

def next_global_unique_id(date_obj):
    global _global_suffix
    if _global_suffix is None:
        # seed from the DB count only once per process
        _global_suffix = EntrySheet.objects.count()
    _global_suffix += 1

    date_str = date_obj.strftime('%Y/%m/%d')
    return f"{date_str}-{_global_suffix:04d}"
