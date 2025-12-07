"""
SEO Analyzer Module for YouTube Intelligence Engine
Uses REAL YouTube API data to compare your video against actual ranking videos.
"""

import re
from typing import List, Dict, Tuple
from collections import Counter

# ===================== CONSTANTS =====================
POWER_WORDS = [
    "ultimate", "complete", "definitive", "essential", "proven", "secret",
    "amazing", "incredible", "unbelievable", "shocking", "insane", "crazy",
    "best", "worst", "top", "how to", "why", "what", "tutorial", "guide",
    "review", "vs", "versus", "explained", "revealed", "truth", "hack",
    "free", "fast", "easy", "simple", "quick", "new", "2024", "2025"
]


def analyze_seo_vs_competitors(
    youtube,
    your_title: str,
    your_description: str,
    your_tags: List[str],
    target_keyword: str
) -> Dict:
    """
    Compare your video's SEO against REAL ranking videos for the same keyword.
    
    Args:
        youtube: Authenticated YouTube API client
        your_title: Your video title
        your_description: Your video description
        your_tags: Your video tags
        target_keyword: The keyword you want to rank for
    
    Returns:
        Dict with comparison analysis and recommendations
    """
    if not youtube or not target_keyword:
        return {"error": "YouTube API client and target keyword required"}
    
    try:
        # 1. Search for top ranking videos for this keyword
        search_response = youtube.search().list(
            q=target_keyword,
            part='id,snippet',
            type='video',
            maxResults=10,
            order='relevance'  # What's actually ranking
        ).execute()
        
        video_items = search_response.get('items', [])
        
        if not video_items:
            return {"error": "No ranking videos found for this keyword"}
        
        video_ids = [item['id']['videoId'] for item in video_items]
        
        # 2. Get detailed data on these videos
        videos_response = youtube.videos().list(
            part='snippet,statistics',
            id=','.join(video_ids)
        ).execute()
        
        ranking_videos = videos_response.get('items', [])
        
        # 3. Analyze ranking videos' patterns
        competitor_analysis = analyze_competitor_seo(ranking_videos, target_keyword)
        
        # 4. Score YOUR video against these patterns
        your_score = score_against_competitors(
            your_title=your_title,
            your_description=your_description,
            your_tags=your_tags,
            target_keyword=target_keyword,
            competitor_data=competitor_analysis
        )
        
        # 5. Generate specific recommendations
        recommendations = generate_seo_recommendations(
            your_title=your_title,
            your_description=your_description,
            your_tags=your_tags,
            competitor_data=competitor_analysis
        )
        
        return {
            "target_keyword": target_keyword,
            "your_score": your_score,
            "competitor_insights": competitor_analysis,
            "ranking_videos": [
                {
                    "title": v['snippet']['title'],
                    "channel": v['snippet']['channelTitle'],
                    "views": int(v.get('statistics', {}).get('viewCount', 0))
                }
                for v in ranking_videos[:5]
            ],
            "recommendations": recommendations,
            "comparison": {
                "your_title_length": len(your_title),
                "avg_ranking_title_length": competitor_analysis.get("avg_title_length", 0),
                "your_tag_count": len(your_tags),
                "avg_ranking_tag_count": competitor_analysis.get("avg_tag_count", 0),
                "your_desc_length": len(your_description.split()),
                "avg_ranking_desc_length": competitor_analysis.get("avg_desc_words", 0)
            }
        }
        
    except Exception as e:
        return {"error": str(e)}


def analyze_competitor_seo(ranking_videos: List[Dict], keyword: str) -> Dict:
    """Analyze SEO patterns from ranking videos."""
    
    if not ranking_videos:
        return {}
    
    titles = []
    descriptions = []
    all_tags = []
    
    keyword_in_title = 0
    keyword_in_first_words = 0
    has_numbers = 0
    has_brackets = 0
    has_power_words = 0
    
    for video in ranking_videos:
        snippet = video.get('snippet', {})
        title = snippet.get('title', '')
        desc = snippet.get('description', '')
        tags = snippet.get('tags', [])
        
        titles.append(title)
        descriptions.append(desc)
        all_tags.extend([t.lower() for t in tags])
        
        title_lower = title.lower()
        keyword_lower = keyword.lower()
        
        # Check keyword placement
        if keyword_lower in title_lower:
            keyword_in_title += 1
            # Check if in first 5 words
            first_words = ' '.join(title_lower.split()[:5])
            if keyword_lower in first_words:
                keyword_in_first_words += 1
        
        # Check patterns
        if re.search(r'\d+', title):
            has_numbers += 1
        if re.search(r'[\[\]\(\)]', title):
            has_brackets += 1
        if any(pw in title_lower for pw in POWER_WORDS):
            has_power_words += 1
    
    total = len(ranking_videos)
    
    # Count tag frequencies
    tag_freq = Counter(all_tags)
    
    return {
        "videos_analyzed": total,
        "keyword_in_title_rate": f"{round(keyword_in_title / total * 100)}%",
        "keyword_in_first_5_words_rate": f"{round(keyword_in_first_words / total * 100)}%",
        "number_usage_rate": f"{round(has_numbers / total * 100)}%",
        "bracket_usage_rate": f"{round(has_brackets / total * 100)}%",
        "power_word_rate": f"{round(has_power_words / total * 100)}%",
        "avg_title_length": round(sum(len(t) for t in titles) / total),
        "avg_desc_words": round(sum(len(d.split()) for d in descriptions) / total),
        "avg_tag_count": round(sum(1 for v in ranking_videos for _ in v.get('snippet', {}).get('tags', [])) / total),
        "common_tags": [tag for tag, _ in tag_freq.most_common(20)],
        "must_use_numbers": has_numbers / total > 0.5,
        "must_use_brackets": has_brackets / total > 0.3
    }


