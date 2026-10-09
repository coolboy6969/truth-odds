import re
from typing import Optional, List, Dict, Any
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

class YouTubeIngestionService:
    """
    Extracts transcripts and metadata from YouTube videos.
    """

    @staticmethod
    def extract_video_id(url_or_id: str) -> Optional[str]:
        """
        Extracts the 11-character YouTube video ID from various URL formats.
        Examples:
          - https://www.youtube.com/watch?v=dQw4w9WgXcQ
          - https://youtu.be/dQw4w9WgXcQ
          - https://www.youtube.com/embed/dQw4w9WgXcQ
          - dQw4w9WgXcQ
        """
        url_or_id = url_or_id.strip()
        if len(url_or_id) == 11 and re.match(r'^[a-zA-Z0-9_-]{11}$', url_or_id):
            return url_or_id

        patterns = [
            r'(?:v=|\/v\/|youtu\.be\/|\/embed\/|\/watch\?v=|\&v=)([a-zA-Z0-9_-]{11})',
            r'^([a-zA-Z0-9_-]{11})$'
        ]
        for pattern in patterns:
            match = re.search(pattern, url_or_id)
            if match:
                return match.group(1)
        return None

    @classmethod
    def get_transcript(cls, url_or_id: str, languages: List[str] = ['ru', 'en']) -> Dict[str, Any]:
        """
        Fetches transcript for the specified video, attempting Russian, English, or auto-translated.
        Returns a dict with video_id, full_text, segments, and status.
        """
        video_id = cls.extract_video_id(url_or_id)
        if not video_id:
            return {
                "success": False,
                "error": "Invalid YouTube URL or Video ID",
                "video_id": None,
                "full_text": ""
            }

        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            
            # Try to find transcript in requested languages or first available
            transcript = None
            try:
                transcript = transcript_list.find_transcript(languages)
            except Exception:
                # Fallback to any transcript available
                for t in transcript_list:
                    transcript = t
                    break

            if not transcript:
                return {
                    "success": False,
                    "error": "No transcripts available for this video.",
                    "video_id": video_id,
                    "full_text": ""
                }

            items = transcript.fetch()
            full_text = " ".join(item['text'] for item in items)
            
            return {
                "success": True,
                "video_id": video_id,
                "language": transcript.language_code,
                "segments_count": len(items),
                "full_text": full_text
            }

        except (TranscriptsDisabled, NoTranscriptFound) as e:
            return {
                "success": False,
                "error": f"Captions/transcripts unavailable: {str(e)}",
                "video_id": video_id,
                "full_text": ""
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error retrieving transcript: {str(e)}",
                "video_id": video_id,
                "full_text": ""
            }
