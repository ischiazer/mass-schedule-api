from flask import Flask, jsonify, request, send_file, Response, send_file
from bs4 import BeautifulSoup
import io
import nest_asyncio
import asyncio
import zipfile
from playwright.async_api import async_playwright
import json
import os
import base64
from datetime import date, datetime, timedelta
from flask_cors import CORS
import mammoth
from pathlib import Path
import zipfile
import io
from lxml import etree
from PIL import Image
import tempfile
from b2sdk.v2 import InMemoryAccountInfo, B2Api
import locale
import logging
import pytz

##################################################################
# APP INITIALISATION
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 MB
HTML_FILE_PATH = "latest.html"
UPLOAD_FOLDER = "uploaded_files"
WORD_FOLDER = "uploaded_word"
HTML_FOLDER = "created_HTML"
UPLOAD_LOG_FILE = "upload_log.txt"
READINGS_PATH_LAST = 'readings_current.html'
READINGS_PATH_STORE = 'readings_%s.html'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(WORD_FOLDER, exist_ok=True)
os.makedirs(HTML_FOLDER, exist_ok=True)
CORS(app, resources={r"/*": {"origins": "*"}})
if not os.path.exists(UPLOAD_LOG_FILE):
    with open(UPLOAD_LOG_FILE, "w", encoding="utf-8") as log:
        log.write("[INIT] Created log file\n")
nest_asyncio.apply()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),  # Console (Render logs)
        logging.FileHandler("log.txt")  # Optional: file in your container
    ]
)
##################################################################
# CONNECT TO BLACKBLAZE
def get_b2_bucket():
    b2_info = InMemoryAccountInfo()
    b2_api = B2Api(b2_info)
    b2_application_key_id = os.getenv("B2_KEY_ID")
    b2_application_key = os.getenv("B2_APPLICATION_KEY")
    b2_api.authorize_account("production", b2_application_key_id, b2_application_key)
    return b2_api.get_bucket_by_name("MeloirFiles")

##################################################################
# UPLOAD FILE TO BLACKBLAZE
def push_b2_file(file_local, file_server):
    bucket = get_b2_bucket()
    bucket.upload_local_file(
        local_file=file_local,
        file_name=file_server
    )

##################################################################
# UTILITY: RE-ENCODING LATIN / UTF-8
def fix_encoding(text):
    try:
        return text.encode('latin1').decode('utf-8')
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


##################################################################
# UTILITY: FORMAT A DATE
def french_date(dt_string):
    try:
        locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
    except locale.Error:
        locale.setlocale(locale.LC_TIME, 'fr_FR')

    # Input string
    date_obj = datetime.strptime(dt_string, "%Y-%m-%d")

    # Format to full French date
    return date_obj.strftime("%A %d %B %Y").capitalize()

##################################################################
# FUNCTION TO UPDATE LOG OF FILES BEING UPLOADED
def log_upload(status, filename, detail=""):
    timestamp = datetime.utcnow().isoformat()
    log_line = f"[{timestamp}] {status.upper()}: {filename} {detail}".strip() + "\n"
    with open(UPLOAD_LOG_FILE, "a", encoding="utf-8") as log:
        log.write(log_line)

##################################################################
# UTILITY : HTML-FORMATTED TIME STAMP


def get_time_stamp_HTML():
    try:
        locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
    except locale.Error:
        locale.setlocale(locale.LC_TIME, 'fr_FR')
    paris_tz = pytz.timezone("Europe/Paris")
    now = datetime.now(paris_tz)
    timestamp = now.strftime("%d-%b-%Y %H:%M:%S")
    return f'<br><small>Mis à jour le {timestamp}</small>'

##################################################################
# QUERY - BASE
@app.route('/')
def home():
    return "Mass Schedule API is running!"

##################################################################
# QUERY - FETCH MASS SCHEDULE ON THE FLY
@app.route('/schedule')
def get_schedule():
    return asyncio.get_event_loop().run_until_complete(fetch_and_clean_schedule())

