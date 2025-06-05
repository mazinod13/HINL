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

import csv
import json

def parse_date(d):
    try:
        return datetime.strptime(d, "%d-%m-%Y").date()
    except Exception as e:
        print("Date parse error:", e)
        return None

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

def entry_sheet_editable_list(request):
    if request.method == 'POST':
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
                    # Cast values to appropriate types
                    if field == "date":
                        value = datetime.strptime(value, "%Y-%m-%d").date()
                    elif field in ["kitta"]:
                        value = int(value) if value else 0
                    elif field in ["rate", "billed_amount"]:
                        value = float(value) if value else 0.0

                    setattr(entry, field, value)
                except Exception as e:
                    messages.error(request, f"Error setting {field} for entry {entry_id}: {e}")

        for entry in updated_entries.values():
            entry.save()

        # Handle new entry creation
        if request.POST.get('new_symbol'):
            try:
                new_entry = EntrySheet(
                    date=parse_date(request.POST.get('new_date')),
                    symbol=request.POST.get('new_symbol'),
                    script=request.POST.get('new_script'),
                    sector=request.POST.get('new_sector'),
                    transaction_type=request.POST.get('new_transaction_type'),
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
    if request.method == "POST":
        csv_file = request.FILES.get("csv_file")
        if not csv_file.name.endswith('.csv'):
            messages.error(request, "This is not a CSV file.")
            return redirect('cms:upload_csv')

        decoded_file = csv_file.read().decode('utf-8').splitlines()
        reader = csv.DictReader(decoded_file)

        for row in reader:
            EntrySheet.objects.create(
                date=row['date'],
                symbol=row['symbol'],
                script=row['script'],
                sector=row['sector'],
                transaction_type=row['transaction_type'],
                kitta=row['kitta'],
                billed_amount=row['billed_amount'],
                rate=row['rate'],
                broker=row['broker'],
            )
        messages.success(request, "CSV uploaded successfully.")
        return redirect('cms:entrysheet_list')

    return render(request, 'cms/upload_csv.html')

#-----DASHBOARD---------#
class DashboardView(View):
    def get(self, request, symbol=None):
        symbols = EntrySheet.objects.values_list('symbol', flat=True).distinct()

        if not symbol:
          if symbols:
              return redirect('cms:dashboard_detail', symbol=symbols[0])
        else:
           return render(request, 'cms/dashboard.html', {'rows': [], 'symbols': [], 'current_symbol': None})


        entries = EntrySheet.objects.filter(symbol=symbol)

        # Aggregate values
        op_qty = entries.filter(transaction='Balance bd').aggregate(total=Sum('kitta'))['total'] or 0
        op_amount = entries.filter(transaction='Balance bd').aggregate(total=Sum('billed_amount'))['total'] or 0

        p_entries = entries.filter(transaction__in=[
            'Buy', 'IPO', 'FPO', 'Bonus', 'Right', 'Conversion(+)', 'Suspense(+)'
        ])
        p_qty = p_entries.aggregate(total=Sum('kitta'))['total'] or 0
        p_amount = p_entries.aggregate(total=Sum('billed_amount'))['total'] or 0

        s_entries = entries.filter(transaction__in=[
            'Sale', 'Conversion(-)', 'Suspense(-)'
        ])
        s_qty = s_entries.aggregate(total=Sum('kitta'))['total'] or 0
        s_amount = s_entries.aggregate(total=Sum('billed_amount'))['total'] or 0

        cl_qty = op_qty + p_qty - s_qty

        op_rate = (op_amount / op_qty) if op_qty else 0
        p_rate = (p_amount / p_qty) if p_qty else 0
        s_rate = (s_amount / s_qty) if s_qty else 0

        avg_buy_rate = p_rate if p_qty else op_rate
        cl_rate = avg_buy_rate
        cl_amount = cl_qty * cl_rate

        consumption = (op_amount + p_amount) - cl_amount
        profit = s_amount - consumption

        rows = []
        for e in entries:
            rows.append({
                'id': e.id,
                'symbol': e.symbol,
                'date': e.date,
                'transaction': e.transaction,
                'qty': e.kitta,
                't_amount': e.billed_amount,
                'rate': e.rate,
                'op_qty': op_qty,
                'op_rate': op_rate,
                'op_amount': op_amount,
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
            })

        return render(request, 'cms/dashboard.html', {
            'rows': rows,
            'symbols': symbols,
            'current_symbol': symbol
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