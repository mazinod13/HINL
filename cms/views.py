from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, CreateView, TemplateView,UpdateView,DeleteView
from django.urls import reverse_lazy
from django.contrib import messages
from datetime import datetime
from django.views import View
from django.http import JsonResponse
from .models import EntrySheet,Calculation,Script
import csv
import json
import random
import string

#-----Script-----
def script_json(request):
    scripts = Script.objects.all().values('symbol', 'script_name', 'sector')
    data = list(scripts)
    return JsonResponse(data, safe=False)

#----unique id----
def generate_suffix(length=3):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=length))

def generate_unique_id(date_obj):
    date_str = date_obj.strftime('%Y%m%d')
    while True:
        suffix = generate_suffix()
        unique_id = f"{date_str}{suffix}"
        if not EntrySheet.objects.filter(unique_id=unique_id).exists():
            return unique_id

# Home view
class HomeView(TemplateView):
    template_name = "cms/home.html"

# Read-only list view (standard ListView)
class EntrySheetListView(ListView):
    model = EntrySheet
    template_name = "cms/entrysheet_list.html"
    context_object_name = "entries"
    
# Optional form-based create view (can be replaced by inline editable view)
class EntrySheetCreateView(CreateView):
    model = EntrySheet
    template_name = "cms/entrysheet_form.html"
    fields = [
        "date",
        "symbol",
        "script",
        "sector",
        "transaction",
        "kitta",
        "billed_amount",
        "rate",
        "broker",
    ]
    success_url = reverse_lazy("cms:entrysheet_list")


def parse_date(d):
    if not d:
        return None
    d = d.strip()
    formats = ["%Y/%m/%d", "%Y-%m-%d", "%d-%m-%Y"]
    for fmt in formats:
        try:
            return datetime.strptime(d, fmt).date()
        except ValueError:
            continue
    print("Date parse error: unsupported format ->", d)
    return None

def entry_sheet_editable_list(request):
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'delete':
            selected_ids = request.POST.get('selected_ids', '')
            if selected_ids:
                ids_to_delete = selected_ids.split(',')
                try:
                    entries_to_delete = EntrySheet.objects.filter(id__in=ids_to_delete)
                    count = entries_to_delete.count()
                    entries_to_delete.delete()
                    messages.success(request, f"{count} entries deleted successfully.")
                except Exception as e:
                    messages.error(request, f"Error deleting entries: {e}")
            else:
                messages.error(request, "No entries selected for deletion.")
            return redirect('cms:entrysheet_editable_list')

        elif action == 'save':
            updated_entries = {}

            # Update existing entries
            for key, value in request.POST.items():
                if key.startswith('entry_') and key.count('_') >= 2:
                    _, entry_id, field = key.split('_', 2)
                    if entry_id not in updated_entries:
                        try:
                            updated_entries[entry_id] = EntrySheet.objects.get(id=entry_id)
                        except EntrySheet.DoesNotExist:
                            continue

                    entry = updated_entries[entry_id]

                    try:
                        if field == "date":
                            value = parse_date(value) if value else None
                        elif field == "kitta":
                            value = int(value) if value else 0
                        elif field in ["rate", "billed_amount"]:
                            value = float(value) if value else 0.0
                        setattr(entry, field, value)
                    except Exception as e:
                        messages.error(request, f"Error setting '{field}' to '{value}' for entry {entry_id}: {e}")

            for entry in updated_entries.values():
                entry.save()

            # Add new entry
            if request.POST.get('new_symbol', '').strip():
                try:
                    new_date = parse_date(request.POST.get('new_date') or '')
                    new_entry = EntrySheet(
                        date=new_date,
                        symbol=request.POST.get('new_symbol').strip(),
                        script=request.POST.get('new_script'),
                        sector=request.POST.get('new_sector'),
                        transaction=request.POST.get('new_transaction'),
                        kitta=int(request.POST.get('new_kitta') or 0),
                        billed_amount=float(request.POST.get('new_billed_amount') or 0.0),
                        rate=float(request.POST.get('new_rate') or 0.0),
                        broker=request.POST.get('new_broker'),
                    )

                    new_entry.save()
                    messages.success(request, "New entry added successfully.")
                except Exception as e:
                    messages.error(request, f"Error creating new entry: {e}")

            messages.success(request, "Entries saved successfully.")
            return redirect('cms:entrysheet_editable_list')

    # GET request
    entries = EntrySheet.objects.all().order_by('-date')
    return render(request, 'cms/entrysheet_list_editable.html', {'entries': entries})
