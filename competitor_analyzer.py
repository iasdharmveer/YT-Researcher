"""
Competitor Analyzer Module for YouTube Intelligence Engine
Uses REAL YouTube API data for deep competitor analysis.
"""

import re
from typing import List, Dict, Optional
from collections import Counter
from datetime import datetime, timedelta


def get_channel_popular_videos(
    youtube,
    channel_id: str,
    start_date: Optional[str] = None,
    max_results: int = 50,
    order_by: str = "views"
) -> Dict:
    """
    Get all popular videos from a channel with date filtering.
    
    Args:
        youtube: Authenticated YouTube API client
        channel_id: YouTube channel ID
        start_date: Only include videos published after this date (YYYY-MM-DD format)
        max_results: Maximum videos to return (up to 50)
        order_by: Sort order - "views", "date", or "engagement"
    
    Returns:
        Dict with channel info and sorted list of videos
    """
    if not youtube or not channel_id:
        return {"error": "YouTube API client and channel ID required"}
    
    try:
        # 1. Get channel info
        channel_response = youtube.channels().list(
            part='snippet,statistics,contentDetails',
            id=channel_id
        ).execute()
        
        if not channel_response.get('items'):
            return {"error": "Channel not found"}
        
        channel = channel_response['items'][0]
        channel_stats = channel.get('statistics', {})
        channel_snippet = channel.get('snippet', {})
        
        # 2. Get uploads playlist
        uploads_playlist = channel.get('contentDetails', {}).get('relatedPlaylists', {}).get('uploads')
        
        if not uploads_playlist:
            return {"error": "Could not find uploads playlist"}
        
        # 3. Get videos from playlist (YouTube API returns in reverse chronological order)
        all_videos = []
        next_page_token = None
        
        # Parse start_date if provided
        filter_date = None
        if start_date:
            try:
                filter_date = datetime.strptime(start_date, "%Y-%m-%d")
            except:
                pass
        
        # Fetch playlist items (up to 200 to ensure we get enough after filtering)
        items_to_fetch = min(max_results * 4, 200)  # Fetch extra to account for date filtering
        fetched = 0
        
        while fetched < items_to_fetch:
            request_size = min(50, items_to_fetch - fetched)
            
            playlist_response = youtube.playlistItems().list(
                part='snippet,contentDetails',
                playlistId=uploads_playlist,
                maxResults=request_size,
                pageToken=next_page_token
            ).execute()
            
            items = playlist_response.get('items', [])
            if not items:
                break
            
            # Get video IDs
            video_ids = [item['contentDetails']['videoId'] for item in items]
            
            # Get video statistics
            videos_response = youtube.videos().list(
                part='statistics,snippet,contentDetails',
                id=','.join(video_ids)
            ).execute()
            
            for video in videos_response.get('items', []):
                v_stats = video.get('statistics', {})
                v_snippet = video['snippet']
                published_str = v_snippet['publishedAt']
                
                # Parse published date
                try:
                    published_date = datetime.fromisoformat(published_str.replace('Z', '+00:00'))
                except:
                    published_date = None
                
                # Apply date filter
                if filter_date and published_date:
                    if published_date.replace(tzinfo=None) < filter_date:
                        continue  # Skip videos before start_date
                
                views = int(v_stats.get('viewCount', 0))
                likes = int(v_stats.get('likeCount', 0))
                comments = int(v_stats.get('commentCount', 0))
                
                engagement_rate = ((likes + comments) / views * 100) if views > 0 else 0
                
                all_videos.append({
                    'title': v_snippet['title'],
                    'video_id': video['id'],
                    'url': f"https://youtube.com/watch?v={video['id']}",
                    'views': views,
                    'likes': likes,
                    'comments': comments,
                    'engagement_rate': round(engagement_rate, 2),
                    'published': published_str[:10],
                    'thumbnail': v_snippet.get('thumbnails', {}).get('medium', {}).get('url', ''),
                    'tags': v_snippet.get('tags', [])[:10]  # First 10 tags
                })
            
            fetched += len(items)
            next_page_token = playlist_response.get('nextPageToken')
            
            if not next_page_token:
                break
        
        # 4. Sort videos
        if order_by == "views":
            all_videos.sort(key=lambda x: x['views'], reverse=True)
        elif order_by == "date":
            all_videos.sort(key=lambda x: x['published'], reverse=True)
        elif order_by == "engagement":
            all_videos.sort(key=lambda x: x['engagement_rate'], reverse=True)
        
        # 5. Limit results
        result_videos = all_videos[:max_results]
        
        # 6. Calculate summary stats
        total_views = sum(v['views'] for v in result_videos)
        total_likes = sum(v['likes'] for v in result_videos)
        avg_views = total_views // len(result_videos) if result_videos else 0
        avg_engagement = sum(v['engagement_rate'] for v in result_videos) / len(result_videos) if result_videos else 0
        
        return {
            "channel": {
                "name": channel_snippet.get('title'),
                "id": channel_id,
                "handle": channel_snippet.get('customUrl', ''),
                "subscribers": int(channel_stats.get('subscriberCount', 0)),
                "total_videos": int(channel_stats.get('videoCount', 0)),
                "thumbnail": channel_snippet.get('thumbnails', {}).get('medium', {}).get('url', '')
            },
            "filter": {
                "start_date": start_date or "All time",
                "order_by": order_by,
                "videos_found": len(result_videos),
                "total_scanned": fetched
            },
            "summary": {
                "total_views": total_views,
                "total_likes": total_likes,
                "avg_views": avg_views,
                "avg_engagement": round(avg_engagement, 2),
                "top_video": result_videos[0] if result_videos else None
            },
            "videos": result_videos
        }
        
    except Exception as e:
        return {"error": str(e)}


