from django.shortcuts import render, redirect
from django.views.generic import ListView, CreateView, TemplateView,UpdateView,DeleteView
from django.urls import reverse_lazy
from django.contrib import messages
from datetime import datetime
from django.views import View
from django.http import JsonResponse
from .models import EntrySheet,Calculation,Script
from asgiref.sync import sync_to_async
import csv
import json
from .utils import update_scripts_from_google_sheet
from django.urls import reverse

def refresh_scripts(request):
    updated = update_scripts_from_google_sheet()
    messages.success(request, f"{updated} scripts updated.")
    return redirect(reverse("cms:script_list_editable"))

#-----Script-----
def script_json(request):
    scripts = Script.objects.all().values('symbol', 'script_name', 'sector')
    data = list(scripts)
    return JsonResponse(data, safe=False)


# module-level cache for the global suffix
_global_suffix = None

def next_global_unique_id(date_obj):
    global _global_suffix
    if _global_suffix is None:
        # seed from the DB count only once per process
        _global_suffix = EntrySheet.objects.count()
    _global_suffix += 1

    date_str = date_obj.strftime('%Y%m%d')
    return f"{date_str}-{_global_suffix:04d}"

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

        # ─── DELETE ──────────────────────────────────────────────────────────
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

        # ─── SAVE (update + add) ─────────────────────────────────────────────
        elif action == 'save':
            # 1) Prepare an in-memory tracker for suffixes per date
            suffix_tracker = {}  # e.g. { '2024/07/18': 2, ... }

            def next_unique_id(date_obj):
                date_str = date_obj.strftime('%Y/%m/%d')
                # seed from DB only once per date
                if date_str not in suffix_tracker:
                    suffix_tracker[date_str] = EntrySheet.objects.filter(date=date_obj).count()
                # increment and format
                suffix_tracker[date_str] += 1
                return f"{date_str}-{suffix_tracker[date_str]:04d}"

            # 2) Update existing entries
            updated_entries = {}
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
                            parsed = parse_date(value) if value else None
                            setattr(entry, 'date', parsed)
                        elif field == "kitta":
                            setattr(entry, 'kitta', int(value) if value else 0)
                        elif field in ["rate", "billed_amount"]:
                            setattr(entry, field, float(value) if value else 0.0)
                        else:
                            setattr(entry, field, value)
                    except Exception as e:
                        messages.error(request, f"Error setting '{field}' to '{value}' for entry {entry_id}: {e}")
            update_scripts_from_google_sheet()
            for entry in updated_entries.values():
                entry.save()

            # 3) Add new entry (if any)
            if request.POST.get('new_symbol', '').strip():
                try:
                    new_date = parse_date(request.POST.get('new_date') or '')
                    new_symbol = request.POST.get('new_symbol').strip().upper()
                    new_entry = EntrySheet(
                        date=new_date,
                        symbol=new_symbol,
                        script=request.POST.get('new_script', ''),
                        sector=request.POST.get('new_sector', ''),
                        transaction=request.POST.get('new_transaction', ''),
                        kitta=int(request.POST.get('new_kitta') or 0),
                        billed_amount=float(request.POST.get('new_billed_amount') or 0.0),
                        rate=float(request.POST.get('new_rate') or 0.0),
                        broker=request.POST.get('new_broker', ''),
                    )
                    # assign the next unique_id for this date
                    new_entry.unique_id = next_global_unique_id(new_date)
                    new_entry.save()
                    messages.success(request, f"New entry {new_entry.unique_id} added successfully.")
                except Exception as e:
                    messages.error(request, f"Error creating new entry: {e}")

            messages.success(request, "Entries saved successfully.")
            return redirect('cms:entrysheet_editable_list')

    # ─── GET ────────────────────────────────────────────────────────────────
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
    
#----------CSV UPLOAD----------
REQUIRED_COLUMNS = ["date", "symbol", "script", "sector", "transaction", "kitta", "billed_amount", "rate", "broker"]

example_csv = """date,symbol,script,sector,transaction,kitta,billed_amount,rate,broker
2024-07-18,ADBL,Agricultural Development Bank Limited,Commercial Banks,BUY,6856,2182384.56,318.3174679,89
2024-07-24,ADBL,Agricultural Development Bank Limited,Commercial Banks,BUY,5000,1713448.31,342.689662,89
"""

# Flexible date parser
def parse_flexible_date(date_str):
    date_str = date_str.strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Invalid date format: {date_str}")