def score_against_competitors(
    your_title: str,
    your_description: str,
    your_tags: List[str],
    target_keyword: str,
    competitor_data: Dict
) -> Dict:
    """Score your video's SEO against competitor patterns."""
    
    score = 0
    breakdown = {}
    keyword_lower = target_keyword.lower()
    title_lower = your_title.lower()
    
    # 1. Keyword in title (25 points)
    if keyword_lower in title_lower:
        first_words = ' '.join(title_lower.split()[:5])
        if keyword_lower in first_words:
            score += 25
            breakdown['keyword_placement'] = {"score": 25, "status": "✅ Keyword in first 5 words"}
        else:
            score += 15
            breakdown['keyword_placement'] = {"score": 15, "status": "⚠️ Keyword present but not in first 5 words"}
    else:
        breakdown['keyword_placement'] = {"score": 0, "status": "❌ Keyword missing from title"}
    
    # 2. Title length compared to competitors (15 points)
    avg_len = competitor_data.get('avg_title_length', 50)
    your_len = len(your_title)
    if abs(your_len - avg_len) <= 10:
        score += 15
        breakdown['title_length'] = {"score": 15, "status": f"✅ Good length ({your_len} chars, avg is {avg_len})"}
    elif abs(your_len - avg_len) <= 20:
        score += 10
        breakdown['title_length'] = {"score": 10, "status": f"⚠️ Slightly off ({your_len} chars, avg is {avg_len})"}
    else:
        score += 5
        breakdown['title_length'] = {"score": 5, "status": f"❌ Far from avg ({your_len} chars, avg is {avg_len})"}
    
    # 3. Number usage if competitors use it (10 points)
    has_number = bool(re.search(r'\d+', your_title))
    if competitor_data.get('must_use_numbers', False):
        if has_number:
            score += 10
            breakdown['numbers'] = {"score": 10, "status": "✅ Using numbers (like competitors)"}
        else:
            breakdown['numbers'] = {"score": 0, "status": "❌ Missing numbers (competitors use them!)"}
    else:
        if has_number:
            score += 8
            breakdown['numbers'] = {"score": 8, "status": "✅ Has numbers"}
        else:
            score += 5
            breakdown['numbers'] = {"score": 5, "status": "ℹ️ No numbers (optional in this niche)"}
    
    # 4. Bracket usage if competitors use it (10 points)
    has_brackets = bool(re.search(r'[\[\]\(\)]', your_title))
    if competitor_data.get('must_use_brackets', False):
        if has_brackets:
            score += 10
            breakdown['brackets'] = {"score": 10, "status": "✅ Using brackets (like competitors)"}
        else:
            breakdown['brackets'] = {"score": 0, "status": "❌ Missing brackets (competitors use them!)"}
    else:
        if has_brackets:
            score += 8
            breakdown['brackets'] = {"score": 8, "status": "✅ Has brackets"}
        else:
            score += 5
            breakdown['brackets'] = {"score": 5, "status": "ℹ️ No brackets (optional)"}
    
    # 5. Description length (15 points)
    your_desc_words = len(your_description.split())
    avg_desc = competitor_data.get('avg_desc_words', 100)
    if your_desc_words >= avg_desc:
        score += 15
        breakdown['description'] = {"score": 15, "status": f"✅ Description longer than avg ({your_desc_words} vs {avg_desc} words)"}
    elif your_desc_words >= avg_desc * 0.7:
        score += 10
        breakdown['description'] = {"score": 10, "status": f"⚠️ Description slightly short ({your_desc_words} vs {avg_desc} words)"}
    else:
        score += 5
        breakdown['description'] = {"score": 5, "status": f"❌ Description too short ({your_desc_words} vs {avg_desc} words)"}
    
    # 6. Tag overlap with competitors (15 points)
    common_tags = competitor_data.get('common_tags', [])
    your_tags_lower = [t.lower() for t in your_tags]
    overlap = len(set(your_tags_lower) & set(common_tags))
    
    if overlap >= 5:
        score += 15
        breakdown['tags'] = {"score": 15, "status": f"✅ Excellent tag overlap ({overlap} matching tags)"}
    elif overlap >= 3:
        score += 10
        breakdown['tags'] = {"score": 10, "status": f"⚠️ Some tag overlap ({overlap} matching tags)"}
    elif overlap >= 1:
        score += 5
        breakdown['tags'] = {"score": 5, "status": f"❌ Low tag overlap ({overlap} matching tags)"}
    else:
        breakdown['tags'] = {"score": 0, "status": "❌ No matching tags with competitors!"}
    
    # 7. Keyword in description (10 points)
    if keyword_lower in your_description.lower():
        if keyword_lower in your_description[:200].lower():
            score += 10
            breakdown['desc_keyword'] = {"score": 10, "status": "✅ Keyword in first 200 chars of description"}
        else:
            score += 7
            breakdown['desc_keyword'] = {"score": 7, "status": "⚠️ Keyword in description but not near start"}
    else:
        breakdown['desc_keyword'] = {"score": 0, "status": "❌ Keyword missing from description"}
    
    # Determine grade
    if score >= 85:
        grade = "A"
    elif score >= 70:
        grade = "B"
    elif score >= 55:
        grade = "C"
    elif score >= 40:
        grade = "D"
    else:
        grade = "F"
    
    return {
        "score": score,
        "grade": grade,
        "breakdown": breakdown,
        "vs_competitor_avg": f"Based on {competitor_data.get('videos_analyzed', 0)} ranking videos"
    }


