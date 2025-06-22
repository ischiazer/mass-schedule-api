from flask import Flask
from flask_cors import CORS
import logging
import nest_asyncio
from .temperature import bp_temperature
from .meloir import bp_meloir, meloir_initialise
from .temperature_functions import background_loop_temperature
from .meloir_functions import periodic_query_readings, periodic_query_vatican_news, periodic_query_perplexity
from .berger import bp_berger, berger_initialise
import threading

##################################################################
# APP INITIALISATION
def create_app():
    # Start the app
    logging.info('create_app: starting')
    app = Flask(__name__)
    logging.info('create_app: Flask done')

    # Register the blue prints
    logging.info('create_app: registering BPs')
    app.register_blueprint(bp_meloir, url_prefix="")
    app.register_blueprint(bp_temperature, url_prefix="")
    app.register_blueprint(bp_berger, url_prefix="")
    logging.info('create_app: BPs registered')
    print('\n\nRoutes registered:')
    for rule in app.url_map.iter_rules():
        print(f"Registered route: {rule}")
    print('\n\n\n\n')

    # Set max file upload size to 10 MB
    app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

    # Enable CORS for all routes
    CORS(app, resources={r"/*": {"origins": "*"}})
    logging.info('create_app: CORS enabled')

    # Enable async handling
    nest_asyncio.apply()
    logging.info('create_app: asyncio enabled')


    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("log.txt")
        ]
    )

    with app.app_context():
        print("\n\nRegistered routes basd on app.app_context():")
        for rule in app.url_map.iter_rules():
            print(rule)
    # Set up background looping tasks
    if False:
        for f in [periodic_query_readings, periodic_query_vatican_news, periodic_query_perplexity,background_loop_temperature]:
            thread = threading.Thread(target=f, daemon=True)
            thread.start()
    return app

##################################################################
# MODULE-LEVEL INITIALISATION
def initialise_modules():
    berger_initialise()
    meloir_initialise()
