from flask import Flask
from flask_cors import CORS
import logging
import nest_asyncio
from .temperature import bp_temperature
from .meloir import bp_meloir
from .temperature_functions import background_loop_temperature
from .meloir_functions import periodic_query_readings, periodic_query_vatican_news, periodic_query_perplexity
import threading

##################################################################
# APP INITIALISATION
def create_app():
    # Start the app
    app = Flask(__name__)

    # Register the blue prints
    app.register_blueprint(bp_meloir)
    app.register_blueprint(bp_temperature)

    # Set max file upload size to 10 MB
    app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

    # Enable CORS for all routes
    CORS(app, resources={r"/*": {"origins": "*"}})

    # Enable async handling
    nest_asyncio.apply()

    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("log.txt")
        ]
    )


    # Set up background looping tasks
    for f in [periodic_query_readings, periodic_query_vatican_news, periodic_query_perplexity,background_loop_temperature]:
        thread = threading.Thread(target=f, daemon=True)
        thread.start()
    return app


##################################################################
# MAIN LOOP

if __name__ == "__main__":
    # Create the app
    app = create_app()


    # Run the app
    app.run(host="0.0.0.0", port=10000)
    logging.info("App started and running on port 10000")
