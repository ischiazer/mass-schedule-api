from flask import Blueprint, request
import asyncio
import os
import json
import io
import zipfile
import logging
import tempfile
from datetime import datetime
from .meloir_functions import fetch_and_clean_schedule, fetch_readings, get_perplexity_events, get_news, call_mass_schedule_and_store
from .meloir_functions import BASE_FOLDER,HTML_FILE_PATH_LOCAL, UPLOAD_FOLDER_LOCAL, UPLOAD_LOG_FILE_LOCAL, WORD_FOLDER_LOCAL, HTML_FOLDER_LOCAL, PATH_BULLETIN_LOCAL, PERPLEXITY_TABLE_LAST_LOCAL,PERPLEXITY_TIMESTAMP_LOCAL,NEWS_TABLE_LOCAL,NEWS_TIMESTAMP_LOCAL,READINGS_PATH_LAST_LOCAL
from .utilities import push_b2_file, throw_static_file, log_msg
from .utilities import log_upload, extract_cropped_images_proportional, convert_docx_to_html_with_cropped_images
from flask import request, send_file, Response



##################################################################
# REGISTER BLUEPRINT
bp_meloir = Blueprint("bp_meloir", __name__)
log_msg('Blueprint Meloir done')

##################################################################
# INITIALISATION OF MODULE
def meloir_initialise():
    pass

##################################################################
# QUERY - FETCH MASS SCHEDULE ON THE FLY
@bp_meloir.route('/schedule')
def get_schedule():
    log_msg(f'(Web access) get_schedule pid= {os.getpid()}')
    return asyncio.get_event_loop().run_until_complete(fetch_and_clean_schedule())

##################################################################
# QUERY - REFRESH MASS SCHEDULE AND STORE
@bp_meloir.route('/refresh')
def refresh_schedule():
    h = call_mass_schedule_and_store()
    return f'call_mass_schedule_and_store done'



##################################################################
# QUERY - UPLOAD HTML FILE
@bp_meloir.route("/upload_html", methods=["POST"])
def upload_html():
    log_msg(f'(Web access) upload_html  pid= {os.getpid()}')
    html_content = request.get_data(as_text=True)
    with open(HTML_FILE_PATH_LOCAL, "w", encoding="utf-8") as f:
        f.write(html_content)
    return "HTML saved", 200

##################################################################
# QUERY - GET LATEST HTML
@bp_meloir.route("/latest")
def latest():
    log_msg(f'(Web access) latest HTML ' + HTML_FILE_PATH_LOCAL + 'pid= {os.getpid()}')
    if os.path.exists(HTML_FILE_PATH_LOCAL):
        return send_file(HTML_FILE_PATH_LOCAL, mimetype="text/html")
    else:
        return "No HTML uploaded yet.", 404

##################################################################
# QUERY - UPLOAD STANDARD ATTACHMENT
@bp_meloir.route("/upload_attachment", methods=["POST"])
def upload_attachment():
    log_msg(f'(Web access) upload_attachment.   pid= {os.getpid()}')
    uploaded_file = request.files.get("file")
    filename = request.form.get("filename")

    if not uploaded_file or not filename:
        log_upload("FAIL", filename or "unknown", "Missing file or filename in multipart/form-data")
        return "Missing file or filename", 400

    try:
        filepath = os.path.join(UPLOAD_FOLDER_LOCAL, filename)
        uploaded_file.save(filepath)

        log_upload("SUCCESS", filename)
        return f"File '{filename}' saved", 200

    except Exception as e:
        log_upload("FAIL", filename, str(e))
        return f"Error saving file: {str(e)}", 500

##################################################################
# QUERY - RETURN THE UPLOAD LOG
@bp_meloir.route("/upload_log")
def show_log():
    log_msg(f'(Web access) show_log  pid= {os.getpid()}')
    if not os.path.exists(UPLOAD_LOG_FILE_LOCAL):
        return "No log available yet.", 404

    with open(UPLOAD_LOG_FILE_LOCAL, "r", encoding="utf-8") as f:
        log_content = f.read()

    return Response(f"<pre>{log_content}</pre>", mimetype="text/html")

##################################################################
# QUERY - ERROR HANDLER
@bp_meloir.errorhandler(413)
def request_entity_too_large(error):
    return "File too large. Limit is 10MB.", 413

