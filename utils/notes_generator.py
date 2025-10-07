import json
import re
from google import genai
from config import Config
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

class NotesGenerator:
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
    
    def clean_json_response(self, response_text):
        """Clean and extract JSON from response."""
        response_text = re.sub(r'```json\s*', '', response_text)
        response_text = re.sub(r'```\s*', '', response_text)
        
        match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if match:
            response_text = match.group(0)
        
        return response_text.strip()
    
    def generate_notes_from_batch(self, batch_text, batch_index, total_batches):
        """Generate structured notes from a batch of chunks using Gemini."""
        notes_prompt = f"""
You are an expert note-taker creating comprehensive, well-structured notes from the following content (which contains multiple sections separated by "--- SECTION ---").

Create detailed notes that:
1. Organize information into clear topics and subtopics
2. Extract key concepts, definitions, and important points
3. Include relevant examples and explanations
4. Use bullet points for clarity
5. Highlight important terminology

Output the notes in JSON format with this structure:

{{
  "sections": [
    {{
      "title": "Main Topic Title",
      "content": "Overview or introduction to this section",
      "subsections": [
        {{
          "subtitle": "Subtopic Title",
          "points": [
            "Key point 1",
            "Key point 2",
            "Key point 3"
          ]
        }}
      ],
      "key_terms": [
        {{
          "term": "Important Term",
          "definition": "Definition of the term"
        }}
      ],
      "examples": [
        "Example 1 explanation",
        "Example 2 explanation"
      ]
    }}
  ]
}}

Make sure the output is valid JSON. Do not include any other text outside the JSON structure.

**Content:**
"{batch_text}"
"""
        
        try:
            print(f"Generating notes from batch {batch_index + 1}/{total_batches}...")
            
            content = self.client.models.generate_content(
                model="gemini-2.0-flash-lite",
                contents=notes_prompt
            )
            
            response_text = content.text
            cleaned_response = self.clean_json_response(response_text)
            
            # Parse JSON
            notes_data = json.loads(cleaned_response)
            
            section_count = len(notes_data.get('sections', []))
            print(f"  ✓ Generated {section_count} section(s)")
            return notes_data
            
        except json.JSONDecodeError as e:
            print(f"  ✗ JSON parsing error for batch {batch_index + 1}: {e}")
            return {"sections": []}
        except Exception as e:
            print(f"  ✗ Error generating notes for batch {batch_index + 1}: {e}")
            return {"sections": []}
    
    def merge_notes(self, all_notes_batches):
        """Merge notes from multiple batches into a single structured document."""
        merged = {
            "title": "Generated Notes",
            "sections": []
        }
        
        for batch_notes in all_notes_batches:
            if 'sections' in batch_notes:
                merged['sections'].extend(batch_notes['sections'])
        
        return merged
    
    def convert_notes_to_markdown(self, notes_data):
        """Convert JSON notes to Markdown format."""
        markdown = f"# {notes_data.get('title', 'Notes')}\n\n"
        
        for section in notes_data.get('sections', []):
            # Section title
            markdown += f"## {section.get('title', 'Untitled Section')}\n\n"
            
            # Section content
            if section.get('content'):
                markdown += f"{section['content']}\n\n"
            
            # Subsections
            for subsection in section.get('subsections', []):
                markdown += f"### {subsection.get('subtitle', 'Untitled Subsection')}\n\n"
                
                for point in subsection.get('points', []):
                    markdown += f"- {point}\n"
                markdown += "\n"
            
            # Key terms
            if section.get('key_terms'):
                markdown += "#### Key Terms\n\n"
                for term_obj in section['key_terms']:
                    term = term_obj.get('term', '')
                    definition = term_obj.get('definition', '')
                    markdown += f"**{term}**: {definition}\n\n"
            
            # Examples
            if section.get('examples'):
                markdown += "#### Examples\n\n"
                for idx, example in enumerate(section['examples'], 1):
                    markdown += f"{idx}. {example}\n"
                markdown += "\n"
            
            markdown += "---\n\n"
        
        return markdown
    
    def generate_notes(self, text_chunks, params=None):
        """Generate comprehensive notes from text chunks."""
        if params is None:
            params = {}
            
        # Set default parameters
        default_params = {
            'similarity_threshold': Config.DEFAULT_SIMILARITY_THRESHOLD,
            'batch_size': Config.DEFAULT_BATCH_SIZE
        }
        
        params = {**default_params, **params}
        
        print("=" * 60)
        print("Starting Notes Generation")
        print("=" * 60)
        
        # Deduplicate chunks
        print(f"\n1. Deduplicating chunks (threshold={params['similarity_threshold']})...")
        unique_chunks = self.deduplicate_chunks(
            text_chunks,
            threshold=params['similarity_threshold']
        )
        print(f"   Kept {len(unique_chunks)} unique chunks")
        
        # Batch chunks together
        print(f"\n2. Batching chunks (batch_size={params['batch_size']})...")
        batched_chunks = self.batch_chunks(
            unique_chunks,
            batch_size=params['batch_size']
        )
        print(f"   Created {len(batched_chunks)} batches")
        
        # Generate notes from each batch
        print(f"\n3. Generating notes...")
        all_notes_batches = []
        
        for idx, batch in enumerate(batched_chunks):
            notes = self.generate_notes_from_batch(batch, idx, len(batched_chunks))
            all_notes_batches.append(notes)
        
        # Merge all notes
        print(f"\n4. Merging notes from all batches...")
        final_notes = self.merge_notes(all_notes_batches)
        total_sections = len(final_notes.get('sections', []))
        print(f"   Total sections: {total_sections}")
        
        print("\n" + "=" * 60)
        print(f"✓ Notes generation complete!")
        print(f"  Total sections generated: {total_sections}")
        print("=" * 60)
        
        return final_notes