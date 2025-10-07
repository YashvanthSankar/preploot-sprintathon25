from youtube_transcript_api import YouTubeTranscriptApi
import re

def extract_video_id(url):
    """Extract YouTube video ID from various URL formats."""
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([^&\n?#]+)',
        r'youtube\.com\/watch\?.*v=([^&\n?#]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def get_transcript(video_id):
    """Get transcript from YouTube video."""
    try:
        ytt_api = YouTubeTranscriptApi()
        fetched_transcript = ytt_api.fetch(video_id)
        
        # Process transcript exactly like the notebook
        full_text = ""
        for snippet in fetched_transcript:
            full_text += snippet.text + " "
            
        return full_text
    except Exception as e:
        raise Exception(f"Failed to fetch transcript: {str(e)}")