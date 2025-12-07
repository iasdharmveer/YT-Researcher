"""
AI Content Tools Module for YouTube Intelligence Engine
Uses REAL YouTube API data to analyze viral patterns and generate optimized content.
"""

import re
import random
from typing import List, Dict, Optional
from collections import Counter


def analyze_viral_titles(youtube, niche_keyword: str, max_results: int = 50) -> Dict:
    """
    Analyze REAL viral titles in a niche to find patterns.
    
    Args:
        youtube: Authenticated YouTube API client
        niche_keyword: The niche/topic to analyze
        max_results: Number of videos to analyze
    
    Returns:
        Dict with title patterns, hooks, and insights
    """
    if not youtube or not niche_keyword:
        return {"error": "YouTube API client and keyword required"}
    
    try:
        # Search for top-performing videos in this niche
        search_response = youtube.search().list(
            q=niche_keyword,
            part='id,snippet',
            type='video',
            maxResults=max_results,
            order='viewCount'  # Get videos with most views
        ).execute()
        
        video_items = search_response.get('items', [])
        
        if not video_items:
            return {"error": "No videos found for this niche"}
        
        # Get video IDs for stats
        video_ids = [item['id']['videoId'] for item in video_items]
        
        # Fetch detailed stats
        videos_response = youtube.videos().list(
            part='statistics,snippet',
            id=','.join(video_ids)
        ).execute()
        
        videos = videos_response.get('items', [])
        
        # Analyze title patterns
        titles = []
        title_lengths = []
        words_per_title = []
        hooks_found = Counter()
        number_usage = 0
        bracket_usage = 0
        question_usage = 0
        emoji_usage = 0
        
        for video in videos:
            title = video['snippet']['title']
            views = int(video.get('statistics', {}).get('viewCount', 0))
            
            titles.append({
                'title': title,
                'views': views,
                'channel': video['snippet']['channelTitle']
            })
            
            title_lengths.append(len(title))
            words_per_title.append(len(title.split()))
            
            # Detect patterns
            if re.search(r'\d+', title):
                number_usage += 1
            if re.search(r'[\[\]\(\)]', title):
                bracket_usage += 1
            if title.endswith('?'):
                question_usage += 1
            if re.search(r'[^\x00-\x7F]', title):
                emoji_usage += 1
            
            # Extract opening hooks (first 2-3 words)
            words = title.split()
            if len(words) >= 2:
                hook = ' '.join(words[:2]).lower()
                hooks_found[hook] += 1
            if len(words) >= 3:
                hook3 = ' '.join(words[:3]).lower()
                hooks_found[hook3] += 1
        
        total = len(videos)
        
        # Sort titles by views
        titles.sort(key=lambda x: x['views'], reverse=True)
        
        return {
            "niche": niche_keyword,
            "total_analyzed": total,
            "top_titles": titles[:20],
            "patterns": {
                "avg_length": round(sum(title_lengths) / total, 1) if total > 0 else 0,
                "avg_words": round(sum(words_per_title) / total, 1) if total > 0 else 0,
                "use_numbers": f"{round(number_usage / total * 100)}%",
                "use_brackets": f"{round(bracket_usage / total * 100)}%",
                "use_questions": f"{round(question_usage / total * 100)}%",
                "use_emoji": f"{round(emoji_usage / total * 100)}%"
            },
            "top_hooks": [{"hook": h, "count": c} for h, c in hooks_found.most_common(15)],
            "best_practices": generate_best_practices(
                number_usage / total if total > 0 else 0,
                bracket_usage / total if total > 0 else 0,
                sum(title_lengths) / total if total > 0 else 0
            )
        }
        
    except Exception as e:
        return {"error": str(e)}


def generate_best_practices(number_rate: float, bracket_rate: float, avg_length: float) -> List[str]:
    """Generate actionable best practices from analysis."""
    practices = []
    
    if number_rate > 0.3:
        practices.append("✅ Use numbers in titles - {:.0%} of viral videos do this".format(number_rate))
    else:
        practices.append("📊 Numbers are optional in this niche - only {:.0%} use them".format(number_rate))
    
    if bracket_rate > 0.2:
        practices.append("✅ Use brackets/parentheses - {:.0%} of top videos use them".format(bracket_rate))
    
    if avg_length < 50:
        practices.append(f"✅ Keep titles short - avg is {avg_length:.0f} characters")
    elif avg_length < 70:
        practices.append(f"📏 Medium-length titles work - avg is {avg_length:.0f} characters")
    else:
        practices.append(f"📏 Longer titles are OK here - avg is {avg_length:.0f} characters")
    
    return practices


