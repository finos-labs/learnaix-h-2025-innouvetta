import os
import snowflake.connector
import requests
from flask import Flask, request, jsonify
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
from doctr.io import DocumentFile
from doctr.models import ocr_predictor
import ssl
import logging
import json
import uuid
from werkzeug.utils import secure_filename
import tempfile
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure SSL (if needed)
ssl._create_default_https_context = ssl._create_unverified_context

# Configure logging
log_level = getattr(logging, os.getenv('LOG_LEVEL', 'INFO').upper())
log_format = os.getenv('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logging.basicConfig(level=log_level, format=log_format)
logger = logging.getLogger(__name__)

# ----------------- Flask Configuration -----------------
app = Flask(__name__)

# Flask settings from environment
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))
app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', tempfile.gettempdir())

# Allowed file extensions
ALLOWED_EXTENSIONS = set(os.getenv('ALLOWED_EXTENSIONS', 'pdf,png,jpg,jpeg').split(','))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ----------------- Snowflake Configuration -----------------
def get_snowflake_connection():
    """Create Snowflake connection using environment variables"""
    try:
        conn = snowflake.connector.connect(
            user=os.getenv('SNOWFLAKE_USER'),
            password=os.getenv('SNOWFLAKE_PASSWORD'),
            account=os.getenv('SNOWFLAKE_ACCOUNT'),
            warehouse=os.getenv('SNOWFLAKE_WAREHOUSE'),
            database=os.getenv('SNOWFLAKE_DATABASE'),
            schema=os.getenv('SNOWFLAKE_SCHEMA')
        )
        logger.info("Snowflake connection established")
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to Snowflake: {e}")
        return None

# Initialize Snowflake connection
conn = get_snowflake_connection()
cur = conn.cursor() if conn else None

# ----------------- Gemini API Configuration -----------------
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GEMINI_API_URL = os.getenv('GEMINI_API_URL')
GEMINI_MAX_TOKENS = int(os.getenv('GEMINI_MAX_TOKENS', 1500))
GEMINI_TEMPERATURE = float(os.getenv('GEMINI_TEMPERATURE', 0.7))

def call_gemini(prompt, max_tokens=None):
    """Call Gemini API with environment configuration"""
    if not GEMINI_API_KEY:
        logger.error("Gemini API key not found in environment variables")
        return "Sorry, AI service is not configured."
    
    try:
        headers = {
            "Content-Type": "application/json"
        }
        
        data = {
            "contents": [{
                "parts": [{
                    "text": prompt
                }]
            }],
            "generationConfig": {
                "maxOutputTokens": max_tokens or GEMINI_MAX_TOKENS,
                "temperature": GEMINI_TEMPERATURE
            }
        }
        
        url_with_key = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"
        response = requests.post(url_with_key, headers=headers, json=data)
        
        if response.status_code == 200:
            result = response.json()
            candidates = result.get("candidates", [])
            if candidates and "content" in candidates[0]:
                content = candidates[0]["content"]
                if "parts" in content and content["parts"]:
                    return content["parts"][0].get("text", "Sorry, I could not generate a response.")
            return "Sorry, I could not generate a response."
        else:
            logger.error(f"Gemini API error: {response.status_code} - {response.text}")
            return "Sorry, there was an error with the AI service."
            
    except Exception as e:
        logger.error(f"Error calling Gemini API: {e}")
        return "Sorry, I could not answer that due to a technical error."

# ----------------- Google Drive Configuration -----------------
def initialize_google_drive():
    """Initialize Google Drive with environment configuration"""
    try:
        service_account_file = os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE')
        settings_file = os.getenv('GOOGLE_DRIVE_SETTINGS_FILE')
        
        if not service_account_file or not os.path.exists(service_account_file):
            logger.error(f"Google service account file not found: {service_account_file}")
            return None
            
        if not settings_file or not os.path.exists(settings_file):
            logger.error(f"Google Drive settings file not found: {settings_file}")
            return None
        
        gauth = GoogleAuth(settings_file=settings_file)
        gauth.ServiceAuth()
        drive = GoogleDrive(gauth)
        logger.info("Google Drive connection established")
        return drive
    except Exception as e:
        logger.error(f"Failed to initialize Google Drive: {e}")
        return None

# Initialize Google Drive
drive = initialize_google_drive()

