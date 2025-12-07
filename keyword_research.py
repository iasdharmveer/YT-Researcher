"""
Keyword Research Module for YouTube Intelligence Engine
Uses REAL YouTube API data for keyword analysis, competition scoring, and suggestions.
"""

from typing import List, Dict, Optional
from collections import Counter
import re


def research_keyword_live(youtube, keyword: str, max_results: int = 20) -> Dict:
    """
    Research a keyword using LIVE YouTube API data.
    
    Args:
        youtube: Authenticated YouTube API client
        keyword: The keyword to research
        max_results: Number of search results to analyze
    
    Returns:
        Dict with real competition data, video analysis, and insights
    """
    if not youtube or not keyword:
        return {"error": "YouTube API client and keyword required"}
    
    try:
        # 1. Search YouTube for this keyword
        search_response = youtube.search().list(
            q=keyword,
            part='id,snippet',
            type='video',
            maxResults=max_results,
            order='relevance'
        ).execute()
        
        video_items = search_response.get('items', [])
        
        if not video_items:
            return {
                "keyword": keyword,
                "total_results": 0,
                "error": "No results found for this keyword"
            }
        
        # 2. Get video IDs for detailed stats
        video_ids = [item['id']['videoId'] for item in video_items]
        
        # 3. Fetch detailed video statistics
        videos_response = youtube.videos().list(
            part='statistics,snippet,contentDetails',
            id=','.join(video_ids)
        ).execute()
        
        videos = videos_response.get('items', [])
        
        # 4. Get channel statistics for competition analysis
        channel_ids = list(set([v['snippet']['channelId'] for v in videos]))
        
        channels_response = youtube.channels().list(
            part='statistics',
            id=','.join(channel_ids)
        ).execute()
        
        channel_map = {c['id']: c for c in channels_response.get('items', [])}
        
        # 5. Analyze the data
        total_views = 0
        total_subs = 0
        total_likes = 0
        total_comments = 0
        view_counts = []
        sub_counts = []
        
        video_analysis = []
        
        for video in videos:
            stats = video.get('statistics', {})
            views = int(stats.get('viewCount', 0))
            likes = int(stats.get('likeCount', 0))
            comments = int(stats.get('commentCount', 0))
            
            channel_id = video['snippet']['channelId']
            channel_stats = channel_map.get(channel_id, {}).get('statistics', {})
            subs = int(channel_stats.get('subscriberCount', 0))
            
            total_views += views
            total_subs += subs
            total_likes += likes
            total_comments += comments
            view_counts.append(views)
            sub_counts.append(subs)
            
            video_analysis.append({
                'title': video['snippet']['title'],
                'channel': video['snippet']['channelTitle'],
                'views': views,
                'likes': likes,
                'subscribers': subs,
                'video_id': video['id']
            })
        
        video_count = len(videos)
        avg_views = total_views // video_count if video_count > 0 else 0
        avg_subs = total_subs // video_count if video_count > 0 else 0
        
        # 6. Calculate REAL competition score
        competition_score = calculate_real_competition_score(
            avg_views=avg_views,
            avg_subs=avg_subs,
            video_count=video_count,
            view_counts=view_counts,
            sub_counts=sub_counts
        )
        
        # 7. Calculate opportunity score
        opportunity_score = calculate_opportunity_score(
            competition_score=competition_score['score'],
            avg_views=avg_views,
            avg_subs=avg_subs
        )
        
        # 8. Extract real keywords from top videos
        extracted_keywords = extract_keywords_from_results(videos)
        
        return {
            "keyword": keyword,
            "total_results": len(videos),
            "competition": competition_score,
            "opportunity": opportunity_score,
            "stats": {
                "avg_views": avg_views,
                "avg_subscribers": avg_subs,
                "total_views_analyzed": total_views,
                "avg_engagement": round((total_likes + total_comments) / total_views * 100, 2) if total_views > 0 else 0
            },
            "top_videos": video_analysis[:10],
            "related_keywords": extracted_keywords,
            "recommendation": get_keyword_recommendation(competition_score['score'], opportunity_score['score'])
        }
        
    except Exception as e:
        return {"keyword": keyword, "error": str(e)}