##################################################################
# QUERY - REFRESH MASS SCHEDULE AND STORE
@app.route('/refresh')
def refresh_schedule():
    data = asyncio.get_event_loop().run_until_complete(fetch_and_clean_schedule())

    os.makedirs("static", exist_ok=True)

    # Save cleaned JSON
    with open("static/schedule.json", "w", encoding="utf-8") as f:
        json.dump(data.get_json(), f, ensure_ascii=False, indent=2)

    # Upload JSON to BlackBlaze
    push_b2_file("static/schedule.json","horaires_messes.json")

    # Save last updated timestamp in French format
    now = datetime.now()
    formatted = now.strftime("%A %d %B %Y à %H:%M")
    with open("static/last_updated.txt", "w", encoding="utf-8") as f:
        f.write(formatted)
    push_b2_file("static/last_updated.txt","horaires_messes_MAJ.txt")

    # Save heartbeat timestamp (ISO format)
    with open("static/heartbeat.txt", "w") as hb:
        hb.write(now.isoformat())
    push_b2_file("static/heartbeat.txt","heartbeat.txt")

    return "Schedule updated and saved to static/schedule.json"

##################################################################
# FUNCTION TO FETCH MASS SCHEDULE AND PROCESS
async def fetch_and_clean_schedule():
    url = "https://messes.info/horaires/paroisse%20notre%20dame%20du%20Bois%20Renou?display=TABLE"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, timeout=60000)
        await page.wait_for_selector("tr td:nth-child(7)", timeout=15000)
        content = await page.content()
        await browser.close()

    soup = BeautifulSoup(content, "html.parser")
    rows = soup.find_all("tr")

    mass_schedule = []
    for row in rows:
        cells = row.find_all("td")
        if len(cells) == 7:
            mass_schedule.append({
                "CP": cells[0].get_text(strip=True),
                "COMMUNE": cells[1].get_text(strip=True),
                "LIEU DE CULTE": cells[2].get_text(strip=True),
                "PAROISSE": cells[3].get_text(strip=True),
                "DATE": cells[4].get_text(strip=True),
                "HEURE": cells[5].get_text(strip=True),
                "LITURGIE": cells[6].get_text(strip=True),
            })

    # Clean and format
    mapping_churches = {
        'Église Notre Dame de la Visitation': 'Hirel',
        "Église Notre-Dame de l'Assomption": 'La Gouesnière',
        'Église Saint-Benoit': 'Saint Benoît',
        'Église Saint-Louis': 'Vildé La Marine',
        'Église Saint-Méen-et-Sainte-Croix': 'La Fresnais',
        'Église Saint-Méloir': 'Saint Méloir'
    }

    mapping_days = {
        'lun': 'Lundi', 'mar': 'Mardi', 'mer': 'Mercredi',
        'jeu': 'Jeudi', 'ven': 'Vendredi', 'sam': 'Samedi', 'dim': 'Dimanche'
    }

    clean_schedule = []
    for row in mass_schedule:
        try:
            clean_row = {
                'Date': row['DATE'][5:],  # Remove "dim. ", etc.
                'Jour': mapping_days.get(row['DATE'][:3], row['DATE'][:3]),
                'Heure': row['HEURE'],
                'Où': mapping_churches.get(row['LIEU DE CULTE'], row['LIEU DE CULTE']),
                'Célébration': row['LITURGIE']
            }
            clean_schedule.append(clean_row)
        except Exception:
            continue

    return jsonify(clean_schedule)

##################################################################
# QUERY - UPLOAD HTML FILE
@app.route("/upload_html", methods=["POST"])
def upload_html():
    html_content = request.get_data(as_text=True)
    with open(HTML_FILE_PATH, "w", encoding="utf-8") as f:
        f.write(html_content)
    return "HTML saved", 200

##################################################################
# QUERY - GET LATEST HTML
@app.route("/latest")
def latest():
    if os.path.exists(HTML_FILE_PATH):
        return send_file(HTML_FILE_PATH, mimetype="text/html")
    else:
        return "No HTML uploaded yet.", 404

##################################################################
# QUERY - UPLOAD STANDARD ATTACHMENT
@app.route("/upload_attachment", methods=["POST"])
def upload_attachment():
    uploaded_file = request.files.get("file")
    filename = request.form.get("filename")

    if not uploaded_file or not filename:
        log_upload("FAIL", filename or "unknown", "Missing file or filename in multipart/form-data")
        return "Missing file or filename", 400

    try:
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        uploaded_file.save(filepath)

        log_upload("SUCCESS", filename)
        return f"✅ File '{filename}' saved", 200

    except Exception as e:
        log_upload("FAIL", filename, str(e))
        return f"❌ Error saving file: {str(e)}", 500

