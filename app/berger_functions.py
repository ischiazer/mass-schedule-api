import sqlite3
import pandas as pd
import pytz
from datetime import datetime
from babel.dates import format_datetime
import random, string
from flask import Flask, request
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import hashlib
from .utilities import push_b2_file,log_msg
import os
#ok
##################################################################
# GLOBAL VARIABLES
HASHED_PASSWORD = 'e172b76465d5da5b220d7dcead985461dc3baeb3a353a2ee7254fd699c8de10c'
if os.path.abspath('.').endswith(('/app/', '/app')):
    BASE_FOLDER = '../app_files/berger_files/'
else:
    BASE_FOLDER = 'app_files/berger_files/'
DB_NAME_LOCAL = os.path.abspath(BASE_FOLDER+'bookings.db')
DB_NAME_BB = 'bookings.db'

BASE_STYLE = os.path.abspath(BASE_FOLDER+'base_style.html')
ADDITIONAL_BODY = os.path.abspath(BASE_FOLDER + 'additional_body.html')
EMBEDDED_JS = os.path.abspath(BASE_FOLDER + 'embedded_js.js')
ADDITIONAL_STYLE = os.path.abspath(BASE_FOLDER + 'additional_style.html')

log_msg('Berger python file dir  = ' + os.path.abspath('.'))
log_msg('Berger local DB file = ' + DB_NAME_LOCAL)
log_msg(f'Berger BASE_STYLE = {BASE_STYLE}')
log_msg(f'Berger ADDITIONAL_BODY = {ADDITIONAL_BODY}')
log_msg(f'Berger EMBEDDED_JS = {EMBEDDED_JS}')
log_msg(f'Berger ADDITIONAL_STYLE = {ADDITIONAL_STYLE}')

os.makedirs(BASE_FOLDER, exist_ok=True)
log_msg('Folder created for Berger')

##################################################################
# Connect to database (creates the file if it doesn't exist)
def get_DB_connection():
    DB_connection = sqlite3.connect(DB_NAME_LOCAL)
    DB_cursor = DB_connection.cursor()
    return DB_connection, DB_cursor

##################################################################
# UPLOAD DATABASE TO BLACKBLAZE
def update_b2_DB():
    log_msg('Pushing Berger DB to B2...')
    push_b2_file('berger',DB_NAME_LOCAL, DB_NAME_BB)
    log_msg('...Done')
    
##################################################################
# SUB-FUNCTION: DUMP BOOKING DATABASE INTO HTML TABLE
def dump_bookings_HTML(include_header_footer=True):
    DB_connection, DB_cursor = get_DB_connection()
    if include_header_footer:
        html = '<HTML>\n'
    else:
        html = ''
    html += '<H2>Bookings</H2>\n' + pd.read_sql_query('SELECT * FROM TableBookings ORDER BY BookingDate DESC', DB_connection).to_html(index=False)
    html += '<H2>Booking dates</H2>\n' + pd.read_sql_query('SELECT * FROM TableBookingDates', DB_connection).to_html(index=False)
    html += '<H2>Dates</H2>\n' + pd.read_sql_query('SELECT * FROM TableDates', DB_connection).to_html(index=False)
    if include_header_footer:
        html += '\n<HTML>'
    DB_connection.close()
    return html


##################################################################
# SUB-FUNCTION: STYLE SHEET
def get_berger_HTML_style():
    with open(BASE_STYLE, 'rt') as f:
        html = f.read()
    return html

##################################################################
# SEND AN HTTP STRING VIA EMAIL
def send_html_email(to_email, subject, html_content):
    sender_email = "berger.comon@gmail.com"  # must be the same as your Brevo account
    smtp_user = "903632001@smtp-brevo.com"
    smtp_pass = "XBCGtUnpY6D5ENJ1"
    base_recipient = 'berger.comon@gmail.com'

    # Create the email
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = base_recipient

    # Attach the HTML content
    html_content += f"<!--intendedfor:{to_email}-->"
    part = MIMEText(html_content, "html")
    msg.attach(part)

    # Send the email
    with smtplib.SMTP("smtp-relay.brevo.com", 587) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(sender_email, base_recipient, msg.as_string())


