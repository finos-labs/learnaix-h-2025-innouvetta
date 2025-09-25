import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account
import snowflake.connector
from dotenv import load_dotenv
import traceback

# Load environment variables from .env file
load_dotenv()

# ---------- Google Drive Setup ----------
SCOPES = ['https://www.googleapis.com/auth/drive']
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
PARENT_FOLDER_ID = os.getenv("GOOGLE_DRIVE_ASSIGNMENTS_FOLDER_ID")

print(f"Service Account File: {SERVICE_ACCOUNT_FILE}")
print(f"Parent Folder ID: {PARENT_FOLDER_ID}")

try:
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    service = build('drive', 'v3', credentials=creds)
    print("✓ Google Drive service initialized successfully")
except Exception as e:
    print(f"✗ Error initializing Google Drive service: {e}")
    exit(1)

# ---------- Snowflake Setup ----------
try:
    conn = snowflake.connector.connect(
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        database=os.getenv("SNOWFLAKE_DATABASE"),
        schema=os.getenv("SNOWFLAKE_SCHEMA")
    )
    cur = conn.cursor()
    print("✓ Snowflake connection established successfully")
except Exception as e:
    print(f"✗ Error connecting to Snowflake: {e}")
    exit(1)

# ---------- Base path ----------
BASE_PATH = os.getenv("ASSIGNMENTS_PDFS_BASE_PATH")
print(f"Base Path: {BASE_PATH}")

if not os.path.exists(BASE_PATH):
    print(f"✗ Base path does not exist: {BASE_PATH}")
    exit(1)

def create_drive_folder(folder_name, parent_id):
    """Create a subfolder in Google Drive and return its ID"""
    try:
        # Check if folder already exists
        query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and '{parent_id}' in parents"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get('files', [])
        
        if files:
            print(f"  ✓ Found existing folder: {folder_name} (ID: {files[0]['id']})")
            return files[0]['id']
        
        # Create new folder
        folder_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_id]
        }
        folder = service.files().create(body=folder_metadata, fields='id').execute()
        folder_id = folder.get('id')
        print(f"  ✓ Created new folder: {folder_name} (ID: {folder_id})")
        return folder_id
    except Exception as e:
        print(f"  ✗ Error creating/finding folder {folder_name}: {e}")
        raise

# Check if base path has any folders
folders_found = []
for item in os.listdir(BASE_PATH):
    item_path = os.path.join(BASE_PATH, item)
    if os.path.isdir(item_path):
        folders_found.append(item)

print(f"Found {len(folders_found)} course folders: {folders_found}")

if not folders_found:
    print("✗ No course folders found in base path")
    exit(1)

# Process each course folder
processed_count = 0
for course in folders_found:
    try:
        course_path = os.path.join(BASE_PATH, course)
        print(f"\n--- Processing course: {course} ---")
        
        # Check for PDF files in this course folder
        pdf_files = [f for f in os.listdir(course_path) if f.lower().endswith('.pdf')]
        print(f"  Found {len(pdf_files)} PDF files: {pdf_files}")
        
        if not pdf_files:
            print(f"  ⚠ No PDF files found in {course}")
            continue
        
        # Create Drive subfolder for course
        print(f"  Creating/finding Google Drive folder for: {course}")
        course_folder_id = create_drive_folder(course, PARENT_FOLDER_ID)
        
        # Process PDFs inside the course folder
        for pdf_file in pdf_files:
            try:
                local_pdf_path = os.path.join(course_path, pdf_file)
                assignment_name = os.path.splitext(pdf_file)[0]  # remove '.pdf' extension
                
                print(f"    Processing PDF: {pdf_file}")
                print(f"    Assignment name: {assignment_name}")
                print(f"    Local path: {local_pdf_path}")
                
                # Check if file exists and is readable
                if not os.path.exists(local_pdf_path):
                    print(f"    ✗ File does not exist: {local_pdf_path}")
                    continue
                
                file_size = os.path.getsize(local_pdf_path)
                print(f"    File size: {file_size} bytes")
                
                if file_size == 0:
                    print(f"    ✗ File is empty: {local_pdf_path}")
                    continue
                
                # ---------- Upload PDF to Google Drive ----------
                print(f"    Uploading to Google Drive...")
                file_metadata = {
                    'name': pdf_file,
                    'parents': [course_folder_id]
                }
                media = MediaFileUpload(local_pdf_path, mimetype='application/pdf')
                file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
                file_id = file.get('id')
                drive_link = f'https://drive.google.com/file/d/{file_id}/view?usp=sharing'
                
                print(f"    ✓ Uploaded successfully. File ID: {file_id}")
                print(f"    Drive link: {drive_link}")
                
                # ---------- Insert assignment record in Snowflake ----------
                print(f"    Inserting into Snowflake...")
                cur.execute(f"""
                    MERGE INTO assignments t
                    USING (SELECT '{course}' AS course_name, '{assignment_name}' AS assignment_name, '{drive_link}' AS assignment_pdf) s
                    ON t.course_name = s.course_name AND t.assignment_name = s.assignment_name
                    WHEN NOT MATCHED THEN
                        INSERT (course_name, assignment_name, assignment_pdf)
                        VALUES (s.course_name, s.assignment_name, s.assignment_pdf)
                    WHEN MATCHED THEN
                        UPDATE SET assignment_pdf = s.assignment_pdf
                """)
                
                print(f"    ✓ Database record updated")
                processed_count += 1
                
            except Exception as e:
                print(f"    ✗ Error processing {pdf_file}: {e}")
                print(f"    Traceback: {traceback.format_exc()}")
                continue
                
    except Exception as e:
        print(f"✗ Error processing course {course}: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        continue

try:
    conn.commit()
    print(f"\n✓ All changes committed to database")
except Exception as e:
    print(f"✗ Error committing to database: {e}")

cur.close()
conn.close()
print(f"\n=== Summary ===")
print(f"Total files processed successfully: {processed_count}")
print("Script completed!")