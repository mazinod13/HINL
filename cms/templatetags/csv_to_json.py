import csv, json, os
from django import template
from django.conf import settings

register = template.Library()

@register.simple_tag
def csv_map_json():
    csv_path = os.path.join(settings.BASE_DIR, 'templates', 'cms', 'script_symbol_map.csv')
    symbol_to_script = {}

    try:
        with open(csv_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                raw_symbol = row.get('Symbol', '').strip()
                raw_script = row.get('Script', '').strip()

                symbol = raw_symbol.replace('"', '').upper()
                script = raw_script.replace('"', '')

                if symbol:
                    symbol_to_script[symbol] = script

    except FileNotFoundError:
        symbol_to_script = {"error": "file not found"}
    except Exception as e:
        symbol_to_script = {"error": str(e)}

    return json.dumps(symbol_to_script)
