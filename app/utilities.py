from b2sdk.v2 import InMemoryAccountInfo, B2Api
import os
import logging
import locale
import pytz
from datetime import datetime
from bs4 import BeautifulSoup
from flask import request, send_file
from babel.dates import format_datetime
import zipfile
from lxml import etree
from PIL import Image
from pathlib import Path
import io
import base64
import mammoth

UPLOAD_LOG_FILE = "upload_log.txt"

##################################################################
# LOG MESSAGES ON CONSOLE AND FILE
def log_msg(msg):
    d = datetime.now(pytz.timezone('Europe/Paris'))
    d_str = format_datetime(d, "d-MM-y HH:mm:ss", locale='fr_FR')
    if not isinstance(msg, str):
        msg = str(msg)
    print(d_str + ' ' + msg)


##################################################################
# CONNECT TO BLACKBLAZE
def get_b2_bucket(bucket_name):
    b2_info = InMemoryAccountInfo()
    b2_api = B2Api(b2_info)
    if bucket_name == 'meloir':
        b2_application_key_id = os.getenv("B2_MELOIR_KEY_ID")
        b2_application_key = os.getenv("B2_MELOIR_APPLICATION_KEY")
        b2_name = 'MeloirFiles'
    elif bucket_name == 'temperature':
        b2_application_key_id = os.getenv("B2_MELOIR_KEY_ID")
        b2_application_key = os.getenv("B2_MELOIR_APPLICATION_KEY")
        b2_name = 'MeloirFiles'
    elif bucket_name == 'berger':
        b2_application_key_id = os.getenv('B2_BERGER_KEY_ID')
        b2_application_key = os.getenv('B2_BERGER_APPLICATION_KEY')
        b2_name = 'bergerbookings'
    else:
        raise ValueError("Unknown bucket name: " + str(bucket_name))
    b2_api.authorize_account("production", b2_application_key_id, b2_application_key)
    
    return b2_api.get_bucket_by_name(b2_name)

##################################################################
# UPLOAD FILE TO BLACKBLAZE
def push_b2_file(bucket_name, file_local, file_server):
    bucket = get_b2_bucket(bucket_name)
    bucket.upload_local_file(
        local_file=file_local,
        file_name=file_server
    )

##################################################################
# DOWNLOAD FILE FROM BLACKBLAZE
def download_file_from_b2(bucket_name, file_name, local_path):
    log_msg'Getting bucket...')
    bucket = get_b2_bucket(bucket_name)
    log_msg('Done')
    log_msg('Downloading file '+ str(file_name))
    x = bucket.download_file_by_name(file_name)
    log_msg('Save file '+ str(local_path))
    x.save_to(local_path)
    log_msg('Done')
    log_msg(f"Downloaded '{file_name}' to '{local_path}'")

##################################################################
# DOWNLOAD FILE FROM BLACKBLAZE ONLY IF ABSENT LOCALLY
def download_file_from_b2_if_absent(bucket_name, file_name, local_path):
    if os.path.exists(local_path):
        log_msg('File already present: '+str(local_path))
    else:
        log_msg('Downloading from BB: ' + str(local_path) + ' | ' + str(file_name))
        download_file_from_b2(bucket_name, file_name, local_path)
        log_msg('\t\tDone')

##################################################################
# UTILITY FUNCTION - POST FILE (USING LOCAL IF AVAILABLE)
def throw_static_file(bucket_name, local_file, BB_file, message):
    log_msg(message)
    download_file_from_b2_if_absent(bucket_name, BB_file, local_file)
    log_msg('Returning content for ' + str(local_file))
    log_msg('      File size =  ' + str(os.path.getsize(local_file)))
    return send_file(local_file, mimetype="text/html")

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
# UTILITY: CURRENT DATE AND TIME IN FRENCH, USING BABEL
def get_now_french():
    paris_tz = pytz.timezone('Europe/Paris')
    now_paris = datetime.now(paris_tz)
    formatted = format_datetime(now_paris, "EEE d MMMM y 'à' HH:mm", locale='fr_FR')
    return formatted


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
# UTILITY FUNCTION - REFORMAT HTML TABLE
def reformat_html_table(html_code):
    # Define your CSS styles
    style = """
    <style>
      table {
        border-collapse: collapse;
        width: 100%;
      }
      th, td {
        border: none;
        border-bottom: 1px solid grey;
        padding: 8px;
        text-align: left;
      }
      th {
        color: #3579BE;
      }
    </style>
    """

    # Parse the HTML and add the style
    soup = BeautifulSoup(html_code, "html.parser")
    full_html = f"{style}{str(soup)}"
    return full_html

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
                    log_msg('Image %s skipped' % image_name)
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
                        log_msg(f"Failed cropping {image_name}: {e}")
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
            log_msg("⚠️ More images in DOCX than available cropped images. Falling back.")
            return {}
        except Exception as e:
            log_msg(f"⚠️ Error processing image: {str(e)}")
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
