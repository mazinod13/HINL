from datetime import date
from django.db import models
#cms_entrysheet
class EntrySheet(models.Model):
    TRANSACTION_CHOICES = [
        ('Buy', 'buy'),
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

    unique_id = models.CharField(max_length=50, unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.unique_id and self.date and self.symbol:
            formatted_date = self.date.strftime('%Y%m%d')  # e.g., 20250606
            self.unique_id = f"{self.symbol}{formatted_date}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.date} - {self.symbol} - {self.transaction}"


#cms_calculation
class Calculation(models.Model):
    entry = models.OneToOneField(
    'EntrySheet',
    on_delete=models.CASCADE,
    to_field='unique_id',
    db_column='entry_unique_id',
    primary_key=True,
    default='00000000abc'  
)
    op_qty = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    op_rate = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    op_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    p_qty = models.IntegerField(default=0)
    p_rate = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    p_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    s_qty = models.IntegerField(default=0)
    s_rate = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    s_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    consumption = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    profit = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    cl_qty = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cl_rate = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    cl_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    def __str__(self):
        return f"Calculation for {self.entry.unique_id}"


#scripts------------
class Script(models.Model):
    symbol = models.CharField(max_length=16, unique=True)
    script_name = models.CharField(max_length=128)
    sector = models.CharField(max_length=64)
    ltp    = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    

    def __str__(self):
        return f"{self.symbol} - {self.script_name}"
