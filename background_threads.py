import threading
from app.temperature_functions import background_loop_temperature
from app.meloir_functions import periodic_query_readings, periodic_query_vatican_news, periodic_query_perplexity, periodic_query_mass_schedule
from app.utilities import log_msg


##################################################################
# SCHEDULE TASKS
def start_background_threads():
    # Define functions to be called at regular intervals
    print('--- beginning of function for background threads')
    for func in [background_loop_temperature, periodic_query_readings, periodic_query_vatican_news, periodic_query_perplexity, periodic_query_mass_schedule]:
        try:
            log_msg(f"Starting background thread: {func.__name__}")
            print(f"--Starting background thread: {func.__name__}")
            thread = threading.Thread(target=func, name=func.__name__, daemon=True)
            thread.start()
        except Exception as e:
            log_msg(f"Failed to start thread {func.__name__}: {e}")
    log_msg('--- end of function for background threads')

