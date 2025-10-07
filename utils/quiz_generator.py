import json
import re
from google import genai
from config import Config
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

class QuizGenerator:
    def __init__(self):
        self.client = genai.Client()
        
    def deduplicate_chunks(self, chunks, threshold=0.85):
        """Deduplicate similar chunks using TF-IDF and cosine similarity."""
        if len(chunks) <= 1:
            return chunks
        
        vectorizer = TfidfVectorizer()
        tfidf_matrix = vectorizer.fit_transform(chunks)
        similarities = cosine_similarity(tfidf_matrix)
        
        keep_indices = []
        seen = set()
        
        for i in range(len(chunks)):
            if i in seen:
                continue
            keep_indices.append(i)
            for j in range(i + 1, len(chunks)):
                if similarities[i][j] > threshold:
                    seen.add(j)
        
        return [chunks[i] for i in keep_indices]
    
    def batch_chunks(self, chunks, batch_size=5):
        """Batch chunks together to reduce API calls."""
        batches = []
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            combined = "\n\n--- SECTION ---\n\n".join(batch)
            batches.append(combined)
        return batches
    
    def generate_quiz_from_batch(self, batch_text, params):
        """Generate quiz questions from a batch of text."""
        # Use the exact same prompt from the notebook
        transcript_prompt = f"""
You are a teacher creating quizzes from a lecture transcript. Using the text below, generate a quiz with a question for each important topic. The quiz should include **multiple-choice questions (MCQs)** only. Each question should have:

1. A "question" string.
2. An "options" list with exactly 4 options.
3. An "answer" string indicating the correct option.
4. A "difficulty" string which can be "easy", "medium", or "hard".

Output the quiz strictly in JSON format like this:

[
  {{
    "question": "Example question?",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "answer": "Option B",
    "difficulty": "medium",
    "explanation": "Explanation for the correct answer."
  }},
  ...
]

Make sure the output is parsable. Do not include any other characters other than the structure I have specified.

**Transcript:**
"{batch_text}"
"""
        try:
            # Generate content using Gemini
            content = self.client.models.generate_content(
                model="gemini-2.0-flash-lite",
                contents=transcript_prompt
            )
            
            # Get the text response
            response_text = content.text
            
            # Clean the response (remove markdown code blocks)
            response_text = response_text.strip("```json").strip("```").strip()
            
            # Parse JSON
            questions = json.loads(response_text)
            
            # Apply filters from params if provided
            if params.get('difficulty') and params['difficulty'] != 'mixed':
                questions = [q for q in questions if q['difficulty'] == params['difficulty']]
            
            if params.get('num_questions'):
                questions = questions[:params['num_questions']]
                
            return questions
            
        except Exception as e:
            print(f"Error generating quiz: {str(e)}")
            return []
    
    def generate_quiz(self, text_chunks, params=None):
        """Generate a complete quiz from text chunks with customization."""
        if params is None:
            params = {}
            
        # Set default parameters
        default_params = {
            'num_questions': 10,
            'difficulty': 'mixed',
            'similarity_threshold': Config.DEFAULT_SIMILARITY_THRESHOLD,
            'batch_size': Config.DEFAULT_BATCH_SIZE
        }
        
        params = {**default_params, **params}
        
        # Deduplicate chunks
        unique_chunks = self.deduplicate_chunks(
            text_chunks,
            threshold=params['similarity_threshold']
        )
        
        # Batch chunks
        batched_chunks = self.batch_chunks(
            unique_chunks,
            batch_size=params['batch_size']
        )
        
        # Generate questions from each batch
        all_questions = []
        questions_needed = params['num_questions']
        
        for batch in batched_chunks:
            if len(all_questions) >= questions_needed:
                break
                
            # Adjust number of questions for this batch
            remaining = questions_needed - len(all_questions)
            params['num_questions'] = min(remaining, 5)  # Max 5 questions per batch
            
            questions = self.generate_quiz_from_batch(batch, params)
            all_questions.extend(questions)
        
        return all_questions[:questions_needed]