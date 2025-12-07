import unittest
from unittest.mock import MagicMock
from transcript_helper import normalize_transcript, get_video_transcript

class TestTranscriptHelper(unittest.TestCase):
    
    def test_normalize_standard_list_of_dicts(self):
        data = [{'text': 'Hello', 'start': 0, 'duration': 1}]
        self.assertEqual(normalize_transcript(data), data)

    def test_normalize_fetched_transcript_object(self):
        # Simulate the User's "FetchedTranscript" object
        class Snippet:
            def __init__(self, text):
                self.text = text
                self.start = 0
                self.duration = 1
        
        class TranscriptObj:
            def __init__(self):
                self.snippets = [Snippet("Hello"), Snippet("World")]
                
        obj = TranscriptObj()
        normalized = normalize_transcript(obj)
        
        self.assertEqual(len(normalized), 2)
        self.assertEqual(normalized[0]['text'], 'Hello')
        self.assertEqual(normalized[1]['text'], 'World')

if __name__ == '__main__':
    unittest.main()
