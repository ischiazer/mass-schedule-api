import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from app.utilities import log_msg

def post_fork(server, worker):
    from app import create_app
    from app.background_threads import set_flask_app, start_background_threads
    log_msg(f"[Gunicorn post_fork] Creating app")
    app = create_app()
    log_msg(f"[Gunicorn post_fork] Setting app reference")
    set_flask_app(app)
    log_msg(f"[Gunicorn post_fork] Starting background threads")
    start_background_threads()
    log_msg(f"[Gunicorn post_fork] Done")
    