class EntrySheetUpdateView(UpdateView):
    model = EntrySheet
    template_name = 'cms/entrysheet_edit.html'
    fields = '__all__'
    success_url = reverse_lazy('cms:entrysheet_list')

class EntrySheetDeleteView(DeleteView):
    model = EntrySheet
    template_name = 'cms/entrysheet_delete.html'
    success_url = reverse_lazy('cms:entrysheet_list')
    

def upload_csv(request):
    if request.method == "POST" and request.FILES.get("csv_file"):
        print("DEBUG: CSV file detected in POST")
        csv_file = request.FILES["csv_file"]
        decoded_file = csv_file.read().decode("utf-8").splitlines()
        reader = csv.DictReader(decoded_file)

        def safe_int(value):
            if value and value.strip():
                value = value.replace(',', '')
                return int(value)
            return 0

        def safe_float(value):
            if value and value.strip():
                value = value.replace(',', '')
                return float(value)
            return 0.0

        for row in reader:
            try:
                date_str = row.get("date", "").strip()
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else None
                unique_id = generate_unique_id(date_obj) if date_obj else None

                EntrySheet.objects.create(
                    unique_id=unique_id,
                    date=date_obj,
                    symbol=row.get("symbol", "").strip(),
                    script=row.get("script", "").strip(),
                    sector=row.get("sector", "").strip(),
                    transaction=row.get("transaction", "").strip(),
                    kitta=safe_int(row.get("kitta", "")),
                    billed_amount=safe_float(row.get("billed_amount", "")),
                    rate=safe_float(row.get("rate", "")),
                    broker=row.get("broker", "").strip(),
                )
            except Exception as e:
                messages.error(request, f"Error processing row {row}: {e}")
                print(f"ERROR processing row {row}: {e}")
                continue

        messages.success(request, "CSV uploaded and entries created successfully.")
        return redirect("cms:entrysheet_list")

    print("DEBUG: Rendering upload_csv.html template")
    return render(request, "cms/upload_csv.html")


