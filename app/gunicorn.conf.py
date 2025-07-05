import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from app.utilities import log_msg

def post_fork(server, worker):
    from background_threads import start_background_threads

    log_msg(f"[Gunicorn post_fork] Starting background threads in worker PID {worker.pid}")
    start_background_threads()