def get_channel_from_video(youtube, video_id: str) -> Optional[str]:
    """
    Get channel ID from a video ID.
    
    Args:
        youtube: Authenticated YouTube API client
        video_id: YouTube video ID
    
    Returns:
        Channel ID or None
    """
    if not youtube or not video_id:
        return None
    
    try:
        video_response = youtube.videos().list(
            part='snippet',
            id=video_id
        ).execute()
        
        if video_response.get('items'):
            return video_response['items'][0]['snippet']['channelId']
        
        return None
    except:
        return None


def extract_video_id_from_url(url: str) -> Optional[str]:
    """Extract video ID from YouTube URL."""
    if not url:
        return None
    
    patterns = [
        r'(?:v=|/)([a-zA-Z0-9_-]{11})',
        r'youtu\.be/([a-zA-Z0-9_-]{11})',
        r'embed/([a-zA-Z0-9_-]{11})'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None


def analyze_channel_deeply(youtube, channel_id: str) -> Dict:
    """
    Deep analysis of a competitor channel with REAL data.
    
    Args:
        youtube: Authenticated YouTube API client
        channel_id: YouTube channel ID
    
    Returns:
        Dict with comprehensive channel analysis
    """
    if not youtube or not channel_id:
        return {"error": "YouTube API client and channel ID required"}
    
    try:
        # 1. Get channel details
        channel_response = youtube.channels().list(
            part='snippet,statistics,contentDetails,brandingSettings',
            id=channel_id
        ).execute()
        
        if not channel_response.get('items'):
            return {"error": "Channel not found"}
        
        channel = channel_response['items'][0]
        stats = channel.get('statistics', {})
        snippet = channel.get('snippet', {})
        
        # 2. Get recent videos
        uploads_playlist = channel.get('contentDetails', {}).get('relatedPlaylists', {}).get('uploads')
        
        recent_videos = []
        if uploads_playlist:
            playlist_response = youtube.playlistItems().list(
                part='snippet,contentDetails',
                playlistId=uploads_playlist,
                maxResults=50
            ).execute()
            
            video_ids = [item['contentDetails']['videoId'] for item in playlist_response.get('items', [])]
            
            if video_ids:
                videos_response = youtube.videos().list(
                    part='statistics,snippet,contentDetails',
                    id=','.join(video_ids)
                ).execute()
                
                for video in videos_response.get('items', []):
                    v_stats = video.get('statistics', {})
                    recent_videos.append({
                        'title': video['snippet']['title'],
                        'video_id': video['id'],
                        'views': int(v_stats.get('viewCount', 0)),
                        'likes': int(v_stats.get('likeCount', 0)),
                        'comments': int(v_stats.get('commentCount', 0)),
                        'published': video['snippet']['publishedAt'],
                        'tags': video['snippet'].get('tags', [])
                    })
        
        # 3. Calculate performance metrics
        total_subs = int(stats.get('subscriberCount', 0))
        total_views = int(stats.get('viewCount', 0))
        video_count = int(stats.get('videoCount', 0))
        
        # Engagement analysis
        recent_views = sum(v['views'] for v in recent_videos)
        recent_likes = sum(v['likes'] for v in recent_videos)
        avg_views = recent_views // len(recent_videos) if recent_videos else 0
        avg_engagement = (recent_likes / recent_views * 100) if recent_views > 0 else 0
        
        # Upload frequency
        upload_analysis = analyze_upload_frequency(recent_videos)
        
        # Content analysis
        content_analysis = analyze_content_patterns(recent_videos)
        
        return {
            "channel": {
                "name": snippet.get('title'),
                "id": channel_id,
                "subscribers": total_subs,
                "total_views": total_views,
                "video_count": video_count,
                "created": snippet.get('publishedAt', '')[:10]
            },
            "performance": {
                "views_per_video": total_views // video_count if video_count > 0 else 0,
                "avg_recent_views": avg_views,
                "avg_engagement_rate": round(avg_engagement, 2),
                "virality_ratio": round(avg_views / total_subs, 2) if total_subs > 0 else 0
            },
            "upload_pattern": upload_analysis,
            "content_patterns": content_analysis,
            "top_videos": sorted(recent_videos, key=lambda x: x['views'], reverse=True)[:10],
            "recent_videos": recent_videos[:10]
        }
        
    except Exception as e:
        return {"error": str(e)}


def analyze_upload_frequency(videos: List[Dict]) -> Dict:
    """Analyze upload frequency from video data."""
    
    if not videos:
        return {"frequency": "Unknown", "schedule": {}}
    
    dates = []
    for video in videos:
        try:
            pub_date = datetime.fromisoformat(video['published'].replace('Z', '+00:00'))
            dates.append(pub_date)
        except:
            continue
    
    if len(dates) < 2:
        return {"frequency": "Insufficient data", "schedule": {}}
    
    dates.sort(reverse=True)
    
    # Calculate gaps between uploads
    gaps = []
    for i in range(len(dates) - 1):
        gap = (dates[i] - dates[i+1]).days
        gaps.append(gap)
    
    avg_gap = sum(gaps) / len(gaps) if gaps else 0
    
    # Determine frequency
    if avg_gap <= 1:
        frequency = "Daily"
    elif avg_gap <= 3:
        frequency = "2-3 times per week"
    elif avg_gap <= 7:
        frequency = "Weekly"
    elif avg_gap <= 14:
        frequency = "Bi-weekly"
    elif avg_gap <= 30:
        frequency = "Monthly"
    else:
        frequency = "Irregular"
    
    # Analyze posting days
    day_counts = Counter()
    hour_counts = Counter()
    
    for d in dates:
        day_counts[d.strftime('%A')] += 1
        hour_counts[d.hour] += 1
    
    best_days = [d for d, _ in day_counts.most_common(3)]
    best_hours = [h for h, _ in hour_counts.most_common(3)]
    
    return {
        "frequency": frequency,
        "avg_days_between_uploads": round(avg_gap, 1),
        "best_days": best_days,
        "best_hours": best_hours,
        "total_in_period": len(dates)
    }


def analyze_content_patterns(videos: List[Dict]) -> Dict:
    """Analyze content patterns from videos."""
    
    if not videos:
        return {}
    
    # Analyze titles
    title_lengths = []
    has_numbers = 0
    has_brackets = 0
    
    # Topic extraction
    all_words = Counter()
    all_tags = Counter()
    
    stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
                  "of", "with", "is", "are", "how", "what", "why", "this", "that", "i", "my"}
    
    for video in videos:
        title = video['title']
        title_lengths.append(len(title))
        
        if re.search(r'\d+', title):
            has_numbers += 1
        if re.search(r'[\[\]\(\)]', title):
            has_brackets += 1
        
        # Extract words
        words = re.findall(r'\b[a-zA-Z]{4,}\b', title.lower())
        words = [w for w in words if w not in stop_words]
        all_words.update(words)
        
        # Collect tags
        tags = video.get('tags', [])
        all_tags.update([t.lower() for t in tags])
    
    total = len(videos)
    
    return {
        "avg_title_length": round(sum(title_lengths) / total),
        "number_usage": f"{round(has_numbers / total * 100)}%",
        "bracket_usage": f"{round(has_brackets / total * 100)}%",
        "common_topics": [w for w, _ in all_words.most_common(10)],
        "common_tags": [t for t, _ in all_tags.most_common(15)],
        "total_unique_tags": len(all_tags)
    }