##################################################################
# QUERY - RETURN (DOWNLOAD) ALL CONTENT
@bp_meloir.route("/download_content")
def download_content():
    log_msg(f'(Web access) download_content ZIP  pid= {os.getpid()}')
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(UPLOAD_FOLDER_LOCAL):
            for filename in files:
                filepath = os.path.join(root, filename)
                # Add file to zip with relative path
                arcname = os.path.relpath(filepath, start=UPLOAD_FOLDER_LOCAL)
                zipf.write(filepath, arcname=arcname)

    zip_buffer.seek(0)
    return send_file(
        zip_buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name="uploaded_content.zip"
    )

##################################################################
# QUERY - FETCH DIR (LISTING OF FILES)
@bp_meloir.route('/show_dir')
def show_dir():
    log_msg(f'(Web access) /show_dir  pid= {os.getpid()}')
    base_path = "."  # Start from current working directory
    file_list = []

    for root, dirs, files in os.walk(base_path):
        for name in files:
            full_path = os.path.join(root, name)
            try:
                size = os.path.getsize(full_path)
            except OSError:
                size = -1  # Could not access file size

            relative_path = os.path.relpath(full_path, start=base_path)
            file_list.append(f"{relative_path} ({size} bytes)")

    file_list.sort()
    output = "\n".join(file_list)

    for root, dirs, files in os.walk(base_path):
        for name in files:
            full_path = os.path.join(root, name)
            file_list.append(os.path.relpath(full_path, start=base_path))

    file_list.sort()
    output = "\n".join(file_list)
    return Response(f"<pre>{output}</pre>", mimetype="text/html")


##################################################################
# QUERY - RECEIVE WORD FILE AND PROCESS INTO HTML
@bp_meloir.route("/deliver_word", methods=["POST"])
def deliver_word():
    log_msg(f'(Web access) deliver_word.  pid= {os.getpid()}')
    uploaded_file = request.files.get("file")
    if not uploaded_file:
        log_upload("FAIL", "unknown", "No file uploaded")
        return "No file uploaded", 400

    # Step a: Save uploaded .docx file with timestamp
    timestamp = datetime.utcnow().strftime("%Y_%m_%d_%H_%M_%S")
    filename = f"{timestamp}.docx"
    docx_path = os.path.join(WORD_FOLDER_LOCAL, filename)
    uploaded_file.save(docx_path)

    try:
        # Step b: Create temp output directory for cropped images
        with tempfile.TemporaryDirectory() as output_dir:
            # Step c: Generate HTML output paths
            html_filename = f"{timestamp}.html"
            html_path = os.path.join(HTML_FOLDER_LOCAL, html_filename)
            latest_path = os.path.join(HTML_FOLDER_LOCAL, "latest_html.html")

            logo_details = (392860, "logo_paroisse2.gif")  # Placeholder — replace if dynamic

            # Process document
            results = extract_cropped_images_proportional(docx_path, output_dir, logo_details)
            results_dict = {k[0]: k[1] for k in results}
            html = convert_docx_to_html_with_cropped_images(docx_path, html_path, results_dict)

            # Also write to latest_html.html
            with open(latest_path, "w", encoding="utf-8") as f:
                f.write(html)

            # Also write to bulletin_paroissial.html
            with open(PATH_BULLETIN_LOCAL, "w", encoding="utf-8") as f:
                f.write(html)

            # Push the HTML file to the BlackBlaze server
            push_b2_file('meloir', latest_path, 'bulletin_paroissial.html')

            log_upload("SUCCESS", filename)
            return f"Processed and saved: {html_filename}", 200

    except Exception as e:
        log_upload("FAIL", filename, str(e))
        return f"Error processing file: {str(e)}", 500

##################################################################
# QUERY - RETURN LATEST HTML
@bp_meloir.route("/latest_word_html")
def latest_word_html():
    log_msg(f'(Web access) latest_word_html  pid= {os.getpid()}')
    latest_path = os.path.join(HTML_FOLDER_LOCAL, "latest_html.html")

    if not os.path.exists(latest_path):
        return "No HTML has been generated yet.", 404

    return send_file(latest_path, mimetype="text/html")


##################################################################
# QUERY - FETCH READINGS
@bp_meloir.route('/fetch_readings')
def force_fetch_readings():
    log_msg(f'/fetch_readings  pid= {os.getpid()}')
    return fetch_readings()


