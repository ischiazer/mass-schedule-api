import threading
from app.temperature_functions import background_loop_temperature
from app.meloir_functions import periodic_query_readings, periodic_query_vatican_news, periodic_query_perplexity, periodic_query_mass_schedule
from app.utilities import log_msg
import os
import glob
_background_started = False


_app = None

##################################################################
# APP
def set_flask_app(app):
    global _app
    _app = app


##################################################################
# CHECK WHETHER THE CURRENT WORKER IS THE PRIMARY ONE
# (THE ONLY ONE ALLOWED TO START BACKGROUND THREADS)
def is_primary_worker():
    try:
        fd = os.open("/tmp/primary_worker.lock", os.O_CREAT | os.O_EXCL | os.O_RDWR)
        os.write(fd, str(os.getpid()).encode())
        return True
    except FileExistsError:
        return False

##################################################################
# SCHEDULE TASKS
