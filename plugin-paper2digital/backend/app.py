import os
import snowflake.connector
import requests
from flask import Flask, request, jsonify, make_response
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
from flask_cors import CORS

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

# Configure CORS properly - SINGLE CORS SETUP
CORS(app, 
     origins=['http://localhost:8000', 'http://127.0.0.1:8000', 'http://localhost:3000', 'http://127.0.0.1:3000'],
     methods=['GET', 'POST', 'OPTIONS'],
     allow_headers=['Content-Type', 'Authorization'],
     supports_credentials=True
)

# Flask settings from environment
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))
app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', tempfile.gettempdir())

# Allowed file extensions
ALLOWED_EXTENSIONS = set(os.getenv('ALLOWED_EXTENSIONS', 'pdf,png,jpg,jpeg').split(','))

# Google Drive configuration for assignments
ASSIGNMENTS_FOLDER_ID = os.getenv('GOOGLE_DRIVE_ASSIGNMENTS_FOLDER_ID', '1example-folder-id-for-assignments')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ----------------- Multilingual Support -----------------
TRANSLATIONS = {
    'en': {
        'welcome': "Hello! I'm your educational assistant. How can I help you today?",
        'course_selection': "I can help you with course-specific questions. Here are the available courses:",
        'chapter_selection': "Perfect! You've selected {course}. Here are the available chapters:",
        'all_chapters': "Great! I'm now ready to answer questions about all chapters in {course}. What would you like to know?",
        'chapter_ready': "Excellent! I'm now ready to answer questions about {chapter} from {course}. What would you like to know?",
        'upload_success': "Document '{filename}' uploaded successfully! I can now answer questions based on this document and course materials. What would you like to know?",
        'scoring_mode': "I can help you score assignments! Please upload two PDFs:\n1. The assignment/question paper\n2. The student's answer sheet\n\nI'll evaluate the answers and provide detailed feedback with scores.",
        'assignment_uploaded': "Assignment '{filename}' uploaded successfully! Now please upload the student's answer sheet.",
        'no_courses': "I'd love to help with course materials, but I don't have access to any courses right now.",
        'course_not_found': "I don't recognize '{course}' as a course. Please choose from the available courses:",
        'chapter_not_found': "I don't recognize '{chapter}' as a chapter. Please choose from:",
        'general_help': "You can ask me:\n• General educational questions\n• Course-specific questions (I'll show you available courses)\n• Upload documents for analysis\n• Score assignments (upload both question and answer PDFs)\n• Generate practice questions\n\nWhat would you like to do?",
        'error_occurred': "I encountered an error while processing your request. Please try again.",
        'session_reset': "Session reset successfully",
        'choose_course_or_general': "Would you like to:\n1. Learn about a specific course\n2. Ask a general question\n3. Score an assignment\n4. Generate practice questions\n\nPlease let me know what you'd prefer!",
        'type_all_chapters': "Please type the chapter name, or type 'all' to search across all chapters.",
        'scoring_complete': "Scoring complete! You can upload new documents or ask me other questions.",
        'solution_submitted': "Solution submitted successfully! Your assignment has been scored.",
        'no_assignments': "No assignments found.",
        'assignment_score': "Your assignment has been scored: {score}/100"
    },
    'hi': {
        'welcome': "नमस्ते! मैं आपका शैक्षणिक सहायक हूं। आज मैं आपकी कैसे मदद कर सकता हूं?",
        'course_selection': "मैं कोर्स-विशिष्ट प्रश्नों में आपकी मदद कर सकता हूं। यहाँ उपलब्ध कोर्स हैं:",
        'chapter_selection': "बेहतरीन! आपने {course} चुना है। यहाँ उपलब्ध अध्याय हैं:",
        'all_chapters': "बहुत अच्छा! मैं अब {course} के सभी अध्यायों के बारे में प्रश्नों का उत्तर देने के लिए तैयार हूं। आप क्या जानना चाहते हैं?",
        'chapter_ready': "उत्कृष्ट! मैं अब {course} के {chapter} के बारे में प्रश्नों का उत्तर देने के लिए तैयार हूं। आप क्या जानना चाहते हैं?",
        'upload_success': "दस्तावेज़ '{filename}' सफलतापूर्वक अपलोड हो गया! अब मैं इस दस्तावेज़ और कोर्स सामग्री के आधार पर प्रश्नों का उत्तर दे सकता हूं। आप क्या जानना चाहते हैं?",
        'scoring_mode': "मैं असाइनमेंट स्कोर करने में आपकी मदद कर सकता हूं! कृपया दो PDF अपलोड करें:\n1. असाइनमेंट/प्रश्न पत्र\n2. छात्र की उत्तर पुस्तिका\n\nमैं उत्तरों का मूल्यांकन करूंगा और स्कोर के साथ विस्तृत फीडबैक प्रदान करूंगा।",
        'assignment_uploaded': "असाइनमेंट '{filename}' सफलतापूर्वक अपलोड हो गया! अब कृपया छात्र की उत्तर पुस्तिका अपलोड करें।",
        'no_courses': "मैं कोर्स सामग्री में मदद करना चाहूंगा, लेकिन मेरे पास अभी किसी कोर्स तक पहुंच नहीं है।",
        'course_not_found': "मैं '{course}' को एक कोर्स के रूप में नहीं पहचानता। कृपया उपलब्ध कोर्सों में से चुनें:",
        'chapter_not_found': "मैं '{chapter}' को एक अध्याय के रूप में नहीं पहचानता। कृपया इनमें से चुनें:",
        'general_help': "आप मुझसे पूछ सकते हैं:\n• सामान्य शैक्षणिक प्रश्न\n• कोर्स-विशिष्ट प्रश्न (मैं आपको उपलब्ध कोर्स दिखाऊंगा)\n• विश्लेषण के लिए दस्तावेज़ अपलोड करें\n• असाइनमेंट स्कोर करें (प्रश्न और उत्तर दोनों PDF अपलोड करें)\n• अभ्यास प्रश्न बनाएं\n\nआप क्या करना चाहेंगे?",
        'error_occurred': "आपके अनुरोध को संसाधित करते समय मुझे एक त्रुटि का सामना करना पड़ा। कृपया पुन: प्रयास करें।",
        'session_reset': "सेशन सफलतापूर्वक रीसेट हो गया",
        'choose_course_or_general': "क्या आप चाहेंगे:\n1. किसी विशिष्ट कोर्स के बारे में जानना\n2. सामान्य प्रश्न पूछना\n3. असाइनमेंट स्कोर करना\n4. अभ्यास प्रश्न बनाना\n\nकृपया बताएं कि आप क्या पसंद करेंगे!",
        'type_all_chapters': "कृपया अध्याय का नाम टाइप करें, या सभी अध्यायों में खोजने के लिए 'सभी' टाइप करें।",
        'scoring_complete': "स्कोरिंग पूर्ण! आप नए दस्तावेज़ अपलोड कर सकते हैं या मुझसे अन्य प्रश्न पूछ सकते हैं।",
        'solution_submitted': "समाधान सफलतापूर्वक जमा हो गया! आपके असाइनमेंट को स्कोर किया गया है।",
        'no_assignments': "कोई असाइनमेंट नहीं मिला।",
        'assignment_score': "आपके असाइनमेंट को स्कोर किया गया: {score}/100"
    },
    'es': {
        'welcome': "¡Hola! Soy tu asistente educativo. ¿Cómo puedo ayudarte hoy?",
        'course_selection': "Puedo ayudarte con preguntas específicas de cursos. Aquí están los cursos disponibles:",
        'chapter_selection': "¡Perfecto! Has seleccionado {course}. Aquí están los capítulos disponibles:",
        'all_chapters': "¡Genial! Ahora estoy listo para responder preguntas sobre todos los capítulos en {course}. ¿Qué te gustaría saber?",
        'chapter_ready': "¡Excelente! Ahora estoy listo para responder preguntas sobre {chapter} de {course}. ¿Qué te gustaría saber?",
        'upload_success': "¡Documento '{filename}' subido exitosamente! Ahora puedo responder preguntas basadas en este documento y materiales del curso. ¿Qué te gustaría saber?",
        'scoring_mode': "¡Puedo ayudarte a calificar tareas! Por favor sube dos PDFs:\n1. La tarea/papel de preguntas\n2. La hoja de respuestas del estudiante\n\nEvaluaré las respuestas y proporcionaré comentarios detallados con puntuaciones.",
        'assignment_uploaded': "¡Tarea '{filename}' subida exitosamente! Ahora por favor sube la hoja de respuestas del estudiante.",
        'no_courses': "Me encantaría ayudar con materiales del curso, pero no tengo acceso a ningún curso ahora mismo.",
        'course_not_found': "No reconozco '{course}' como un curso. Por favor elige de los cursos disponibles:",
        'chapter_not_found': "No reconozco '{chapter}' como un capítulo. Por favor elige de:",
        'general_help': "Puedes preguntarme:\n• Preguntas educativas generales\n• Preguntas específicas de cursos (te mostraré los cursos disponibles)\n• Subir documentos para análisis\n• Calificar tareas (sube PDFs de preguntas y respuestas)\n• Generar preguntas de práctica\n\n¿Qué te gustaría hacer?",
        'error_occurred': "Encontré un error al procesar tu solicitud. Por favor intenta de nuevo.",
        'session_reset': "Sesión reiniciada exitosamente",
        'choose_course_or_general': "¿Te gustaría:\n1. Aprender sobre un curso específico\n2. Hacer una pregunta general\n3. Calificar una tarea\n4. Generar preguntas de práctica\n\n¡Por favor dime qué prefieres!",
        'type_all_chapters': "Por favor escribe el nombre del capítulo, o escribe 'todo' para buscar en todos los capítulos.",
        'scoring_complete': "¡Calificación completa! Puedes subir nuevos documentos o hacerme otras preguntas.",
        'solution_submitted': "¡Solución enviada exitosamente! Tu tarea ha sido calificada.",
        'no_assignments': "No se encontraron tareas.",
        'assignment_score': "Tu tarea ha sido calificada: {score}/100"
    },
    'fr': {
        'welcome': "Bonjour! Je suis votre assistant éducatif. Comment puis-je vous aider aujourd'hui?",
        'course_selection': "Je peux vous aider avec des questions spécifiques aux cours. Voici les cours disponibles:",
        'chapter_selection': "Parfait! Vous avez sélectionné {course}. Voici les chapitres disponibles:",
        'all_chapters': "Génial! Je suis maintenant prêt à répondre aux questions sur tous les chapitres de {course}. Que souhaitez-vous savoir?",
        'chapter_ready': "Excellent! Je suis maintenant prêt à répondre aux questions sur {chapter} de {course}. Que souhaitez-vous savoir?",
        'upload_success': "Document '{filename}' téléchargé avec succès! Je peux maintenant répondre aux questions basées sur ce document et les matériaux de cours. Que souhaitez-vous savoir?",
        'scoring_mode': "Je peux vous aider à noter les devoirs! Veuillez télécharger deux PDFs:\n1. Le devoir/questionnaire\n2. La feuille de réponses de l'étudiant\n\nJ'évaluerai les réponses et fournirai des commentaires détaillés avec des scores.",
        'assignment_uploaded': "Devoir '{filename}' téléchargé avec succès! Maintenant, veuillez télécharger la feuille de réponses de l'étudiant.",
        'no_courses': "J'aimerais aider avec les matériaux de cours, mais je n'ai accès à aucun cours pour le moment.",
        'course_not_found': "Je ne reconnais pas '{course}' comme un cours. Veuillez choisir parmi les cours disponibles:",
        'chapter_not_found': "Je ne reconnais pas '{chapter}' comme un chapitre. Veuillez choisir parmi:",
        'general_help': "Vous pouvez me demander:\n• Questions éducatives générales\n• Questions spécifiques aux cours (je vous montrerai les cours disponibles)\n• Télécharger des documents pour analyse\n• Noter des devoirs (téléchargez les PDFs de questions et réponses)\n• Générer des questions de pratique\n\nQue souhaitez-vous faire?",
        'error_occurred': "J'ai rencontré une erreur lors du traitement de votre demande. Veuillez réessayer.",
        'session_reset': "Session réinitialisée avec succès",
        'choose_course_or_general': "Souhaitez-vous:\n1. Apprendre sur un cours spécifique\n2. Poser une question générale\n3. Noter un devoir\n4. Générer des questions de pratique\n\nVeuillez me dire ce que vous préférez!",
        'type_all_chapters': "Veuillez taper le nom du chapitre, ou tapez 'tous' pour rechercher dans tous les chapitres.",
        'scoring_complete': "Notation terminée! Vous pouvez télécharger de nouveaux documents ou me poser d'autres questions.",
        'solution_submitted': "Solution soumise avec succès! Votre devoir a été noté.",
        'no_assignments': "Aucun devoir trouvé.",
        'assignment_score': "Votre devoir a été noté: {score}/100"
    }
}