##################################################################
# ADDITIONAL JAVASCRIPTS TO INCLUDE
def get_berger_HTML_scripts(include_script=True):
    html = """
          // Close any open tooltips when clicking elsewhere
          document.addEventListener('click', function (event) {
            document.querySelectorAll('.tooltip').forEach(el => {
              if (!el.contains(event.target)) {
                el.classList.remove('show-tooltip');
              }
            });
          });
        
          // Toggle tooltip on tap/click
          document.querySelectorAll('.tooltip').forEach(el => {
            el.addEventListener('click', function (e) {
              e.stopPropagation(); // Prevent body click from closing it immediately
              el.classList.toggle('show-tooltip');
            });
          });
    """
    if include_script:
        html = '<SCRIPT>\n' + html + '</SCRIPT>\n\n'
    return html

##################################################################
# SUB-FUNCTION: PRODUCE HTML SHOWING ALL RESERVATIONS BY MONTH
def get_historical_bookings_HTML():
    # Get historical bookings
    DB_connection, DB_cursor = get_DB_connection()
    sql = """
        SELECT
            d.Date,
            d.MonthYearName,
            d.Day,
            d.DayOfWeek,
            d.DayName,
            d.WeekNumber,
            d.MonthNumber,
            CASE 
                WHEN EXISTS (
                    SELECT 1
                    FROM TableBookingDates b
                    WHERE b.Date = d.Date
                ) THEN 1
                ELSE 0
            END AS HasBooking
        FROM
            TableDates d
        ORDER BY
            d.Date;
        """
    
    x = pd.read_sql_query(sql, DB_connection)
    x = x[x.Date<=(x[x.HasBooking==1].Date).max()]
    x = x[x.Date>=(x[x.HasBooking==1].Date).min()]
    list_months = x.groupby(by='MonthYearName')[['Date']].min().sort_values(by='Date').index.tolist()
    total_by_month = x.groupby(by='MonthYearName').agg({'HasBooking':'sum','MonthNumber':'mean'}).sort_values('MonthNumber')[['HasBooking']]
    x.set_index('Date', inplace=True)
    
    # Get the names of people associated with bookings
    booker_names = pd.read_sql_query('SELECT TableBookingDates.Date, TableBookings.Name FROM TableBookingDates INNER JOIN TableBookings ON (TableBookingDates.BookingCode=TableBookings.BookingCode)', DB_connection)
    booker_names = booker_names.groupby('Date')['Name'].agg(lambda names: ' | '.join(names))

    # Create a series of HTML tables with the bookings of each month
    list_html = []
    for m in list_months:
        y=x[x.MonthYearName==m]
        table_values = pd.DataFrame('',index=sorted(list(set(y.WeekNumber))),columns=sorted(list(set(y.DayOfWeek))))
        table_booker = pd.DataFrame('',index=sorted(list(set(y.WeekNumber))),columns=sorted(list(set(y.DayOfWeek))))
        table_type = pd.DataFrame(0,index=sorted(list(set(y.WeekNumber))),columns=sorted(list(set(y.DayOfWeek))))
        for d in y.index:
            if x.loc[d,'HasBooking']>0:
                table_type.loc[x.loc[d,'WeekNumber'],x.loc[d,'DayOfWeek']] = 1
                table_booker.loc[x.loc[d,'WeekNumber'],x.loc[d,'DayOfWeek']] = booker_names.loc[d ]
            else:
                table_type.loc[x.loc[d,'WeekNumber'],x.loc[d,'DayOfWeek']] = 0
            table_values.loc[x.loc[d,'WeekNumber'],x.loc[d,'DayOfWeek']] = x.loc[d,'Day']
        list_day_names = pd.read_sql_query('SELECT DayOfWeek, DayName FROM TableDates GROUP BY DayOfWeek, DayName ORDER BY DayOfWeek', DB_connection)['DayName'].tolist()
        table_values.columns = list_day_names
        table_type.columns = list_day_names
        table_booker.columns = list_day_names
        
        # Title of table
        html = '<table class="tablesmall">\n'
        html += '<caption style="caption-side: top; text-align: center; font-weight: bold; color: #CE6D6A; font-size: 16px; padding-bottom: 8px;">' + m + '</caption>\n'
        
        # Header row
        html += '<thead><tr>\n'
        for col in table_values.columns:
            html += f'<th style="text-align: center; vertical-align: middle; font-weight: bold;">{col}</th>'
        html += '</tr></thead>\n'
        
        # Table data
        html += '<tbody>'
        for i in table_values.index:
            html += '<tr>'
            for j in table_values.columns:
                if table_type.loc[i, j] == 1:
                    style = 'font-weight: bold; background-color: lightgrey; color: black;'
                    html += f'<td style="text-align: center; vertical-align: middle; {style}"><span class="tooltip" data-tooltip="{table_booker.loc[i,j]}">{table_values.loc[i, j]}</span></td>\n'
                else:
                    style = 'font-weight: normal; background-color: transparent; color: grey;'
                    html += f'<td style="text-align: center; vertical-align: middle; {style}"><span class="tooltip_free" data-tooltip="Libre">{table_values.loc[i, j]}</span></td>\n'

            html += '</tr>\n\n'
        html += '</tbody>\n'
        
        # End table
        html += '</table>\n<BR>\n\n\n'
        list_html.append(html)
    
    # HTML head
    html = '<HTML>\n' + get_berger_HTML_style() + '\n\n<BODY>\n'
    
    # HTML for the summary
    html += "<H2>Aperçu d'ensemble</H2><BR>\n"
    html += ' <div style="margin: 10px; padding: 10px; box-sizing: border-box;">\n'
    html += '<table class="tablesmall">\n'
    html += '<caption style="caption-side: top; text-align: center; font-weight: bold; color: #CE6D6A; font-size: 16px; padding-bottom: 8px;">Total par mois</caption>\n'
    html += '<thead><tr>\n'
    html += '<th style="text-align: left; vertical-align: middle; font-weight: bold;">Month</th>'
    html += '<th style="text-align: center; vertical-align: middle; font-weight: bold;">Booked</th>'
    html += '</tr></thead>\n'
    html += '<tbody>'
    for i in total_by_month.index:
        html += '<tr>'
        html += f'<td style="text-align: left; vertical-align: middle; ">{i}</td>\n'
        html += f'<td style="text-align: center; vertical-align: middle; ">{total_by_month.loc[i, "HasBooking"]}</td>\n'
        html += '</tr>\n\n'
    html += '</tbody>\n'
    html += '</table>\n<BR>\n\n\n'
    html += '<div class="table-container">\n\n'
    
    # Concatenate HTML tables for each month
    for h in list_html:
        html += ' <div style="margin: 10px; padding: 10px; box-sizing: border-box;">\n'
        html += h
        html += '</div>\n'
    html += '</div>\n\n'

    # Add 
    html += get_berger_HTML_scripts() + '</BODY>\n</HTML>\n'
    
    # Close database connection
    DB_connection.close()
    
    return html