def compare_channels_live(youtube, channel_ids: List[str]) -> Dict:
    """
    Compare multiple channels side by side with REAL data.
    
    Args:
        youtube: Authenticated YouTube API client
        channel_ids: List of channel IDs to compare
    
    Returns:
        Dict with comparison data
    """
    if not youtube or not channel_ids:
        return {"error": "YouTube API client and channel IDs required"}
    
    try:
        # Get all channels
        channels_response = youtube.channels().list(
            part='snippet,statistics',
            id=','.join(channel_ids)
        ).execute()
        
        channels = channels_response.get('items', [])
        
        if not channels:
            return {"error": "No channels found"}
        
        comparison = []
        
        for channel in channels:
            stats = channel.get('statistics', {})
            comparison.append({
                'name': channel['snippet']['title'],
                'id': channel['id'],
                'subscribers': int(stats.get('subscriberCount', 0)),
                'total_views': int(stats.get('viewCount', 0)),
                'videos': int(stats.get('videoCount', 0)),
                'views_per_video': int(stats.get('viewCount', 0)) // max(int(stats.get('videoCount', 1)), 1)
            })
        
        # Sort by subscribers
        comparison.sort(key=lambda x: x['subscribers'], reverse=True)
        
        # Add rankings
        for i, ch in enumerate(comparison):
            ch['rank'] = i + 1
        
        return {
            "channels_compared": len(comparison),
            "comparison": comparison,
            "leader": comparison[0]['name'] if comparison else None,
            "total_combined_subs": sum(c['subscribers'] for c in comparison),
            "avg_subs": sum(c['subscribers'] for c in comparison) // len(comparison) if comparison else 0
        }
        
    except Exception as e:
        return {"error": str(e)}