#-----Calculation Sheet---------#
class DashboardView(View):
    def get(self, request, symbol=None):
        symbols = EntrySheet.objects.values_list('symbol', flat=True).distinct()

        if not symbol:
            if symbols:
                return redirect('cms:dashboard_detail', symbol=symbols[0])
            else:
                return render(request, 'cms/dashboard.html', {
                    'rows': [],
                    'symbols': [],
                    'current_symbol': None,
                    'summary': {}
                })

        entries = EntrySheet.objects.filter(symbol=symbol).order_by('date', 'transaction', 'id')
        script_name = entries[0].script if entries else ""

        op_qty = 0
        op_amount = 0
        rows = []

        for idx, e in enumerate(entries):
            qty = e.kitta or 0
            amount = e.billed_amount or 0
            transaction = e.transaction

            p_qty = p_amount = s_qty = s_amount = 0
            row_op_qty = op_qty
            row_op_amount = op_amount
            row_op_rate = (row_op_amount / row_op_qty) if row_op_qty else 0

            if transaction.lower() == 'balance b/d':
                row_op_qty = qty
                row_op_amount = amount
                row_op_rate = (amount / qty) if qty else 0
                cl_qty = row_op_qty
                cl_amount = row_op_amount
                cl_rate = row_op_rate
                consumption = profit = p_rate = s_rate = 0
            else:
                if transaction in ['Buy','buy', 'IPO', 'FPO', 'Bonus', 'Right', 'Conversion(+)', 'Suspense(+)','BUY']:
                    p_qty = qty
                    p_amount = amount
                elif transaction in ['Sale','sale', 'Conversion(-)', 'Suspense(-)','SALE']:
                    s_qty = qty
                    s_amount = amount

                cl_qty = row_op_qty + p_qty - s_qty
                consumption = ((p_amount + row_op_amount) / (p_qty + row_op_qty)) * s_qty if (p_qty + row_op_qty) else 0
                cl_amount = row_op_amount + p_amount - consumption
                cl_rate = (cl_amount / cl_qty) if cl_qty else 0
                p_rate = (p_amount / p_qty) if p_qty else 0
                s_rate = (s_amount / s_qty) if s_qty else 0
                profit = s_amount - consumption

            rows.append({
                'id': e.id,
                'symbol': e.symbol,
                'date': e.date,
                'transaction': transaction,
                'qty': qty,
                't_amount': amount,
                'rate': e.rate,
                'unique_id': e.unique_id,

                'op_qty': round(row_op_qty, 2),
                'op_rate': round(row_op_rate, 2),
                'op_amount': round(row_op_amount, 2),
                'p_qty': p_qty,
                'p_rate': round(p_rate, 2),
                'p_amount': round(p_amount, 2),
                's_qty': s_qty,
                's_rate': round(s_rate, 2),
                's_amount': round(s_amount, 2),
                'consumption': round(consumption, 2),
                'profit': round(profit, 2),
                'cl_qty': cl_qty,
                'cl_rate': round(cl_rate, 2),
                'cl_amount': round(cl_amount, 2),
            })

            # Update opening for next loop
            op_qty = cl_qty
            op_amount = cl_amount

            # Save calculations per entry INSIDE the loop
            Calculation.objects.update_or_create(
                entry=e,
                defaults={
                    'op_qty': row_op_qty,
                    'op_rate': row_op_rate,
                    'op_amount': row_op_amount,
                    'p_qty': p_qty,
                    'p_rate': p_rate,
                    'p_amount': p_amount,
                    's_qty': s_qty,
                    's_rate': s_rate,
                    's_amount': s_amount,
                    'consumption': consumption,
                    'profit': profit,
                    'cl_qty': cl_qty,
                    'cl_rate': cl_rate,
                    'cl_amount': cl_amount,
                }
            )

        # Summary calculations
        if rows:
            summary = {
                "start_date": rows[0]["date"],
                "end_date": rows[-1]["date"],
                "total_p_qty": sum(row["p_qty"] for row in rows),
                "total_p_amount": sum(row["p_amount"] for row in rows),
                "total_s_qty": sum(row["s_qty"] for row in rows),
                "total_s_amount": sum(row["s_amount"] for row in rows),
                "closing_qty": rows[-1]["cl_qty"],
                "closing_amount": rows[-1]["cl_amount"],
                "closing_rate": rows[-1]["cl_rate"],
            }
            summary["p_rate"] = summary["total_p_amount"] / summary["total_p_qty"] if summary["total_p_qty"] else 0
            summary["s_rate"] = summary["total_s_amount"] / summary["total_s_qty"] if summary["total_s_qty"] else 0
            summary["profit"] = sum(row.get("profit", 0) for row in rows)

            bep_rate = summary["p_rate"]
            cl_qty = summary["closing_qty"]
            cl_rate = summary["closing_rate"]
            
            
            try:
               ltp = Script.objects.get(symbol=symbol).ltp
            except Script.DoesNotExist:
             ltp = 0

            summary["ltp"] = ltp  # optional: for showing in template

            summary["unrealized_profit"] = cl_qty * (ltp - cl_rate)
            summary["unrealized_percent"] = (
                (summary["unrealized_profit"] / summary["closing_amount"]) * 100
                if summary["closing_amount"] else 0
            )
        else:
            summary = {
                "start_date": "",
                "end_date": "",
                "total_p_qty": 0,
                "total_p_amount": 0,
                "p_rate": 0,
                "total_s_qty": 0,
                "total_s_amount": 0,
                "s_rate": 0,
                "closing_qty": 0,
                "closing_amount": 0,
                "closing_rate": 0,
                "profit": 0,
                "unrealized_profit": 0,
                "unrealized_percent": 0,
                "ltp":0,
            }

        return render(request, 'cms/dashboard.html', {
            'rows': rows,
            'symbols': symbols,
            'current_symbol': symbol,
            'script_name': script_name,
            'summary': summary,
        })

    def post(self, request, symbol=None):
        data = json.loads(request.body.decode('utf-8'))
        for item in data.get('items', []):
            entry_id = item.get('id')
            field = item.get('field')
            value = item.get('value')

            field_map = {
                'transaction': 'transaction',
                'qty': 'kitta',
                't_amount': 'billed_amount',
                'rate': 'rate'
            }

            if field in field_map:
                EntrySheet.objects.filter(id=entry_id).update(**{field_map[field]: value})

        return JsonResponse({'status': 'success'})