##################################################################
# SUB-FUNCTION: PRODUCE HTML CORRESPONDING TO A SINGLE BOOKING
def get_single_booking_confirmation_HTML(booking_code, type_query):
    DB_connection, DB_cursor = get_DB_connection()
    type_query = type_query.lower()
    if not (type_query in ['new','cancel','check']):
        raise ValueError('Booking query %s not available' % str(type_query))
    
    res_details = pd.read_sql_query(f"SELECT BookingCode, Name, Email, NumberPeople, BookingDate, BookingTime FROM TableBookings WHERE BookingCode='{booking_code}'", DB_connection)
    if res_details.shape[0] == 0:
        return None
    elif res_details.shape[0] > 1:
        return None
    res_details = res_details.iloc[0,:].to_dict()
    res_dates = pd.read_sql_query(f"SELECT TableBookingDates.Date, TableDates.DateNameLong FROM TableBookingDates LEFT JOIN TableDates ON (TableBookingDates.Date=TableDates.Date) WHERE BookingCode='{booking_code}'", DB_connection)
    if res_dates.shape[0] == 0:
        return None
    booking_name = res_details['Name']
    booking_email = res_details['Email']
    booking_number_people = res_details['NumberPeople']
    booking_made_date = res_details['BookingDate']
    booking_made_time = res_details['BookingTime']
    
    list_dates_booked = ''
    for i in res_dates.index:
        list_dates_booked += '\t\t<TR><TD style=3D"min-width:400px">' + res_dates.loc[i,'DateNameLong']+'</TD></TR>\n'
    
    if type_query == 'new':
        intro_message = '<H3>Bientôt à Paris</H3>\n<H2>Nouvelle réservation Georges Berger</H2>\n'
        code_reminder = "Ce code sera nécessaire si vous souhaitez plus tard l'annuler"
        str_conclusion = 'Bon séjour à Paris!'
    elif type_query == 'cancel':
        intro_message = '<H3>Annulation</H3>\n<H2>La réservation Georges Berger est annulée</H2>\n'
        code_reminder = ""
        str_conclusion = 'Réservation annulée'
    elif type_query == 'check':
        intro_message = '<H3>Bientôt à Paris</H3>\n<H2>Détails de la réservation Georges Berger</H2>\n'
        code_reminder = ""
        str_conclusion = 'Bon séjour à Paris!'

    h = get_berger_HTML_style()
    h += f"""
        <HEAD>
        </HEAD>
        <BODY style=3D"margin:40;padding:0">
            {intro_message}
            <BR>
            Code de réservation: <B>{booking_code}</B> {code_reminder}
            <BR><BR>{str_conclusion}<BR>
            <BR>
            <BR><TABLE class="tablesimple">
            <CAPTION>Vos coordonnées</CAPTION>
            <TR><TD>Votre nom</TD><TD style=3D"min-width:400px">{booking_name}</TD></TR>
            <TR><TD>Votre email</TD><TD>{booking_email}</TD></TR>
            <TR><TD>Nombre de personnes</TD><TD>{booking_number_people}</TD></TR><TR>
            <TR><TD>Code</TD><TD>{booking_code}</TD></TR><TR>
            <TD>Réservation faite le </TD><TD>{booking_made_date} | {booking_made_time}</TD></TR>
            </TABLE>
            <BR>
            <TABLE class="tablesimple">
            <CAPTION>Dates</CAPTION>
            {list_dates_booked}
            </TABLE>
            <BR>
            <TABLE>
            <CAPTION>Si vous changez d'avis</CAPTION>
            <TR><TD>Connectez-vous sur <a HREF=3D'http://www.ondesmusicales.com/paris'>http://www.ondesmusicales.com/paris</A></TD></TR>
            </TABLE>
            <BR>
            </BODY>
            </HTML>
    """
    DB_connection.close()
    return h