def get_text(key, lang='en', **kwargs):
    """Get translated text"""
    if lang not in TRANSLATIONS:
        lang = 'en'
    
    text = TRANSLATIONS[lang].get(key, TRANSLATIONS['en'].get(key, key))
    if kwargs:
        try:
            return text.format(**kwargs)
        except:
            return text
    return text

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

def call_gemini(prompt, max_tokens=None, language='en'):
    """Call Gemini API with environment configuration and language support"""
    if not GEMINI_API_KEY:
        logger.error("Gemini API key not found in environment variables")
        return get_text('error_occurred', language)
    
    # Add language instruction to prompt
    lang_instruction = {
        'en': 'Please respond in English.',
        'hi': 'कृपया हिंदी में उत्तर दें।',
        'es': 'Por favor responde en español.',
        'fr': 'Veuillez répondre en français.'
    }
    
    enhanced_prompt = f"{lang_instruction.get(language, lang_instruction['en'])}\n\n{prompt}"
    
    try:
        headers = {
            "Content-Type": "application/json"
        }
        
        data = {
            "contents": [{
                "parts": [{
                    "text": enhanced_prompt
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
                    return content["parts"][0].get("text", get_text('error_occurred', language))
            return get_text('error_occurred', language)
        else:
            logger.error(f"Gemini API error: {response.status_code} - {response.text}")
            return get_text('error_occurred', language)
            
    except Exception as e:
        logger.error(f"Error calling Gemini API: {e}")
        return get_text('error_occurred', language)

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
        self.state = "general"
        self.current_course = None
        self.current_chapter = None
        self.uploaded_documents = []
        self.assignment_pdf = None
        self.answer_pdf = None
        self.language = 'en'
        
    def reset(self):
        self.state = "general"
        self.current_course = None
        self.current_chapter = None
        self.uploaded_documents = []
        self.assignment_pdf = None
        self.answer_pdf = None

# ----------------- Assignment Helper Functions -----------------
def get_all_assignments():
    """Get all assignments from database"""
    if not cur:
        return []
    try:
        cur.execute("SELECT id, course_name, assignment_name, assignment_pdf, solution_pdf, score FROM assignments ORDER BY course_name, assignment_name")
        return cur.fetchall()
    except Exception as e:
        logger.error(f"Error fetching assignments: {e}")
        return []

def get_assignment_by_id(assignment_id):
    """Get specific assignment by ID"""
    if not cur:
        return None
    try:
        cur.execute("SELECT id, course_name, assignment_name, assignment_pdf, solution_pdf, score FROM assignments WHERE id = %s", (assignment_id,))
        return cur.fetchone()
    except Exception as e:
        logger.error(f"Error fetching assignment: {e}")
        return None

def update_assignment_solution(assignment_id, solution_pdf_link, score):
    """Update assignment with solution PDF link and score"""
    if not cur:
        return False
    try:
        cur.execute(
            "UPDATE assignments SET solution_pdf = %s, score = %s WHERE id = %s",
            (solution_pdf_link, score, assignment_id)
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error updating assignment solution: {e}")
        return False

def upload_solution_to_drive(file_path, assignment_id, assignment_name):
    """Upload solution PDF to Google Drive assignments folder"""
    if not drive:
        raise Exception("Google Drive not initialized")
    
    try:
        filename = f"solution_{assignment_id}_{assignment_name.replace(' ', '_')}.pdf"
        
        file_metadata = {
            'title': filename,
            'parents': [{'id': ASSIGNMENTS_FOLDER_ID}]
        }
        
        file_drive = drive.CreateFile(file_metadata)
        file_drive.SetContentFile(file_path)
        file_drive.Upload()
        
        # Make file shareable
        file_drive.InsertPermission({
            'type': 'anyone',
            'role': 'reader'
        })
        
        return file_drive['alternateLink']
        
    except Exception as e:
        logger.error(f"Error uploading solution to drive: {e}")
        raise

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
    lang = session.language
    
    # Check for language change
    if 'language' in message_lower or 'भाषा' in message_lower or 'idioma' in message_lower or 'langue' in message_lower:
        return get_text('choose_course_or_general', lang)
    
    # Check keywords based on language
    course_keywords = {
        'en': ['course', 'subject', 'learn', 'study', 'chapter', 'material'],
        'hi': ['कोर्स', 'विषय', 'सीखना', 'पढ़ाई', 'अध्याय', 'सामग्री'],
        'es': ['curso', 'materia', 'aprender', 'estudiar', 'capítulo', 'material'],
        'fr': ['cours', 'matière', 'apprendre', 'étudier', 'chapitre', 'matériel']
    }
    
    scoring_keywords = {
        'en': ['score', 'grade', 'evaluate', 'check', 'mark', 'assessment'],
        'hi': ['स्कोर', 'ग्रेड', 'मूल्यांकन', 'जांच', 'अंक', 'आकलन'],
        'es': ['puntuar', 'calificar', 'evaluar', 'revisar', 'marcar', 'evaluación'],
        'fr': ['noter', 'évaluer', 'vérifier', 'marquer', 'évaluation']
    }
    
    qa_keywords = {
        'en': ['question', 'quiz', 'test', 'practice', 'q&a', 'qa'],
        'hi': ['प्रश्न', 'प्रश्नोत्तरी', 'परीक्षा', 'अभ्यास'],
        'es': ['pregunta', 'cuestionario', 'prueba', 'práctica'],
        'fr': ['question', 'quiz', 'test', 'pratique']
    }
    
    # Check for scoring mode
    if any(keyword in message_lower for keyword in scoring_keywords.get(lang, scoring_keywords['en'])):
        session.state = "scoring_mode"
        return get_text('scoring_mode', lang)
    
    # Check for Q&A mode
    elif any(keyword in message_lower for keyword in qa_keywords.get(lang, qa_keywords['en'])):
        courses = get_all_courses()
        if courses:
            course_list = "\n".join([f"• {course}" for course in courses])
            return f"{get_text('course_selection', lang)}\n\n{course_list}\n\n{get_text('choose_course_or_general', lang)}"
        else:
            return get_text('no_courses', lang)
    
    # Check for course-specific help
    elif any(keyword in message_lower for keyword in course_keywords.get(lang, course_keywords['en'])):
        courses = get_all_courses()
        if courses:
            course_list = "\n".join([f"• {course}" for course in courses])
            session.state = "course_selection"
            return f"{get_text('course_selection', lang)}\n\n{course_list}"
        else:
            return get_text('no_courses', lang)
    
    else:
        # Handle as general knowledge question
        prompt = f"You are a helpful educational assistant. Please answer this question clearly and educationally: {message}"
        return call_gemini(prompt, language=lang)

def handle_course_selection(message, session):
    """Handle course selection"""
    courses = get_all_courses()
    message_clean = message.strip()
    lang = session.language
    
    if message_clean in courses:
        session.current_course = message_clean
        chapters = get_chapters_for_course(message_clean)
        
        if chapters:
            session.state = "chapter_selection"
            chapter_list = "\n".join([f"• {chapter}" for chapter in chapters])
            return f"{get_text('chapter_selection', lang, course=message_clean)}\n\n{chapter_list}\n\n{get_text('type_all_chapters', lang)}"
        else:
            return f"{get_text('chapter_selection', lang, course=message_clean)} {get_text('no_courses', lang)}"
    else:
        course_list = "\n".join([f"• {course}" for course in courses])
        return f"{get_text('course_not_found', lang, course=message_clean)}\n\n{course_list}"

def handle_chapter_selection(message, session):
    """Handle chapter selection and subsequent queries"""
    if not session.current_course:
        session.reset()
        return get_text('error_occurred', session.language)
    
    chapters = get_chapters_for_course(session.current_course)
    message_clean = message.strip()
    lang = session.language
    
    # Check for 'all' in different languages
    all_keywords = ['all', 'सभी', 'todo', 'tous']
    
    if message_clean.lower() in all_keywords:
        session.current_chapter = None
        session.state = "qa_mode"
        return get_text('all_chapters', lang, course=session.current_course)
    
    elif message_clean in chapters:
        session.current_chapter = message_clean
        session.state = "qa_mode"
        return get_text('chapter_ready', lang, chapter=message_clean, course=session.current_course)
    
    else:
        chapter_list = "\n".join([f"• {chapter}" for chapter in chapters])
        return f"{get_text('chapter_not_found', lang, chapter=message_clean)}\n\n{chapter_list}\n\n{get_text('type_all_chapters', lang)}"

def handle_qa_mode(message, session):
    """Handle Q&A mode with course materials"""
    if not session.current_course:
        session.reset()
        return get_text('error_occurred', session.language)
    
    lang = session.language
    
    try:
        # Check for practice question generation in different languages
        generate_keywords = {
            'en': ['generate', 'create', 'make', 'give me questions', 'practice questions'],
            'hi': ['बनाएं', 'प्रश्न बनाएं', 'अभ्यास प्रश्न', 'प्रश्न दें'],
            'es': ['generar', 'crear', 'hacer', 'dame preguntas', 'preguntas de práctica'],
            'fr': ['générer', 'créer', 'faire', 'donnez-moi des questions', 'questions de pratique']
        }
        
        if any(word in message.lower() for word in generate_keywords.get(lang, generate_keywords['en'])):
            combined_text = process_course_materials(session.current_course, session.current_chapter)
            
            if combined_text.strip():
                chapter_info = f" from {session.current_chapter}" if session.current_chapter else " from all chapters"
                
                question_prompts = {
                    'en': f"Based on the following course material from {session.current_course}{chapter_info}, create 5 practice questions with answers.\n\nCourse Material:\n{combined_text[:3000]}\n\nPlease format as:\nQ1: [Question]\nA1: [Answer]\n\nQ2: [Question]\nA2: [Answer]\n\netc.",
                    'hi': f"{session.current_course}{chapter_info} की निम्नलिखित कोर्स सामग्री के आधार पर, उत्तरों के साथ 5 अभ्यास प्रश्न बनाएं।\n\nकोर्स सामग्री:\n{combined_text[:3000]}\n\nकृपया इस प्रकार प्रारूपित करें:\nप्र1: [प्रश्न]\nउ1: [उत्तर]\n\nप्र2: [प्रश्न]\nउ2: [उत्तर]\n\nआदि।",
                    'es': f"Basado en el siguiente material del curso de {session.current_course}{chapter_info}, crea 5 preguntas de práctica con respuestas.\n\nMaterial del Curso:\n{combined_text[:3000]}\n\nPor favor formatea como:\nP1: [Pregunta]\nR1: [Respuesta]\n\nP2: [Pregunta]\nR2: [Respuesta]\n\netc.",
                    'fr': f"Basé sur le matériel de cours suivant de {session.current_course}{chapter_info}, créez 5 questions de pratique avec réponses.\n\nMatériel de Cours:\n{combined_text[:3000]}\n\nVeuillez formater comme:\nQ1: [Question]\nR1: [Réponse]\n\nQ2: [Question]\nR2: [Réponse]\n\netc."
                }
                
                prompt = question_prompts.get(lang, question_prompts['en'])
                return call_gemini(prompt, max_tokens=1500, language=lang)
            else:
                return f"{get_text('no_courses', lang)} {session.current_course}{chapter_info}"
        
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
                
                context_prompts = {
                    'en': f"You are a helpful teaching assistant for {session.current_course}{chapter_info}.\n\nStudent question: {message}\n\nPlease answer based on the following course material:\n{context[:4000]}\n\nProvide a clear, educational response that directly addresses the student's question.",
                    'hi': f"आप {session.current_course}{chapter_info} के लिए एक सहायक शिक्षण सहायक हैं।\n\nछात्र का प्रश्न: {message}\n\nकृपया निम्नलिखित कोर्स सामग्री के आधार पर उत्तर दें:\n{context[:4000]}\n\nएक स्पष्ट, शैक्षणिक प्रतिक्रिया प्रदान करें जो सीधे छात्र के प्रश्न को संबोधित करे।",
                    'es': f"Eres un asistente de enseñanza útil para {session.current_course}{chapter_info}.\n\nPregunta del estudiante: {message}\n\nPor favor responde basándote en el siguiente material del curso:\n{context[:4000]}\n\nProporciona una respuesta clara y educativa que aborde directamente la pregunta del estudiante.",
                    'fr': f"Vous êtes un assistant pédagogique utile pour {session.current_course}{chapter_info}.\n\nQuestion de l'étudiant: {message}\n\nVeuillez répondre en vous basant sur le matériel de cours suivant:\n{context[:4000]}\n\nFournissez une réponse claire et éducative qui répond directement à la question de l'étudiant."
                }
                
                prompt = context_prompts.get(lang, context_prompts['en'])
                return call_gemini(prompt, max_tokens=1000, language=lang)
            else:
                fallback_prompt = f"Educational question about {message}"
                return f"{get_text('no_courses', lang)} {session.current_course}{chapter_info}, " + call_gemini(fallback_prompt, language=lang)
    
    except Exception as e:
        logger.error(f"Error in QA mode: {e}")
        return get_text('error_occurred', lang)

def handle_scoring_mode(message, session):
    """Handle assignment scoring mode"""
    lang = session.language
    
    if session.assignment_pdf and session.answer_pdf:
        # Both PDFs uploaded, perform scoring
        try:
            assignment_text = session.assignment_pdf['text']
            answer_text = session.answer_pdf['text']
            
            scoring_prompts = {
                'en': f"You are an experienced teacher evaluating a student's work.\n\nASSIGNMENT/QUESTIONS:\n{assignment_text[:2000]}\n\nSTUDENT'S ANSWERS:\n{answer_text[:2000]}\n\nPlease provide:\n1. Overall score out of 100\n2. Detailed feedback for each question/section\n3. Specific areas where the student did well\n4. Areas that need improvement\n5. Suggestions for better answers\n\nBe constructive and helpful in your feedback.",
                'hi': f"आप एक अनुभवी शिक्षक हैं जो छात्र के काम का मूल्यांकन कर रहे हैं।\n\nअसाइनमेंट/प्रश्न:\n{assignment_text[:2000]}\n\nछात्र के उत्तर:\n{answer_text[:2000]}\n\nकृपया प्रदान करें:\n1. 100 में से कुल स्कोर\n2. प्रत्येक प्रश्न/अनुभाग के लिए विस्तृत फीडबैक\n3. विशिष्ट क्षेत्र जहाँ छात्र ने अच्छा काम किया\n4. सुधार की आवश्यकता वाले क्षेत्र\n5. बेहतर उत्तरों के लिए सुझाव\n\nअपने फीडबैक में रचनात्मक और सहायक बनें।",
                'es': f"Eres un profesor experimentado evaluando el trabajo de un estudiante.\n\nTAREA/PREGUNTAS:\n{assignment_text[:2000]}\n\nRESPUESTAS DEL ESTUDIANTE:\n{answer_text[:2000]}\n\nPor favor proporciona:\n1. Puntuación general sobre 100\n2. Comentarios detallados para cada pregunta/sección\n3. Áreas específicas donde el estudiante lo hizo bien\n4. Áreas que necesitan mejora\n5. Sugerencias para mejores respuestas\n\nSé constructivo y útil en tus comentarios.",
                'fr': f"Vous êtes un enseignant expérimenté évaluant le travail d'un étudiant.\n\nDEVOIR/QUESTIONS:\n{assignment_text[:2000]}\n\nRÉPONSES DE L'ÉTUDIANT:\n{answer_text[:2000]}\n\nVeuillez fournir:\n1. Score global sur 100\n2. Commentaires détaillés pour chaque question/section\n3. Domaines spécifiques où l'étudiant a bien réussi\n4. Domaines qui nécessitent des améliorations\n5. Suggestions pour de meilleures réponses\n\nSoyez constructif et utile dans vos commentaires."
            }
            
            prompt = scoring_prompts.get(lang, scoring_prompts['en'])
            response = call_gemini(prompt, max_tokens=1500, language=lang)
            
            # Reset scoring mode after evaluation
            session.assignment_pdf = None
            session.answer_pdf = None
            session.state = "general"
            
            return response + f"\n\n---\n{get_text('scoring_complete', lang)}"
            
        except Exception as e:
            logger.error(f"Error in scoring: {e}")
            return get_text('error_occurred', lang)
    
    elif session.assignment_pdf:
        return get_text('assignment_uploaded', lang, filename="answer sheet")
    
    elif session.answer_pdf:
        return get_text('assignment_uploaded', lang, filename="assignment")
    
    else:
        return get_text('scoring_mode', lang)

# ----------------- Main Chat Endpoint -----------------
@app.route("/chat", methods=["POST"])
def chat():
    try:
        # Get or create session ID - handle both JSON and FormData
        session_id = None
        user_message = None
        lang = 'en'
        
        # Check if it's a file upload (multipart/form-data)
        if request.content_type and 'multipart/form-data' in request.content_type:
            session_id = request.form.get('session_id')
            user_message = request.form.get('message', '').strip()
            lang = request.form.get('language', 'en')
        # Check if it's JSON data
        elif request.is_json and request.json:
            session_id = request.json.get('session_id')
            user_message = request.json.get('message', '').strip()
            lang = request.json.get('language', 'en')
        # Check if it's form data
        elif request.form:
            session_id = request.form.get('session_id')
            user_message = request.form.get('message', '').strip()
            lang = request.form.get('language', 'en')
        else:
            return jsonify({"error": "Invalid request format"}), 400
        
        if not session_id:
            session_id = str(uuid.uuid4())
        
        if session_id not in user_sessions:
            user_sessions[session_id] = ChatSession()
        
        session = user_sessions[session_id]
        session.language = lang if lang in TRANSLATIONS else 'en'
        
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
                            response = get_text('assignment_uploaded', session.language, filename=filename)
                        elif not session.answer_pdf:
                            session.answer_pdf = {
                                'filename': filename,
                                'text': extracted_text
                            }
                            response = handle_scoring_mode("", session)
                        else:
                            response = handle_scoring_mode("", session)
                    else:
                        # Add to uploaded documents for context
                        session.uploaded_documents.append({
                            'filename': filename,
                            'text': extracted_text
                        })
                        response = get_text('upload_success', session.language, filename=filename)
                    
                    # Clean up file
                    try:
                        os.remove(filepath)
                    except:
                        pass
                    
                    return jsonify({
                        "answer": response,
                        "session_id": session_id,
                        "state": session.state,
                        "language": session.language
                    })
                    
                except Exception as e:
                    logger.error(f"Error processing uploaded file: {e}")
                    return jsonify({"error": get_text('error_occurred', session.language)}), 500
        
        # Handle text messages
        if not user_message:
            return jsonify({"error": "No message provided"}), 400
        
        # Route based on session state
        if session.state == "general":
            response = handle_general_query(user_message, session)
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
            "current_chapter": session.current_chapter,
            "language": session.language
        })
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        return jsonify({"error": "An internal error occurred"}), 500

# ----------------- Assignment Endpoints -----------------
@app.route("/assignments", methods=["GET"])
def get_assignments():
    """Get all assignments"""
    try:
        assignments = get_all_assignments()
        assignments_list = []
        
        for assignment in assignments:
            assignments_list.append({
                "id": assignment[0],
                "course_name": assignment[1],
                "assignment_name": assignment[2],
                "assignment_pdf": assignment[3],
                "solution_pdf": assignment[4],
                "score": assignment[5]
            })
        
        return jsonify({"assignments": assignments_list})
    except Exception as e:
        logger.error(f"Error fetching assignments: {e}")
        return jsonify({"error": "Failed to fetch assignments"}), 500

@app.route("/submit_solution", methods=["POST"])
def submit_solution():
    """Submit solution for an assignment"""
    try:
        assignment_id = request.form.get('assignment_id')
        
        if not assignment_id:
            return jsonify({"error": "Assignment ID is required"}), 400
            
        # Get assignment details
        assignment = get_assignment_by_id(assignment_id)
        if not assignment:
            return jsonify({"error": "Assignment not found"}), 404
            
        # Check if solution file is uploaded
        if 'solution_file' not in request.files:
            return jsonify({"error": "Solution file is required"}), 400
            
        file = request.files['solution_file']
        if file.filename == '' or not allowed_file(file.filename):
            return jsonify({"error": "Invalid file format"}), 400
        
        # Save and process the solution file
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"solution_{assignment_id}_{filename}")
        file.save(filepath)
        
        try:
            # Extract text from solution file
            solution_text = extract_text_from_file(filepath)
            
            # Download and extract text from assignment PDF
            assignment_pdf_path = f"/tmp/assignment_{assignment_id}.pdf"
            download_pdf(assignment[3], assignment_pdf_path)  # assignment[3] is assignment_pdf URL
            assignment_text = extract_text_from_file(assignment_pdf_path)
            
            # Score the solution using Gemini
            prompt = f"You are an experienced teacher evaluating a student's work. Please provide a numerical score out of 100 and brief feedback.\n\nASSIGNMENT:\n{assignment_text[:2000]}\n\nSTUDENT'S SOLUTION:\n{solution_text[:2000]}\n\nPlease respond in the format:\nSCORE: [number]/100\nFEEDBACK: [brief feedback]"
            
            gemini_response = call_gemini(prompt, max_tokens=500)
            
            # Extract score from response
            score = 0
            try:
                if "SCORE:" in gemini_response:
                    score_line = gemini_response.split("SCORE:")[1].split("FEEDBACK:")[0].strip()
                    score = int(score_line.split("/")[0].strip())
            except:
                score = 75  # Default score if parsing fails
                
            # Upload solution to Google Drive
            solution_drive_link = upload_solution_to_drive(
                filepath, assignment_id, assignment[2]  # assignment[2] is assignment_name
            )
            
            # Update database
            update_assignment_solution(assignment_id, solution_drive_link, score)
            
            # Clean up files
            try:
                os.remove(filepath)
                os.remove(assignment_pdf_path)
            except:
                pass
            
            return jsonify({
                "message": get_text('solution_submitted'),
                "score": score,
                "feedback": gemini_response,
                "solution_pdf": solution_drive_link
            })
            
        except Exception as e:
            # Clean up file on error
            try:
                os.remove(filepath)
            except:
                pass
            raise e
            
    except Exception as e:
        logger.error(f"Error submitting solution: {e}")
        return jsonify({"error": get_text('error_occurred')}), 500

# ----------------- Additional Endpoints -----------------
@app.route("/reset_session", methods=["POST"])
def reset_session():
    try:
        # Handle both JSON and form data
        if request.is_json and request.json:
            data = request.json
        elif request.form:
            data = request.form
        else:
            return jsonify({"error": "Invalid request format"}), 400
            
        session_id = data.get("session_id")
        
        if session_id and session_id in user_sessions:
            lang = user_sessions[session_id].language
            user_sessions[session_id].reset()
            user_sessions[session_id].language = lang
            return jsonify({"message": get_text('session_reset', lang)})
        
        return jsonify({"error": "Session not found"}), 404
    
    except Exception as e:
        logger.error(f"Error resetting session: {e}")
        return jsonify({"error": "Failed to reset session"}), 500

@app.route("/set_language", methods=["POST"])
def set_language():
    try:
        # Handle both JSON and form data
        if request.is_json and request.json:
            data = request.json
        elif request.form:
            data = request.form
        else:
            return jsonify({"error": "Invalid request format"}), 400
            
        session_id = data.get("session_id")
        language = data.get("language", 'en')
        
        if language not in TRANSLATIONS:
            language = 'en'
            
        if session_id and session_id in user_sessions:
            user_sessions[session_id].language = language
            return jsonify({
                "message": get_text('welcome', language),
                "language": language
            })
        
        return jsonify({"error": "Session not found"}), 404
    
    except Exception as e:
        logger.error(f"Error setting language: {e}")
        return jsonify({"error": "Failed to set language"}), 500

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

@app.route("/languages", methods=["GET"])
def get_languages():
    try:
        return jsonify({
            "languages": [
                {"code": "en", "name": "English"},
                {"code": "hi", "name": "हिंदी"},
                {"code": "es", "name": "Español"},
                {"code": "fr", "name": "Français"}
            ]
        })
    except Exception as e:
        logger.error(f"Error fetching languages: {e}")
        return jsonify({"error": "Failed to fetch languages"}), 500

# ----------------- API Compatibility Routes -----------------
@app.route("/api/ask", methods=["POST"])
def api_ask():
    """Compatibility route that redirects to /chat endpoint"""
    return chat()

@app.route("/ask", methods=["POST"])  
def ask():
    """Alternative compatibility route"""
    return chat()

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "healthy",
        "snowflake": "connected" if cur else "disconnected",
        "drive": "connected" if drive else "disconnected",
        "ocr": "loaded" if ocr_model else "not loaded",
        "languages": list(TRANSLATIONS.keys())
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