##################################################################
# QUERY - RETURN THE UPLOAD LOG
@app.route("/upload_log")
def show_log():
    if not os.path.exists(UPLOAD_LOG_FILE):
        return "No log available yet.", 404

    with open(UPLOAD_LOG_FILE, "r", encoding="utf-8") as f:
        log_content = f.read()

    return Response(f"<pre>{log_content}</pre>", mimetype="text/html")

##################################################################
# QUERY - ERROR HANDLER
@app.errorhandler(413)
def request_entity_too_large(error):
    return "❌ File too large. Limit is 10MB.", 413

##################################################################
# QUERY - RETURN (DOWNLOAD) ALL CONTENT
@app.route("/download_content")
def download_content():
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(UPLOAD_FOLDER):
            for filename in files:
                filepath = os.path.join(root, filename)
                # Add file to zip with relative path
                arcname = os.path.relpath(filepath, start=UPLOAD_FOLDER)
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
@app.route("/show_dir")
def show_dir():
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
# FUNCTION - CROP IMAGES
def extract_cropped_images_proportional(docx_path, output_dir, logo_details):
    all_extensions = tuple(['.png', '.jpg', '.jpeg', '.gif', '.tif', '.tiff','.bmp','.emf','.wmf','.svg','.ico'])
    ns = {
        "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    }
    rels_ns = {
        "pr": "http://schemas.openxmlformats.org/package/2006/relationships"
    }

    (logo_len, logo_GIF) = (logo_details[0], logo_details[1])

    with zipfile.ZipFile(docx_path, 'r') as z:
        doc_xml = etree.fromstring(z.read("word/document.xml"))
        rels_xml = etree.fromstring(z.read("word/_rels/document.xml.rels"))

        # Map relationship IDs to image filenames
        rel_map = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in rels_xml.findall(".//pr:Relationship", namespaces=rels_ns)
            if "Target" in rel.attrib and rel.attrib["Target"].startswith("media/")
        }

        # Load media binaries
        media_files = {
            name: z.read(name)
            for name in z.namelist()

            if name.startswith("word/media/") and name.lower().endswith(all_extensions)
        }

        results = []

        # Iterate over image references
        for blip in doc_xml.findall(".//a:blip", namespaces=ns):
            rid = blip.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed")
            if rid not in rel_map:
                continue

            image_name = rel_map[rid].split("/")[-1]
            image_path = f"word/{rel_map[rid]}"
            if image_path not in media_files:
                continue
            if (Path(image_path).suffix.lower()=='.XXXXwmf') :
                results.append([image_name, Path(logo_GIF)])
            else:
                try:
                    img = Image.open(io.BytesIO(media_files[image_path])).convert("RGB")
                except:
                    print('Image %s skipped' % image_name)
                    results.append((image_name, Path(output_dir)/Path(image_path)))
                else:
                    width_px, height_px = img.size

                    # Locate cropping and layout size
                    srcRect = blip.getparent().find("a:srcRect", namespaces=ns)
                    xfrm = blip.getparent().getparent().find(".//a:xfrm", namespaces=ns)
                    if srcRect is None or xfrm is None:
                        results.append(image_path)
                        continue
                    width_px, height_px = img.size
                    data_crop = {k: int(srcRect.attrib.get(k, "0")) for k in ["l", "r", "t", "b"]}
                    crop_x1 = int(data_crop['l']*width_px/100000)
                    crop_y1 = int(data_crop['t']*height_px/100000)
                    crop_x2 = int((1-data_crop['r']/100000)*width_px)
                    crop_y2 = int((1-data_crop['b']/100000)*height_px)
                    cropped = img.crop((crop_x1, crop_y1,crop_x2,crop_y2))

                    try:
                        out_path = f"{output_dir}/{image_name.replace('.', '_cropped.')}"
                        cropped.save(out_path)
                        results.append((image_name, out_path))
                    except Exception as e:
                        print(f"Failed cropping {image_name}: {e}")
                        continue

        return results