##################################################################
# SUB-FUNCTION: CONVERT LONG DATE TO yyyy-mm-dd FORMAT
def berger_convert_date(dt_long):
    DB_connection, DB_cursor = get_DB_connection()
    x = pd.read_sql_query("SELECT Date,DateNameLong FROM TableDates ORDER BY Date;", DB_connection)
    DB_connection.close()
    if dt_long.find('-')<0:
        x['DateAlt'] = [s.replace('-', ' ') for s in x.DateNameLong]
        return x[x.DateAlt==dt_long].Date.values[0]
    else:
        return x[x.DateNameLong==dt_long].Date.values[0]
        

##################################################################
# SUB-FUNCTION: PRODUCE HTML FOR BOOKING SELECTION
def get_new_booking_selection_HTML():
    # Get the list of dates
    DB_connection, DB_cursor = get_DB_connection()
    sql = "SELECT Date, Year, Month, MonthYearName,Day,DayOfWeek,DayName,WeekNumber,MonthNumber,DateIndex,DateNameLong FROM TableDates ORDER BY Date;"
    x_dt = pd.read_sql_query(sql, DB_connection)
    x_dt['YearM'] = x_dt.Year + x_dt.Month/100
    now_paris = datetime.now(pytz.timezone('Europe/Paris'))
    x_dt = x_dt[x_dt.YearM>=now_paris.year+now_paris.month/100]
    x_dt = x_dt[x_dt.YearM<=now_paris.year+1+now_paris.month/100]

    # Get the existing bookings for these dates
    sql =  'SELECT TableBookingDates.Date, TableBookings.NumberPeople FROM TableBookingDates INNER JOIN TableBookings ON (TableBookingDates.BookingCode=TableBookings.BookingCode)'    
    x_number_bookings = pd.read_sql_query(sql, DB_connection).groupby(by='Date')[['NumberPeople']].sum()
    x_dt = x_dt.join(x_number_bookings,on='Date',how='left')
    x_dt.loc[x_dt[pd.isnull(x_dt.NumberPeople)].index,'NumberPeople'] = 0
    #x_dt.set_index('Date', inplace=True)

    list_months = x_dt.groupby(by='MonthYearName')[['Date']].min().sort_values(by='Date').index.tolist()
    x_dt.set_index('Date', inplace=True)
    
    # Create a series of HTML tables for each month
    list_html = []
    list_dt_index = []
    n_cells = 0
    list_busy = []

    for m in list_months:
        y=x_dt[x_dt.MonthYearName==m]
        table_values = pd.DataFrame('',index=sorted(list(set(y.WeekNumber))),columns=sorted(list(set(y.DayOfWeek))))
        table_date_ID = pd.DataFrame(index=sorted(list(set(y.WeekNumber))),columns=sorted(list(set(y.DayOfWeek))))
        table_busy = pd.DataFrame(index=sorted(list(set(y.WeekNumber))),columns=sorted(list(set(y.DayOfWeek))))
        for d in y.index:
            table_values.loc[x_dt.loc[d,'WeekNumber'],x_dt.loc[d,'DayOfWeek']] = x_dt.loc[d,'Day']
            table_date_ID.loc[x_dt.loc[d,'WeekNumber'],x_dt.loc[d,'DayOfWeek']] = x_dt.loc[d,'DateIndex']
            table_busy.loc[x_dt.loc[d,'WeekNumber'],x_dt.loc[d,'DayOfWeek']] = x_dt.loc[d,'NumberPeople']
        list_day_names = pd.read_sql_query('SELECT DayOfWeek, DayName FROM TableDates GROUP BY DayOfWeek, DayName ORDER BY DayOfWeek', DB_connection)['DayName'].tolist()
        table_values.columns = list_day_names
        table_date_ID.columns = list_day_names
        table_busy.columns = list_day_names
        
        # Title of table
        html = '<DIV class="content"><div class="calendar-box" style="background-color: white; padding: 20px; display: inline-block; margin-left: -40px;">'
        html += '<TABLE class="tablemedium" >\n'
        html += '<caption style="caption-side: top; text-align: center; font-weight: bold; color: #CE6D6A; font-size: 16px; padding-bottom: 8px;">' + m + '</caption>\n'
        
        # Header row
        html += '<thead><tr>\n'
        for col in table_values.columns:
            html += f'<th style="text-align: center; vertical-align: middle; font-weight: bold;">{col}</th>'
        html += '</tr></thead>\n'
        
        # Table data
        html += '<tbody>'
        for i in table_values.index:
            html += '<tr>'
            for j in table_values.columns:
                n = table_date_ID.loc[i, j]
                if pd.isnull(n):
                    html += f'<td style="text-align: center; vertical-align: middle;"> {table_values.loc[i, j]}</td>\n'
                else:
                    html += f'<td ID="Cell{n_cells}" style="text-align: center; vertical-align: middle;"> {table_values.loc[i, j]}</td>\n'
                    n_cells += 1
                    list_dt_index.append(n)
                    list_busy.append(int(table_busy.loc[i,j]))
            html += '</tr>\n\n'
        html += '</tbody>\n'
        
        # End table
        html += '</TABLE>\n\n</DIV></DIV>\n<BR>\n\n\n'
        list_html.append(html)
    
    # Mapping of dates
    mapping_dt = {int(n): x_dt[x_dt.DateIndex==n]['DateNameLong'].values[0].replace('-',' ') for n in list_dt_index if not pd.isnull(n)}

    # HTML head
    html_main = '<HTML>\n' + get_berger_HTML_style() + '\n\n<BODY>\n'

    # Add body
    with open(ADDITIONAL_BODY,'rt') as f:
        html_main += f.read()

    # Concatenate HTML tables for each month
    html_calendar = ''
    for h in list_html:
        html_calendar += ' <div style="padding: 10px; box-sizing: border-box;">\n'
        html_calendar += h
        html_calendar += '</div>\n'
    html_calendar += '</div>\n\n'
    html_main += html_calendar
    # Embed Javascript
    with open(EMBEDDED_JS, 'rt') as f:
        js_code = f.read()
    with open(ADDITIONAL_STYLE, 'rt') as f:    
        additional_style = f.read()
    html_main += "<STYLE>\n" + additional_style + '</STYLE>\n'
    html_main += '<SCRIPT>'
    html_main += f'n_cells={n_cells};\n'
    html_main += 'n_people=1;\n'
    original_selection_list = [0]*n_cells
    original_selection = '[' + ','.join(["'"+str(k)+"'" for k in original_selection_list]) + ']'
    original_busy = '[' + ','.join([str(k) for k in list_busy]) + ']'
    original_dt = '[' + ','.join(["'"+mapping_dt[ix]+"'" for ix in list_dt_index]) + ']'
    html_main += f'list_selected={original_selection};\n'
    html_main += f'list_busy={original_busy};\n'
    html_main += f'list_dt={original_dt};\n'
    html_main += js_code
    html_main += 'set_table_click_reaction();\n'
    html_main += 'show_clicked_bookings();\n'
    html_main += 'select_number_people(n_people);\n'
    html_main += '</SCRIPT>'

    # Dictionary of settings for JavaScript
    dict_settings = {'n_cells': n_cells,
                     'n_people': 1,
                     'initial_selection': original_selection_list,
                     'initial_busy': list_busy,
                     'list_dt': [mapping_dt[ix] for ix in list_dt_index],
                     'html_calendar': html_calendar}

    # Add  closing items
    html_main += get_berger_HTML_scripts() + '</BODY>\n</HTML>\n'
    
    # Close database connection
    DB_connection.close()
    return html_main, dict_settings 