def generate_titles_from_viral(youtube, topic: str, count: int = 10) -> Dict:
    """
    Generate title suggestions based on REAL viral video patterns.
    
    Args:
        youtube: Authenticated YouTube API client
        topic: Topic to generate titles for
        count: Number of titles to generate
    
    Returns:
        Dict with generated titles and source patterns
    """
    if not youtube or not topic:
        return {"error": "YouTube API client and topic required", "titles": []}
    
    try:
        # First, analyze viral videos in this niche
        analysis = analyze_viral_titles(youtube, topic, max_results=30)
        
        if "error" in analysis:
            return {"error": analysis["error"], "titles": []}
        
        top_titles = analysis.get("top_titles", [])
        top_hooks = analysis.get("top_hooks", [])
        patterns = analysis.get("patterns", {})
        
        # Extract successful patterns
        hooks = [h["hook"] for h in top_hooks[:10]]
        
        # Generate new titles based on patterns
        generated = []
        
        # Strategy 1: Use top hooks with topic
        for hook in hooks[:5]:
            new_title = f"{hook.title()} {topic.title()}"
            if len(new_title) < 50:
                new_title += " (Complete Guide)"
            generated.append({
                "title": new_title,
                "strategy": "Based on viral hook",
                "source_hook": hook
            })
        
        # Strategy 2: Remix top-performing titles
        for viral in top_titles[:5]:
            original = viral['title']
            # Replace core topic words
            words = original.split()
            if len(words) >= 3:
                # Try to adapt the structure
                remixed = adapt_title_structure(original, topic)
                if remixed:
                    generated.append({
                        "title": remixed,
                        "strategy": "Remixed from viral",
                        "original_views": viral['views']
                    })
        
        # Strategy 3: Number-based if patterns show it works
        if "%" in patterns.get("use_numbers", "") and int(patterns["use_numbers"].replace("%", "")) > 30:
            number_titles = [
                f"10 {topic.title()} Tips That Actually Work",
                f"5 {topic.title()} Mistakes You're Making",
                f"7 {topic.title()} Secrets Nobody Tells You",
                f"Top 3 {topic.title()} for Beginners in 2025"
            ]
            for t in number_titles:
                generated.append({
                    "title": t,
                    "strategy": "Number format (works in this niche)"
                })
        
        return {
            "topic": topic,
            "titles": generated[:count],
            "analysis_summary": {
                "videos_analyzed": analysis.get("total_analyzed", 0),
                "patterns_found": patterns,
                "top_hooks_used": hooks[:5]
            }
        }
        
    except Exception as e:
        return {"error": str(e), "titles": []}


def adapt_title_structure(original_title: str, new_topic: str) -> Optional[str]:
    """Adapt a viral title structure to a new topic."""
    # Common patterns to detect and adapt
    patterns = [
        (r'^(How to .+?) -', f'How to {new_topic.title()} -'),
        (r'^(Why .+?) (is|are)', f'Why {new_topic.title()} is'),
        (r'^(\d+) (.+?) (Tips|Tricks|Secrets|Hacks)', f'\\1 {new_topic.title()} \\3'),
        (r'^(The Ultimate .+?) Guide', f'The Ultimate {new_topic.title()} Guide'),
        (r'^(I Tried .+?) for', f'I Tried {new_topic.title()} for'),
    ]
    
    for pattern, replacement in patterns:
        if re.search(pattern, original_title, re.IGNORECASE):
            try:
                return re.sub(pattern, replacement, original_title, flags=re.IGNORECASE)[:70]
            except:
                continue
    
    return None


