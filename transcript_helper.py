from youtube_transcript_api import YouTubeTranscriptApi

# Try to import specific exceptions for better error handling
try:
    from youtube_transcript_api._errors import (
        TranscriptsDisabled, 
        NoTranscriptFound, 
        NoTranscriptAvailable,
        VideoUnavailable
    )
except ImportError:
    # Fallback for older versions - create dummy classes
    class TranscriptsDisabled(Exception): pass
    class NoTranscriptFound(Exception): pass
    class NoTranscriptAvailable(Exception): pass
    class VideoUnavailable(Exception): pass

# Extended language list for better transcript coverage
LANGUAGES_TO_TRY = [
    'en', 'en-US', 'en-GB', 'en-AU', 'en-CA', 'en-IN',  # English variants
    'hi', 'hi-IN',  # Hindi (common for Indian content)
    'es', 'fr', 'de', 'pt', 'it', 'ru', 'ja', 'ko', 'zh-Hans', 'zh-Hant',  # Major languages
]

def normalize_transcript(data):
    """
    Normalizes transcript data from various formats (List[Dict], FetchedTranscript obj)
    into a standard List[Dict] format: [{'text': '...', 'start': 0.0, 'duration': 0.0}]
    """
    snippets = []
    
    # CASE A: It's a FetchedTranscript object (User's unique environment)
    # Check for 'snippets' attribute
    if hasattr(data, 'snippets'):
        data = data.snippets
    
    # Handle if data itself is iterable but not a list
    if not isinstance(data, list):
        try:
            data = list(data)
        except:
            return []

    for item in data:
        try:
            # CASE B: Item is a Dictionary (Standard API)
            if isinstance(item, dict):
                snippets.append({
                    'text': str(item.get('text', '')),
                    'start': float(item.get('start', 0.0)),
                    'duration': float(item.get('duration', 0.0))
                })
            
            # CASE C: Item is an Object with text attribute that's a string
            elif hasattr(item, 'text') and isinstance(getattr(item, 'text', None), str):
                snippets.append({
                    'text': item.text,
                    'start': float(getattr(item, 'start', 0.0)),
                    'duration': float(getattr(item, 'duration', 0.0))
                })
            
            # CASE D: Item is an Object but text might be a dict (edge case)
            elif hasattr(item, 'text'):
                text_val = getattr(item, 'text', '')
                if isinstance(text_val, dict):
                    text_val = text_val.get('text', str(text_val))
                snippets.append({
                    'text': str(text_val),
                    'start': float(getattr(item, 'start', 0.0)),
                    'duration': float(getattr(item, 'duration', 0.0))
                })
            
            # CASE E: Try to convert item to string as last resort
            else:
                snippets.append({
                    'text': str(item),
                    'start': 0.0,
                    'duration': 0.0
                })
        except Exception:
            # Skip problematic items
            continue
            
    return snippets


def _try_static_get_transcript(video_id, languages, errors):
    """Try the static get_transcript method."""
    if not hasattr(YouTubeTranscriptApi, 'get_transcript'):
        return None
    try:
        return YouTubeTranscriptApi.get_transcript(video_id, languages=languages)
    except (TranscriptsDisabled, NoTranscriptFound, NoTranscriptAvailable) as e:
        errors.append(f"Static get_transcript: {type(e).__name__}")
        return None
    except Exception as e:
        error_msg = str(e)
        if "Subtitles are disabled" in error_msg:
            errors.append("Subtitles are disabled for this video")
        elif "No transcript" in error_msg.lower():
            errors.append("No transcript available")
        else:
            errors.append(f"Static get_transcript failed: {error_msg[:100]}")
        return None