def find_content_gaps_live(youtube, your_channel_id: str, competitor_channel_ids: List[str]) -> Dict:
    """
    Find content gaps - topics competitors cover that you don't.
    
    Args:
        youtube: Authenticated YouTube API client
        your_channel_id: Your channel ID
        competitor_channel_ids: List of competitor channel IDs
    
    Returns:
        Dict with content gap analysis
    """
    if not youtube or not your_channel_id or not competitor_channel_ids:
        return {"error": "All parameters required"}
    
    try:
        # Get your topics
        your_analysis = analyze_channel_deeply(youtube, your_channel_id)
        your_topics = set(your_analysis.get('content_patterns', {}).get('common_topics', []))
        your_tags = set(your_analysis.get('content_patterns', {}).get('common_tags', []))
        
        # Get competitor topics
        competitor_topics = Counter()
        competitor_tags = Counter()
        
        for comp_id in competitor_channel_ids[:3]:  # Limit to 3 to save API quota
            comp_analysis = analyze_channel_deeply(youtube, comp_id)
            comp_topics = comp_analysis.get('content_patterns', {}).get('common_topics', [])
            comp_tags = comp_analysis.get('content_patterns', {}).get('common_tags', [])
            
            competitor_topics.update(comp_topics)
            competitor_tags.update(comp_tags)
        
        # Find gaps
        topic_gaps = [t for t, count in competitor_topics.most_common(20) 
                      if t not in your_topics and count >= 2]
        
        tag_gaps = [t for t, count in competitor_tags.most_common(30) 
                    if t not in your_tags and count >= 2]
        
        return {
            "your_channel": your_channel_id,
            "competitors_analyzed": len(competitor_channel_ids),
            "topic_gaps": topic_gaps[:10],
            "tag_gaps": tag_gaps[:15],
            "your_unique_topics": list(your_topics - set(competitor_topics.keys())),
            "recommendation": f"Consider creating content about: {', '.join(topic_gaps[:3])}" if topic_gaps else "No significant gaps found"
        }
        
    except Exception as e:
        return {"error": str(e)}


