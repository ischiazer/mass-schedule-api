import threading
from app.temperature_functions import background_loop_temperature
from app.meloir_functions import periodic_query_readings, periodic_query_vatican_news, periodic_query_perplexity, periodic_query_mass_schedule
from app.bike_functions import periodic_query_bike, periodic_query_dott, periodic_query_all_bikes
from app.berger_confessions import periodic_query_confessions
from app.berger_mass import periodic_query_berger_mass
from app.berger_shops import periodic_query_berger_shops
from app.berger_cinema import periodic_cinema_update
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
def start_background_threads():
    global _background_started

    if not is_primary_worker():
        log_msg(f"Skipping background threads in worker PID {os.getpid()}")
        return
    log_msg(f"Name of app in background_threads = {str(_app)}")
    log_msg(f"Starting background threads in primary worker PID {os.getpid()}")
    if _background_started:
        log_msg("The background threads have already been started.")
        return
    _background_started = True    

    def wrap_async(func):
        log_msg('')
        def wrapper():
            with _app.app_context():
                log_msg(f">>> Starting async function {func.__name__}")
                import asyncio
                asyncio.run(func())
        wrapper.__name__ = func.__name__
        return wrapper

    thread_funcs = [
        lambda: background_loop_temperature(_app),
        periodic_query_readings,
        periodic_query_perplexity,
        periodic_query_vatican_news,
        periodic_query_bike,
        periodic_query_dott,
        periodic_query_all_bikes,
        wrap_async(periodic_query_confessions),
        wrap_async(periodic_query_mass_schedule),  
        wrap_async(periodic_query_berger_mass),
        periodic_query_berger_shops,
        periodic_cinema_update
    ]


    for i, func in enumerate(thread_funcs):
        try:
            log_msg(f"Starting background thread {i}")
            thread = threading.Thread(target=func, name=func.__name__, daemon=True)
            thread.start()
            log_msg(f"Done starting background thread #{i}: {func.__name__}")
        except Exception as e:
            log_msg(f"Failed to start thread #{i} {func.__name__}: {e}")
    
    log_msg('--- end of function for background threads')

