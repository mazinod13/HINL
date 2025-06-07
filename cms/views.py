from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, CreateView, TemplateView,UpdateView,DeleteView
from django.urls import reverse_lazy
from django.contrib import messages
from datetime import datetime
from django.views import View
from django.http import JsonResponse
from django.db.models import DecimalField,IntegerField
from django.db.models import Sum, Case, When, F, Value
from .models import EntrySheet
from uuid import uuid4
import csv
import json

# Home view
class HomeView(TemplateView):
    template_name = "cms/home.html"

# Read-only list view (standard ListView)
class EntrySheetListView(ListView):
    model = EntrySheet
    template_name = "cms/entrysheet_list.html"
    context_object_name = "entries"
#---unique ID----
for entry in EntrySheet.objects.filter(unique_id__isnull=True):
    entry.unique_id = str(uuid4())
    entry.save()
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
        updated_entries = {}

        # === Update existing entries ===
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

        # === Add new entry ===
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

    # === GET request ===
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
        csv_file = request.FILES["csv_file"]
        decoded_file = csv_file.read().decode("utf-8").splitlines()
        reader = csv.DictReader(decoded_file)

        for row in reader:
            try:
                # Convert date string to date object
                date_obj = datetime.strptime(row["date"], "%Y-%m-%d").date()

                # Generate unique_id
                unique_id = f"{date_obj.strftime('%Y%m%d')}{row['symbol']}"

                EntrySheet.objects.create(
                    date=date_obj,
                    symbol=row["symbol"],
                    script=row["script"],
                    sector=row["sector"],
                    transaction=row["transaction"],
                    kitta=int(row["kitta"]),
                    billed_amount=float(row["billed_amount"]),
                    rate=float(row["rate"]),
                    broker=row["broker"],
                    unique_id=unique_id,
                )
            except Exception as e:
                messages.error(request, f"Error processing row {row}: {e}")
                continue

        messages.success(request, "CSV uploaded and entries created successfully.")
        return redirect("cms:entrysheet_list")

    return render(request, "cms/upload_csv.html")
#-----DASHBOARD---------#
from django.views import View
from django.shortcuts import render, redirect
from django.db.models import Sum
from django.http import JsonResponse
import json
from .models import EntrySheet

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

        entries = EntrySheet.objects.filter(symbol=symbol).order_by('date', 'id')
        script_name = entries[0].script if entries else ""

        op_qty = 0
        op_amount = 0
        p_qty = 0
        p_amount = 0
        s_qty = 0
        s_amount = 0

        rows = []

        # Initial values
        op_qty = 0
        op_amount = 0

        for e in entries:
            qty = e.kitta or 0
            amount = e.billed_amount or 0
            transaction = e.transaction

            # Set opening values for this row (from previous closing)
            row_op_qty = op_qty
            row_op_amount = op_amount
            row_op_rate = (row_op_amount / row_op_qty) if row_op_qty else 0

            p_qty = 0
            p_amount = 0
            s_qty = 0
            s_amount = 0

            # Transaction logic
            if transaction == 'Balance b/d':
                row_op_qty += qty
                row_op_amount += amount
            elif transaction in ['Buy', 'IPO', 'FPO', 'Bonus', 'Right', 'Conversion(+)', 'Suspense(+)']:
                p_qty = qty
                p_amount = amount
            elif transaction in ['Sale', 'Conversion(-)', 'Suspense(-)']:
                s_qty = qty
                s_amount = amount

            cl_qty = row_op_qty + p_qty - s_qty
            p_rate = (p_amount / p_qty) if p_qty else 0
            s_rate = (s_amount / s_qty) if s_qty else 0

            if (p_qty + row_op_qty) != 0:
                consumption = ((p_amount + row_op_amount) / (p_qty + row_op_qty)) * s_qty
            else:
                consumption = 0

            cl_amount = row_op_amount + p_amount - consumption
            cl_rate = (cl_amount / cl_qty) if cl_qty else 0
            profit = s_amount - consumption

            rows.append({
                'id': e.id,
                'symbol': e.symbol,
                'date': e.date,
                'transaction': e.transaction,
                'qty': qty,
                't_amount': amount,
                'rate': e.rate,

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

            # Update op_qty/op_amount for next row
            op_qty = cl_qty
            op_amount = cl_amount
        # Summary block should be outside the loop
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
                "closing_rate": rows[-1]["cl_rate"]           
            }
            summary["p_rate"] = summary["total_p_amount"] / summary["total_p_qty"] if summary["total_p_qty"] else 0
            summary["s_rate"] = summary["total_s_amount"] / summary["total_s_qty"] if summary["total_s_qty"] else 0
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
