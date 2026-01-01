from flask import Flask
from flask_cors import CORS
import logging
import nest_asyncio
from .meloir import meloir_initialise
from .temperature_functions import background_loop_temperature
from .meloir_functions import periodic_query_readings, periodic_query_vatican_news, periodic_query_perplexity
from .berger import berger_initialise
from .utilities import log_msg
import threading


##################################################################
# BLUEPRINT REGISTRATIONS
def register_blueprints(app):
    log_msg('/ register_bluperint function/')
    from .berger import bp_berger
    from .meloir import bp_meloir
    from .temperature import bp_temperature
    from .bike import bp_bike
    from .berger_cinema import bp_cinema

    app.register_blueprint(bp_berger, url_prefix="")
    app.register_blueprint(bp_meloir, url_prefix="")
    app.register_blueprint(bp_temperature, url_prefix="")
    app.register_blueprint(bp_bike, url_prefix="")
    app.register_blueprint(bp_cinema, url_prefix="")
    log_msg('/ end of register_bluperint function/')

##################################################################
# APP INITIALISATION
def create_app():
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("log.txt")
        ]
    )
    log_msg('create_app: baseic config  done')

    # Start the app
    log_msg('create_app: starting')
    app = Flask(__name__)
    log_msg('create_app: Flask started')

    # Register the blue prints
    register_blueprints(app)
    log_msg('Executed register_blueprints')

    # Set max file upload size to 10 MB
    app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024
    log_msg('create_app: config done')

    # Enable CORS for all routes
    CORS(app, resources={r"/*": {"origins": "*"}})
    log_msg('create_app: CORS done')

    # Enable async handling
    nest_asyncio.apply()
    log_msg('create_app: best_async done')

    # Set up background looping tasks
    if False:
        for f in [periodic_query_readings, periodic_query_vatican_news, periodic_query_perplexity,background_loop_temperature]:
            thread = threading.Thread(target=f, daemon=True)
            thread.start()
    log_msg('create_app: returning app')
    return app

##################################################################
# MODULE-LEVEL INITIALISATION
def initialise_modules():
    berger_initialise()
    meloir_initialise()
