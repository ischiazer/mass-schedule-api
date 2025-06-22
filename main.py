import threading
import logging
from app import create_app
from app import initialise_modules
from app.temperature_functions import background_loop_temperature
from app.meloir_functions import periodic_query_readings, periodic_query_vatican_news, periodic_query_perplexity  
import os

##################################################################
# SET UP LOGGING
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

##################################################################
# SCHEDULE TASKS
def start_background_threads():
    if False:
        # Define functions to be called at regular intervals
        for func in []: #[background_loop_temperature, periodic_query_readings, periodic_query_vatican_news, periodic_query_perplexity]:
            try:
                logging.info(f"Starting background thread: {func.__name__}")
                thread = threading.Thread(target=func, name=func.__name__, daemon=True)
                thread.start()
            except Exception as e:
                logging.error(f"Failed to start thread {func.__name__}: {e}")
    else:
        print('No background\n\n\n')

##################################################################
# MAIN
if __name__ == "__main__":
    logging.info('Starting the app...')
    print('*starting the app*')
    app = create_app()
    print('*app created*')
    initialise_modules()
    print('*modules initialised*')
    logging.info('... started')
    logging.info('Starting background threads...')
    start_background_threads()
    logging.info('...done')
    if os.getenv("LOCAL_LAPTOP")=='':
        print('* on server *')
        logging.info("Starting Flask server on remote location")
        port = int(os.environ.get("PORT", 10000))
        logging.info('Port = ' + str(port))
        app.run(host="0.0.0.0", port=port)
        logging.info("Flask server started")
    else:
        print('* is local *')
        logging.info("Starting Flask server locally on port 5050")
        app.run(debug=True, port=5050)
        logging.info("Flask server started")
    