##################################################################
# QUERY - FETCH PERPLEXITY
@bp_meloir.route('/fetch_perplexity')
def force_fetch_perplexity():
    log_msg("/fetch_perplexity called")
    log_msg(f'(Web access) force_fetch_perplexity  pid= {os.getpid()}')
    try:
        get_perplexity_events()
    except Exception as e:
        log_msg('Error running get_perplexity_events')


##################################################################
# QUERY - FETCH VATICAN NEWS
@bp_meloir.route('/fetch_vatican_news')
def force_fetch_vatican_news():
    log_msg('f/fetch_vatican_news  pid= {os.getpid()}')
    try:
        get_news()
        return 'Vatican news Updated now', 200
    except Exception as e:
        log_msg(f"Vatican news step failed {str(e)}")


##################################################################
# QUERY - STATIC PERPLEXITY NEWS
@bp_meloir.route('/static_news_nearby')
def query_static_perplexity():
    log_msg(f'/static_news_nearby  pid= {os.getpid()}')
    try:
        f= throw_static_file('meloir',PERPLEXITY_TABLE_LAST_LOCAL,"evenements.html", "/query_static_perplexity called")
        log_msg('static_news_nearby successful')
        return f
    except Exception as e:
        log_msg(f"Error in query_static_perplexity: {str(e)}")
        return f"Error fetching perplexity news: {str(e)}", 500

##################################################################
# QUERY - STATIC PERFPLEXITY NEWS
@bp_meloir.route('/static_news_nearby_timestamp')
def query_static_perplexity_timestamp():
    log_msg(f'/static_news_nearby_timestamp  pid= {os.getpid()}')
    try:
        f = throw_static_file('meloir', PERPLEXITY_TIMESTAMP_LOCAL,"evenements_MAJ.txt", "/static_news_nearby_timestamp called")
        log_msg('query_static_perplexity_timestamp successful')
        return f
    except Exception as e:
        log_msg(f"Error static_news_nearby_timestamp: {str(e)}")
        return f"Error static_news_nearby_timestamp: {str(e)}", 500

##################################################################
# QUERY - STATIC VATICAN NEWS
@bp_meloir.route('/static_news_vatican')
def query_static_vatican():
    log_msg(f'/static_news_vatican  pid= {os.getpid()}')
    try:
        f = throw_static_file('meloir',NEWS_TABLE_LOCAL,"nouvelles_vatican.html", "/static_news_vatican called")
        log_msg('static_news_vatican successful')
        return f
    except Exception as e:
        log_msg(f"Error in query_static_vatican: {str(e)}")
        return f"Error fetching Vatican news: {str(e)}", 500
    

##################################################################
# QUERY - STATIC VATICAN NEWS TIMESTAMP
@bp_meloir.route('/static_news_vatican_timestamp')
def static_news_vatican_timestamp():
    log_msg(f'/static_news_vatican_timestamp  pid= {os.getpid()}')
    try:
        f = throw_static_file('meloir',NEWS_TIMESTAMP_LOCAL,"nouvelles_vatican_MAJ.txt", "/static_news_vatican_timestamp called")
        log_msg('static_news_vatican_timestamp successful')
        return f
    except Exception as e:
        log_msg(f"Error static_news_vatican_timestamp: {str(e)}")
        return f"Error static_news_vatican_timestamp: {str(e)}", 500


##################################################################
# QUERY - STATIC READINGS
@bp_meloir.route('/static_readings')
def query_static_readings():
    log_msg(f'/static_readings pid= {os.getpid()}')
    try:
        f = throw_static_file('meloir',READINGS_PATH_LAST_LOCAL,"lectures.html", "/query_static_readings called")
        log_msg('static_readings successful')
        return f
    except Exception as e:
        log_msg(f"Error in query_static_readings: {str(e)}")
        return f"Error fetching readings: {str(e)}", 500


##################################################################
# QUERY - STATIC PARISH PAPER
@bp_meloir.route('/static_bulletin')
def query_static_bulletin():
    log_msg(f'/static_bulletin  pid= {os.getpid()}')
    try:
        f = throw_static_file('meloir',PATH_BULLETIN_LOCAL,"bulletin_paroissial.html", "/query_static_bulletin called")
        log_msg('query_static_bulletin successful')
        return f
    except Exception as e:
        log_msg(f"Error in query_static_bulletin: {str(e)}")
        return f"Error fetching bulletin: {str(e)}", 500
    