def upload_csv(request):
    if request.method == "POST" and request.FILES.get("csv_file"):
        csv_file = request.FILES["csv_file"]
        decoded_file = csv_file.read().decode("utf-8").splitlines()
        reader = csv.DictReader(decoded_file)

        # ── Validate header ───────────────────────────────────────────
        missing = [col for col in REQUIRED_COLUMNS if col not in reader.fieldnames]
        if missing:
            messages.error(request, f"CSV missing columns: {', '.join(missing)}")
            return render(request, "cms/upload_csv.html", {"example_csv": example_csv})

        rows = list(reader)
        errors = []

        # ── Row validation (dates & numeric) ─────────────────────────
        for i, row in enumerate(rows, start=2):
            # date parse check
            try:
                _ = parse_flexible_date(row.get("date", "").strip())
            except Exception:
                errors.append(f"Row {i}: Invalid date '{row.get('date')}'")

            # numeric checks
            for field in ("kitta", "billed_amount", "rate"):
                val = row.get(field, "").replace(",", "").strip()
                if val:
                    try:
                        int(val) if field == "kitta" else float(val)
                    except ValueError:
                        errors.append(f"Row {i}: Invalid number in '{field}': {val}")

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, "cms/upload_csv.html", {"example_csv": example_csv})
         #safe converters
        def safe_int(val):
            val = val.replace(',', '').strip()
            return int(val) if val else 0

        def safe_float(val):
            val = val.replace(',', '').strip()
            return float(val) if val else 0.0
        


        # ── Create entries ────────────────────────────────────────────
        for row in rows:
            try:
                date_obj = parse_flexible_date(row["date"].strip())
                symbol   = row["symbol"].strip().upper()
                script   = row["script"].strip()
                sector   = row["sector"].strip()
                uid = next_global_unique_id(date_obj)
                
                # autofill
                if (not script or not sector) and symbol:
                    try:
                        s = Script.objects.get(symbol=symbol)
                        script = script or s.script_name
                        sector = sector or s.sector
                    except Script.DoesNotExist:
                        messages.warning(request, f"No script info for '{symbol}'")
                EntrySheet.objects.create(
                    unique_id   = uid,
                    date        = date_obj,
                    symbol      = symbol,
                    script      = script,
                    sector      = sector,
                    transaction = row["transaction"].strip(),
                    kitta       = safe_int(row["kitta"]),
                    billed_amount = safe_float(row["billed_amount"]),
                    rate        = safe_float(row["rate"]),
                    broker      = row["broker"].strip(),
                )
            except Exception as e:
                messages.error(request, f"Error on row {row}: {e}")
                continue

        messages.success(request, "CSV uploaded and entries created successfully.")
        return redirect("cms:entrysheet_list")
    return render(request, "cms/upload_csv.html", {"example_csv": example_csv})
