import json
import os
import csv
import requests
from io import StringIO
from django.conf import settings
from django.utils.dateparse import parse_date as django_parse_date
from .models import Script


def load_symbols_from_json():
    json_path = os.path.join(
        settings.BASE_DIR,
        'cms', 'static', 'cms',
        'symbol_script_map.json'
    )
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    for entry in data:
        # Use django_parse_date to turn strings into date objects
        ltpdate_raw = entry.get("LTPDATE") or entry.get("ltpdate") or ""
        ltpdate = django_parse_date(ltpdate_raw) if ltpdate_raw else None

        Script.objects.update_or_create(
            symbol=entry["Symbol"].strip().upper(),
            defaults={
                "script_name": entry["Script"].strip(),
                "sector":      entry["Sector"].strip(),
                "ltp":         float(entry.get("LTP") or 0),
                "ltpdate":     ltpdate,
            }
        )

SENTINELS = {'#N/A', 'N/A', 'NA', ''}

def update_scripts_from_google_sheet():
    url = (
        "https://docs.google.com/spreadsheets/d/"
        "1KLSF2dW6cy5sMdRpzvUza2Ko0G0S9J0GSQCV05p3uQI/"
        "export?format=csv&gid=0"
    )
    resp = requests.get(url)
    resp.raise_for_status()

    reader = csv.DictReader(StringIO(resp.text))
    print(">>> CSV fields:", reader.fieldnames)

    updated = 0
    for raw_row in reader:
        # 1) Normalize headers: strip spaces, uppercase
        row = {
            k.strip().replace(" ", "").upper(): v
            for k, v in raw_row.items()
        }

        symbol = row.get("TICKER", "").strip().upper()
        if not symbol:
            continue

        # 2) Parse LTP, but if it’s in our sentinels, treat as “no change”
        ltp_raw = row.get("LTP", "").replace(",", "").strip()
        if ltp_raw.upper() in SENTINELS:
            new_ltp = None
        else:
            try:
                new_ltp = float(ltp_raw)
            except ValueError:
                print(f"⚠️ Couldn’t parse LTP {ltp_raw!r} for {symbol!r}; skipping only LTP")
                new_ltp = None

        # 3) Parse LTPDATE, similarly ignoring sentinels
        ltpdate_raw = row.get("LTPDATE", "").strip()
        if ltpdate_raw.upper() in SENTINELS:
            new_date = None
        else:
            new_date = django_parse_date(ltpdate_raw)

        # 4) Lookup & upe
        try:
            script = Script.objects.get(symbol=symbol)
        except Script.DoesNotExist:
            print(f"Script for symbol={symbol!r} not found, skipping")
            continue

        changed = False

        if new_ltp is not None and script.ltp != new_ltp:
            print(f" → {symbol}: LTP {script.ltp} → {new_ltp}")
            script.ltp = new_ltp
            changed = True

        if new_date is not None and script.ltpdate != new_date:
            print(f" → {symbol}: LTPDATE {script.ltpdate} → {new_date}")
            script.ltpdate = new_date
            changed = True

        if changed:
            script.save()
            updated += 1

    print(f"Total scripts updated: {updated}")
    return updated