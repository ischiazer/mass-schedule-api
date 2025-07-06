import threading
from app.temperature_functions import background_loop_temperature
from app.meloir_functions import periodic_query_readings, periodic_query_vatican_news, periodic_query_perplexity, periodic_query_mass_schedule
from app.utilities import log_msg
import os
import glob
_background_started = False


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
def start_background_threads():
    global _background_started

    if not is_primary_worker():
        log_msg(f"Skipping background threads in worker PID {os.getpid()}")
        return
    log_msg(f"Starting background threads in primary worker PID {os.getpid()}")
    if _background_started:
        log_msg("The background threads have already been started.")
        return
    _background_started = True    
    for i, func in enumerate([background_loop_temperature, periodic_query_readings, periodic_query_vatican_news, periodic_query_perplexity, periodic_query_mass_schedule]):
        log_msg(f"Starting background thread {i}")
        try:
            log_msg(f"Trying to start  background thread #{i}: {func.__name__}")
            thread = threading.Thread(target=func, name=func.__name__, daemon=True)
            log_msg(f"Progressing #{i}")
            thread.start()
            log_msg(f"Done starting background thread #{i}: {func.__name__}")
        except Exception as e:
            log_msg(f"Failed to start thread #{i} {func.__name__}: {e}")
    log_msg('--- end of function for background threads')

