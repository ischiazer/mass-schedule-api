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
    pids = [int(os.path.basename(p)) for p in glob.glob("/proc/[0-9]*") if os.path.isdir(p)]
    min_pid = min(pids) if pids else None
    return os.getpid() == min_pid

##################################################################
# SCHEDULE TASKS
def start_background_threads():
    global _background_started
    if _background_started:
        return
    _background_started = True    

    if not is_primary_worker():
        log_msg(f"Skipping background threads in worker PID {os.getpid()}")
        return
    log_msg(f"Starting background threads in primary worker PID {os.getpid()}")
    for func in [background_loop_temperature, periodic_query_readings, periodic_query_vatican_news, periodic_query_perplexity, periodic_query_mass_schedule]:
        try:
            log_msg(f"Starting background thread: {func.__name__}")
            print(f"--Starting background thread: {func.__name__}")
            thread = threading.Thread(target=func, name=func.__name__, daemon=True)
            thread.start()
        except Exception as e:
            log_msg(f"Failed to start thread {func.__name__}: {e}")
    log_msg('--- end of function for background threads')

