# cms/urls.py
from django.urls import path
from .views import (
    HomeView,
    EntrySheetListView,
    EntrySheetCreateView,
    EntrySheetDeleteView,
    EntrySheetUpdateView,
    DashboardView,
    TopStockListView,
    script_json,
    entry_sheet_editable_list,
    add_script,
    upload_csv,
)

app_name = 'cms'

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('entries/', EntrySheetListView.as_view(), name='entrysheet_list'),
    path('entries/<int:pk>/edit/', EntrySheetUpdateView.as_view(), name='entry_edit'),
    path('entries/<int:pk>/delete/', EntrySheetDeleteView.as_view(), name='entry_delete'),
    path('entries/add/', EntrySheetCreateView.as_view(), name='entrysheet_create'),
    path('entries/editable/', entry_sheet_editable_list, name='entrysheet_editable_list'),
    path('upload-csv/', upload_csv, name='upload_csv'),
    path('dashboard/',DashboardView.as_view(),name='dashboard'),
    path('dashboard/<str:symbol>/', DashboardView.as_view(), name='dashboard_detail'),
    path('stocks/', TopStockListView.as_view(), name='stock_list'),
    path('scripts/json/', script_json, name='script_json'),
    path('scripts/add/', add_script, name='script_add'),
]
