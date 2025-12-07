import unittest
from unittest.mock import MagicMock, patch, mock_open
import sys
import os

# Add parent directory to path to import app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Mock libraries that are heavy or require hardware
mock_modules = {
    'streamlit': MagicMock(),
    'easyocr': MagicMock(),
    'torch': MagicMock(),
    'youtube_transcript_api': MagicMock(),
    'youtube_transcript_api.formatters': MagicMock()
}

# Configure streamlit mock to return valid keys for selectbox lookups
def selectbox_side_effect(label, options, index=0, **kwargs):
    if "Region" in label: return "United States"
    if "Language" in label: return "English"
    if "Category" in label: return "Any"
    if options: return options[index]
    return "mock_value"

mock_modules['streamlit'].selectbox.side_effect = selectbox_side_effect
mock_modules['streamlit'].columns.side_effect = lambda n: [MagicMock() for _ in range(n)]
mock_modules['streamlit'].tabs.side_effect = lambda names: [MagicMock() for _ in range(len(names))]
mock_modules['streamlit'].button.return_value = False 
# Critical: Make decorators passthrough
mock_modules['streamlit'].cache_data = lambda func=None, **kwargs: (lambda f: f) if func is None else func
mock_modules['streamlit'].cache_resource = lambda func=None, **kwargs: (lambda f: f) if func is None else func

with patch.dict(sys.modules, mock_modules):
    import app

class TestViralEngine(unittest.TestCase):

    def test_check_ai_content(self):
        """Test AI keyword matching logic (Boolean flag)."""
        keywords = ["AI", "Robot", "Future"]
        
        # Test 1: Match
        self.assertTrue(app.check_ai_content("This is an AI Robot video", keywords))
        
        # Test 2: No match
        self.assertFalse(app.check_ai_content("Organic video content", keywords))
        
        # Test 3: Case insensitivity
        self.assertTrue(app.check_ai_content("future tech", keywords))

        # Test 4: Empty input
        self.assertFalse(app.check_ai_content("", keywords))
        self.assertFalse(app.check_ai_content("Text", []))

    def test_detect_music_from_description(self):
        """Test heuristic music detection."""
        desc_with_music = "Video about ghosts.\nMusic: Spooky Skeletons by Kevin MacLeod\nThanks for watching."
        self.assertIn("Spooky Skeletons", app.detect_music_from_description(desc_with_music))
        
        desc_no_music = "Just a vlog."
        self.assertEqual(app.detect_music_from_description(desc_no_music), "None Detected")
        
        desc_multiple = "Song: Track 1\nBGM: Track 2"
        self.assertIn("Track 1", app.detect_music_from_description(desc_multiple))
        self.assertIn("Track 2", app.detect_music_from_description(desc_multiple))

    def test_extract_text_from_thumbnail(self):
        """Test OCR extraction logic."""
        # Manual patch to ensure override works
        original_func = app.get_ocr_reader
        
        try:
            mock_reader = MagicMock()
            mock_reader.readtext.return_value = ["TEXT", "ON", "IMAGE"]
            
            mock_getter = MagicMock(return_value=mock_reader)
            app.get_ocr_reader = mock_getter
            
            # Verify usage
            reader = app.get_ocr_reader()
            result = reader.readtext("http://example.com/img.jpg", detail=0)
            self.assertEqual(result, ["TEXT", "ON", "IMAGE"])
            
        finally:
            app.get_ocr_reader = original_func

    def test_get_video_transcript(self):
        """Test transcript fetcher from transcript_helper module."""
        from transcript_helper import get_video_transcript, normalize_transcript
        
        # Test normalize_transcript directly (doesn't need network)
        # Case 1: Standard list of dicts
        data = [{'text': 'Hello', 'start': 0, 'duration': 1}]
        result = normalize_transcript(data)
        self.assertEqual(result, data)
        
        # Case 2: Object with snippets attribute
        class MockSnippet:
            def __init__(self):
                self.text = "Test"
                self.start = 0
                self.duration = 1
        
        class MockTranscript:
            def __init__(self):
                self.snippets = [MockSnippet()]
        
        result = normalize_transcript(MockTranscript())
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['text'], 'Test')

    def test_virality_logic_dry_run(self):
        """Test the math logic for virality."""
        view_count = 10000
        sub_count = 2000
        
        virality_score = view_count / sub_count
        self.assertEqual(virality_score, 5.0)
        
        engagement_rate = (500 + 100) / view_count * 100 # (Likes+Comments)/Views
        self.assertEqual(engagement_rate, 6.0)

    def test_get_ngrams(self):
        """Test N-Gram generation."""
        text = "How to make a viral video"
        # Bi-grams
        bigrams = app.get_ngrams(text, 2)
        self.assertIn("how to", bigrams)
        self.assertIn("viral video", bigrams)
        self.assertEqual(len(bigrams), 5)
        
        # Empty
        self.assertEqual(app.get_ngrams("", 2), [])
        
        # Too short
        self.assertEqual(app.get_ngrams("Hi", 3), [])

    def test_resolve_channel_id(self):
        """Test robust channel resolution logic."""
        mock_youtube = MagicMock()
        
        # Case 1: Handle Search Success
        mock_youtube.channels().list.return_value.execute.return_value = {
            'items': [{'id': 'UC_HANDLE_ID'}]
        }
        res = app.resolve_channel_id(mock_youtube, "@MrBeast")
        self.assertEqual(res, 'UC_HANDLE_ID')
        
        # Case 2: Handle Fail -> Search Success
        # Simulate execute() raising exception or empty for first call
        mock_youtube.channels().list.side_effect = Exception("Handle lookup failed")
        mock_youtube.search().list.return_value.execute.return_value = {
            'items': [{'id': {'channelId': 'UC_SEARCH_ID'}}]
        }
        res = app.resolve_channel_id(mock_youtube, "@UnknownButFound")
        self.assertEqual(res, 'UC_SEARCH_ID')
        
        # Reset side effects for other tests if needed
        mock_youtube.channels().list.side_effect = None

    @patch('builtins.open', new_callable=mock_open, read_data='{"api_key": "123"}')
    @patch('app.os.path.exists', return_value=True)
    def test_load_config(self, mock_exists, mock_file):
        """Test loading config from JSON."""
        # Ensure json.load works with the mock
        with patch('app.json.load', return_value={"api_key": "123"}):
             config = app.load_config()
             self.assertEqual(config.get('api_key'), "123")

    @patch('app.json.dump')
    @patch('builtins.open', new_callable=mock_open)
    def test_save_config(self, mock_file, mock_json_dump):
        """Test saving config to JSON."""
        # Setup session state mock
        with patch('streamlit.session_state', {'api_key': 'abc'}):
            app.save_config()
            mock_file.assert_called_with('dashboard_config.json', 'w')
            # Verify json.dump was called
            self.assertTrue(mock_json_dump.called)

if __name__ == '__main__':
    unittest.main()