def generate_description_from_competitors(youtube, keyword: str, video_length: int = 10) -> Dict:
    """
    Generate description based on analyzing real competitor descriptions.
    
    Args:
        youtube: Authenticated YouTube API client
        keyword: Topic/keyword for the video
        video_length: Approximate video length in minutes
    
    Returns:
        Dict with generated description and insights
    """
    if not youtube or not keyword:
        return {"error": "YouTube API client and keyword required"}
    
    try:
        # Search for top videos
        search_response = youtube.search().list(
            q=keyword,
            part='id',
            type='video',
            maxResults=10,
            order='viewCount'
        ).execute()
        
        video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]
        
        if not video_ids:
            return {"error": "No videos found"}
        
        # Get full descriptions
        videos_response = youtube.videos().list(
            part='snippet',
            id=','.join(video_ids)
        ).execute()
        
        videos = videos_response.get('items', [])
        
        # Analyze patterns
        has_timestamps = 0
        has_links = 0
        has_hashtags = 0
        has_cta = 0
        avg_length = 0
        common_hashtags = Counter()
        
        for video in videos:
            desc = video['snippet'].get('description', '')
            avg_length += len(desc.split())
            
            if re.search(r'\d{1,2}:\d{2}', desc):
                has_timestamps += 1
            if re.search(r'https?://', desc):
                has_links += 1
            if '#' in desc:
                has_hashtags += 1
                tags = re.findall(r'#(\w+)', desc)
                common_hashtags.update(tags)
            if any(cta in desc.lower() for cta in ['subscribe', 'like', 'comment', 'share']):
                has_cta += 1
        
        total = len(videos)
        avg_length = avg_length // total if total > 0 else 0
        
        # Generate optimized description
        description = generate_optimized_description(
            keyword=keyword,
            video_length=video_length,
            use_timestamps=has_timestamps / total > 0.5 if total > 0 else True,
            use_hashtags=has_hashtags / total > 0.3 if total > 0 else True,
            common_hashtags=[h for h, _ in common_hashtags.most_common(5)]
        )
        
        return {
            "description": description,
            "insights": {
                "competitors_analyzed": total,
                "avg_description_length": avg_length,
                "timestamps_usage": f"{has_timestamps}/{total} use timestamps",
                "links_usage": f"{has_links}/{total} include links",
                "cta_usage": f"{has_cta}/{total} have call-to-action",
                "top_hashtags": [h for h, _ in common_hashtags.most_common(10)]
            }
        }
        
    except Exception as e:
        return {"error": str(e)}


def generate_optimized_description(
    keyword: str,
    video_length: int,
    use_timestamps: bool,
    use_hashtags: bool,
    common_hashtags: List[str]
) -> str:
    """Generate an optimized description based on analysis."""
    
    parts = []
    
    # Hook (first 150 chars are most important for SEO)
    parts.append(f"🎯 In this video, you'll learn everything about {keyword}. This is the complete guide you've been looking for!\n")
    
    # Body
    parts.append(f"Whether you're a complete beginner or already have experience, this {video_length}-minute guide covers everything you need to know about {keyword}.\n")
    
    # Timestamps (if competitors use them)
    if use_timestamps:
        parts.append("\n⏰ TIMESTAMPS:")
        if video_length <= 5:
            parts.append("0:00 - Introduction")
            parts.append("0:30 - Main Content")
            parts.append(f"{video_length-1}:00 - Conclusion\n")
        elif video_length <= 15:
            parts.append("0:00 - Introduction")
            parts.append("1:00 - Part 1")
            parts.append("5:00 - Part 2")
            parts.append("10:00 - Part 3")
            parts.append(f"{video_length-1}:00 - Conclusion\n")
        else:
            parts.append("0:00 - Introduction")
            parts.append("2:00 - Background")
            parts.append("7:00 - Main Topic")
            parts.append("15:00 - Advanced Tips")
            parts.append("25:00 - Q&A")
            parts.append(f"{video_length-2}:00 - Conclusion\n")
    
    # CTA
    parts.append("\n📌 If you found this helpful:")
    parts.append("👍 LIKE this video")
    parts.append("💬 COMMENT your thoughts")
    parts.append("🔔 SUBSCRIBE for more content\n")
    
    # Links placeholder
    parts.append("\n🔗 RESOURCES:")
    parts.append("• Link 1: [Add your link]")
    parts.append("• Link 2: [Add your link]\n")
    
    # Hashtags (if competitors use them)
    if use_hashtags and common_hashtags:
        keyword_tag = keyword.replace(' ', '')
        tags = [f"#{keyword_tag}"] + [f"#{h}" for h in common_hashtags[:4]]
        parts.append("\n" + " ".join(tags))
    
    return "\n".join(parts)


