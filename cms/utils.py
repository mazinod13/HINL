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


# cms/utils.py
import csv
import requests
from datetime import datetime
from io import StringIO
from .models import Script

def update_scripts_from_google_sheet():
    url = (
        "https://docs.google.com/spreadsheets/d/"
        "1KLSF2dW6cy5sMdRpzvUza2Ko0G0S9J0GSQCV05p3uQI/"
        "export?format=csv&gid=0"
    )
    resp = requests.get(url)
    if resp.status_code != 200:
        return 0

    reader = csv.DictReader(StringIO(resp.text))
    print(">>> CSV fields:", reader.fieldnames)
    updated = 0

    for row in reader:
        symbol  = row.get("Company Name") or row.get("symbol")
        sector  = row.get("Sector") or row.get("sector")
        ltp     = row.get("LTP")
        ltpdate = row.get("LTP DATE")
      

        if not symbol or not ltp:
            continue

        try:
            script = Script.objects.get(symbol=symbol)
            new_ltp   = float(ltp)
            new_date  = (
                datetime.strptime(ltpdate, "%Y-%m-%d").date()
                if ltpdate else None
            )

            # Only update if any value changed
            changed = False
            if script.ltp != new_ltp:
                script.ltp = new_ltp
                changed = True

            if hasattr(script, "ltpdate") and script.ltpdate != new_date:
                script.ltpdate = new_date
                changed = True

            if sector and script.sector != sector:
                script.sector = sector
                changed = True

            if changed:
                script.save()
                updated += 1

        except Script.DoesNotExist:
            continue

    return updated






