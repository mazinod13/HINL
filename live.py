# live.py
from livereload import Server
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stock_analysis.settings')

def start():
    from django.core.wsgi import get_wsgi_application
    return get_wsgi_application()

server = Server(start())

# Watch relevant file types
server.watch('templates/')
server.watch('static/')
server.watch('**/*.py')

# Start livereload server on port 5500
server.serve(port=5500, host='127.0.0.1', liveport=35729, open_url_delay=True)
