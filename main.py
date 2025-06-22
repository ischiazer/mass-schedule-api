import threading
import logging
from app import create_app
from app.temperature_functions import background_loop_temperature
from app.some_module import periodic_query_readings, periodic_query_vatican_news, periodic_query_perplexity  # adjust as needed

##################################################################
# SET UP LOGGING
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

##################################################################
# SCHEDULE TASKS
def start_background_threads():
    background_tasks = [
        background_loop_temperature,
        periodic_query_readings,
        periodic_query_vatican_news,
        periodic_query_perplexity
    ]
    # Define functions to be called at regular intervals
    for func in [background_loop_temperature, periodic_query_readings, periodic_query_vatican_news, periodic_query_perplexity]:
        try:
            logging.info(f"Starting background thread: {func.__name__}")
            thread = threading.Thread(target=func, name=func.__name__, daemon=True)
            thread.start()
        except Exception as e:
            logging.error(f"Failed to start thread {func.__name__}: {e}")

##################################################################
# MAIN
if __name__ == "__main__":
    app = create_app()
    start_background_threads()

    logging.info("Starting Flask server on http://0.0.0.0:10000")
    app.run(host="0.0.0.0", port=10000)
    logging.info("Flask server started")
    