#-----TOP STOCKLISTS------
class TopStockListView(View):
    def get(self, request):
        symbols = EntrySheet.objects.values_list('symbol', flat=True).distinct()
        top_stocks = []

        for symbol in symbols:
            entries = EntrySheet.objects.filter(symbol=symbol).order_by('date', 'transaction', 'id')
            if not entries.exists():
                continue

            op_qty = op_amount = 0
            rows = []

            for e in entries:
                qty = e.kitta or 0
                amount = e.billed_amount or 0
                transaction = e.transaction

                p_qty = p_amount = s_qty = s_amount = 0
                row_op_qty = op_qty
                row_op_amount = op_amount

                if transaction.lower() == 'balance b/d':
                    row_op_qty = qty
                    row_op_amount = amount
                    cl_qty = row_op_qty
                    cl_amount = row_op_amount
                    cl_rate = (cl_amount / cl_qty) if cl_qty else 0
                    profit = consumption = 0
                else:
                    if transaction in ['Buy', 'buy', 'IPO', 'FPO', 'Bonus', 'Right', 'Conversion(+)', 'Suspense(+)','BUY']:
                        p_qty = qty
                        p_amount = amount
                    elif transaction in ['Sale', 'sale', 'Conversion(-)', 'Suspense(-)','SALE']:
                        s_qty = qty
                        s_amount = amount

                    total_qty = row_op_qty + p_qty
                    total_amount = row_op_amount + p_amount
                    avg_rate = (total_amount / total_qty) if total_qty else 0
                    consumption = avg_rate * s_qty
                    cl_qty = row_op_qty + p_qty - s_qty
                    cl_amount = total_amount - consumption
                    cl_rate = (cl_amount / cl_qty) if cl_qty else 0
                    profit = s_amount - consumption

                rows.append({
                    'p_qty': p_qty,
                    'p_amount': p_amount,
                    's_qty': s_qty,
                    's_amount': s_amount,
                    'profit': profit,
                    'cl_qty': cl_qty,
                    'cl_amount': cl_amount,
                    'cl_rate': cl_rate,
                })

                op_qty = cl_qty
                op_amount = cl_amount

            # Summary for this symbol
            total_p_qty = sum(row['p_qty'] for row in rows)
            total_p_amount = sum(row['p_amount'] for row in rows)
            total_s_amount = sum(row['s_amount'] for row in rows)
            profit = sum(row['profit'] for row in rows)
            closing_qty = rows[-1]['cl_qty']
            closing_amount = rows[-1]['cl_amount']
            closing_rate = rows[-1]['cl_rate']
            bep = total_p_amount / total_p_qty if total_p_qty else 0

            # Get latest traded price
            try:
                ltp = Script.objects.get(symbol=symbol).ltp
            except Script.DoesNotExist:
                ltp = 0

            unrealized_profit = closing_qty * (ltp - closing_rate)
            unrealized_percent = (unrealized_profit / closing_amount * 100) if closing_amount else 0

            top_stocks.append({
                'symbol': symbol,
                'script': entries.first().script,
                'total_p_amount': total_p_amount,
                'total_p_qty': total_p_qty,
                'total_s_amount': total_s_amount,
                'closing_qty': closing_qty,
                'closing_amount': closing_amount,
                'closing_rate': closing_rate,
                'bep': bep,
                'ltp': ltp,
                'profit': profit,
                'unrealized_profit': unrealized_profit,
                'unrealized_percent': unrealized_percent
            })

        # Sort by realized profit
        top_stocks = sorted(top_stocks, key=lambda x: x['profit'], reverse=True)

        return render(request, 'cms/stock_list.html', {
            'top_stocks': top_stocks
        })

        

#-------Scripts Management---------------

from django.shortcuts import render, redirect
from cms.models import Script

def editable_script_list(request):
    if request.method == 'POST':
        # Update existing scripts
        for script in Script.objects.all():
            new_symbol = request.POST.get(f'symbol_{script.id}', '').strip()
            new_name   = request.POST.get(f'script_name_{script.id}', '').strip()
            new_sector = request.POST.get(f'sector_{script.id}', '').strip()
            new_ltp    = request.POST.get(f'ltp_{script.id}', '').strip()

            changed = False

            if new_symbol and new_symbol != script.symbol:
                script.symbol = new_symbol
                changed = True
            if new_name and new_name != script.script_name:
                script.script_name = new_name
                changed = True
            if new_sector and new_sector != script.sector:
                script.sector = new_sector
                changed = True
            if new_ltp:
                try:
                    new_ltp_val = float(new_ltp)
                    if script.ltp != new_ltp_val:
                        script.ltp = new_ltp_val
                        changed = True
                except ValueError:
                    # If LTP is invalid, you might want to skip or set to None
                    pass

            if changed:
                script.save()

        # Handle new script row
        ns   = request.POST.get('new_symbol', '').strip()
        nn   = request.POST.get('new_script_name', '').strip()
        nsec = request.POST.get('new_sector', '').strip()
        nltp = request.POST.get('new_ltp', '').strip()

        if ns:  # Only add if symbol is provided
            try:
                ltp_val = float(nltp) if nltp else None
            except ValueError:
                ltp_val = None  # Skip if not a valid number

            Script.objects.create(
                symbol=ns,
                script_name=nn,
                sector=nsec,
                ltp=ltp_val
            )

        return redirect('cms:script_list_editable')

    # GET: show existing scripts
    scripts = Script.objects.all()
    return render(request, 'cms/script_list_editable.html', {'scripts': scripts})