def analyze_video_performance(youtube, video_id: str) -> Dict:
    """
    Deep analysis of a single video's performance.
    
    Args:
        youtube: Authenticated YouTube API client
        video_id: YouTube video ID
    
    Returns:
        Dict with video performance analysis
    """
    if not youtube or not video_id:
        return {"error": "YouTube API client and video ID required"}
    
    try:
        # Get video details
        video_response = youtube.videos().list(
            part='snippet,statistics,contentDetails',
            id=video_id
        ).execute()
        
        if not video_response.get('items'):
            return {"error": "Video not found"}
        
        video = video_response['items'][0]
        snippet = video['snippet']
        stats = video.get('statistics', {})
        
        views = int(stats.get('viewCount', 0))
        likes = int(stats.get('likeCount', 0))
        comments = int(stats.get('commentCount', 0))
        
        # Get channel stats for comparison
        channel_id = snippet['channelId']
        channel_response = youtube.channels().list(
            part='statistics',
            id=channel_id
        ).execute()
        
        channel_subs = 0
        if channel_response.get('items'):
            channel_subs = int(channel_response['items'][0]['statistics'].get('subscriberCount', 0))
        
        # Calculate metrics
        engagement_rate = ((likes + comments) / views * 100) if views > 0 else 0
        view_to_sub_ratio = (views / channel_subs) if channel_subs > 0 else 0
        
        # Performance verdict
        if view_to_sub_ratio > 1:
            performance = "🔥 VIRAL - Views exceed subscriber count!"
        elif view_to_sub_ratio > 0.5:
            performance = "✅ Strong - Above average performance"
        elif view_to_sub_ratio > 0.2:
            performance = "📊 Average - Normal performance"
        else:
            performance = "📉 Below average - Underperforming"
        
        return {
            "video": {
                "title": snippet['title'],
                "channel": snippet['channelTitle'],
                "published": snippet['publishedAt'][:10],
                "description_preview": snippet.get('description', '')[:200],
                "tags": snippet.get('tags', [])
            },
            "metrics": {
                "views": views,
                "likes": likes,
                "comments": comments,
                "engagement_rate": round(engagement_rate, 2),
                "view_to_sub_ratio": round(view_to_sub_ratio, 2)
            },
            "channel_context": {
                "channel_subscribers": channel_subs,
                "expected_views": int(channel_subs * 0.3)  # Rough estimate
            },
            "performance_verdict": performance,
            "title_analysis": analyze_title_seo(snippet['title']),
            "tag_count": len(snippet.get('tags', []))
        }
        
    except Exception as e:
        return {"error": str(e)}


def analyze_title_seo(title: str) -> Dict:
    """Quick SEO analysis of a title."""
    
    return {
        "length": len(title),
        "word_count": len(title.split()),
        "has_number": bool(re.search(r'\d+', title)),
        "has_brackets": bool(re.search(r'[\[\]\(\)]', title)),
        "has_question": title.endswith('?'),
        "capitalization": "Title Case" if title.istitle() else "Mixed/Other"
    }


def get_channel_id_from_handle(youtube, handle: str) -> Optional[str]:
    """Resolve a @handle to channel ID."""
    
    if not youtube or not handle:
        return None
    
    try:
        handle = handle.strip()
        if handle.startswith('@'):
            response = youtube.channels().list(
                forHandle=handle,
                part='id'
            ).execute()
            
            if response.get('items'):
                return response['items'][0]['id']
        
        # Fallback to search
        search_response = youtube.search().list(
            q=handle,
            type='channel',
            part='id',
            maxResults=1
        ).execute()
        
        if search_response.get('items'):
            return search_response['items'][0]['id']['channelId']
        
        return None
        
    except:
        return None


# Legacy compatibility functions
def compare_channels(channels_data):
    """Legacy function."""
    return {"error": "Use compare_channels_live with YouTube API client"}

def analyze_competitor_video(video_data):
    """Legacy function."""
    return {"error": "Use analyze_video_performance with YouTube API client"}

def extract_competitor_tags(videos):
    """Legacy function."""
    all_tags = []
    for v in videos:
        all_tags.extend(v.get('tags', []))
    return Counter(all_tags).most_common(20)

def find_content_gaps(your_videos, competitor_videos):
    """Legacy function."""
    return {"error": "Use find_content_gaps_live with YouTube API client"}

def analyze_upload_schedule(videos):
    """Legacy function."""
    return analyze_upload_frequency(videos)

def generate_channel_scorecard(channel_data):
    """Legacy function."""
    return {"error": "Use analyze_channel_deeply with YouTube API client"}
