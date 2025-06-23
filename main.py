import threading
import logging
from app import create_app
from app import initialise_modules
from app.temperature_functions import background_loop_temperature
from app.meloir_functions import periodic_query_readings, periodic_query_vatican_news, periodic_query_perplexity  
import os
from app.utilities import log_msg

##################################################################
# SET UP LOGGING
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

##################################################################
# CREATE APP
log_msg('Starting the app...')
log_msg('*starting the app*')
app = create_app()
log_msg('*app created*')

##################################################################
# SCHEDULE TASKS
def start_background_threads():
    # Define functions to be called at regular intervals
    print('--- beginning of function for background threads')
    for func in [background_loop_temperature, periodic_query_readings, periodic_query_vatican_news, periodic_query_perplexity]:
        try:
            logging.info(f"Starting background thread: {func.__name__}")
            print(f"--Starting background thread: {func.__name__}")
            thread = threading.Thread(target=func, name=func.__name__, daemon=True)
            thread.start()
        except Exception as e:
            logging.error(f"Failed to start thread {func.__name__}: {e}")
    print('--- end of function for background threads')

##################################################################
# MAIN
    initialise_modules()
    log_msg('*modules initialised*')
    log_msg('... started')
    log_msg('Starting background threads...')
    start_background_threads()
    log_msg('...done')
    is_local = False
    env_var = os.getenv("LOCAL_LAPTOP")
    if not (env_var is None):
        if env_var != '':
            is_local = True
            print('//-- local details: --->.  <' + str(env_var) + '>')
    if is_local:
        log_msg('* is local *')
        log_msg('type of environment variable: '+str(type(env_var)))
        log_msg('value of environment variable: <'+str(env_var) + '>')
        log_msg("Starting Flask server locally on port 5050")
        app.run(debug=True, port=5050)
        log_msg("Flask server started")
    else:
        log_msg('* on server *')
        log_msg("Starting Flask server on remote location")
        port = int(os.environ.get("PORT", 10000))
        log_msg('Port = ' + str(port))
        app.run(host="0.0.0.0", port=port)
        log_msg("Flask server started")
    