def generate_seo_recommendations(
    your_title: str,
    your_description: str,
    your_tags: List[str],
    competitor_data: Dict
) -> List[Dict]:
    """Generate specific, actionable recommendations."""
    
    recommendations = []
    priority = 1
    
    common_tags = competitor_data.get('common_tags', [])
    your_tags_lower = [t.lower() for t in your_tags]
    
    # Tag recommendations
    missing_important_tags = [t for t in common_tags[:10] if t not in your_tags_lower]
    if missing_important_tags:
        recommendations.append({
            "priority": priority,
            "category": "Tags",
            "action": f"Add these tags used by ranking videos: {', '.join(missing_important_tags[:5])}",
            "impact": "High"
        })
        priority += 1
    
    # Title recommendations
    if competitor_data.get('must_use_numbers') and not re.search(r'\d+', your_title):
        recommendations.append({
            "priority": priority,
            "category": "Title",
            "action": "Add a number to your title (e.g., '5 Tips', 'Top 10')",
            "impact": "High"
        })
        priority += 1
    
    if competitor_data.get('must_use_brackets') and not re.search(r'[\[\]\(\)]', your_title):
        recommendations.append({
            "priority": priority,
            "category": "Title",
            "action": "Add brackets/parentheses (e.g., '[Full Guide]' or '(2025)')",
            "impact": "Medium"
        })
        priority += 1
    
    # Description recommendations
    avg_desc = competitor_data.get('avg_desc_words', 100)
    your_desc_words = len(your_description.split())
    if your_desc_words < avg_desc * 0.7:
        recommendations.append({
            "priority": priority,
            "category": "Description",
            "action": f"Increase description length to at least {int(avg_desc * 0.8)} words (you have {your_desc_words})",
            "impact": "Medium"
        })
        priority += 1
    
    if not recommendations:
        recommendations.append({
            "priority": 1,
            "category": "Overall",
            "action": "Great job! Your SEO is well-optimized for this keyword.",
            "impact": "N/A"
        })
    
    return recommendations


def get_competitor_tags(youtube, keyword: str) -> List[str]:
    """Quick function to get tags from top ranking videos."""
    
    if not youtube or not keyword:
        return []
    
    try:
        search_response = youtube.search().list(
            q=keyword,
            part='id',
            type='video',
            maxResults=10,
            order='relevance'
        ).execute()
        
        video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]
        
        if not video_ids:
            return []
        
        videos_response = youtube.videos().list(
            part='snippet',
            id=','.join(video_ids)
        ).execute()
        
        all_tags = []
        for video in videos_response.get('items', []):
            tags = video.get('snippet', {}).get('tags', [])
            all_tags.extend([t.lower() for t in tags])
        
        tag_freq = Counter(all_tags)
        return [tag for tag, _ in tag_freq.most_common(20)]
        
    except:
        return []


# Legacy functions for backwards compatibility
def calculate_seo_score(title, description, tags, target_keyword="", additional_keywords=None):
    """Legacy function - returns basic score without API comparison."""
    from seo_analyzer_legacy import calculate_seo_score as legacy_score
    return legacy_score(title, description, tags, target_keyword, additional_keywords)


def analyze_title(title, target_keyword=""):
    """Legacy function for basic title analysis."""
    score = 50
    suggestions = []
    
    if target_keyword and target_keyword.lower() in title.lower():
        score += 20
    
    if re.search(r'\d+', title):
        score += 10
    
    if 40 <= len(title) <= 60:
        score += 10
    else:
        suggestions.append(f"Adjust title length (currently {len(title)} chars, ideal is 40-60)")
    
    return {"score": min(score, 100), "suggestions": suggestions}


def generate_tag_suggestions(title, description, existing_tags=None):
    """Legacy function for basic tag suggestions."""
    suggestions = []
    text = f"{title} {description}".lower()
    
    words = re.findall(r'\b[a-z]{4,}\b', text)
    stop_words = {"this", "that", "with", "from", "have", "been"}
    words = [w for w in words if w not in stop_words]
    
    word_freq = Counter(words)
    return [w for w, _ in word_freq.most_common(10)]