# ----------------- OCR Configuration -----------------
def initialize_ocr():
    """Initialize OCR model with environment configuration"""
    try:
        pretrained = os.getenv('OCR_PRETRAINED', 'True').lower() == 'true'
        ocr_model = ocr_predictor(pretrained=pretrained)
        logger.info("OCR model loaded")
        return ocr_model
    except Exception as e:
        logger.error(f"Failed to load OCR model: {e}")
        return None

# Initialize OCR
ocr_model = initialize_ocr()

# ----------------- Session Management -----------------
user_sessions = {}

class ChatSession:
    def __init__(self):
        self.state = "general"  # general, course_selection, chapter_selection, qa_mode, scoring_mode
        self.current_course = None
        self.current_chapter = None
        self.uploaded_documents = []
        self.assignment_pdf = None
        self.answer_pdf = None
        
    def reset(self):
        self.state = "general"
        self.current_course = None
        self.current_chapter = None
        self.uploaded_documents = []
        self.assignment_pdf = None
        self.answer_pdf = None

# ----------------- Database Helper Functions -----------------
def get_all_courses():
    if not cur:
        return []
    try:
        cur.execute("SELECT DISTINCT course_id FROM course_pdfs ORDER BY course_id")
        return [row[0] for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Error fetching courses: {e}")
        return []

def get_chapters_for_course(course_id):
    if not cur:
        return []
    try:
        cur.execute("SELECT DISTINCT chapter_name FROM course_pdfs WHERE course_id = %s ORDER BY chapter_name", (course_id,))
        return [row[0] for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Error fetching chapters: {e}")
        return []

def get_pdf_links(course, chapter=None):
    if not cur:
        return []
    try:
        if chapter:
            query = "SELECT course_id, chapter_name, pdf_uri FROM course_pdfs WHERE course_id = %s AND chapter_name = %s"
            cur.execute(query, (course, chapter))
        else:
            query = "SELECT course_id, chapter_name, pdf_uri FROM course_pdfs WHERE course_id = %s"
            cur.execute(query, (course,))
        return cur.fetchall()
    except Exception as e:
        logger.error(f"Error fetching PDF links: {e}")
        return []

def get_cached_ocr(course, chapter, pdf_uri):
    if not cur:
        return None
    try:
        query = "SELECT ocr_text FROM pdf_ocr_cache WHERE course_id = %s AND chapter_name = %s AND pdf_uri = %s"
        cur.execute(query, (course, chapter, pdf_uri))
        row = cur.fetchone()
        return row[0] if row else None
    except Exception as e:
        logger.error(f"Error getting cached OCR: {e}")
        return None

def cache_ocr(course, chapter, pdf_uri, ocr_text):
    if not cur:
        return
    try:
        escaped_text = ocr_text.replace("'", "''")
        query = """
        MERGE INTO pdf_ocr_cache AS target
        USING (SELECT %s AS course_id, %s AS chapter_name, %s AS pdf_uri) AS source
        ON target.course_id = source.course_id AND target.chapter_name = source.chapter_name AND target.pdf_uri = source.pdf_uri
        WHEN MATCHED THEN UPDATE SET ocr_text = %s, last_updated = CURRENT_TIMESTAMP()
        WHEN NOT MATCHED THEN INSERT (course_id, chapter_name, pdf_uri, ocr_text)
        VALUES (%s, %s, %s, %s)
        """
        cur.execute(query, (course, chapter, pdf_uri, escaped_text, course, chapter, pdf_uri, escaped_text))
        conn.commit()
    except Exception as e:
        logger.error(f"Error caching OCR: {e}")

# ----------------- File Processing Functions -----------------
def download_pdf(drive_link, local_path):
    if not drive:
        raise Exception("Google Drive not initialized")
    try:
        file_id = drive_link.split("/d/")[1].split("/")[0]
        file = drive.CreateFile({'id': file_id})
        file.GetContentFile(local_path)
        return local_path
    except Exception as e:
        logger.error(f"Error downloading PDF: {e}")
        raise

def extract_text_from_file(file_path):
    if not ocr_model:
        raise Exception("OCR model not loaded")
    
    try:
        # Handle different file types
        if file_path.lower().endswith('.pdf'):
            doc = DocumentFile.from_pdf(file_path)
        else:
            doc = DocumentFile.from_images(file_path)
        
        result = ocr_model(doc)
        text_per_page = []
        
        for page in result.pages:
            page_text = ""
            for block in page.blocks:
                for line in block.lines:
                    for word in line.words:
                        page_text += word.value + " "
                    page_text += "\n"
                page_text += "\n"
            text_per_page.append(page_text)
        
        return "\n".join(text_per_page)
    except Exception as e:
        logger.error(f"Error extracting text: {e}")
        raise

def process_course_materials(course, chapter=None):
    pdf_rows = get_pdf_links(course, chapter)
    combined_text = ""
    
    for c_id, chap_name, pdf_uri in pdf_rows:
        try:
            ocr_text = get_cached_ocr(c_id, chap_name, pdf_uri)
            
            if not ocr_text:
                os.makedirs("/tmp", exist_ok=True)
                local_path = f"/tmp/{chap_name.replace(' ', '_').replace('/', '_')}.pdf"
                download_pdf(pdf_uri, local_path)
                ocr_text = extract_text_from_file(local_path)
                cache_ocr(c_id, chap_name, pdf_uri, ocr_text)
                try:
                    os.remove(local_path)
                except:
                    pass
            
            combined_text += f"\n[{chap_name}] {ocr_text}"
            
        except Exception as e:
            logger.error(f"Error processing PDF for {chap_name}: {e}")
            continue
    
    return combined_text

# ----------------- Chat Logic Functions -----------------
def handle_general_query(message, session):
    """Handle general queries and route to specific modes"""
    message_lower = message.lower()
    
    # Check if user wants course-specific help
    course_keywords = ['course', 'subject', 'learn', 'study', 'chapter', 'material']
    scoring_keywords = ['score', 'grade', 'evaluate', 'check', 'mark', 'assessment']
    qa_keywords = ['question', 'quiz', 'test', 'practice', 'q&a', 'qa']
    
    if any(keyword in message_lower for keyword in scoring_keywords):
        session.state = "scoring_mode"
        return "I can help you score assignments! Please upload two PDFs:\n1. The assignment/question paper\n2. The student's answer sheet\n\nI'll evaluate the answers and provide detailed feedback with scores."
    
    elif any(keyword in message_lower for keyword in qa_keywords):
        courses = get_all_courses()
        if courses:
            course_list = "\n".join([f"• {course}" for course in courses])
            return f"I can generate practice questions for you! First, please choose a course from the list below, then I'll show you the chapters:\n\n{course_list}\n\nJust type the course name you're interested in."
        else:
            return "I'd love to help with practice questions, but I don't have access to course materials right now."
    
    elif any(keyword in message_lower for keyword in course_keywords):
        courses = get_all_courses()
        if courses:
            course_list = "\n".join([f"• {course}" for course in courses])
            return f"Great! I can help you with course-specific questions. Here are the available courses:\n\n{course_list}\n\nPlease type the name of the course you'd like to learn about."
        else:
            return "I'd love to help with course materials, but I don't have access to any courses right now."
    
    else:
        # Handle as general knowledge question
        prompt = f"You are a helpful educational assistant. Please answer this question clearly and educationally: {message}"
        return call_gemini(prompt)

def handle_course_selection(message, session):
    """Handle course selection"""
    courses = get_all_courses()
    message_clean = message.strip()
    
    if message_clean in courses:
        session.current_course = message_clean
        chapters = get_chapters_for_course(message_clean)
        
        if chapters:
            session.state = "chapter_selection"
            chapter_list = "\n".join([f"• {chapter}" for chapter in chapters])
            return f"Perfect! You've selected {message_clean}. Here are the available chapters:\n\n{chapter_list}\n\nPlease type the chapter name, or type 'all' to search across all chapters."
        else:
            return f"I found the course {message_clean}, but there are no chapters available. You can still ask me general questions about this course."
    else:
        course_list = "\n".join([f"• {course}" for course in courses])
        return f"I don't recognize '{message_clean}' as a course. Please choose from the available courses:\n\n{course_list}"

def handle_chapter_selection(message, session):
    """Handle chapter selection and subsequent queries"""
    if not session.current_course:
        session.reset()
        return "Something went wrong. Let's start over. What would you like to learn about?"
    
    chapters = get_chapters_for_course(session.current_course)
    message_clean = message.strip()
    
    if message_clean.lower() == 'all':
        session.current_chapter = None
        session.state = "qa_mode"
        return f"Great! I'm now ready to answer questions about all chapters in {session.current_course}. What would you like to know?"
    
    elif message_clean in chapters:
        session.current_chapter = message_clean
        session.state = "qa_mode"
        return f"Excellent! I'm now ready to answer questions about {message_clean} from {session.current_course}. What would you like to know?"
    
    else:
        chapter_list = "\n".join([f"• {chapter}" for chapter in chapters])
        return f"I don't recognize '{message_clean}' as a chapter. Please choose from:\n\n{chapter_list}\n\nOr type 'all' for all chapters."

def handle_qa_mode(message, session):
    """Handle Q&A mode with course materials"""
    if not session.current_course:
        session.reset()
        return "Something went wrong. Let's start over. What would you like to learn about?"
    
    try:
        # Check if user wants to generate practice questions
        if any(word in message.lower() for word in ['generate', 'create', 'make', 'give me questions', 'practice questions']):
            combined_text = process_course_materials(session.current_course, session.current_chapter)
            
            if combined_text.strip():
                chapter_info = f" from {session.current_chapter}" if session.current_chapter else " from all chapters"
                prompt = f"""Based on the following course material from {session.current_course}{chapter_info}, create 5 practice questions with answers. 

Course Material:
{combined_text[:3000]}

Please format as:
Q1: [Question]
A1: [Answer]

Q2: [Question]
A2: [Answer]

etc."""
                
                return call_gemini(prompt, max_tokens=1500)
            else:
                return f"I don't have material available for {session.current_course}{chapter_info} to generate questions."
        
        else:
            # Process uploaded documents if any
            uploaded_context = ""
            for doc_info in session.uploaded_documents:
                uploaded_context += f"\n[Uploaded Document] {doc_info['text']}"
            
            # Get course materials
            combined_text = process_course_materials(session.current_course, session.current_chapter)
            
            context = combined_text + uploaded_context
            
            if context.strip():
                chapter_info = f" from {session.current_chapter}" if session.current_chapter else ""
                prompt = f"""You are a helpful teaching assistant for {session.current_course}{chapter_info}. 

Student question: {message}

Please answer based on the following course material:
{context[:4000]}

Provide a clear, educational response that directly addresses the student's question."""
                
                return call_gemini(prompt, max_tokens=1000)
            else:
                return f"I don't have specific material for {session.current_course}{chapter_info}, but I can try to help with general knowledge: " + call_gemini(f"Educational question about {message}")
    
    except Exception as e:
        logger.error(f"Error in QA mode: {e}")
        return "I encountered an error while processing your question. Please try again."

def handle_scoring_mode(message, session):
    """Handle assignment scoring mode"""
    if session.assignment_pdf and session.answer_pdf:
        # Both PDFs uploaded, perform scoring
        try:
            assignment_text = session.assignment_pdf['text']
            answer_text = session.answer_pdf['text']
            
            prompt = f"""You are an experienced teacher evaluating a student's work. 

ASSIGNMENT/QUESTIONS:
{assignment_text[:2000]}

STUDENT'S ANSWERS:
{answer_text[:2000]}

Please provide:
1. Overall score out of 100
2. Detailed feedback for each question/section
3. Specific areas where the student did well
4. Areas that need improvement
5. Suggestions for better answers

Be constructive and helpful in your feedback."""
            
            response = call_gemini(prompt, max_tokens=1500)
            
            # Reset scoring mode after evaluation
            session.assignment_pdf = None
            session.answer_pdf = None
            session.state = "general"
            
            return response + "\n\n---\nScoring complete! You can upload new documents or ask me other questions."
            
        except Exception as e:
            logger.error(f"Error in scoring: {e}")
            return "I encountered an error while scoring the assignment. Please try uploading the documents again."
    
    elif session.assignment_pdf:
        return "I have the assignment. Now please upload the student's answer sheet to complete the evaluation."
    
    elif session.answer_pdf:
        return "I have the answer sheet. Now please upload the assignment/question paper to complete the evaluation."
    
    else:
        return "To score an assignment, I need both documents:\n1. The assignment/question paper\n2. The student's answer sheet\n\nPlease upload the first document."

# ----------------- Main Chat Endpoint -----------------
@app.route("/chat", methods=["POST"])
def chat():
    try:
        # Get or create session ID
        session_id = None
        if request.json:
            session_id = request.json.get('session_id')
        elif request.form:
            session_id = request.form.get('session_id')
        
        if not session_id:
            session_id = str(uuid.uuid4())
        
        if session_id not in user_sessions:
            user_sessions[session_id] = ChatSession()
        
        session = user_sessions[session_id]
        
        # Handle file uploads
        if 'file' in request.files:
            file = request.files['file']
            if file.filename != '' and allowed_file(file.filename):
                try:
                    filename = secure_filename(file.filename)
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{session_id}_{filename}")
                    file.save(filepath)
                    
                    # Extract text from uploaded file
                    extracted_text = extract_text_from_file(filepath)
                    
                    # Determine file purpose based on current state
                    if session.state == "scoring_mode":
                        if not session.assignment_pdf:
                            session.assignment_pdf = {
                                'filename': filename,
                                'text': extracted_text
                            }
                            response = f"Assignment '{filename}' uploaded successfully! Now please upload the student's answer sheet."
                        elif not session.answer_pdf:
                            session.answer_pdf = {
                                'filename': filename,
                                'text': extracted_text
                            }
                            response = handle_scoring_mode("", session)
                        else:
                            response = "I already have both documents. Processing the evaluation..."
                            response = handle_scoring_mode("", session)
                    else:
                        # Add to uploaded documents for context
                        session.uploaded_documents.append({
                            'filename': filename,
                            'text': extracted_text
                        })
                        response = f"Document '{filename}' uploaded successfully! I can now answer questions based on this document and course materials. What would you like to know?"
                    
                    # Clean up file
                    try:
                        os.remove(filepath)
                    except:
                        pass
                    
                    return jsonify({
                        "answer": response,
                        "session_id": session_id,
                        "state": session.state
                    })
                    
                except Exception as e:
                    logger.error(f"Error processing uploaded file: {e}")
                    return jsonify({"error": "Failed to process uploaded file"}), 500
        
        # Handle text messages
        data = request.json if request.json else {}
        user_message = data.get("message", "").strip()
        
        if not user_message:
            return jsonify({"error": "No message provided"}), 400
        
        # Route based on session state
        if session.state == "general":
            response = handle_general_query(user_message, session)
            # If we're showing courses, transition to course_selection state
            if any(keyword in user_message.lower() for keyword in ['course', 'subject', 'learn', 'study', 'chapter', 'material']) and 'available courses' in response:
                session.state = "course_selection"
            elif any(keyword in user_message.lower() for keyword in ['question', 'quiz', 'test', 'practice', 'q&a', 'qa']) and 'choose a course' in response:
                session.state = "course_selection"
        elif session.state == "course_selection":
            response = handle_course_selection(user_message, session)
        elif session.state == "chapter_selection":
            response = handle_chapter_selection(user_message, session)
        elif session.state == "qa_mode":
            response = handle_qa_mode(user_message, session)
        elif session.state == "scoring_mode":
            response = handle_scoring_mode(user_message, session)
        else:
            session.reset()
            response = handle_general_query(user_message, session)
        
        return jsonify({
            "answer": response,
            "session_id": session_id,
            "state": session.state,
            "current_course": session.current_course,
            "current_chapter": session.current_chapter
        })
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        return jsonify({"error": "An internal error occurred"}), 500

# ----------------- Additional Endpoints -----------------
@app.route("/reset_session", methods=["POST"])
def reset_session():
    try:
        data = request.json
        session_id = data.get("session_id")
        
        if session_id and session_id in user_sessions:
            user_sessions[session_id].reset()
            return jsonify({"message": "Session reset successfully"})
        
        return jsonify({"error": "Session not found"}), 404
    
    except Exception as e:
        logger.error(f"Error resetting session: {e}")
        return jsonify({"error": "Failed to reset session"}), 500

@app.route("/courses", methods=["GET"])
def get_courses():
    try:
        courses = get_all_courses()
        return jsonify({"courses": courses})
    except Exception as e:
        logger.error(f"Error fetching courses: {e}")
        return jsonify({"error": "Failed to fetch courses"}), 500

@app.route("/chapters/<course_id>", methods=["GET"])
def get_chapters(course_id):
    try:
        chapters = get_chapters_for_course(course_id)
        return jsonify({"chapters": chapters})
    except Exception as e:
        logger.error(f"Error fetching chapters: {e}")
        return jsonify({"error": "Failed to fetch chapters"}), 500

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "healthy",
        "snowflake": "connected" if cur else "disconnected",
        "drive": "connected" if drive else "disconnected",
        "ocr": "loaded" if ocr_model else "not loaded"
    })

if __name__ == "__main__":
    # Get Flask configuration from environment
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    
    logger.info(f"Starting Flask app on {host}:{port} with debug={debug}")
    
    # Check critical environment variables
    required_vars = ['SNOWFLAKE_USER', 'GEMINI_API_KEY']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        logger.error("Please check your .env file and ensure all required variables are set.")
    else:
        logger.info("All required environment variables are set")
    
    app.run(host=host, port=port, debug=debug)