import os
import hashlib
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
from utils.youtube import extract_video_id, get_transcript
from utils.pdf_processor import PDFProcessor
from utils.quiz_generator import QuizGenerator
from utils.notes_generator import NotesGenerator
from utils.cache_manager import CacheManager
from utils.user_manager import create_user_directories
from config import Config

app = Flask(__name__)
CORS(app)  # Enable CORS
app.config.from_object(Config)

# Initialize components
quiz_generator = QuizGenerator()
notes_generator = NotesGenerator()
cache_manager = CacheManager()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS

@app.route('/api/user/<user_id>/upload/pdf', methods=['POST'])
def upload_pdf(user_id):
    """Upload PDF or DOCX for a specific user."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
        
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Only PDF and DOCX files are allowed.'}), 400
    
    try:
        # Create user-specific PDF processor
        pdf_processor = PDFProcessor(user_id)
        
        filename = secure_filename(file.filename)
        file_data = file.read()
        
        # Save file to user's data folder
        file_path = pdf_processor.save_file(file_data, filename)
        
        # Process file and store in user's vector database
        vectorstore = pdf_processor.store_chroma_function()
        
        # Generate cache ID from file content and user ID
        file_hash = hashlib.md5(file_data).hexdigest()
        cache_id = f'doc_{user_id}_{file_hash}'
        
        return jsonify({
            'message': f'{filename} processed successfully',
            'cache_id': cache_id,
            'user_id': user_id,
            'file_type': 'pdf' if filename.endswith('.pdf') else 'docx'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/<user_id>/upload/youtube', methods=['POST'])
def process_youtube(user_id):
    """Process YouTube video for a specific user."""
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({'error': 'No URL provided'}), 400
    
    try:
        video_id = extract_video_id(data['url'])
        if not video_id:
            return jsonify({'error': 'Invalid YouTube URL'}), 400
        
        # Check cache first
        cache_id = f'yt_{user_id}_{video_id}'
        cached_transcript = cache_manager.get_from_cache(cache_id)
        
        if cached_transcript:
            return jsonify({
                'message': 'Transcript retrieved from cache',
                'cache_id': cache_id,
                'user_id': user_id
            })
        
        # Fetch and process transcript
        transcript = get_transcript(video_id)
        cache_manager.save_to_cache(transcript, cache_id)
        
        return jsonify({
            'message': 'YouTube transcript processed successfully',
            'cache_id': cache_id,
            'user_id': user_id
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/<user_id>/generate/quiz', methods=['POST'])
def generate_quiz(user_id):
    """Generate quiz for a specific user."""
    data = request.get_json()
    if not data or 'cache_id' not in data:
        return jsonify({'error': 'No cache ID provided'}), 400
    
    try:
        # Get parameters
        params = {
            'num_questions': int(data.get('num_questions', 10)),
            'difficulty': data.get('difficulty', 'mixed'),
            'similarity_threshold': float(data.get('similarity_threshold', Config.DEFAULT_SIMILARITY_THRESHOLD))
        }
        
        # Validate parameters
        if params['num_questions'] > Config.MAX_QUESTIONS_PER_QUIZ:
            return jsonify({'error': f'Maximum {Config.MAX_QUESTIONS_PER_QUIZ} questions allowed'}), 400
        
        if params['difficulty'] not in ['mixed', 'easy', 'medium', 'hard']:
            return jsonify({'error': 'Invalid difficulty level'}), 400
        
        # Check for cached quiz
        quiz_cache_id = f"{data['cache_id']}_{params['num_questions']}_{params['difficulty']}"
        cached_quiz = cache_manager.get_from_cache(quiz_cache_id)
        
        if cached_quiz:
            return jsonify({
                'message': 'Quiz retrieved from cache',
                'quiz': cached_quiz,
                'user_id': user_id
            })
        
        # Generate new quiz
        if data['cache_id'].startswith(f'yt_{user_id}_'):
            # Handle YouTube transcript
            transcript = cache_manager.get_from_cache(data['cache_id'])
            if not transcript:
                return jsonify({'error': 'Transcript not found'}), 404
            
            quiz = quiz_generator.generate_quiz([transcript], params)
        elif data['cache_id'].startswith(f'doc_{user_id}_'):
            # Handle document (PDF/DOCX) content
            pdf_processor = PDFProcessor(user_id)
            vectorstore = pdf_processor.get_vectorstore()
            if not vectorstore:
                return jsonify({'error': 'No documents in vector store'}), 404
            
            all_docs = vectorstore.get()
            if not all_docs or 'documents' not in all_docs:
                return jsonify({'error': 'No documents found'}), 404
            
            quiz = quiz_generator.generate_quiz(all_docs['documents'], params)
        else:
            return jsonify({'error': 'Invalid cache ID format'}), 400
        
        # Cache the generated quiz
        cache_manager.save_to_cache(quiz, quiz_cache_id)
        
        return jsonify({
            'message': 'Quiz generated successfully',
            'quiz': quiz,
            'user_id': user_id
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/<user_id>/generate/notes', methods=['POST'])
def generate_notes(user_id):
    """Generate notes for a specific user."""
    data = request.get_json()
    if not data or 'cache_id' not in data:
        return jsonify({'error': 'No cache ID provided'}), 400
    
    try:
        # Get parameters
        params = {
            'similarity_threshold': float(data.get('similarity_threshold', Config.DEFAULT_SIMILARITY_THRESHOLD)),
            'batch_size': int(data.get('batch_size', Config.DEFAULT_BATCH_SIZE))
        }
        
        # Check for cached notes
        notes_cache_id = f"{data['cache_id']}_notes_{params['similarity_threshold']}"
        cached_notes = cache_manager.get_from_cache(notes_cache_id)
        
        if cached_notes:
            return jsonify({
                'message': 'Notes retrieved from cache',
                'notes': cached_notes,
                'user_id': user_id
            })
        
        # Generate new notes
        if data['cache_id'].startswith(f'yt_{user_id}_'):
            # Handle YouTube transcript
            transcript = cache_manager.get_from_cache(data['cache_id'])
            if not transcript:
                return jsonify({'error': 'Transcript not found'}), 404
            
            notes = notes_generator.generate_notes([transcript], params)
        elif data['cache_id'].startswith(f'doc_{user_id}_'):
            # Handle document (PDF/DOCX) content
            pdf_processor = PDFProcessor(user_id)
            vectorstore = pdf_processor.get_vectorstore()
            if not vectorstore:
                return jsonify({'error': 'No documents in vector store'}), 404
            
            all_docs = vectorstore.get()
            if not all_docs or 'documents' not in all_docs:
                return jsonify({'error': 'No documents found'}), 404
            
            notes = notes_generator.generate_notes(all_docs['documents'], params)
        else:
            return jsonify({'error': 'Invalid cache ID format'}), 400
        
        # Cache the generated notes
        cache_manager.save_to_cache(notes, notes_cache_id)
        
        # Also generate markdown version
        markdown_content = notes_generator.convert_notes_to_markdown(notes)
        
        return jsonify({
            'message': 'Notes generated successfully',
            'notes': notes,
            'markdown': markdown_content,
            'user_id': user_id
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/<user_id>/files', methods=['GET'])
def list_user_files(user_id):
    """List all files for a specific user."""
    try:
        from utils.user_manager import list_user_files
        files = list_user_files(user_id)
        file_names = [os.path.basename(f) for f in files]
        
        return jsonify({
            'user_id': user_id,
            'files': file_names,
            'count': len(file_names)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/<user_id>/clear', methods=['DELETE'])
def clear_user_data(user_id):
    """Clear all data for a specific user."""
    try:
        from utils.user_manager import delete_user_data
        delete_user_data(user_id)
        
        return jsonify({
            'message': f'All data cleared for user {user_id}',
            'user_id': user_id
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Create required directories and initialize app
def create_app():
    os.makedirs(Config.BASE_DATA_DIR, exist_ok=True)
    os.makedirs(Config.CACHE_FOLDER, exist_ok=True)

create_app()

# Periodic cleanup of expired cache
@app.before_request
def cleanup_cache():
    cache_manager.clear_expired_cache()

if __name__ == '__main__':
    app.run(debug=True)