def generate_tags_from_competitors(youtube, keyword: str, max_tags: int = 15) -> Dict:
    """
    Generate tags based on REAL competitor video tags.
    
    Args:
        youtube: Authenticated YouTube API client
        keyword: Topic/keyword
        max_tags: Maximum number of tags to return
    
    Returns:
        Dict with extracted tags and analysis
    """
    if not youtube or not keyword:
        return {"error": "YouTube API client and keyword required", "tags": []}
    
    try:
        # Search for top videos
        search_response = youtube.search().list(
            q=keyword,
            part='id',
            type='video',
            maxResults=20,
            order='viewCount'
        ).execute()
        
        video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]
        
        if not video_ids:
            return {"error": "No videos found", "tags": []}
        
        # Get tags from videos
        videos_response = youtube.videos().list(
            part='snippet',
            id=','.join(video_ids)
        ).execute()
        
        videos = videos_response.get('items', [])
        
        # Collect and count tags
        all_tags = Counter()
        tag_video_performance = {}  # Track which tags come from high-view videos
        
        for video in videos:
            tags = video['snippet'].get('tags', [])
            views = int(video.get('statistics', {}).get('viewCount', 0)) if 'statistics' in video else 0
            
            for tag in tags:
                tag_lower = tag.lower()
                all_tags[tag_lower] += 1
                
                if tag_lower not in tag_video_performance:
                    tag_video_performance[tag_lower] = []
                tag_video_performance[tag_lower].append(views)
        
        # Score tags by frequency and performance
        scored_tags = []
        for tag, count in all_tags.most_common(50):
            avg_views = sum(tag_video_performance.get(tag, [0])) / max(len(tag_video_performance.get(tag, [1])), 1)
            score = count * 10 + (avg_views / 10000)
            
            scored_tags.append({
                "tag": tag,
                "frequency": count,
                "avg_views": int(avg_views),
                "score": round(score, 1)
            })
        
        # Sort by score
        scored_tags.sort(key=lambda x: x['score'], reverse=True)
        
        # Get top tags
        top_tags = scored_tags[:max_tags]
        
        return {
            "keyword": keyword,
            "tags": [t['tag'] for t in top_tags],
            "tag_details": top_tags,
            "copy_ready": ", ".join([t['tag'] for t in top_tags]),
            "videos_analyzed": len(videos),
            "unique_tags_found": len(all_tags)
        }
        
    except Exception as e:
        return {"error": str(e), "tags": []}


def get_video_ideas_from_trends(youtube, niche: str, days_back: int = 30) -> Dict:
    """
    Get video ideas based on REAL trending content in a niche.
    
    Args:
        youtube: Authenticated YouTube API client
        niche: The niche/topic to analyze
        days_back: How many days back to analyze
    
    Returns:
        Dict with trending topics and video ideas
    """
    if not youtube or not niche:
        return {"error": "YouTube API client and niche required"}
    
    try:
        from datetime import datetime, timedelta
        
        # Get recent viral videos
        published_after = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%dT%H:%M:%SZ')
        
        search_response = youtube.search().list(
            q=niche,
            part='id,snippet',
            type='video',
            maxResults=50,
            order='viewCount',
            publishedAfter=published_after
        ).execute()
        
        video_items = search_response.get('items', [])
        
        if not video_items:
            return {"error": "No recent videos found"}
        
        # Get stats
        video_ids = [item['id']['videoId'] for item in video_items]
        
        videos_response = youtube.videos().list(
            part='statistics,snippet,contentDetails',
            id=','.join(video_ids)
        ).execute()
        
        videos = videos_response.get('items', [])
        
        # Analyze what's working
        topic_patterns = Counter()
        format_patterns = Counter()
        duration_buckets = {"short": 0, "medium": 0, "long": 0}
        
        top_performers = []
        
        for video in videos:
            title = video['snippet']['title']
            views = int(video.get('statistics', {}).get('viewCount', 0))
            
            # Extract topics from title
            words = re.findall(r'\b[a-zA-Z]{4,}\b', title.lower())
            topic_patterns.update(words)
            
            # Detect format
            if re.search(r'^(how|tutorial|guide)', title.lower()):
                format_patterns['tutorial'] += 1
            elif re.search(r'^\d+', title):
                format_patterns['listicle'] += 1
            elif re.search(r'vs\.?|versus', title.lower()):
                format_patterns['comparison'] += 1
            elif re.search(r'review', title.lower()):
                format_patterns['review'] += 1
            else:
                format_patterns['other'] += 1
            
            top_performers.append({
                'title': title,
                'views': views,
                'channel': video['snippet']['channelTitle']
            })
        
        # Sort by views
        top_performers.sort(key=lambda x: x['views'], reverse=True)
        
        # Generate ideas based on gaps
        ideas = []
        
        # Find popular topics
        hot_topics = [t for t, _ in topic_patterns.most_common(10)]
        
        # Best format
        best_format = format_patterns.most_common(1)[0][0] if format_patterns else 'tutorial'
        
        # Generate ideas combining hot topics with best format
        for topic in hot_topics[:5]:
            if best_format == 'tutorial':
                ideas.append(f"How to {topic.title()} - Complete {niche} Guide")
            elif best_format == 'listicle':
                ideas.append(f"10 Best {topic.title()} Tips for {niche}")
            elif best_format == 'comparison':
                ideas.append(f"{topic.title()} vs Alternatives - {niche} Showdown")
            else:
                ideas.append(f"The Truth About {topic.title()} in {niche}")
        
        return {
            "niche": niche,
            "period": f"Last {days_back} days",
            "trending_topics": hot_topics,
            "best_format": best_format,
            "format_distribution": dict(format_patterns),
            "top_performers": top_performers[:10],
            "video_ideas": ideas,
            "videos_analyzed": len(videos)
        }
        
    except Exception as e:
        return {"error": str(e)}


