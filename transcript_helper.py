from youtube_transcript_api import YouTubeTranscriptApi

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

def get_video_transcript(video_id):
    """
    Robust fetcher handling Static vs Instance API and various return types.
    Returns: List[Dict] or String (Error Message)
    """
    errors = []
    try:
        raw_data = None
        
        # 1. ATTEMPT FETCH
        # Try Standard Static Method first
        if hasattr(YouTubeTranscriptApi, 'get_transcript'):
            try:
                raw_data = YouTubeTranscriptApi.get_transcript(video_id, languages=['en', 'en-US', 'en-GB'])
            except Exception as e:
                errors.append(f"Static get_transcript failed: {str(e)}")

        # Try Instance Method (Polyfill) if static failed/missing
        if not raw_data and hasattr(YouTubeTranscriptApi, 'list'):
            try:
                # Try instantiating
                api = YouTubeTranscriptApi()
                try:
                    transcript_list = api.list(video_id)
                    errors.append(f"Instance list() returned type: {type(transcript_list)}")
                except Exception as e:
                    errors.append(f"Instance list() call failed: {str(e)}")
                    transcript_list = None
                
                if transcript_list:
                    # 2a. Try explicit English MANUALLY CREATED
                    try:
                        if hasattr(transcript_list, 'find_transcript'):
                            t = transcript_list.find_transcript(['en', 'en-US', 'en-GB'])
                            raw_data = t.fetch()
                        else:
                            errors.append("transcript_list has no find_transcript")
                    except Exception as e:
                        errors.append(f"find_transcript failed: {str(e)}")

                    # 2b. Try explicit English AUTO-GENERATED (Restored Logic)
                    if not raw_data:
                        try:
                            if hasattr(transcript_list, 'find_generated_transcript'):
                                t = transcript_list.find_generated_transcript(['en', 'en-US'])
                                raw_data = t.fetch()
                        except Exception as e:
                            errors.append(f"find_generated_transcript failed: {str(e)}")

                    # 2c. Fallback: Try EVERYTHING
                    if not raw_data:
                        try:
                            for t in transcript_list:
                                try:
                                    raw_data = t.fetch()
                                    if raw_data: break
                                except Exception as inner_e:
                                    errors.append(f"Failed to fetch {t.language_code}: {str(inner_e)}")
                                    continue
                        except Exception as e2:
                             errors.append(f"Fallback iteration critical fail: {str(e2)}")

            except Exception as e:
                errors.append(f"Instance logic general fail: {str(e)}")
                
        # 2. VALIDATE & NORMALIZE
        if raw_data:
            normalized = normalize_transcript(raw_data)
            if normalized:
                return normalized
            else:
                return f"Transcript found but normalization failed. Raw type: {type(raw_data)}"
        
        return f"No transcript found. Debug: {'; '.join(errors)}"

    except Exception as e:
        return f"System Error: {str(e)} | Log: {'; '.join(errors)}"