##################################################################
# SUB-FUNCTION: GENERATE A NEW UNIQUE BOOKING CODE
def berger_generate_new_booking_code():
    DB_connection, DB_cursor = get_DB_connection()
    existing_bookings = pd.read_sql_query('SELECT BookingCode FROM TableBookings GROUP BY BookingCode', DB_connection).BookingCode.tolist()
    DB_connection.close()
    code = ''
    while (code=='') or (code in existing_bookings):
        code = ''.join(random.choices(string.ascii_uppercase, k=4))
    return code

##################################################################
# SUB-FUNCTION: CREATE A NEW BOOKING IN DATABASE
def berger_create_new_booking(booker_name, booker_email, number_people, list_dates_to_book):
    # Get a random code
    booking_code = berger_generate_new_booking_code()
    
    # Open database
    DB_connection, DB_cursor = get_DB_connection()

    # Create entry for the bookings table    
    now_paris = datetime.now(pytz.timezone('Europe/Paris'))
    now_date = format_datetime(now_paris,'yyyy-MM-dd')
    now_time = format_datetime(now_paris,'HH:mm:ss')
    sql = f"""INSERT INTO TableBookings
            (BookingCode,Name,Email,NumberPeople,BookingDate,BookingTime)
            VALUES (
                '{booking_code}',
                '{booker_name}',
                '{booker_email}',
                {number_people},
                '{now_date}',
                '{now_time}')
            """
    DB_cursor.execute(sql)
    
    # Create entries for the dates booked
    log_msg('Trying to insert new data in booking DB...')
    for dt in list_dates_to_book:
        sql = f"INSERT INTO TableBookingDates (Date, BookingCode) VALUES ('{berger_convert_date(dt)}','{booking_code}')"
        DB_cursor.execute(sql)
    log_msg('...done')

    # Commmit the changes to the database
    DB_connection.commit()

    # Close database
    DB_connection.close()

    # Update BlackBlaze clone of the database
    update_b2_DB()

    return booking_code