# ===================== LEGACY FUNCTIONS FOR BACKWARDS COMPATIBILITY =====================

def generate_titles(topic: str, style: str = "how_to", count: int = 5) -> List[Dict]:
    """
    Legacy function - Generate title suggestions without API.
    
    Args:
        topic: Topic to generate titles for
        style: Title style (how_to, listicle, review, etc.)
        count: Number of titles to generate
    
    Returns:
        List of dicts with title and ctr_score
    """
    templates = {
        "how_to": [
            f"How to {topic.title()} - Complete Beginner Guide",
            f"How to {topic.title()} Like a Pro in 2025",
            f"How to {topic.title()} (Step-by-Step Tutorial)",
            f"How to {topic.title()} - Everything You Need to Know",
            f"How to {topic.title()} the RIGHT Way",
            f"How to {topic.title()} Fast and Easy",
            f"How to {topic.title()} Without Experience"
        ],
        "listicle": [
            f"10 Best {topic.title()} Tips You Need to Know",
            f"5 {topic.title()} Mistakes Everyone Makes",
            f"7 {topic.title()} Secrets Nobody Tells You",
            f"Top 10 {topic.title()} for Beginners",
            f"15 {topic.title()} Hacks That Actually Work",
            f"3 {topic.title()} Tricks That Changed My Life",
            f"20 {topic.title()} Ideas for 2025"
        ],
        "review": [
            f"{topic.title()} Review - Is It Worth It?",
            f"Honest {topic.title()} Review (No BS)",
            f"I Tried {topic.title()} for 30 Days - Here's What Happened",
            f"{topic.title()} Review - Before You Buy",
            f"The Truth About {topic.title()} (Full Review)",
            f"{topic.title()} - Best or Worst? Honest Review",
            f"My {topic.title()} Experience - Complete Review"
        ],
        "comparison": [
            f"{topic.title()} vs The Competition - Which Is Best?",
            f"Best {topic.title()} Compared (2025)",
            f"{topic.title()} Showdown - Ultimate Comparison",
            f"Which {topic.title()} Should You Choose?",
            f"{topic.title()} Comparison You Need to See",
            f"Top 5 {topic.title()} Compared Side by Side",
            f"{topic.title()} Battle - Who Wins?"
        ]
    }
    
    # Get templates for the style, default to how_to
    style_templates = templates.get(style, templates["how_to"])
    
    results = []
    import random
    
    # Calculate pseudo CTR scores based on patterns
    for template in style_templates[:count]:
        ctr_score = 50  # Base score
        
        # Boost for numbers
        if any(char.isdigit() for char in template):
            ctr_score += 15
        
        # Boost for brackets
        if '(' in template or '[' in template:
            ctr_score += 10
        
        # Boost for power words
        power_words = ['best', 'ultimate', 'secret', 'truth', 'honest', 'complete', 'pro']
        if any(pw in template.lower() for pw in power_words):
            ctr_score += 10
        
        # Boost for year
        if '2025' in template:
            ctr_score += 5
        
        # Boost for questions
        if '?' in template:
            ctr_score += 5
        
        # Add some randomness
        ctr_score += random.randint(-5, 10)
        
        results.append({
            "title": template,
            "ctr_score": min(ctr_score, 100)
        })
    
    return results