def calculate_real_competition_score(
    avg_views: int,
    avg_subs: int,
    video_count: int,
    view_counts: List[int],
    sub_counts: List[int]
) -> Dict:
    """
    Calculate competition score based on REAL data from search results.
    
    Score 0-100 where:
    - 0-30: Low competition (easy to rank)
    - 31-60: Medium competition
    - 61-100: High competition (hard to rank)
    """
    score = 0
    factors = {}
    
    # Factor 1: Average subscriber count of ranking channels (40% weight)
    if avg_subs < 10000:
        sub_score = 10
        factors['channel_size'] = "Small channels dominate (Easy)"
    elif avg_subs < 100000:
        sub_score = 30
        factors['channel_size'] = "Medium channels dominate"
    elif avg_subs < 500000:
        sub_score = 50
        factors['channel_size'] = "Large channels present"
    elif avg_subs < 1000000:
        sub_score = 70
        factors['channel_size'] = "Big channels dominate (Hard)"
    else:
        sub_score = 90
        factors['channel_size'] = "Mega channels only (Very Hard)"
    
    score += sub_score * 0.4
    
    # Factor 2: Average views of top results (30% weight)
    if avg_views < 10000:
        view_score = 15
        factors['view_potential'] = "Low views (Niche topic)"
    elif avg_views < 100000:
        view_score = 35
        factors['view_potential'] = "Moderate views"
    elif avg_views < 500000:
        view_score = 55
        factors['view_potential'] = "Good views (Competitive)"
    else:
        view_score = 80
        factors['view_potential'] = "Viral potential (Very Competitive)"
    
    score += view_score * 0.3
    
    # Factor 3: Variation in subscriber counts (30% weight)
    # If there's high variation, smaller channels can break through
    if sub_counts:
        min_subs = min(sub_counts) if sub_counts else 0
        max_subs = max(sub_counts) if sub_counts else 0
        
        if min_subs > 0 and max_subs > 0:
            ratio = min_subs / max_subs
            if ratio < 0.01:  # High variation - small channels ranking
                var_score = 20
                factors['variation'] = "Mixed channel sizes (Opportunity!)"
            elif ratio < 0.1:
                var_score = 40
                factors['variation'] = "Some variation"
            else:
                var_score = 70
                factors['variation'] = "Similar-sized channels only"
        else:
            var_score = 50
            factors['variation'] = "Unknown"
    else:
        var_score = 50
        factors['variation'] = "Insufficient data"
    
    score += var_score * 0.3
    
    # Determine difficulty level
    if score <= 30:
        level = "Low"
        color = "🟢"
    elif score <= 60:
        level = "Medium"
        color = "🟡"
    else:
        level = "High"
        color = "🔴"
    
    return {
        "score": round(score),
        "level": level,
        "color": color,
        "factors": factors
    }


def calculate_opportunity_score(
    competition_score: int,
    avg_views: int,
    avg_subs: int
) -> Dict:
    """
    Calculate opportunity score - how good is this keyword for a small channel?
    
    High opportunity = Low competition + High view potential
    """
    # Invert competition (lower competition = higher opportunity base)
    base_opportunity = 100 - competition_score
    
    # Boost for high views relative to subscriber count (viral potential)
    if avg_subs > 0:
        virality_ratio = avg_views / avg_subs
        if virality_ratio > 5:
            boost = 20
            insight = "Videos going viral relative to channel size!"
        elif virality_ratio > 2:
            boost = 10
            insight = "Good view-to-subscriber ratio"
        elif virality_ratio > 1:
            boost = 5
            insight = "Normal performance"
        else:
            boost = 0
            insight = "Below average performance"
    else:
        boost = 0
        insight = "No subscriber data"
    
    final_score = min(100, base_opportunity + boost)
    
    if final_score >= 70:
        verdict = "Excellent Opportunity 🚀"
    elif final_score >= 50:
        verdict = "Good Opportunity ✅"
    elif final_score >= 30:
        verdict = "Fair Opportunity ⚠️"
    else:
        verdict = "Difficult Opportunity ❌"
    
    return {
        "score": round(final_score),
        "verdict": verdict,
        "insight": insight
    }


