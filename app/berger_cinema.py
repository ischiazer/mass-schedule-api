import asyncio
import logging
import nest_asyncio, os, pytz, asyncio,time
from .cinema_functions import run_cinema_update, get_cinema_html_stored
from .utilities import throw_static_file, log_msg
from flask import Blueprint
import os

##################################################################
# REGISTER BLUEPRINT
bp_cinema = Blueprint("cinema_bp", __name__)

##################################################################
# QUERY - FETCH CURRENT TEMPERATURE
@bp_cinema.route('/force_update_cinema')
def query_current_cinema():
    log_msg(f"Force cinema update  pid= {os.getpid()}")
    try:
        run_cinema_update()
        return 'Done'
    except Exception as e:
        logging.error(f"Cinema update failed: {e}")
        return f"Error update cinema: {e}", 500


##################################################################
# REGULAR CALL TO THE CINEMA UPDATE FUNCTION
def periodic_cinema_update():
    log_msg('Entering background function periodic_cinema_update ')
    log_msg('periodic_cinema_update sleep')
    time.sleep(1)
    log_msg('periodic_cinema_update sleep end')
    while True:
        log_msg('periodic_cinema_update loop step ')
        try:
            run_cinema_update()
        except Exception as e:
            log_msg('Error in periodic_cinema_update update: ' + str(e))
        else:
            log_msg('periodic_cinema_update update done')
        time.sleep(12 * 60 * 60)

##################################################################
# QUERY - FETCH CINEMA HTML
@bp_cinema.route('/get_cinema_html')
def get_cinema_html():
    return get_cinema_html_stored()