def generate_description(
    title: str,
    keywords: List[str],
    video_length_minutes: int = 10,
    niche: str = ""
) -> Dict:
    """
    Legacy function - Generate video description without API.
    
    Args:
        title: Video title
        keywords: List of keywords to include
        video_length_minutes: Video length in minutes
        niche: Video niche/category
    
    Returns:
        Dict with description and word_count
    """
    # Build description parts
    parts = []
    
    # Hook (SEO-optimized first line)
    keyword_str = keywords[0] if keywords else title
    parts.append(f"🎯 Learn everything about {keyword_str} in this comprehensive guide!")
    parts.append(f"This is the most complete {keyword_str} tutorial you'll find on YouTube in 2025.")
    parts.append("")
    
    # Body
    parts.append(f"In this {video_length_minutes}-minute video, we dive deep into {title.lower()}.")
    if niche:
        parts.append(f"Whether you're new to {niche} or looking to level up, this video is for you.")
    parts.append(f"By the end of this video, you'll have a complete understanding of {keyword_str}.")
    parts.append("")
    
    # What You'll Learn
    parts.append("📚 WHAT YOU'LL LEARN:")
    parts.append(f"• Complete beginner-friendly introduction to {keyword_str}")
    parts.append("• Step-by-step walkthrough of all key concepts")
    parts.append("• Pro tips and best practices from experts")
    parts.append("• Common mistakes to avoid")
    parts.append("")
    
    # Timestamps
    parts.append("⏰ TIMESTAMPS:")
    parts.append("0:00 - Introduction")
    if video_length_minutes > 5:
        parts.append("1:00 - Getting Started")
        parts.append(f"{video_length_minutes // 3}:00 - Main Content")
        parts.append(f"{video_length_minutes * 2 // 3}:00 - Advanced Tips")
    parts.append(f"{video_length_minutes - 1}:00 - Conclusion")
    parts.append("")
    
    # Keywords naturally embedded
    if keywords:
        parts.append("📝 Topics Covered:")
        for kw in keywords[:5]:
            parts.append(f"• {kw.title()}")
    parts.append("")
    
    # CTA
    parts.append("📌 Don't forget to:")
    parts.append("👍 LIKE this video if you found it helpful")
    parts.append("💬 COMMENT any questions below")
    parts.append("🔔 SUBSCRIBE for more content")
    parts.append("🔔 Hit the notification bell to never miss an upload")
    parts.append("")
    
    # Links placeholder
    parts.append("🔗 RESOURCES:")
    parts.append("• [Link 1]")
    parts.append("• [Link 2]")
    parts.append("• [Link 3]")
    parts.append("")
    
    # Hashtags
    if keywords:
        hashtags = [f"#{kw.replace(' ', '')}" for kw in keywords[:3]]
        parts.append(" ".join(hashtags))
    
    description = "\n".join(parts)
    
    return {
        "description": description,
        "word_count": len(description.split())
    }


def generate_tags(
    title: str,
    description: str = "",
    base_keywords: List[str] = None
) -> Dict:
    """
    Legacy function - Generate video tags without API.
    
    Args:
        title: Video title
        description: Video description
        base_keywords: Base keywords to include
    
    Returns:
        Dict with tags list
    """
    import re
    
    tags = set()
    
    # Add base keywords first
    if base_keywords:
        for kw in base_keywords:
            tags.add(kw.lower())
            # Add variations
            tags.add(kw.lower().replace(" ", ""))
            words = kw.split()
            if len(words) > 1:
                tags.add(words[0].lower())
    
    # Extract from title
    title_words = re.findall(r'\b[a-zA-Z]{4,}\b', title.lower())
    stop_words = {"this", "that", "with", "from", "have", "been", "will", "your", "what", "when", "where", "which", "there", "their", "about"}
    
    for word in title_words:
        if word not in stop_words:
            tags.add(word)
    
    # Extract from description
    if description:
        desc_words = re.findall(r'\b[a-zA-Z]{4,}\b', description.lower())
        word_freq = {}
        for word in desc_words:
            if word not in stop_words:
                word_freq[word] = word_freq.get(word, 0) + 1
        
        # Add most frequent words
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        for word, _ in sorted_words[:10]:
            tags.add(word)
    
    # Add common YouTube tags
    common_tags = ["tutorial", "guide", "howto", "tips", "2025", "best"]
    for tag in common_tags:
        if tag in title.lower() or (description and tag in description.lower()):
            tags.add(tag)
    
    # Convert to sorted list
    tag_list = sorted(list(tags))[:30]  # YouTube allows max 500 chars, ~30 tags is safe
    
    return {
        "tags": tag_list,
        "count": len(tag_list)
    }