def extract_keywords_from_results(videos: List[Dict]) -> List[Dict]:
    """
    Extract real keywords from actual video titles and tags.
    """
    all_words = []
    all_tags = []
    
    stop_words = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "must", "i", "you", "he", "she", "it", "we",
        "they", "my", "your", "his", "her", "its", "our", "their", "this",
        "that", "these", "how", "what", "why", "when", "where", "who"
    }
    
    for video in videos:
        title = video.get('snippet', {}).get('title', '')
        tags = video.get('snippet', {}).get('tags', [])
        
        # Extract words from title
        words = re.findall(r'\b[a-zA-Z]{3,}\b', title.lower())
        filtered_words = [w for w in words if w not in stop_words]
        all_words.extend(filtered_words)
        
        # Collect tags
        all_tags.extend([t.lower() for t in tags])
    
    # Count frequencies
    word_freq = Counter(all_words)
    tag_freq = Counter(all_tags)
    
    # Combine and deduplicate
    keywords = []
    seen = set()
    
    # Top tags first (more reliable)
    for tag, count in tag_freq.most_common(15):
        if tag not in seen and len(tag) > 2:
            keywords.append({
                "keyword": tag,
                "frequency": count,
                "source": "competitor_tags"
            })
            seen.add(tag)
    
    # Then title words
    for word, count in word_freq.most_common(10):
        if word not in seen:
            keywords.append({
                "keyword": word,
                "frequency": count,
                "source": "titles"
            })
            seen.add(word)
    
    return keywords[:20]


def get_keyword_recommendation(competition: int, opportunity: int) -> str:
    """Generate actionable recommendation based on scores."""
    
    if opportunity >= 70 and competition <= 40:
        return "🎯 HIGHLY RECOMMENDED: Low competition with high opportunity. Create content on this topic ASAP!"
    elif opportunity >= 50 and competition <= 60:
        return "✅ GOOD CHOICE: Reasonable competition with decent opportunity. Worth pursuing with strong content."
    elif opportunity >= 50 and competition > 60:
        return "⚠️ CHALLENGING: High competition but opportunity exists. Need exceptional content to rank."
    elif opportunity < 50 and competition <= 40:
        return "🤔 LOW POTENTIAL: Easy to rank but limited views. Consider for niche audience only."
    else:
        return "❌ NOT RECOMMENDED: High competition with low opportunity. Find alternative keywords."


def get_youtube_suggestions(youtube, keyword: str) -> List[str]:
    """
    Get YouTube's autocomplete suggestions for a keyword.
    This shows what people are actually searching for.
    """
    try:
        # Use search to find related queries
        search_response = youtube.search().list(
            q=keyword,
            part='snippet',
            type='video',
            maxResults=10,
            order='relevance'
        ).execute()
        
        # Extract unique title patterns
        suggestions = set()
        for item in search_response.get('items', []):
            title = item['snippet']['title'].lower()
            # Extract phrases containing the keyword
            if keyword.lower() in title:
                suggestions.add(item['snippet']['title'])
        
        return list(suggestions)[:10]
    except:
        return []


def analyze_keyword_trend(youtube, keyword: str) -> Dict:
    """
    Analyze if a keyword is trending by comparing recent vs older videos.
    """
    try:
        from datetime import datetime, timedelta
        
        # Search for recent videos (last 7 days)
        recent_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%SZ')
        
        recent_response = youtube.search().list(
            q=keyword,
            part='id',
            type='video',
            maxResults=50,
            order='date',
            publishedAfter=recent_date
        ).execute()
        
        recent_count = len(recent_response.get('items', []))
        
        # Search for older videos (7-30 days ago)
        older_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')
        
        older_response = youtube.search().list(
            q=keyword,
            part='id',
            type='video',
            maxResults=50,
            order='date',
            publishedAfter=older_date,
            publishedBefore=recent_date
        ).execute()
        
        older_count = len(older_response.get('items', []))
        
        # Calculate trend
        if older_count > 0:
            growth_rate = ((recent_count - older_count) / older_count) * 100
        else:
            growth_rate = 100 if recent_count > 0 else 0
        
        if growth_rate > 50:
            trend = "🔥 RISING FAST"
            status = "hot"
        elif growth_rate > 10:
            trend = "📈 Trending Up"
            status = "rising"
        elif growth_rate > -10:
            trend = "➡️ Stable"
            status = "stable"
        else:
            trend = "📉 Declining"
            status = "declining"
        
        return {
            "recent_uploads": recent_count,
            "older_uploads": older_count,
            "growth_rate": round(growth_rate, 1),
            "trend": trend,
            "status": status
        }
        
    except Exception as e:
        return {"error": str(e), "trend": "Unknown", "status": "unknown"}