##################################################################
# SUB-FUNCTION: GENERATE 'BOOKING NOT FOUND' MESSAGE
def berger_booking_not_found(booking_code):
    html = '<HTML>\n' + get_berger_HTML_style() + '\n\n<BODY>\n'
    html += f"""
        <BR><BR>
        <H2>Réservation inconnue</H2>
        Le code de réservation <B>{booking_code.upper()}</B> peut pas être trouvé. Renouvellez s'il vous plaît votre demande après avoir vérifié le code
        <BR><BR>   
        </BODY></HTML>
    """
    return html

##################################################################
# SUB-FUNCTION: DELETE A BOOKING
def berger_delete_booking(booking_code):
    # Clean up the booking code
    booking_code = booking_code.upper().strip()

    # Open database
    DB_connection, DB_cursor = get_DB_connection()

    # Check that the booking exists
    existing1 = pd.read_sql_query(f"SELECT BookingCode FROM TableBookings WHERE BookingCode='{booking_code}'", DB_connection).BookingCode
    if existing1.shape[0] == 0:
        return False
    existing2 = pd.read_sql_query(f"SELECT BookingCode FROM TableBookingDates WHERE BookingCode='{booking_code}'", DB_connection)
    if existing2.shape[0] == 0:
        return False

    # DeLete booking
    DB_cursor.execute("DELETE FROM TableBookingDates WHERE BookingCode = ?", (booking_code,))
    DB_cursor.execute("DELETE FROM TableBookings WHERE BookingCode = ?", (booking_code,))

    # Commmit the changes to the database
    DB_connection.commit()

    # Close database
    DB_connection.close()
    
    # Update BlackBlaze clone of the database
    update_b2_DB()

    return True

##################################################################
# SUB-FUNCTION: GET THE EMAIL ASSOCIATED WITH A BOOKING
def get_email_from_booking_code(booking_code):
    booking_code = booking_code.upper().strip()
    DB_connection, DB_cursor = get_DB_connection()
    email = pd.read_sql_query(f"SELECT Email FROM TableBookings WHERE BookingCode='{booking_code}'", DB_connection).Email.values[0]
    DB_connection.close()
    return email


##################################################################
# SUB-FUNCTION: HASH A PASSWORD
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()



