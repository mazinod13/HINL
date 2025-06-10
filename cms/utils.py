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
