import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account
import snowflake.connector
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ---------- Google Drive Setup ----------
SCOPES = ['https://www.googleapis.com/auth/drive']
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
PARENT_FOLDER_ID = os.getenv("GOOGLE_DRIVE_PARENT_FOLDER_ID")

creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)
service = build('drive', 'v3', credentials=creds)

# ---------- Snowflake Setup ----------
conn = snowflake.connector.connect(
    user=os.getenv("SNOWFLAKE_USER"),
    password=os.getenv("SNOWFLAKE_PASSWORD"),
    account=os.getenv("SNOWFLAKE_ACCOUNT"),
    warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
    database=os.getenv("SNOWFLAKE_DATABASE"),
    schema=os.getenv("SNOWFLAKE_SCHEMA")
)
cur = conn.cursor()

# ---------- Base path ----------
BASE_PATH = os.getenv("COURSE_PDFS_BASE_PATH")

def create_drive_folder(folder_name, parent_id):
    """Create a subfolder in Google Drive and return its ID"""
    # Check if folder already exists
    query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and '{parent_id}' in parents"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get('files', [])
    if files:
        return files[0]['id']
    
    # Create new folder
    folder_metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_id]
    }
    folder = service.files().create(body=folder_metadata, fields='id').execute()
    return folder.get('id')

for course in os.listdir(BASE_PATH):
    course_path = os.path.join(BASE_PATH, course)
    if not os.path.isdir(course_path):
        continue

    # Insert course into Snowflake
    cur.execute(f"""
    MERGE INTO courses t
    USING (SELECT '{course}' AS course_id, '{course}' AS course_name) s
    ON t.course_id = s.course_id
    WHEN NOT MATCHED THEN
        INSERT (course_id, course_name)
        VALUES (s.course_id, s.course_name)
    """)

    # Create Drive subfolder for course
    course_folder_id = create_drive_folder(course, PARENT_FOLDER_ID)

    # Process PDFs inside the course folder
    for pdf_file in os.listdir(course_path):
        if not pdf_file.lower().endswith('.pdf'):
            continue

        local_pdf_path = os.path.join(course_path, pdf_file)
        chapter_name = os.path.splitext(pdf_file)[0]  # remove '.pdf'

        # ---------- Upload PDF to Google Drive ----------
        file_metadata = {
            'name': pdf_file,
            'parents': [course_folder_id]
        }
        media = MediaFileUpload(local_pdf_path, mimetype='application/pdf')
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        file_id = file.get('id')
        drive_link = f'https://drive.google.com/file/d/{file_id}/view?usp=sharing'

        # ---------- Insert PDF record in Snowflake ----------
        cur.execute(f"""
        MERGE INTO course_pdfs t
        USING (SELECT '{course}' AS course_id, '{chapter_name}' AS chapter_name, '{drive_link}' AS pdf_uri) s
        ON t.course_id = s.course_id AND t.chapter_name = s.chapter_name AND t.pdf_uri = s.pdf_uri
        WHEN NOT MATCHED THEN
            INSERT (course_id, chapter_name, pdf_uri)
            VALUES (s.course_id, s.chapter_name, s.pdf_uri)
        """)

conn.commit()
cur.close()
conn.close()
print("All PDFs uploaded to Google Drive and Snowflake tables updated!")