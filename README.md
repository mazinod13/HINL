Stock_analysis

Stock_analysis is a Django web application built to help users track, analyze, and visualize stock market transactions efficiently. It enables detailed management of stock entries and provides insightful portfolio summaries by stock symbol.

---

Key Features

- Comprehensive Transaction Management: Supports various transaction types including Buy, Sale, IPO, Bonus, Conversion, and more.
- Real-time Financial Calculations: Automatically calculates opening balances, consumption, profit, and closing balances.
- Interactive Dashboard: Filterable views by stock symbol showing detailed transaction data.
- Portfolio Summary: Provides overall summary with total quantities, amounts, average rates, and unrealized profit metrics.
- Editable Entries: Update transactions easily with immediate reflection on calculations.
- Sector and Script Support: Categorizes stocks by sector and script for better organization.

---

Prerequisites

- Python 3.7+
- MySQL Server
- Git

---

Installation & Setup

1. Clone the repository:
    git clone https://github.com/mazinod13/HINL.git
    cd stock_analysis

2. Create and activate a virtual environment:
    python3 -m venv venv
    source venv/bin/activate       # Linux/macOS
    venv\Scripts\activate          # Windows

3. Install dependencies:
    pip install -r requirements.txt

4. Configure MySQL Database:
    - Create a MySQL database named stock_analysis.
    - Create a database user (e.g., stock_user) with proper privileges.
    - Update your Django settings.py file to include your MySQL credentials:

    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': database_name',
            'USER': 'your_username',
            'PASSWORD': 'your_password',
            'HOST': 'localhost',
            'PORT': '3306',
        }
    }

5. Apply migrations:
    python manage.py migrate

6. Create a superuser to access Django admin:
    python manage.py createsuperuser

7. Run the development server:
    python manage.py runserver

---

Usage

- Access the dashboard at http://127.0.0.1:8000/
- Filter stock entries by symbol.
- Add, edit, or delete transaction entries.
- View detailed portfolio summaries and real-time profit calculations.

---

Additional Notes

- Make sure to install the MySQL Python driver, typically mysqlclient:
    pip install mysqlclient
- For any database connection issues, verify your MySQL user permissions and firewall settings.

---




