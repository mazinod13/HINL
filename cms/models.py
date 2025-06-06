# cms/models.py

import uuid

from django.db import models

class EntrySheet(models.Model):
    TRANSACTION_CHOICES = [
        ('Buy', 'Buy'),
        ('Sale', 'Sale'),
        ('balance b/d', 'Balance b/d'),
        ('IPO', 'IPO'),
        ('FPO', 'FPO'),
        ('Bonus', 'Bonus'),
        ('Right', 'Right'),
        ('Conversion(+)', 'Conversion(+)'),
        ('Conversion(-)', 'Conversion(-)'),
        ('Suspense(+)', 'Suspense(+)'),
        ('Suspense(-)', 'Suspense(-)'),
    ]
    # models.py
    unique_id = models.CharField(max_length=50, unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.unique_id:
            formatted_date = self.date.strftime('%Y%m%d')  # e.g., 20250606
            self.unique_id = f"{self.symbol}{formatted_date}"
        super().save(*args, **kwargs)
    date = models.DateField()
    symbol = models.CharField(max_length=150)
    script = models.CharField(max_length=150)
    sector = models.CharField(max_length=150)

    transaction = models.CharField(
        max_length=20,
        choices=TRANSACTION_CHOICES,
        default='Buy'
    )

    kitta = models.IntegerField()
    billed_amount = models.DecimalField(max_digits=12, decimal_places=2)
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    broker = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.date} - {self.symbol} - {self.transaction}"


class DashboardEntry(models.Model):
    entry = models.ForeignKey(EntrySheet, on_delete=models.CASCADE, related_name="dashboard_entries")

    # Raw Entry Data
    date = models.DateField()
    transaction = models.CharField(max_length=20)
    qty = models.IntegerField()
    t_amount = models.DecimalField(max_digits=12, decimal_places=2)
    rate = models.DecimalField(max_digits=10, decimal_places=2)

    # Opening
    op_qty = models.IntegerField(default=0)
    op_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    op_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    # Purchase
    p_qty = models.IntegerField(default=0)
    p_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    p_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    # Sale
    s_qty = models.IntegerField(default=0)
    s_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    s_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    # Derived
    consumption = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    profit = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    # Closing
    cl_qty = models.IntegerField(default=0)
    cl_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    cl_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.entry.symbol} - {self.date} - {self.transaction}"
