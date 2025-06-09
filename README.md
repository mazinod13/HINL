Stock_analysis
Stock_analysis is a Django-based web application designed to help users track, analyze, and visualize stock market entries. It supports detailed transaction tracking, profit and loss calculations, and portfolio summaries by symbol.

Features
View and manage stock transactions such as Buy, Sale, IPO, Bonus, and more.

Real-time calculations for opening balance, consumption, profit, and closing balance.

Dashboard view filtered by stock symbol with detailed transaction rows.

Summary statistics including total quantities, amounts, rates, and unrealized profits.

Editable transaction entries with instant updates.

Support for multiple stock sectors and scripts.

steps:
git clone https://github.com/mazinod13/HINL.git
cd stock_analysis
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver


//fill with your SQL server info
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'stock_analysis',
        'USER': 'stock_user',
        'PASSWORD': 'your_password',
        'HOST': 'localhost',
        'PORT': '3306',
    }
}