#-----Calculation Sheet---------#
class CalculaionView(View):
    def get(self, request, symbol=None):
        symbols = EntrySheet.objects.values_list('symbol', flat=True).distinct()

        if not symbol:
            if symbols:
                return redirect('cms:calculationsheet_detail', symbol=symbols[0])
            else:
                return render(request, 'cms/calculationsheet.html', {
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
                if transaction in ['Buy','buy', 'IPO', 'FPO', 'Bonus', 'Right', 'Conversion(+)', 'Suspense(+)','BUY','BONUS','RIGHT']:
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

        return render(request, 'cms/calculationsheet.html', {
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
                    if transaction in ['Buy', 'buy', 'IPO', 'FPO', 'Bonus', 'Right', 'Conversion(+)', 'Suspense(+)','BUY','BONUS','RIGHT']:
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
            if closing_qty < 1:
                bep = 0
            else:
                raw_bep = (closing_amount - profit) / closing_qty
                bep = raw_bep if raw_bep >= 0 else 0


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

def editable_script_list(request):
    if request.method == 'POST':
        action = request.POST.get('action')

        # ─── Handle “Refresh from Google Sheet” ────────────────────
        if action == 'refresh':
            try:
                updated = update_scripts_from_google_sheet()
                messages.success(request, f"{updated} scripts updated from Google Sheet.")
            except Exception as e:
                messages.error(request, f"Error refreshing scripts: {e}")
            return redirect('cms:script_list_editable')

        # ─── Handle “Save Changes” ─────────────────────────────────
        if action == 'save':
            # 1) Update existing scripts
            for script in Script.objects.all():
                changed = False

                # text fields
                new_symbol  = request.POST.get(f'symbol_{script.id}', '').strip()
                new_name    = request.POST.get(f'script_name_{script.id}', '').strip()
                new_sector  = request.POST.get(f'sector_{script.id}', '').strip()

                if new_symbol and new_symbol != script.symbol:
                    script.symbol = new_symbol
                    changed = True
                if new_name and new_name != script.script_name:
                    script.script_name = new_name
                    changed = True
                if new_sector and new_sector != script.sector:
                    script.sector = new_sector
                    changed = True

                # numeric LTP (don’t bail out the row on parse errors)
                new_ltp_raw = request.POST.get(f'ltp_{script.id}', '').strip()
                new_ltp = None
                if new_ltp_raw:
                    try:
                        new_ltp = float(new_ltp_raw)
                    except ValueError:
                        messages.warning(request, f"Invalid LTP for {script.symbol}: {new_ltp_raw}")

                if new_ltp is not None and script.ltp != new_ltp:
                    script.ltp = new_ltp
                    changed = True

                # date LTPDATE
                new_date_raw = request.POST.get(f'ltpdate_{script.id}', '').strip()
                new_date = None
                if new_date_raw:
                    try:
                        new_date = datetime.strptime(new_date_raw, '%Y-%m-%d').date()
                    except ValueError:
                        messages.warning(request, f"Invalid LTP date for {script.symbol}: {new_date_raw}")

                if new_date is not None and script.ltpdate != new_date:
                    script.ltpdate = new_date
                    changed = True

                if changed:
                    script.save()

            # 2) Create the new‐script row if a symbol was given
            ns  = request.POST.get('new_symbol', '').strip()
            if ns:
                nn   = request.POST.get('new_script_name', '').strip()
                nsec = request.POST.get('new_sector', '').strip()
                nltp = request.POST.get('new_ltp', '').strip()
                ndt  = request.POST.get('new_ltpdate', '').strip()

                create_kwargs = {
                    'symbol':      ns,
                    'script_name': nn,
                    'sector':      nsec,
                }

                if nltp:
                    try:
                        create_kwargs['ltp'] = float(nltp)
                    except ValueError:
                        create_kwargs['ltp'] = None

                if ndt:
                    try:
                        create_kwargs['ltpdate'] = datetime.strptime(ndt, '%Y-%m-%d').date()
                    except ValueError:
                        pass

                Script.objects.create(**create_kwargs)
                messages.success(request, f"Added new script {ns}")

            messages.success(request, "Scripts saved.")
            return redirect('cms:script_list_editable')

    # GET: render form
    scripts = Script.objects.all().order_by('id')
    return render(request, 'cms/script_list_editable.html', {
        'scripts': scripts
    })


#---------Final Dashboard--------------
class DashboardView(View):
    template_name = 'cms/dashboard.html'

    async def get(self, request, symbol=None):
        symbols = await sync_to_async(list)(
            EntrySheet.objects.values_list('symbol', flat=True).distinct()
        )

        if not symbol:
            if symbols:
                return redirect('cms:dashboard', symbol=symbols[0])
            else:
                return await sync_to_async(render)(
                    request, self.template_name, {'symbols': symbols}
                )

        # Fetch entries
        entries = await sync_to_async(list)(
            EntrySheet.objects.filter(symbol=symbol).order_by('date', 'id')
        )

        # Process entries to rows
        rows = []
        for entry in entries:
            try:
                calc = await Calculation.objects.aget(entry=entry)
            except Calculation.DoesNotExist:
                continue

            rows.append({
                'id': entry.id,
                'unique_id':entry.unique_id,
                'date': entry.date,
                'transaction': entry.transaction,
                'qty': entry.kitta,
                't_amount': entry.billed_amount,
                'rate': entry.rate,
                'op_qty': calc.op_qty,
                'op_rate': calc.op_rate,
                'p_qty': calc.p_qty,
                'p_amount': calc.p_amount,
                's_qty': calc.s_qty,
                's_amount': calc.s_amount,
                'consumption': calc.consumption,
                'profit': calc.profit,
                'cl_qty': calc.cl_qty,
                'cl_rate': calc.cl_rate,
                'cl_amount': calc.cl_amount,
                'broker': entry.broker,
            })

        # Calculate summary
        total_p_qty = sum(r['p_qty'] for r in rows)
        total_p_amount = sum(r['p_amount'] for r in rows)
        total_s_qty = sum(r['s_qty'] for r in rows)
        total_s_amount = sum(r['s_amount'] for r in rows)
        realized_profit = sum(r['profit'] for r in rows)

        if rows:
            closing_qty = rows[-1]['cl_qty']
            closing_amount = rows[-1]['cl_amount']
            closing_rate = rows[-1]['cl_rate']
        else:
            closing_qty = closing_amount = closing_rate = 0

        try:
            script = await Script.objects.aget(symbol=symbol)
            ltp = script.ltp or 0
            ltpdate = script.ltpdate  
        except Script.DoesNotExist:
            ltp = 0
            ltpdate = None
            
        profit=realized_profit
        unrealized_profit = closing_qty * (ltp - closing_rate) if closing_qty else 0
        if closing_qty < 1:
                bep = 0
        else:
                raw_bep = (closing_amount - profit) / closing_qty
                bep = raw_bep if raw_bep >= 0 else 0

        
         # Totals across all symbols
        total_book_value = 0
        total_market_value = 0
        total_realized_profit = 0
        total_unrealized_profit = 0
        
        for sym in symbols:
            latest_entry = await sync_to_async(
                EntrySheet.objects.filter(symbol=sym).order_by('-date', '-id').first
            )()
            if not latest_entry:
                continue

            try:
                calc = await Calculation.objects.aget(entry=latest_entry)
            except Calculation.DoesNotExist:
                continue

            try:
                script = await Script.objects.aget(symbol=sym)
                sym_ltp = script.ltp or 0
            except Script.DoesNotExist:
                sym_ltp = 0

            total_book_value += calc.cl_amount
            total_market_value += calc.cl_qty * sym_ltp
            total_realized_profit += calc.s_amount-calc.consumption # assuming calc.profit is realized profit for symbol

            # Calculate unrealized profit for symbol
            total_unrealized_profit += calc.cl_qty * (sym_ltp - calc.cl_rate)
        if total_book_value:
                nav = (total_market_value + total_realized_profit) / total_book_value
        else:
                 nav = 0
            
        summary = {
            'total_p_qty': total_p_qty,
            'total_p_amount': total_p_amount,
            'p_rate': (total_p_amount / total_p_qty) if total_p_qty else 0,
            'total_s_qty': total_s_qty,
            'total_s_amount': total_s_amount,
            's_rate': (total_s_amount / total_s_qty) if total_s_qty else 0,
            'closing_qty': closing_qty,
            'closing_amount': closing_amount,
            'closing_rate': closing_rate,
            'realized_profit': realized_profit,
            'unrealized_profit': unrealized_profit,
            'nav': nav,
            'ltp': ltp,
            'ltpdate':ltpdate,
            'bep':bep,
            'total_book_value': total_book_value,
            'total_market_value': total_market_value,
            'total_realized_profit':total_realized_profit,
            'total_unrealized_profit':total_unrealized_profit,
            
            
        }

                # Prepare Top Stocks List
        top_stocks = []
        for sym in symbols:
            latest_entry = await sync_to_async(
                EntrySheet.objects.filter(symbol=sym).order_by('-date', '-id').first
            )()
            if not latest_entry:
                continue

            try:
                calc = await Calculation.objects.aget(entry=latest_entry)
                script = await Script.objects.aget(symbol=sym)
            except (Calculation.DoesNotExist, Script.DoesNotExist):
                continue

            ltp = script.ltp or 0
            cl_qty = calc.cl_qty
            cl_amount = calc.cl_amount
            cl_rate = calc.cl_rate
            profit = calc.s_amount - calc.consumption

            bep = (cl_amount - profit) / cl_qty if cl_qty else 0
            unrealized_profit = cl_qty * (ltp - cl_rate)
            unrealized_percent = ((ltp - cl_rate) / cl_rate) * 100 if cl_rate else 0

            top_stocks.append({
                'symbol': sym,
                'closing_qty': cl_qty,
                'closing_amount': cl_amount,
                'closing_rate': cl_rate,
                'bep': bep,
                'profit': profit,
                'unrealized_profit': unrealized_profit,
                'unrealized_percent': unrealized_percent,
            })

        # Optionally sort by unrealized profit
        top_stocks = sorted(top_stocks, key=lambda x: x['unrealized_profit'], reverse=True)

        context = {
            'symbols': symbols,
            'all_symbols': symbols,
            'current_symbol': symbol,
            'rows': rows,
            'summary': summary,
            'top_stocks': top_stocks,
            
        }

        return await sync_to_async(render)(request, self.template_name, context)

    async def post(self, request, symbol=None):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)

        field_map = {
            'qty': 'kitta',
            't_amount': 'billed_amount',
            'rate': 'rate',
        }

        for item in data.get('items', []):
            eid = item.get('id')
            field = item.get('field')
            value = item.get('value')

            if field in field_map and eid:
                await sync_to_async(
                    EntrySheet.objects.filter(id=eid).update
                )(**{field_map[field]: value})

        return JsonResponse({'status': 'ok'})