def _try_static_list_transcripts(video_id, languages, errors):
    """Try the static list_transcripts method."""
    if not hasattr(YouTubeTranscriptApi, 'list_transcripts'):
        return None
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        # Try manual transcripts first (better quality)
        try:
            transcript = transcript_list.find_manually_created_transcript(languages)
            return transcript.fetch()
        except:
            pass
        
        # Try auto-generated transcripts
        try:
            transcript = transcript_list.find_generated_transcript(languages)
            return transcript.fetch()
        except:
            pass
        
        # Try any available transcript
        try:
            for transcript in transcript_list:
                try:
                    return transcript.fetch()
                except:
                    continue
        except:
            pass
        
        return None
    except (TranscriptsDisabled, NoTranscriptFound, NoTranscriptAvailable) as e:
        errors.append(f"Static list_transcripts: {type(e).__name__}")
        return None
    except Exception as e:
        error_msg = str(e)
        if "Subtitles are disabled" not in error_msg:
            errors.append(f"Static list_transcripts: {error_msg[:80]}")
        return None


def _try_instance_api(video_id, languages, errors):
    """Try the instance-based API (newer versions)."""
    try:
        api = YouTubeTranscriptApi()
    except Exception as e:
        errors.append(f"Cannot instantiate API: {str(e)[:50]}")
        return None
    
    try:
        transcript_list = api.list(video_id)
    except (TranscriptsDisabled, NoTranscriptFound, NoTranscriptAvailable) as e:
        errors.append(f"Instance list: {type(e).__name__}")
        return None
    except Exception as e:
        error_msg = str(e)
        if "Subtitles are disabled" in error_msg:
            errors.append("Subtitles disabled")
        elif "No transcript" in error_msg.lower():
            errors.append("No transcript available")
        else:
            errors.append(f"Instance list failed: {error_msg[:80]}")
        return None
    
    if not transcript_list:
        return None
    
    # Try find_transcript for manual captions
    try:
        if hasattr(transcript_list, 'find_transcript'):
            t = transcript_list.find_transcript(languages)
            return t.fetch()
    except:
        pass
    
    # Try find_generated_transcript for auto-generated
    try:
        if hasattr(transcript_list, 'find_generated_transcript'):
            t = transcript_list.find_generated_transcript(languages)
            return t.fetch()
    except:
        pass
    
    # Fallback: iterate through all available transcripts
    try:
        for t in transcript_list:
            try:
                data = t.fetch()
                if data:
                    return data
            except:
                continue
    except:
        pass
    
    return None


def get_video_transcript(video_id):
    """
    Robust fetcher handling Static vs Instance API and various return types.
    Returns: List[Dict] or String (Error Message)
    
    Attempts multiple strategies:
    1. Static get_transcript with English languages
    2. Static list_transcripts for manual/auto transcripts
    3. Instance-based API (newer versions)
    4. Extended language fallback
    """
    errors = []
    raw_data = None
    
    try:
        # Strategy 1: Static get_transcript (most common, fastest)
        raw_data = _try_static_get_transcript(video_id, ['en', 'en-US', 'en-GB'], errors)
        
        # Strategy 2: Static list_transcripts
        if not raw_data:
            raw_data = _try_static_list_transcripts(video_id, LANGUAGES_TO_TRY[:6], errors)
        
        # Strategy 3: Instance-based API
        if not raw_data:
            raw_data = _try_instance_api(video_id, LANGUAGES_TO_TRY[:6], errors)
        
        # Strategy 4: Try extended languages with static method
        if not raw_data and hasattr(YouTubeTranscriptApi, 'get_transcript'):
            try:
                raw_data = YouTubeTranscriptApi.get_transcript(video_id, languages=LANGUAGES_TO_TRY)
            except:
                pass
        
        # Validate & Normalize
        if raw_data:
            normalized = normalize_transcript(raw_data)
            if normalized:
                return normalized
            else:
                return f"Transcript found but normalization failed. Raw type: {type(raw_data)}"
        
        # Determine the best error message to show
        if any("disabled" in e.lower() for e in errors):
            return "⚠️ Subtitles/Captions are disabled for this video. The video owner has not enabled captions."
        elif any("TranscriptsDisabled" in e for e in errors):
            return "⚠️ Transcripts are disabled for this video by the uploader."
        elif any("NoTranscript" in e for e in errors):
            return "⚠️ No transcript available for this video in any supported language."
        else:
            return f"No transcript found. Debug: {'; '.join(errors) if errors else 'No methods succeeded'}"

    except Exception as e:
        return f"System Error: {str(e)}"
