"""
Tests for new modules added in the TubeBuddy/VidIQ enhancement.
"""

import unittest

class TestSEOAnalyzer(unittest.TestCase):
    """Test SEO scoring module."""
    
    def test_analyze_title(self):
        from seo_analyzer import analyze_title
        
        # Good title with keyword
        result = analyze_title("How to Make Money Online in 2025 (Complete Guide)", "money online")
        self.assertGreater(result["score"], 50)
        self.assertIn("breakdown", result)
    
    def test_analyze_title_empty(self):
        from seo_analyzer import analyze_title
        
        result = analyze_title("", "")
        self.assertEqual(result["score"], 0)
    
    def test_calculate_seo_score(self):
        from seo_analyzer import calculate_seo_score
        
        result = calculate_seo_score(
            title="How to Start a YouTube Channel in 2025",
            description="In this video, I'll show you how to start a YouTube channel from scratch. We'll cover everything from equipment to SEO. Subscribe for more tips!",
            tags=["youtube", "youtube channel", "how to start youtube"],
            target_keyword="youtube channel"
        )
        
        self.assertIn("overall_score", result)
        self.assertIn("grade", result)
        self.assertIn("components", result)
        self.assertGreater(result["overall_score"], 0)


class TestKeywordResearch(unittest.TestCase):
    """Test keyword research module."""
    
    def test_generate_related_keywords(self):
        from keyword_research import generate_related_keywords
        
        result = generate_related_keywords("gaming", limit=10)
        
        self.assertIsInstance(result, list)
        self.assertLessEqual(len(result), 10)
        
        if result:
            self.assertIn("keyword", result[0])
            self.assertIn("type", result[0])
    
    def test_extract_keywords_from_text(self):
        from keyword_research import extract_keywords_from_text
        
        text = "This is a gaming video about gaming setup and gaming gear"
        result = extract_keywords_from_text(text, top_n=5)
        
        self.assertIsInstance(result, list)
        # "gaming" should be top keyword
        if result:
            self.assertIn("gaming", result[0]["keyword"])


class TestCompetitorAnalyzer(unittest.TestCase):
    """Test competitor analysis module."""
    
    def test_analyze_title_elements(self):
        from competitor_analyzer import analyze_title_elements
        
        result = analyze_title_elements("10 Best Gaming Tips You NEED to Know!")
        
        self.assertTrue(result["has_number"])
        self.assertGreater(result["hook_score"], 0)
    
    def test_parse_duration(self):
        from competitor_analyzer import parse_duration
        
        self.assertEqual(parse_duration("PT1H30M15S"), 5415)
        self.assertEqual(parse_duration("PT5M30S"), 330)
        self.assertEqual(parse_duration("PT30S"), 30)


class TestAIContentTools(unittest.TestCase):
    """Test AI content generation module."""
    
    def test_generate_titles(self):
        from ai_content_tools import generate_titles
        
        titles = generate_titles("cooking", style="how_to", count=5)
        
        self.assertEqual(len(titles), 5)
        self.assertIn("title", titles[0])
        self.assertIn("ctr_score", titles[0])
    
    def test_generate_description(self):
        from ai_content_tools import generate_description
        
        result = generate_description(
            title="Test Video",
            keywords=["test", "video"],
            video_length_minutes=10,
            niche="tech"
        )
        
        self.assertIn("description", result)
        self.assertGreater(result["word_count"], 100)
    
    def test_generate_tags(self):
        from ai_content_tools import generate_tags
        
        result = generate_tags(
            title="Best Gaming Setup 2025",
            description="My gaming setup tour",
            base_keywords=["gaming", "setup"]
        )
        
        self.assertIn("tags", result)
        self.assertGreater(len(result["tags"]), 0)


if __name__ == '__main__':
    unittest.main()