##################################################################
# FUNCTION - CONVERT WORD FILE INTO HTML
def convert_docx_to_html_with_cropped_images(docx_path, output_html_path, pic_file_mapping):
    """
    Parameters:
    - docx_path: path to the original .docx file
    - cropped_image_map: dict mapping image names like 'image1.jpeg' to full paths of cropped versions
    - output_html_path: where to save the final HTML
    """
    def convert_image(image):
        image_file_name = Path(image.open().thing.name).name
        image_file_use = pic_file_mapping[image_file_name]
        try:
            ext = Path(image_file_use).suffix[1:]
            with open(image_file_use, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            return {"src": f"data:image/{ext};base64,{b64}"}
        except StopIteration:
            print("⚠️ More images in DOCX than available cropped images. Falling back.")
            return {}
        except Exception as e:
            print(f"⚠️ Error processing image: {e}")
            return {}

    result = mammoth.convert_to_html(docx_path, convert_image=mammoth.images.inline(convert_image))
    html = result.value

    html_wrapped = f"""<!DOCTYPE html>
        <html lang="fr">
        <head>
          <meta charset="UTF-8">
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
          <style>
            body {{
              font-family: sans-serif;
              max-width: 800px;
              margin: auto;
              padding: 2em;
              line-height: 1.6;
            }}
            img {{
              max-width: 100%;
              height: auto;
              display: block;
              margin: 1em 0;
            }}
          </style>
        </head>
        <body>
        {html}
        </body>
        </html>
        """

    with open(output_html_path, "w", encoding="utf-8") as f:
        f.write(html_wrapped)
    return html_wrapped


##################################################################
# QUERY - RECEIVE WORD FILE AND PROCESS INTO HTML
@app.route("/deliver_word", methods=["POST"])
def deliver_word():
    uploaded_file = request.files.get("file")
    if not uploaded_file:
        log_upload("FAIL", "unknown", "No file uploaded")
        return "No file uploaded", 400

    # Step a: Save uploaded .docx file with timestamp
    timestamp = datetime.utcnow().strftime("%Y_%m_%d_%H_%M_%S")
    filename = f"{timestamp}.docx"
    docx_path = os.path.join(WORD_FOLDER, filename)
    uploaded_file.save(docx_path)

    try:
        # Step b: Create temp output directory for cropped images
        with tempfile.TemporaryDirectory() as output_dir:
            # Step c: Generate HTML output paths
            html_filename = f"{timestamp}.html"
            html_path = os.path.join(HTML_FOLDER, html_filename)
            latest_path = os.path.join(HTML_FOLDER, "latest_html.html")

            logo_details = (392860, "logo_paroisse2.gif")  # Placeholder — replace if dynamic

            # Process document
            results = extract_cropped_images_proportional(docx_path, output_dir, logo_details)
            results_dict = {k[0]: k[1] for k in results}
            html = convert_docx_to_html_with_cropped_images(docx_path, html_path, results_dict)

            # Also write to latest_html.html
            with open(latest_path, "w", encoding="utf-8") as f:
                f.write(html)

            # Push the HTML file to the BlackBlaze server
            push_b2_file(latest_path, 'bulletin_paroissial.html')

            log_upload("SUCCESS", filename)
            return f"✅ Processed and saved: {html_filename}", 200

    except Exception as e:
        log_upload("FAIL", filename, str(e))
        return f"❌ Error processing file: {str(e)}", 500

##################################################################
# QUERY - RETURN LATEST HTML
@app.route("/latest_word_html")
def latest_word_html():
    latest_path = os.path.join(HTML_FOLDER, "latest_html.html")

    if not os.path.exists(latest_path):
        return "No HTML has been generated yet.", 404

    return send_file(latest_path, mimetype="text/html")

##################################################################
# SUBFUNCTION FOR READINGS: DATE OP NEXT SUNDAY

def get_next_sunday():
    today = date.today()
    days_until_sunday = (6 - today.weekday()) % 7
    next_sunday = today + timedelta(days=days_until_sunday)
    return next_sunday.strftime('%Y-%m-%d')

##################################################################
# SUBFUNCTION FOR READINGS: GIVE CURRENT URL TO READ

def get_current_readings_URL():
    base_url = "https://levangileauquotidien.org/FR/gospel/"
    return base_url + get_next_sunday()


##################################################################
# SUB-FUNCTION TO FETCH READINGS VIA CHROMIUM

async def readings_extract_all_sections(url):
    logging.info("/fetch_readings async started")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            logging.info("/fetch_readings async opening URL")
            await page.goto(url)
            logging.info("/fetch_readings async opened URL")
            await page.wait_for_selector("h2")
            logging.info("/fetch_readings async selector")

            # Get all h2s (titles of sections like Première lecture, Cantique, etc.)
            titles = await page.query_selector_all("h2")
            result = []

            for title_el in titles:
                logging.info("/fetch_readings async title " + str(title_el))
                title_text = await title_el.inner_text()

                # Get the next sibling: h3 for reference
                parent = await title_el.evaluate_handle("node => node.parentElement")
                h3 = await parent.query_selector("h3")
                reference = await h3.inner_text() if h3 else ""

                # Now get the div.reading-text that follows the title
                # We'll look for the next sibling with that class
                reading_text_el = await parent.evaluate_handle('node => node.parentElement.querySelector(".reading-text")')
                text = await reading_text_el.inner_text() if reading_text_el else ""

                result.append({
                    "title": title_text,
                    "reference": reference,
                    "text": text
                })

            # Get the commentary separately
            comment_el = await page.query_selector("div.comment-text")
            commentary = await comment_el.inner_text() if comment_el else "(Pas de commentaire trouvé)"
            result.append({
                "title": "Commentaire",
                "reference": "",
                "text": commentary
            })

            await browser.close()
            return result
    except:
        return None

##################################################################
# MAIN FUNCTION TO FETCH READINGS

def fetch_readings():
    global z
    url = get_current_readings_URL()
    logging.info("/fetch_readings URL defined")
    try:
        readings = asyncio.get_event_loop().run_until_complete(readings_extract_all_sections(url))
        logging.info("/fetch_readings URL requested")
        if readings is None:
            full_text = ''
            logging.info("/fetch_readings content empty")
        else:
            logging.info("/fetch_readings content obtained")
            z = readings
            full_text = '<P>' + french_date(get_next_sunday()) + '</P?<BR>'
            logging.info("/fetch_readings starting sections")
            list_sections = ['1e lecture', 'Psaume', '2e lecture','Evangile']

            for i, r in enumerate(readings[:4]):
                logging.info("/fetch_readings processing section #%d" % i)
                full_text += '<div class="sqs-block-content">'
                full_text += f"<H3 class='sqs-block-title' style='color: rgb(55, 125, 197); margin-top: 2em; margin-bottom: 0.3em;'>{fix_encoding(list_sections[i])}</H3>\n"
                full_text += f"<I>{fix_encoding(r['title'])}</I><BR>\n"
                full_text += '<p>' + fix_encoding(r['text'])+'<BR></P>\n'
                full_text += '</DIV>'
    full_text += get_time_stamp_HTML()

    except Exception as e:
        logging.info("/fetch_readings error %s" % str(e))
        full_text = ''
    with open(READINGS_PATH_LAST, "w", encoding="utf-8") as f:
        f.write(full_text)
    logging.info(f"/fetch_readings local file written ({len(full_text)} length)")
    push_b2_file(READINGS_PATH_LAST, 'lectures.html')
    logging.info(f"/fetch_readings local file size {os.path.getsize(READINGS_PATH_LAST)} bytes")
    logging.info("/fetch_readings local file written uploaded to BB")

    with open(READINGS_PATH_STORE % get_next_sunday(), "w", encoding="utf-8") as f:
        f.write(full_text)
    push_b2_file(READINGS_PATH_STORE % get_next_sunday(), 'historique_lectures_%s.html' % get_next_sunday())
    return full_text

##################################################################
# QUERY - FETCH MASS SCHEDULE ON THE FLY
@app.route('/fetch_readings')
def force_fetch_readings():
    logging.info("/fetch_readings called")
    return fetch_readings()


##################################################################
# MAIN LOOP

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
