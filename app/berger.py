from flask import Blueprint, request
from .berger_functions import get_berger_HTML_style
from .berger_functions import get_historical_bookings_HTML,dump_bookings_HTML,get_single_booking_confirmation_HTML,berger_create_new_booking,berger_booking_not_found,get_email_from_booking_code, berger_delete_booking,get_new_booking_selection_HTML
from .berger_functions import send_html_email
from .berger_functions import DB_NAME, HASHED_PASSWORD, BASE_FOLDER
from .utilities import download_file_from_b2_if_absent
from flask import request, jsonify, send_file, Response
import logging

##################################################################
# REGISTER BLUEPRINT
bp_berger = Blueprint("bp_berger", __name__)
logging.info('BP Berger started')
print("Registering bp_berger") 

##################################################################
# INITIALISATION OF MODULE
def berger_initialise():
    print('Checking if Berger DB is present...')
    download_file_from_b2_if_absent('berger',DB_NAME, DB_NAME)
    print('...done')

##################################################################
# QUERY - Process request for synthetic summary
@bp_berger.route("/berger_web_calendar_summary", methods=["GET"])
def berger_web_calendar_summary():
    logging.info("Berger - getting web_calendar_summary...")
    html = get_historical_bookings_HTML()
    logging.info('...done')
    return html

##################################################################
# QUERY - Process request for dump
@bp_berger.route("/berger_web_dump", methods=["GET"])
def berger_web_dump():
    logging.info("Berger - getting web_dump...")
    html = dump_bookings_HTML()
    logging.info('...done')
    return html

##################################################################
# QUERY - Process request for recap of existing booking
@bp_berger.route("/berger_web_booking_recap", methods=["GET"])
def berger_web_booking_recap():
    logging.info("Berger - getting web_booking_recap...")
    booking_code = request.args.get("booking_code", "")
    booking_code = booking_code.upper().strip()
    html = get_single_booking_confirmation_HTML(booking_code, 'check')
    logging.info('...done')
    if html is None:
        html = berger_booking_not_found(booking_code)
    return html


##################################################################
# QUERY - Process request for new booking
@bp_berger.route("/berger_web_process_new_booking", methods=["POST"])
def berger_web_process_new_booking():
    logging.info("Berger - processing new booking...")
    print('** receive')
    data = request.get_json()
    x = data.get("x", [])
    print("Received list:", x)
    booker_name = x[1]
    booker_email = x[2]
    number_people = x[3]
    list_dates_to_book = x[4]
    booking_code = berger_create_new_booking(booker_name, booker_email, number_people, list_dates_to_book)
    print('New booking:')
    print(booking_code)
    html = get_single_booking_confirmation_HTML(booking_code, 'check')
    send_html_email(booker_email,f'Réservation Georges Berge {booking_code}',html)
    logging.info('...done')
    return html

##################################################################
# QUERY - Process request for cancellation
@bp_berger.route("/berger_web_process_cancel_booking", methods=["POST"])
def berger_web_process_cancel_booking():
    logging.info("Berger - processing cancellation...")
    data = request.get_json()
    x = data.get("x", [])
    booking_code = x[1]
    booking_code = booking_code.upper().strip()
    html = get_single_booking_confirmation_HTML(booking_code, 'cancel')
    if html is None:
        html = berger_booking_not_found(booking_code)
        return html
    booker_email = get_email_from_booking_code(booking_code)
    success = berger_delete_booking(booking_code)
    logging.info('...done')
    if success:
        send_html_email(booker_email,f'Annulation Georges Berger {booking_code}',html)
        return html
    else:
        return 'Error in the cancellation process'


##################################################################
# QUERY - Process request for booking check
@bp_berger.route("/berger_web_process_check_booking", methods=["POST"])
def berger_web_process_check_booking():
    logging.info("Berger - processing check booking...")
    data = request.get_json()
    x = data.get("x", [])
    booking_code = x[1]
    booking_code = booking_code.upper().strip()
    html = get_single_booking_confirmation_HTML(booking_code, 'check')
    if html is None:
        html = berger_booking_not_found(booking_code)
        return html
    booker_email = get_email_from_booking_code(booking_code)
    logging.info('...done')
    return html

##################################################################
# QUERY - provide new booking settings
@bp_berger.route("/provide_new_booking_settings", methods=["GET"])
def provide_new_booking_settings():
    logging.info("Berger - getting new booking settings...")
    full_HTML, dict_settings = get_new_booking_selection_HTML()
    json_dict = jsonify(dict_settings)
    print('JSON string = <' + str(json_dict)+'>')
    logging.info('JSON string = <' + str(json_dict))
    return json_dict


##################################################################
# QUERY - Process admin page request
@bp_berger.route('/berger_process_admin', methods=['POST'])
def berger_process_admin():
    logging.info("Berger - processing admin page request...")
    data = request.get_json()
    input_password = data.get("hashed_password", "")
    print('Receiving password ['+input_password+']')
    if input_password != HASHED_PASSWORD:
        html = '<HTML>\n' + get_berger_HTML_style() + '\n\n<BODY>\n'
        html += '<H2>Administration</H2><BR>Le mot de passe fourni est incorrect. Veuillez réessayer</BODY></HTML>'
        return html

    html = '<HTML>\n' + get_berger_HTML_style() + '\n\n<BODY>\n'
    html += get_historical_bookings_HTML()
    html += dump_bookings_HTML(include_header_footer=False)
    html += '</BODY></HTML>'
    logging.info('...done')
    return html

##################################################################
# THROW MAIN ADMIN PAGE
@bp_berger.route('/berger_admin_page', methods=['GET'])
def berger_admin_page():
    logging.info("Berger - throwing admin page...")
    html = '<HTML>\n' + get_berger_HTML_style() + '\n\n<BODY>\n'
    with open(BASE_FOLDER+'body_admin.html','rt') as f:
        html += f.read()
    html += '</BODY></HTML>'
    logging.info('...done')
    return html

##################################################################
# THROW MAIN NEW BOOKING PAGE
@bp_berger.route("/new_booking_page", methods=["GET"])
def new_booking_page():
    logging.info("Berger - throwing new booking page...")
    full_HTML, dict_settings = get_new_booking_selection_HTML()
    logging.info('...done')
    return full_HTML

##################################################################
# THROW MAIN CANCEL PAGE
@bp_berger.route("/cancel_page", methods=["GET"])
def cancel_page():
    logging.info("Berger - throwing cancel page...")
    html = '<HTML>\n' + get_berger_HTML_style() + '\n\n<BODY>\n'
    with open(BASE_FOLDER+'body_cancellation.html','rt') as f:
        html += f.read()
    html += '</BODY></HTML>'
    logging.info('...done')
    return html


##################################################################
# THROW MAIN CHECK PAGE
@bp_berger.route("/check_page", methods=["GET"])
def check_page():
    logging.info("Berger - throwing check page...")
    html = '<HTML>\n' + get_berger_HTML_style() + '\n\n<BODY>\n'
    with open(BASE_FOLDER+'body_check.html','rt') as f:
        html += f.read()
    html += '</BODY></HTML>'
    logging.info('...done')
    return html

