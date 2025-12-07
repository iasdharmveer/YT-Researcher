import streamlit as st
import pandas as pd
import re
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
import easyocr
import isodate
import os
import json
import datetime
from collections import Counter
import string
from transcript_helper import get_video_transcript
from streamlit_local_storage import LocalStorage

# Initialize localStorage for browser-based API key persistence
local_storage = LocalStorage()

# New Module Imports - All using REAL YouTube API data
from seo_analyzer import analyze_seo_vs_competitors, get_competitor_tags
from keyword_research import research_keyword_live, analyze_keyword_trend
from competitor_analyzer import (
    analyze_channel_deeply, compare_channels_live, 
    analyze_video_performance, find_content_gaps_live,
    get_channel_id_from_handle, get_channel_popular_videos,
    get_channel_from_video, extract_video_id_from_url
)
from ai_content_tools import (
    analyze_viral_titles, generate_titles_from_viral,
    generate_description_from_competitors, generate_tags_from_competitors,
    get_video_ideas_from_trends
)

# --- UI Configuration (Clean Professional Theme) ---
st.set_page_config(page_title="YouTube Intelligence Engine", page_icon="⚡", layout="wide")

# --- Constants ---
REGION_CODES = {
    "United States": "US", "India": "IN", "United Kingdom": "GB", "Canada": "CA", 
    "Australia": "AU", "Japan": "JP", "Germany": "DE", "Brazil": "BR", "France": "FR", 
    "Russia": "RU", "South Korea": "KR", "Global (Default)": None
}

LANGUAGES = {
    "English": "en", "Hindi": "hi", "Spanish": "es", "Portuguese": "pt", 
    "Russian": "ru", "Japanese": "ja", "German": "de", "French": "fr", "Any": None
}

VIDEO_CATEGORIES = {
    "Any": None,
    "Film & Animation": "1",
    "Autos & Vehicles": "2",
    "Music": "10",
    "Pets & Animals": "15",
    "Sports": "17",
    "Travel & Events": "19",
    "Gaming": "20",
    "People & Blogs": "22",
    "Comedy": "23",
    "Entertainment": "24",
    "News & Politics": "25",
    "Howto & Style": "26",
    "Education": "27",
    "Science & Technology": "28",
    "Nonprofits & Activism": "29"
}

def inject_custom_css():
    st.markdown("""
    <style>
        /* Minimal Clean Tweaks */
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
        
        /* Metric Cards - Clean Borders */
        div[data-testid="stMetric"] {
            background-color: #f8f9fa;
            border: 1px solid #e9ecef;
            padding: 15px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        /* Dark mode support for metrics if user has system dark mode */
        @media (prefers-color-scheme: dark) {
            div[data-testid="stMetric"] {
                background-color: #262730;
                border: 1px solid #363945;
            }
        }
        
        /* Sidebar Styling */
        section[data-testid="stSidebar"] {
            border-right: 1px solid #ddd;
        }
        
        /* Headers */
        h1, h2, h3 {
            font-weight: 700 !important;
        }
    </style>
    """, unsafe_allow_html=True)

inject_custom_css()

# --- Persistence Manager ---
CONFIG_FILE = 'dashboard_config.json'

def load_config():
    """Load config from file (excludes sensitive data like API keys)."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_config():
    """Save config to file - EXCLUDES API KEY for security!"""
    state = {
        # NOTE: API key is intentionally NOT saved to file for security
        'search_mode': st.session_state.get('search_mode', 'Channel Deep Dive'),
        'search_query': st.session_state.get('search_query', 'Future Tech'),
        'region_name': st.session_state.get('region_name', 'United States'),
        'lang_name': st.session_state.get('lang_name', 'English'),
        'channel_name': st.session_state.get('channel_name', '@UnXplained_Official'),
        'max_results': st.session_state.get('max_results', 50),
        'order_by': st.session_state.get('order_by', 'viewCount'),
        'published_after': str(st.session_state.get('published_after', datetime.date.today() - datetime.timedelta(days=365))),
        'cat_name': st.session_state.get('cat_name', 'Any'),
        'video_duration': st.session_state.get('video_duration', ['any']),
        'video_type': st.session_state.get('video_type', ['any']),
        'safe_search': st.session_state.get('safe_search', 'moderate'),
        'creative_commons': st.session_state.get('creative_commons', False),
        'min_virality': st.session_state.get('min_virality', 0.0),
        'min_view_count': st.session_state.get('min_view_count', 0),
        'ai_keywords_input': st.session_state.get('ai_keywords_input', "ChatGPT, Midjourney, AI Art, Stable Diffusion, ElevenLabs"),
        'enable_transcript': st.session_state.get('enable_transcript', True),
        'enable_ocr': st.session_state.get('enable_ocr', False)
    }
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(state, f)
    except:
        pass

def get_api_key():
    """
    Securely get API key from multiple sources (in priority order):
    1. Session state (user input in sidebar)
    2. Browser localStorage (persistent across sessions for each user)
    3. Local file (.api_key) - fallback for localStorage issues
    4. Streamlit secrets (for cloud deployment fallback)
    5. Environment variable (for local development)
    """
    # First check session state (user entered in UI)
    if st.session_state.get('api_key'):
        return st.session_state.get('api_key')
    
    # Then check browser localStorage (persists for each visitor)
    try:
        stored_key = local_storage.getItem("youtube_api_key")
        if stored_key:
            st.session_state['api_key'] = stored_key
            return stored_key
    except:
        pass
    
    # Then check local file (fallback for localStorage async issues)
    try:
        if os.path.exists('.api_key'):
            with open('.api_key', 'r') as f:
                file_key = f.read().strip()
                if file_key:
                    st.session_state['api_key'] = file_key
                    return file_key
    except:
        pass
    
    # Then check Streamlit secrets (for Streamlit Cloud)
    try:
        if hasattr(st, 'secrets') and 'YOUTUBE_API_KEY' in st.secrets:
            return st.secrets['YOUTUBE_API_KEY']
    except:
        pass
    
    # Finally check environment variable
    env_key = os.environ.get('YOUTUBE_API_KEY')
    if env_key:
        return env_key
    
    return ''

def save_api_key_to_storage(key: str):
    """Save API key to browser localStorage and local file for persistence."""
    success = False
    # Try localStorage first
    try:
        local_storage.setItem("youtube_api_key", key)
        success = True
    except:
        pass
    
    # Also save to file as fallback (for same-machine persistence)
    try:
        with open('.api_key', 'w') as f:
            f.write(key)
        success = True
    except:
        pass
    
    # Always update session state
    st.session_state['api_key'] = key
    return success

def clear_api_key_from_storage():
    """Remove API key from browser localStorage and local file."""
    success = False
    try:
        local_storage.deleteItem("youtube_api_key")
        success = True
    except:
        pass
    
    # Also remove from file
    try:
        if os.path.exists('.api_key'):
            os.remove('.api_key')
        success = True
    except:
        pass
    
    # Clear session state
    if 'api_key' in st.session_state:
        del st.session_state['api_key']
    return success

# --- Shared YouTube API Helper (DRY) ---
@st.cache_resource
def get_youtube_client(_api_key: str):
    """Create a cached YouTube API client. Use _api_key for caching."""
    if not _api_key:
        return None
    return build('youtube', 'v3', developerKey=_api_key)

def youtube_api_call(func):
    """Decorator to handle YouTube API errors consistently (DRY)."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except HttpError as e:
            st.error(f"YouTube API Error: {e}")
            return None
        except Exception as e:
            st.error(f"Error: {e}")
            return None
    return wrapper

def display_metrics(metrics_dict: dict, cols: int = 4):
    """Display metrics in a row of columns (DRY helper for UI)."""
    columns = st.columns(cols)
    for i, (label, value) in enumerate(metrics_dict.items()):
        columns[i % cols].metric(label, value)

def format_number(num: int) -> str:
    """Format large numbers with K/M suffix (DRY helper)."""
    if num >= 1_000_000:
        return f"{num / 1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num / 1_000:.1f}K"
    return str(num)

# Load Config at Startup
config = load_config()

# --- Helper Functions ---
def get_ngrams(text, n=2):
    """Generate n-grams from text."""
    if not text: return []
    # Remove punctuation and lowercase
    try:
        text = text.translate(str.maketrans('', '', string.punctuation)).lower()
    except:
        return []
    words = text.split()
    if len(words) < n:
        return []
    return [' '.join(words[i:i+n]) for i in range(len(words)-n+1)]

@st.cache_resource
def get_ocr_reader():
    return easyocr.Reader(['en'], gpu=False)

def detect_music_from_description(description):
    """Heuristic to find music credits in description."""
    if not description:
        return "None Detected"
    
    music_lines = []
    lines = description.split('\n')
    keywords = ["Music:", "Song:", "Track:", "Music by:", "BGM:", "Background Music:"]
    
    for line in lines:
        for kw in keywords:
            if kw.lower() in line.lower():
                clean_line = line.strip()
                if len(clean_line) < 100: 
                    music_lines.append(clean_line)
                break
    
    return " | ".join(music_lines) if music_lines else "None Detected"

def check_ai_content(text, keywords_list):
    """Boolean flag if content is likely AI-generated based on keywords."""
    if not text or not keywords_list:
        return False
    text_lower = text.lower()
    for kw in keywords_list:
        if kw.strip().lower() in text_lower:
            return True
    return False



# --- Mission Control Sidebar ---
st.sidebar.title("⚡ Mission Control")

# 1. Authentication (Browser LocalStorage - Each visitor uses their own key!)
with st.sidebar.expander("🔐 Your API Key", expanded=not get_api_key()):
    # Check for existing key in localStorage
    stored_key = None
    try:
        stored_key = local_storage.getItem("youtube_api_key")
    except:
        pass
    
    if stored_key:
        st.success("✅ API Key saved in your browser")
        st.caption("Your key is stored locally - not on our servers!")
        
        # Show masked key
        masked = stored_key[:8] + "..." + stored_key[-4:] if len(stored_key) > 12 else "***"
        st.code(f"Key: {masked}", language=None)
        
        # Clear button
        if st.button("🗑️ Remove Key", key="clear_api_key"):
            clear_api_key_from_storage()
            st.rerun()
        
        api_key = stored_key
        st.session_state['api_key'] = stored_key
    else:
        st.info("🔑 **Your API key stays in YOUR browser only!**")
        st.caption("Get a free key from [Google Cloud Console](https://console.cloud.google.com/apis/credentials)")
        
        # Input field
        new_key = st.text_input(
            "Enter your YouTube Data API Key", 
            value='',
            type="password", 
            help="Key is saved to your browser's localStorage - never sent to any server",
            key="new_api_key_input"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 Save Key", type="primary", key="save_api_key"):
                if new_key:
                    save_api_key_to_storage(new_key)
                    st.session_state['api_key'] = new_key
                    st.success("✅ Saved!")
                    st.rerun()
                else:
                    st.warning("Enter a key first")
        
        api_key = new_key if new_key else ''
    
    # Final API key from all sources
    api_key = get_api_key()

# 2. Search Strategy
with st.sidebar.expander("🎯 Search Strategy", expanded=True):
    search_mode = st.radio("Search Mode", ["Keyword Search", "Channel Deep Dive"], index=0 if config.get('search_mode') == "Keyword Search" else 1, key="search_mode", on_change=save_config)
    
    if search_mode == "Keyword Search":
        search_query = st.text_input("Main Keywords", value=config.get('search_query', "Future Tech"), key="search_query", on_change=save_config)
        
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            region_name = st.selectbox("Region", list(REGION_CODES.keys()), index=list(REGION_CODES.keys()).index(config.get('region_name', 'United States')), key="region_name", on_change=save_config)
            region_code = REGION_CODES[region_name]
        with col_s2:
            lang_name = st.selectbox("Language", list(LANGUAGES.keys()), index=list(LANGUAGES.keys()).index(config.get('lang_name', 'English')), key="lang_name", on_change=save_config)
            relevance_lang = LANGUAGES[lang_name]
            
    else:
        channel_name_input = st.text_input("Channel Name / Handle (@ID)", value=config.get('channel_name', '@UnXplained_Official'), key="channel_name", on_change=save_config)
        region_code = None # Default
        relevance_lang = None # Default

    max_results = st.number_input("Max Results (1-50)", min_value=1, max_value=50, value=config.get('max_results', 50), key="max_results", on_change=save_config)
    
    # Handle order_by index safely
    order_options = ["relevance", "date", "rating", "title", "videoCount", "viewCount"]
    saved_order = config.get('order_by', 'viewCount')
    order_index = order_options.index(saved_order) if saved_order in order_options else 5
    order_by = st.selectbox("Order By", order_options, index=order_index, key="order_by", on_change=save_config)
    
    # Handle Date safely
    default_date = datetime.date.today() - datetime.timedelta(days=365)
    saved_date_str = config.get('published_after', str(default_date))
    try:
        saved_date = datetime.datetime.strptime(saved_date_str, '%Y-%m-%d').date()
    except:
        saved_date = default_date
        
    published_after = st.date_input("Published After", value=saved_date, key="published_after", on_change=save_config)

# 3. Technical & Metric Filters
with st.sidebar.expander("⚙️ Filters", expanded=True):
    st.markdown("**API Filters**")
    
    # Handle category index
    cat_keys = list(VIDEO_CATEGORIES.keys())
    saved_cat = config.get('cat_name', 'Any')
    cat_index = cat_keys.index(saved_cat) if saved_cat in cat_keys else 0
    cat_name = st.selectbox("Video Category", cat_keys, index=cat_index, key="cat_name", on_change=save_config)
    video_category_id = VIDEO_CATEGORIES[cat_name]
    
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        video_duration = st.multiselect("Video Duration", ["any", "long", "medium", "short"], default=config.get('video_duration', ["any"]), key="video_duration", on_change=save_config)
    with col_f2:
        video_type = st.multiselect("Video Type", ["any", "episode", "movie"], default=config.get('video_type', ["any"]), key="video_type", on_change=save_config)
        
    safe_options = ["moderate", "none", "strict"]
    saved_safe = config.get('safe_search', 'moderate')
    safe_index = safe_options.index(saved_safe) if saved_safe in safe_options else 0
    safe_search = st.selectbox("Safe Search", safe_options, index=safe_index, key="safe_search", on_change=save_config)
    
    creative_commons = st.checkbox("Restrict to Creative Commons?", value=config.get('creative_commons', False), key="creative_commons", on_change=save_config)
    
    st.markdown("---")
    st.markdown("**Post-Processing Filters**")
    min_view_count = st.number_input("Min View Count", min_value=0, value=config.get('min_view_count', 0), step=1000, key="min_view_count", on_change=save_config)
    min_virality_score = st.slider("Min Virality Score", 0.0, 10.0, config.get('min_virality', 0.0), 0.1, help="Score = Views / Subscribers. Set to 0.0 to see all videos.", key="min_virality", on_change=save_config)

# 5. Intelligence Settings
with st.sidebar.expander("🧠 Intelligence Settings", expanded=True):
    ai_keywords_input = st.text_area("AI Niche Keywords", value=config.get('ai_keywords_input', "ChatGPT, Midjourney, AI Art, Stable Diffusion, ElevenLabs"), key="ai_keywords_input", on_change=save_config)
    ai_keywords = [k.strip() for k in ai_keywords_input.split(",") if k.strip()]
    enable_transcript = st.checkbox("Enable Transcript Extraction?", value=config.get('enable_transcript', True), key="enable_transcript", on_change=save_config)
    enable_ocr = st.checkbox("Enable Thumbnail OCR?", value=config.get('enable_ocr', False), key="enable_ocr", on_change=save_config)

# --- Main Engine ---

st.title("⚡ YouTube Intelligence Engine")
st.markdown("### *Your Complete YouTube Growth Toolkit - Like TubeBuddy & VidIQ*")

# --- NEW: Creator Toolbox Section ---
st.divider()
toolbox_tabs = st.tabs(["🔍 Research Engine", "📊 SEO Analyzer", "🔑 Keyword Explorer", "🧠 AI Content Studio", "🎯 Competitor Intel"])

# ==================== TAB 1: Research Engine (Original Functionality) ====================
with toolbox_tabs[0]:
    st.subheader("🔍 Research Engine")
    st.caption("Deep analysis of videos and channels - original engine functionality below")

# ==================== TAB 2: SEO Analyzer (REAL-TIME COMPARISON) ====================
with toolbox_tabs[1]:
    st.subheader("📊 Live SEO Analyzer")
    st.caption("Compare your video SEO against ACTUAL ranking videos - powered by real YouTube API data!")
    
    if not api_key:
        st.warning("⚠️ Enter your YouTube API key in the sidebar to use this feature")
    else:
        with st.form("seo_form"):
            col1, col2 = st.columns([2, 1])
            with col1:
                seo_title = st.text_input("Your Video Title", placeholder="Enter your video title...")
                seo_description = st.text_area("Your Description", placeholder="Enter your video description...", height=100)
            with col2:
                seo_target_keyword = st.text_input("Target Keyword", placeholder="keyword to rank for")
                seo_tags_input = st.text_input("Your Tags (comma-separated)", placeholder="tag1, tag2, tag3")
            
            seo_submit = st.form_submit_button("🔍 Compare Against Ranking Videos", type="primary")
        
        if seo_submit and seo_title and seo_target_keyword:
            seo_tags = [t.strip() for t in seo_tags_input.split(",") if t.strip()]
            
            with st.spinner(f"Analyzing top ranking videos for '{seo_target_keyword}'..."):
                try:
                    youtube = build('youtube', 'v3', developerKey=api_key)
                    
                    # Get REAL comparison data
                    seo_result = analyze_seo_vs_competitors(
                        youtube=youtube,
                        your_title=seo_title,
                        your_description=seo_description,
                        your_tags=seo_tags,
                        target_keyword=seo_target_keyword
                    )
                    
                    if "error" in seo_result:
                        st.error(f"Error: {seo_result['error']}")
                    else:
                        # Main Score Display
                        st.divider()
                        score_col1, score_col2, score_col3 = st.columns([1, 2, 1])
                        
                        with score_col2:
                            your_score = seo_result.get("your_score", {})
                            score = your_score.get("score", 0)
                            grade = your_score.get("grade", "?")
                            
                            if score >= 80:
                                score_color = "🟢"
                            elif score >= 60:
                                score_color = "🟡"
                            else:
                                score_color = "🔴"
                            
                            st.markdown(f"## {score_color} SEO Score: **{score}/100** (Grade: {grade})")
                            st.progress(score / 100)
                            st.caption(your_score.get("vs_competitor_avg", ""))
                        
                        # Detailed Breakdown
                        st.divider()
                        st.subheader("📋 Score Breakdown (vs Ranking Videos)")
                        
                        breakdown = your_score.get("breakdown", {})
                        for category, data in breakdown.items():
                            col1, col2 = st.columns([1, 3])
                            with col1:
                                st.metric(category.replace("_", " ").title(), f"{data.get('score', 0)} pts")
                            with col2:
                                st.write(data.get('status', ''))
                        
                        # Comparison Stats
                        st.divider()
                        st.subheader("📊 Your Video vs Competitors")
                        
                        comparison = seo_result.get("comparison", {})
                        comp_cols = st.columns(3)
                        
                        with comp_cols[0]:
                            st.metric("Your Title Length", 
                                     f"{comparison.get('your_title_length', 0)} chars",
                                     delta=f"Avg: {comparison.get('avg_ranking_title_length', 0)}")
                        with comp_cols[1]:
                            st.metric("Your Tag Count", 
                                     comparison.get('your_tag_count', 0),
                                     delta=f"Avg: {comparison.get('avg_ranking_tag_count', 0)}")
                        with comp_cols[2]:
                            st.metric("Your Desc Length", 
                                     f"{comparison.get('your_desc_length', 0)} words",
                                     delta=f"Avg: {comparison.get('avg_ranking_desc_length', 0)}")
                        
                        # Recommendations
                        recommendations = seo_result.get("recommendations", [])
                        if recommendations:
                            st.divider()
                            st.subheader("💡 Priority Actions")
                            for rec in recommendations:
                                if rec.get("impact") == "High":
                                    st.error(f"**{rec.get('category')}**: {rec.get('action')}")
                                elif rec.get("impact") == "Medium":
                                    st.warning(f"**{rec.get('category')}**: {rec.get('action')}")
                                else:
                                    st.info(f"**{rec.get('category')}**: {rec.get('action')}")
                        
                        # Top Ranking Videos
                        st.divider()
                        st.subheader("🏆 Top Ranking Videos for This Keyword")
                        
                        ranking_videos = seo_result.get("ranking_videos", [])
                        if ranking_videos:
                            for v in ranking_videos:
                                st.write(f"• **{v['title']}** - {v['channel']} ({v['views']:,} views)")
                        
                        # Competitor Tags
                        st.divider()
                        st.subheader("🏷️ Tags Used by Ranking Videos")
                        
                        comp_insights = seo_result.get("competitor_insights", {})
                        common_tags = comp_insights.get("common_tags", [])
                        if common_tags:
                            st.code(", ".join(common_tags[:15]), language=None)
                        
                except HttpError as e:
                    st.error(f"YouTube API Error: {e}")
                except Exception as e:
                    st.error(f"Error: {e}")

# ==================== TAB 3: Keyword Explorer (REAL API DATA) ====================
with toolbox_tabs[2]:
    st.subheader("🔑 Live Keyword Research Tool")
    st.caption("Analyze REAL competition using YouTube API - See actual ranking videos and their stats")
    
    if not api_key:
        st.warning("⚠️ Enter your YouTube API key in the sidebar to use this feature")
    else:
        keyword_input = st.text_input("Enter a keyword to research", placeholder="e.g., 'gaming setup'", key="keyword_research_input")
        
        if st.button("🔍 Research This Keyword", type="primary") and keyword_input:
            with st.spinner("Analyzing real YouTube data..."):
                try:
                    youtube = build('youtube', 'v3', developerKey=api_key)
                    
                    # Get REAL keyword research data
                    research = research_keyword_live(youtube, keyword_input, max_results=20)
                    
                    if "error" in research and research.get("total_results", 0) == 0:
                        st.error(f"Error: {research['error']}")
                    else:
                        st.divider()
                        
                        # Main Scores
                        col1, col2, col3 = st.columns(3)
                        
                        comp = research.get("competition", {})
                        opp = research.get("opportunity", {})
                        stats = research.get("stats", {})
                        
                        with col1:
                            st.metric(
                                "🎯 Competition Score",
                                f"{comp.get('score', 50)}/100",
                                delta=f"{comp.get('level', 'Medium')} {comp.get('color', '🟡')}"
                            )
                        
                        with col2:
                            st.metric(
                                "🚀 Opportunity Score",
                                f"{opp.get('score', 50)}/100",
                                delta=opp.get('verdict', 'Unknown')
                            )
                        
                        with col3:
                            st.metric(
                                "👁️ Avg Views (Top 20)",
                                f"{stats.get('avg_views', 0):,}",
                                delta=f"Avg Subs: {stats.get('avg_subscribers', 0):,}"
                            )
                        
                        # Recommendation
                        st.divider()
                        recommendation = research.get("recommendation", "")
                        if "RECOMMENDED" in recommendation or "GOOD" in recommendation:
                            st.success(recommendation)
                        elif "NOT RECOMMENDED" in recommendation or "CHALLENGING" in recommendation:
                            st.error(recommendation)
                        else:
                            st.warning(recommendation)
                        
                        # Competition Factors
                        st.divider()
                        st.subheader("📊 Competition Analysis")
                        
                        factors = comp.get("factors", {})
                        factor_cols = st.columns(3)
                        
                        with factor_cols[0]:
                            st.info(f"**Channel Size:** {factors.get('channel_size', 'Unknown')}")
                        with factor_cols[1]:
                            st.info(f"**View Potential:** {factors.get('view_potential', 'Unknown')}")
                        with factor_cols[2]:
                            st.info(f"**Variation:** {factors.get('variation', 'Unknown')}")
                        
                        # Top Ranking Videos
                        st.divider()
                        st.subheader("🏆 Top Ranking Videos (Real Data)")
                        
                        top_videos = research.get("top_videos", [])
                        if top_videos:
                            video_df = pd.DataFrame(top_videos)
                            st.dataframe(video_df, use_container_width=True, hide_index=True)
                        
                        # Related Keywords (Extracted from real videos)
                        st.divider()
                        st.subheader("🔗 Keywords from Competitor Videos")
                        
                        related = research.get("related_keywords", [])
                        if related:
                            kw_cols = st.columns(2)
                            
                            with kw_cols[0]:
                                st.markdown("**From Competitor Tags:**")
                                tag_keywords = [k for k in related if k.get("source") == "competitor_tags"]
                                for kw in tag_keywords[:10]:
                                    st.write(f"• {kw['keyword']} (used {kw['frequency']}x)")
                            
                            with kw_cols[1]:
                                st.markdown("**From Video Titles:**")
                                title_keywords = [k for k in related if k.get("source") == "titles"]
                                for kw in title_keywords[:10]:
                                    st.write(f"• {kw['keyword']} (appears {kw['frequency']}x)")
                            
                            # Copy-ready tags
                            st.divider()
                            all_kw = [k['keyword'] for k in related]
                            st.subheader("📋 Copy These Tags")
                            st.code(", ".join(all_kw), language=None)
                        
                        # Trend Analysis
                        st.divider()
                        st.subheader("📈 Trend Analysis")
                        
                        with st.spinner("Analyzing upload trends..."):
                            trend = analyze_keyword_trend(youtube, keyword_input)
                            
                            if "error" not in trend:
                                trend_cols = st.columns(4)
                                trend_cols[0].metric("Recent Uploads (7 days)", trend.get("recent_uploads", 0))
                                trend_cols[1].metric("Older Uploads (7-30 days)", trend.get("older_uploads", 0))
                                trend_cols[2].metric("Growth Rate", f"{trend.get('growth_rate', 0)}%")
                                trend_cols[3].metric("Trend", trend.get("trend", "Unknown"))
                            else:
                                st.warning(f"Could not analyze trend: {trend.get('error')}")
                        
                except HttpError as e:
                    st.error(f"YouTube API Error: {e}")
                except Exception as e:
                    st.error(f"Error: {e}")

# ==================== TAB 4: AI Content Studio (REAL DATA) ====================
with toolbox_tabs[3]:
    st.subheader("🧠 AI Content Studio (Powered by Real Data)")
    st.caption("Generate titles, descriptions, and ideas based on ACTUAL viral video patterns")
    
    if not api_key:
        st.warning("⚠️ Enter your YouTube API key in the sidebar to use this feature")
    else:
        ai_subtabs = st.tabs(["✨ Viral Title Analyzer", "📝 Smart Description", "💡 Trending Ideas", "🏷️ Competitor Tags"])
        
        # --- Viral Title Analyzer ---
        with ai_subtabs[0]:
            st.markdown("**Analyze viral titles in your niche and generate similar ones**")
            
            with st.form("title_gen_form"):
                title_topic = st.text_input("Your Topic/Niche", placeholder="e.g., 'iPhone 16 review'")
                title_count = st.slider("Number of Titles to Generate", 5, 15, 10)
                title_submit = st.form_submit_button("🔍 Analyze Viral Titles & Generate", type="primary")
            
            if title_submit and title_topic:
                with st.spinner(f"Analyzing top-performing videos for '{title_topic}'..."):
                    try:
                        youtube = build('youtube', 'v3', developerKey=api_key)
                        
                        # Analyze real viral titles
                        analysis = analyze_viral_titles(youtube, title_topic, max_results=30)
                        
                        if "error" in analysis:
                            st.error(f"Error: {analysis['error']}")
                        else:
                            st.divider()
                            
                            # Pattern Analysis
                            st.subheader("📊 Viral Title Patterns (from Real Videos)")
                            
                            patterns = analysis.get("patterns", {})
                            pattern_cols = st.columns(4)
                            pattern_cols[0].metric("Avg Length", f"{patterns.get('avg_length', 0)} chars")
                            pattern_cols[1].metric("Use Numbers", patterns.get('use_numbers', '0%'))
                            pattern_cols[2].metric("Use Brackets", patterns.get('use_brackets', '0%'))
                            pattern_cols[3].metric("Use Questions", patterns.get('use_questions', '0%'))
                            
                            # Best Practices
                            st.divider()
                            st.subheader("✅ What Works in This Niche")
                            for practice in analysis.get("best_practices", []):
                                st.write(practice)
                            
                            # Top Hooks
                            st.divider()
                            st.subheader("🪝 Most Common Hooks (First Words)")
                            hooks = analysis.get("top_hooks", [])
                            hook_text = [f"'{h['hook']}' ({h['count']}x)" for h in hooks[:10]]
                            st.write(" | ".join(hook_text) if hook_text else "No common hooks found")
                            
                            # Top Performing Titles
                            st.divider()
                            st.subheader("🏆 Top Performing Titles (Real)")
                            for i, vid in enumerate(analysis.get("top_titles", [])[:5], 1):
                                st.write(f"**{i}.** {vid['title']} ({vid['views']:,} views)")
                            
                            # Generate Titles Based on Analysis
                            st.divider()
                            st.subheader("🎬 Generated Titles (Based on Patterns)")
                            
                            generated = generate_titles_from_viral(youtube, title_topic, count=title_count)
                            
                            if generated.get("titles"):
                                for i, t in enumerate(generated["titles"], 1):
                                    col1, col2 = st.columns([4, 1])
                                    with col1:
                                        st.write(f"**{i}.** {t['title']}")
                                    with col2:
                                        st.caption(t.get('strategy', ''))
                            
                    except HttpError as e:
                        st.error(f"YouTube API Error: {e}")
                    except Exception as e:
                        st.error(f"Error: {e}")
        
        # --- Smart Description Generator ---
        with ai_subtabs[1]:
            st.markdown("**Generate descriptions based on what competitors are doing**")
            
            with st.form("desc_gen_form"):
                desc_keyword = st.text_input("Topic/Keyword", placeholder="What's your video about?")
                desc_length = st.number_input("Video Length (minutes)", min_value=1, max_value=180, value=10)
                desc_submit = st.form_submit_button("📝 Generate Description", type="primary")
            
            if desc_submit and desc_keyword:
                with st.spinner(f"Analyzing competitor descriptions for '{desc_keyword}'..."):
                    try:
                        youtube = build('youtube', 'v3', developerKey=api_key)
                        
                        result = generate_description_from_competitors(
                            youtube=youtube,
                            keyword=desc_keyword,
                            video_length=desc_length
                        )
                        
                        if "error" in result:
                            st.error(f"Error: {result['error']}")
                        else:
                            st.divider()
                            
                            # Competitor Insights
                            insights = result.get("insights", {})
                            st.subheader("📊 Competitor Description Analysis")
                            
                            ins_cols = st.columns(4)
                            ins_cols[0].metric("Videos Analyzed", insights.get("competitors_analyzed", 0))
                            ins_cols[1].metric("Avg Length", f"{insights.get('avg_description_length', 0)} words")
                            ins_cols[2].metric("Timestamps", insights.get("timestamps_usage", "N/A"))
                            ins_cols[3].metric("CTAs", insights.get("cta_usage", "N/A"))
                            
                            # Top Hashtags
                            top_tags = insights.get("top_hashtags", [])
                            if top_tags:
                                st.info(f"**Popular Hashtags:** {' '.join(['#'+t for t in top_tags[:8]])}")
                            
                            # Generated Description
                            st.divider()
                            st.subheader("📋 Generated Description")
                            st.text_area("Copy this:", result.get("description", ""), height=350)
                            
                    except HttpError as e:
                        st.error(f"YouTube API Error: {e}")
                    except Exception as e:
                        st.error(f"Error: {e}")
        
        # --- Trending Ideas ---
        with ai_subtabs[2]:
            st.markdown("**Get video ideas based on REAL trending content in your niche**")
            
            with st.form("ideas_form"):
                ideas_niche = st.text_input("Your Niche", placeholder="e.g., Personal Finance")
                ideas_days = st.slider("Analyze videos from last X days", 7, 90, 30)
                ideas_submit = st.form_submit_button("💡 Find Trending Ideas", type="primary")
            
            if ideas_submit and ideas_niche:
                with st.spinner(f"Analyzing trending content in '{ideas_niche}'..."):
                    try:
                        youtube = build('youtube', 'v3', developerKey=api_key)
                        
                        result = get_video_ideas_from_trends(youtube, ideas_niche, days_back=ideas_days)
                        
                        if "error" in result:
                            st.error(f"Error: {result['error']}")
                        else:
                            st.divider()
                            
                            # Stats
                            stats_cols = st.columns(3)
                            stats_cols[0].metric("Videos Analyzed", result.get("videos_analyzed", 0))
                            stats_cols[1].metric("Best Format", result.get("best_format", "Unknown"))
                            stats_cols[2].metric("Period", result.get("period", "N/A"))
                            
                            # Trending Topics
                            st.divider()
                            st.subheader("🔥 Trending Topics")
                            topics = result.get("trending_topics", [])
                            st.write(" • ".join(topics) if topics else "No clear trends found")
                            
                            # Format Distribution
                            st.divider()
                            st.subheader("📊 What's Working")
                            formats = result.get("format_distribution", {})
                            for fmt, count in formats.items():
                                st.write(f"• **{fmt.title()}**: {count} videos")
                            
                            # Video Ideas
                            st.divider()
                            st.subheader("💡 Generated Video Ideas")
                            for i, idea in enumerate(result.get("video_ideas", []), 1):
                                st.success(f"**{i}.** {idea}")
                            
                            # Top Performers Reference
                            st.divider()
                            st.subheader("🏆 Recent Top Performers")
                            for vid in result.get("top_performers", [])[:5]:
                                st.write(f"• {vid['title']} ({vid['views']:,} views)")
                            
                    except HttpError as e:
                        st.error(f"YouTube API Error: {e}")
                    except Exception as e:
                        st.error(f"Error: {e}")
        
        # --- Competitor Tags ---
        with ai_subtabs[3]:
            st.markdown("**Extract the most effective tags from top-performing videos**")
            
            with st.form("tag_gen_form"):
                tag_keyword = st.text_input("Topic/Keyword", placeholder="e.g., 'gaming headset review'")
                tag_count = st.slider("Max Tags to Return", 10, 30, 15)
                tag_submit = st.form_submit_button("🏷️ Extract Tags", type="primary")
            
            if tag_submit and tag_keyword:
                with st.spinner(f"Extracting tags from top videos for '{tag_keyword}'..."):
                    try:
                        youtube = build('youtube', 'v3', developerKey=api_key)
                        
                        result = generate_tags_from_competitors(youtube, tag_keyword, max_tags=tag_count)
                        
                        if "error" in result:
                            st.error(f"Error: {result['error']}")
                        else:
                            st.divider()
                            
                            # Stats
                            stats_cols = st.columns(3)
                            stats_cols[0].metric("Videos Analyzed", result.get("videos_analyzed", 0))
                            stats_cols[1].metric("Unique Tags Found", result.get("unique_tags_found", 0))
                            stats_cols[2].metric("Top Tags Returned", len(result.get("tags", [])))
                            
                            # Tag Details
                            st.divider()
                            st.subheader("🏷️ Best Tags (Ranked by Performance)")
                            
                            tag_details = result.get("tag_details", [])
                            if tag_details:
                                tag_df = pd.DataFrame(tag_details)
                                st.dataframe(tag_df, use_container_width=True, hide_index=True)
                            
                            # Copy Ready
                            st.divider()
                            st.subheader("📋 Copy These Tags")
                            st.code(result.get("copy_ready", ""), language=None)
                            
                    except HttpError as e:
                        st.error(f"YouTube API Error: {e}")
                    except Exception as e:
                        st.error(f"Error: {e}")

# ==================== TAB 5: Competitor Intel (REAL DATA) ====================
with toolbox_tabs[4]:
    st.subheader("🎯 Competitor Intelligence (Live Analysis)")
    st.caption("Deep analysis of competitor videos and channels with REAL data")
    
    if not api_key:
        st.warning("⚠️ Enter your YouTube API key in the sidebar to use this feature")
    else:
        intel_subtabs = st.tabs(["🎬 Video Analysis", "📊 Channel Analysis", "🔄 Channel Comparison", "🔥 Popular Videos Research"])
        
        # --- Video Analysis ---
        with intel_subtabs[0]:
            st.markdown("**Analyze any YouTube video and explore the channel's top content**")
            
            video_url = st.text_input("YouTube Video URL", placeholder="https://www.youtube.com/watch?v=...", key="video_analysis_url")
            
            # Date filter
            col_date, col_sort = st.columns(2)
            with col_date:
                default_date = datetime.date.today() - datetime.timedelta(days=365)
                video_start_date = st.date_input("Videos Published After", value=default_date, key="video_analysis_date")
            with col_sort:
                video_sort_options = ["views", "date", "engagement"]
                video_sort_by = st.selectbox("Sort Videos By", video_sort_options, index=0, key="video_analysis_sort")
            
            if st.button("🔍 Analyze Video & Channel", key="analyze_video_btn") and video_url:
                video_id_match = re.search(r'(?:v=|/)([a-zA-Z0-9_-]{11})', video_url)
                
                if video_id_match:
                    video_id = video_id_match.group(1)
                    
                    with st.spinner("Analyzing video and fetching channel data..."):
                        try:
                            youtube = build('youtube', 'v3', developerKey=api_key)
                            result = analyze_video_performance(youtube, video_id)
                            
                            if "error" in result:
                                st.error(f"Error: {result['error']}")
                            else:
                                st.divider()
                                
                                # Video Info
                                vid_info = result.get("video", {})
                                st.subheader(f"📹 {vid_info.get('title', 'Unknown')[:60]}...")
                                st.caption(f"By: {vid_info.get('channel', 'Unknown')} | Published: {vid_info.get('published', 'N/A')}")
                                
                                # Performance
                                st.divider()
                                metrics = result.get("metrics", {})
                                verdict = result.get("performance_verdict", "")
                                
                                st.markdown(f"### {verdict}")
                                
                                perf_cols = st.columns(5)
                                perf_cols[0].metric("Views", f"{metrics.get('views', 0):,}")
                                perf_cols[1].metric("Likes", f"{metrics.get('likes', 0):,}")
                                perf_cols[2].metric("Comments", f"{metrics.get('comments', 0):,}")
                                perf_cols[3].metric("Engagement", f"{metrics.get('engagement_rate', 0)}%")
                                perf_cols[4].metric("View/Sub Ratio", f"{metrics.get('view_to_sub_ratio', 0):.2f}")
                                
                                # Channel Context
                                chan = result.get("channel_context", {})
                                channel_id = vid_info.get("channel_id", "")
                                
                                st.divider()
                                st.subheader(f"📺 Channel Analysis: {vid_info.get('channel', 'Unknown')}")
                                
                                chan_cols = st.columns(4)
                                chan_cols[0].metric("Subscribers", f"{chan.get('channel_subscribers', 0):,}")
                                chan_cols[1].metric("Expected Views", f"{chan.get('expected_views', 0):,}")
                                chan_cols[2].metric("Total Videos", f"{chan.get('total_videos', 0):,}" if chan.get('total_videos') else "N/A")
                                chan_cols[3].metric("Avg View Performance", f"{metrics.get('view_to_sub_ratio', 0):.2f}x subs")
                                
                                # Title Analysis
                                st.divider()
                                st.subheader("🪝 Title Analysis")
                                title_analysis = result.get("title_analysis", {})
                                
                                ta_cols = st.columns(4)
                                ta_cols[0].metric("Length", f"{title_analysis.get('length', 0)} chars")
                                ta_cols[1].metric("Has Number", "✅" if title_analysis.get('has_number') else "❌")
                                ta_cols[2].metric("Has Brackets", "✅" if title_analysis.get('has_brackets') else "❌")
                                ta_cols[3].metric("Words", title_analysis.get('word_count', 0))
                                
                                # Tags
                                st.divider()
                                st.subheader(f"🏷️ Tags ({result.get('tag_count', 0)} total)")
                                tags = vid_info.get("tags", [])
                                if tags:
                                    st.code(", ".join(tags[:20]), language=None)
                                else:
                                    st.warning("No public tags on this video")
                                
                                # ==================== FETCH CHANNEL'S POPULAR VIDEOS ====================
                                st.divider()
                                st.subheader(f"🔥 Top 50 Videos from {vid_info.get('channel', 'this channel')}")
                                st.caption(f"Sorted by: {video_sort_by} | After: {video_start_date}")
                                
                                with st.spinner("Fetching channel's popular videos..."):
                                    # Get channel ID from the video
                                    if channel_id:
                                        popular_result = get_channel_popular_videos(
                                            youtube=youtube,
                                            channel_id=channel_id,
                                            max_results=50,
                                            order_by=video_sort_by,
                                            start_date=str(video_start_date)
                                        )
                                        
                                        if "error" in popular_result:
                                            st.warning(f"Could not fetch channel videos: {popular_result.get('error')}")
                                        else:
                                            # Channel Summary Stats
                                            summary = popular_result.get("summary", {})
                                            if summary:
                                                sum_cols = st.columns(4)
                                                sum_cols[0].metric("Total Views", f"{summary.get('total_views', 0):,}")
                                                sum_cols[1].metric("Total Likes", f"{summary.get('total_likes', 0):,}")
                                                sum_cols[2].metric("Avg Views", f"{summary.get('avg_views', 0):,}")
                                                sum_cols[3].metric("Avg Engagement", f"{summary.get('avg_engagement', 0)}%")
                                            
                                            # Video List
                                            videos = popular_result.get("videos", [])
                                            
                                            if videos:
                                                # Create DataFrame for display with ALL research engine columns
                                                display_data = []
                                                for i, v in enumerate(videos, 1):
                                                    # Format tags as comma-separated string
                                                    tags_str = ", ".join(v.get('tags', []))
                                                    
                                                    display_data.append({
                                                        "Rank": i,
                                                        "Title": v['title'][:50] + "..." if len(v['title']) > 50 else v['title'],
                                                        "Views": f"{v['views']:,}",
                                                        "Likes": f"{v['likes']:,}",
                                                        "Engagement": f"{v['engagement_rate']}%",
                                                        "Published": v['published'][:10] if v.get('published') else "N/A",
                                                        "Duration_Minutes": v.get('duration_minutes', 0),
                                                        "Video_Topics": v.get('video_topics', 'N/A'),
                                                        "Background_Music": v.get('background_music', 'None Detected'),
                                                        "Tags": tags_str if tags_str else 'N/A',
                                                        "Description": v.get('description', '')[:200] + "..." if len(v.get('description', '')) > 200 else v.get('description', 'N/A')
                                                    })
                                                
                                                videos_df = pd.DataFrame(display_data)
                                                st.dataframe(videos_df, use_container_width=True, hide_index=True)
                                                
                                                # Common Tags Analysis
                                                st.divider()
                                                st.subheader("🏷️ Common Tags Across Channel Videos")
                                                
                                                all_tags = []
                                                for v in videos:
                                                    all_tags.extend([t.lower() for t in v.get('tags', [])])
                                                
                                                if all_tags:
                                                    from collections import Counter
                                                    tag_counts = Counter(all_tags)
                                                    top_tags = [f"{tag} ({count})" for tag, count in tag_counts.most_common(20)]
                                                    st.write(" • ".join(top_tags))
                                                else:
                                                    st.info("No tags data available from videos")
                                            else:
                                                st.info("No videos found in the specified date range")
                                    else:
                                        st.warning("Could not determine channel ID from video")
                                
                        except HttpError as e:
                            st.error(f"YouTube API Error: {e}")
                        except Exception as e:
                            st.error(f"Error: {e}")
                else:
                    st.error("Invalid YouTube URL")
        
        # --- Channel Analysis ---
        with intel_subtabs[1]:
            st.markdown("**Deep dive into a competitor channel**")
            
            channel_input = st.text_input("Channel Handle or Name", placeholder="@ChannelName or Channel Name")
            
            if st.button("📊 Analyze Channel", key="analyze_channel") and channel_input:
                with st.spinner("Analyzing channel..."):
                    try:
                        youtube = build('youtube', 'v3', developerKey=api_key)
                        
                        # Resolve channel ID
                        channel_id = get_channel_id_from_handle(youtube, channel_input)
                        
                        if not channel_id:
                            st.error("Channel not found")
                        else:
                            result = analyze_channel_deeply(youtube, channel_id)
                            
                            if "error" in result:
                                st.error(f"Error: {result['error']}")
                            else:
                                st.divider()
                                
                                # Channel Info
                                chan_info = result.get("channel", {})
                                st.subheader(f"📺 {chan_info.get('name', 'Unknown')}")
                                st.caption(f"Channel ID: {chan_info.get('id', '')} | Created: {chan_info.get('created', 'N/A')}")
                                
                                # Stats
                                chan_cols = st.columns(4)
                                chan_cols[0].metric("Subscribers", f"{chan_info.get('subscribers', 0):,}")
                                chan_cols[1].metric("Total Views", f"{chan_info.get('total_views', 0):,}")
                                chan_cols[2].metric("Videos", chan_info.get('video_count', 0))
                                chan_cols[3].metric("Views/Video", f"{result.get('performance', {}).get('views_per_video', 0):,}")
                                
                                # Performance
                                st.divider()
                                perf = result.get("performance", {})
                                st.subheader("📈 Performance Metrics")
                                
                                perf_cols = st.columns(3)
                                perf_cols[0].metric("Avg Recent Views", f"{perf.get('avg_recent_views', 0):,}")
                                perf_cols[1].metric("Engagement Rate", f"{perf.get('avg_engagement_rate', 0)}%")
                                perf_cols[2].metric("Virality Ratio", f"{perf.get('virality_ratio', 0):.2f}")
                                
                                # Upload Pattern
                                st.divider()
                                upload = result.get("upload_pattern", {})
                                st.subheader("📅 Upload Pattern")
                                
                                up_cols = st.columns(3)
                                up_cols[0].metric("Frequency", upload.get("frequency", "Unknown"))
                                up_cols[1].metric("Avg Days Between", upload.get("avg_days_between_uploads", "N/A"))
                                up_cols[2].metric("Best Days", ", ".join(upload.get("best_days", [])[:2]) if upload.get("best_days") else "N/A")
                                
                                # Content Patterns
                                st.divider()
                                content = result.get("content_patterns", {})
                                st.subheader("📊 Content Patterns")
                                
                                st.write(f"**Common Topics:** {', '.join(content.get('common_topics', [])[:8])}")
                                st.write(f"**Number Usage:** {content.get('number_usage', '0%')} | **Brackets:** {content.get('bracket_usage', '0%')}")
                                
                                # Top Videos
                                st.divider()
                                st.subheader("🏆 Top Videos")
                                
                                for vid in result.get("top_videos", [])[:5]:
                                    st.write(f"• **{vid['title'][:50]}...** - {vid['views']:,} views")
                                
                                # Common Tags
                                st.divider()
                                st.subheader("🏷️ Most Used Tags")
                                common_tags = content.get("common_tags", [])
                                if common_tags:
                                    st.code(", ".join(common_tags[:15]), language=None)
                                
                    except HttpError as e:
                        st.error(f"YouTube API Error: {e}")
                    except Exception as e:
                        st.error(f"Error: {e}")
        
        # --- Channel Comparison ---
        with intel_subtabs[2]:
            st.markdown("**Compare multiple channels side by side**")
            
            st.info("Enter up to 5 channel handles (one per line)")
            channels_text = st.text_area("Channel Handles", placeholder="@Channel1\n@Channel2\n@Channel3", height=100)
            
            if st.button("📊 Compare Channels", key="compare_channels") and channels_text:
                channels = [c.strip() for c in channels_text.strip().split('\n') if c.strip()]
                
                if len(channels) < 2:
                    st.warning("Enter at least 2 channels to compare")
                elif len(channels) > 5:
                    st.warning("Maximum 5 channels for comparison")
                else:
                    with st.spinner(f"Comparing {len(channels)} channels..."):
                        try:
                            youtube = build('youtube', 'v3', developerKey=api_key)
                            
                            # Resolve all channel IDs
                            channel_ids = []
                            for handle in channels:
                                cid = get_channel_id_from_handle(youtube, handle)
                                if cid:
                                    channel_ids.append(cid)
                            
                            if len(channel_ids) < 2:
                                st.error("Could not resolve enough channels. Check the handles.")
                            else:
                                result = compare_channels_live(youtube, channel_ids)
                                
                                if "error" in result:
                                    st.error(f"Error: {result['error']}")
                                else:
                                    st.divider()
                                    
                                    st.subheader(f"📊 Comparison of {result.get('channels_compared', 0)} Channels")
                                    st.success(f"**Leader:** {result.get('leader', 'Unknown')}")
                                    
                                    comp_df = pd.DataFrame(result.get("comparison", []))
                                    st.dataframe(comp_df, use_container_width=True, hide_index=True)
                                    
                                    st.info(f"**Combined Subscribers:** {result.get('total_combined_subs', 0):,} | **Average:** {result.get('avg_subs', 0):,}")
                                
                        except HttpError as e:
                            st.error(f"YouTube API Error: {e}")
                        except Exception as e:
                            st.error(f"Error: {e}")
        
        # --- Popular Videos Research ---
        with intel_subtabs[3]:
            st.markdown("**Research popular videos from any channel - enter a handle or video link**")
            
            col1, col2 = st.columns([2, 1])
            with col1:
                input_query = st.text_input(
                    "Channel Handle or Video URL", 
                    placeholder="@ChannelHandle or https://youtube.com/watch?v=...",
                    key="popular_research_input"
                )
            with col2:
                start_date = st.date_input(
                    "Start Date (optional)", 
                    value=None,
                    key="popular_start_date"
                )
            
            col3, col4 = st.columns(2)
            with col3:
                order_by = st.selectbox("Sort By", ["views", "date", "engagement"], key="popular_order")
            with col4:
                max_results = st.slider("Max Videos", 10, 50, 30, key="popular_max")
            
            if st.button("🔍 Research Popular Videos", type="primary", key="research_popular"):
                if input_query:
                    with st.spinner("Fetching popular videos..."):
                        try:
                            youtube = build('youtube', 'v3', developerKey=api_key)
                            
                            # Determine if input is video URL or channel handle
                            channel_id = None
                            
                            # Check if it's a video URL
                            video_id = extract_video_id_from_url(input_query)
                            if video_id:
                                # Get channel from video
                                channel_id = get_channel_from_video(youtube, video_id)
                                if channel_id:
                                    st.info("📹 Detected video URL - fetching channel's popular videos...")
                            else:
                                # It's a channel handle/name
                                channel_id = get_channel_id_from_handle(youtube, input_query)
                            
                            if not channel_id:
                                st.error("Could not find channel. Check the handle or video URL.")
                            else:
                                # Convert date to string format
                                date_str = None
                                if start_date:
                                    date_str = start_date.strftime("%Y-%m-%d")
                                
                                # Get popular videos
                                result = get_channel_popular_videos(
                                    youtube=youtube,
                                    channel_id=channel_id,
                                    start_date=date_str,
                                    max_results=max_results,
                                    order_by=order_by
                                )
                                
                                if "error" in result:
                                    st.error(f"Error: {result['error']}")
                                else:
                                    st.divider()
                                    
                                    # Channel Info
                                    chan = result.get("channel", {})
                                    st.subheader(f"📺 {chan.get('name', 'Unknown')} ({chan.get('handle', '')})")
                                    
                                    chan_cols = st.columns(3)
                                    chan_cols[0].metric("Subscribers", f"{chan.get('subscribers', 0):,}")
                                    chan_cols[1].metric("Total Videos", chan.get('total_videos', 0))
                                    chan_cols[2].metric("Videos Found", result.get('filter', {}).get('videos_found', 0))
                                    
                                    # Summary Stats
                                    st.divider()
                                    summary = result.get("summary", {})
                                    
                                    sum_cols = st.columns(4)
                                    sum_cols[0].metric("Total Views", f"{summary.get('total_views', 0):,}")
                                    sum_cols[1].metric("Total Likes", f"{summary.get('total_likes', 0):,}")
                                    sum_cols[2].metric("Avg Views", f"{summary.get('avg_views', 0):,}")
                                    sum_cols[3].metric("Avg Engagement", f"{summary.get('avg_engagement', 0)}%")
                                    
                                    # Filter Info
                                    filter_info = result.get("filter", {})
                                    st.caption(f"📅 Date filter: {filter_info.get('start_date', 'All time')} | Sort: {filter_info.get('order_by', 'views')} | Scanned: {filter_info.get('total_scanned', 0)} videos")
                                    
                                    # Video List
                                    st.divider()
                                    st.subheader(f"🔥 Top {len(result.get('videos', []))} Videos (by {order_by})")
                                    
                                    videos = result.get("videos", [])
                                    
                                    # Create DataFrame for display with ALL research engine columns
                                    if videos:
                                        display_data = []
                                        for i, v in enumerate(videos, 1):
                                            # Format tags as comma-separated string
                                            tags_str = ", ".join(v.get('tags', []))
                                            
                                            display_data.append({
                                                "Rank": i,
                                                "Title": v['title'][:60] + "..." if len(v['title']) > 60 else v['title'],
                                                "Views": f"{v['views']:,}",
                                                "Likes": f"{v['likes']:,}",
                                                "Engagement": f"{v['engagement_rate']}%",
                                                "Published": v['published'],
                                                "Duration_Minutes": v.get('duration_minutes', 0),
                                                "Video_Topics": v.get('video_topics', 'N/A'),
                                                "Background_Music": v.get('background_music', 'None Detected'),
                                                "Tags": tags_str if tags_str else 'N/A',
                                                "Description": v.get('description', '')[:200] + "..." if len(v.get('description', '')) > 200 else v.get('description', 'N/A'),
                                                "Video_ID": v['video_id']
                                            })
                                        
                                        videos_df = pd.DataFrame(display_data)
                                        st.dataframe(videos_df, use_container_width=True, hide_index=True)
                                        
                                        # Expandable details
                                        st.divider()
                                        st.subheader("📋 Detailed Video List")
                                        
                                        for i, v in enumerate(videos[:20], 1):  # Show first 20 in detail
                                            with st.expander(f"#{i} - {v['title'][:50]}..."):
                                                det_cols = st.columns(4)
                                                det_cols[0].metric("Views", f"{v['views']:,}")
                                                det_cols[1].metric("Likes", f"{v['likes']:,}")
                                                det_cols[2].metric("Comments", f"{v['comments']:,}")
                                                det_cols[3].metric("Engagement", f"{v['engagement_rate']}%")
                                                
                                                st.write(f"**Published:** {v['published']}")
                                                st.write(f"**URL:** [youtube.com/watch?v={v['video_id']}](https://youtube.com/watch?v={v['video_id']})")
                                                
                                                if v.get('tags'):
                                                    st.write("**Tags:**")
                                                    st.code(", ".join(v['tags']), language=None)
                                        
                                        # Tags from all videos
                                        st.divider()
                                        st.subheader("🏷️ Common Tags Across Videos")
                                        
                                        all_tags = []
                                        for v in videos:
                                            all_tags.extend([t.lower() for t in v.get('tags', [])])
                                        
                                        if all_tags:
                                            from collections import Counter
                                            tag_counts = Counter(all_tags)
                                            top_tags = [f"{tag} ({count})" for tag, count in tag_counts.most_common(20)]
                                            st.write(" • ".join(top_tags))
                                    
                        except HttpError as e:
                            st.error(f"YouTube API Error: {e}")
                        except Exception as e:
                            st.error(f"Error: {e}")
                else:
                    st.warning("Please enter a channel handle or video URL")

@st.cache_data(ttl=3600)
def resolve_channel_id(_youtube, query):
    """Robustly resolve channel ID from Handle or Name."""
    query = query.strip()
    
    # 1. Try Handle Search (Exact Match)
    if query.startswith("@"):
        try:
            resp = _youtube.channels().list(forHandle=query, part='id').execute()
            if resp.get('items'):
                return resp['items'][0]['id']
        except Exception:
            pass # Fallback to search if handle fails
            
    # 2. Try Standard Search (Best Effort)
    try:
        search_resp = _youtube.search().list(q=query, type='channel', part='id', maxResults=1).execute()
        if search_resp.get('items'):
            return search_resp['items'][0]['id']['channelId']
    except Exception:
        return None
        
    return None

# Move to Research Engine tab context
with toolbox_tabs[0]:
    if st.button("🚀 Start Deep Analysis", type="primary", key="research_engine_btn"):
        if not api_key:
            st.error("⚠️ API Key is required to run the engine.")
        else:
            try:
                youtube = build('youtube', 'v3', developerKey=api_key)
                status_container = st.empty()
            
                # --- Phase 1: Search ---
                status_container.info(f"📡 Phase 1: Scanning Network ({search_mode})...")
            
                video_ids = []
            
                if search_mode == "Keyword Search":
                    video_type_val = video_type[0] if video_type else 'any'
                    video_duration_val = video_duration[0] if video_duration else 'any'
                    published_after_rfc = f"{published_after}T00:00:00Z"
                
                    # Validate order_by to ensure it's a valid YouTube API value
                    valid_order_values = ["relevance", "date", "rating", "title", "videoCount", "viewCount"]
                    safe_order_by = order_by if order_by in valid_order_values else "viewCount"
                
                    search_params = {
                        'q': search_query,
                        'part': 'id,snippet',
                        'maxResults': max_results,
                        'regionCode': region_code,
                        'relevanceLanguage': relevance_lang,
                        'order': safe_order_by,
                        'publishedAfter': published_after_rfc,
                        'type': 'video', 
                        'safeSearch': safe_search,
                        'videoType': video_type_val if video_type_val != 'any' else None,
                        'videoDuration': video_duration_val if video_duration_val != 'any' else None,
                        'videoDuration': video_duration_val if video_duration_val != 'any' else None,
                        'videoLicense': 'creativeCommon' if creative_commons else None,
                        'videoCategoryId': video_category_id
                    }
                    # Clean None values
                    search_params = {k: v for k, v in search_params.items() if v is not None}
                
                    search_response = youtube.search().list(**search_params).execute()
                    video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]
            
                else: # Channel Deep Dive
                    target_channel_id = resolve_channel_id(youtube, channel_name_input)
                
                    if not target_channel_id:
                         st.error(f"Channel '{channel_name_input}' not found. Please double check the handle (e.g. @MrBeast).")
                    else:
                    
                        # Get Uploads Playlist
                        ch_resp = youtube.channels().list(id=target_channel_id, part='contentDetails').execute()
                        uploads_id = ch_resp['items'][0]['contentDetails']['relatedPlaylists']['uploads']
                    
                        # Fetch Items from Playlist
                        pl_resp = youtube.playlistItems().list(
                            playlistId=uploads_id,
                            part='contentDetails,snippet',
                            maxResults=max_results
                        ).execute()
                    
                        # Filter by date manually for playlist items
                        for item in pl_resp.get('items', []):
                             vid_pub = pd.to_datetime(item['snippet']['publishedAt']).tz_convert(None)
                             if vid_pub >= pd.to_datetime(published_after):
                                 video_ids.append(item['contentDetails']['videoId'])

                if not video_ids:
                    status_container.warning("No results found. Adjust filters.")
                else:
                    # --- Phase 2: Enrichment (Batching) ---
                    status_container.info(f"🛰️ Phase 2: Enriching data for {len(video_ids)} videos...")
                
                    # Videos List (Batch) - requesting MORE parts
                    videos_response = youtube.videos().list(
                        part='snippet,statistics,contentDetails,topicDetails,status',
                        id=','.join(video_ids)
                    ).execute()
                
                    video_items = videos_response.get('items', [])
                
                    # Channels List (Batch) - requesting MORE parts
                    channel_ids = list(set([v['snippet']['channelId'] for v in video_items]))
                    channels_response = youtube.channels().list(
                        part='statistics,brandingSettings,topicDetails',
                        id=','.join(channel_ids)
                    ).execute()
                
                    channel_map = {c['id']: c for c in channels_response.get('items', [])}
                
                    # --- Phase 3 & 4: Logic & Content Scraping ---
                    processed_rows = []
                
                    progress_bar = st.progress(0)
                
                    for idx, vid in enumerate(video_items):
                        status_container.text(f"Processing {idx+1}/{len(video_items)}: {vid['snippet']['title'][:40]}...")
                        progress_bar.progress((idx + 1) / len(video_items))
                    
                        # Data Extraction
                        snippet = vid['snippet']
                        stats = vid['statistics']
                        content = vid['contentDetails']
                        topic_details = vid.get('topicDetails', {})
                        status = vid.get('status', {})
                        content_rating = content.get('contentRating', {})
                        vid_id = vid['id']
                    
                        # Metrics
                        views = int(stats.get('viewCount', 0))
                        likes = int(stats.get('likeCount', 0))
                        comments = int(stats.get('commentCount', 0))
                    
                        # --- Post-Processing Filters ---
                        if views < min_view_count:
                            continue
                    
                        # Channel Context
                        channel_id = snippet['channelId']
                        channel_data = channel_map.get(channel_id, {})
                        channel_stats = channel_data.get('statistics', {})
                        channel_branding = channel_data.get('brandingSettings', {})
                        channel_topics = channel_data.get('topicDetails', {})
                    
                        subs = int(channel_stats.get('subscriberCount', 1))
                        if subs == 0: subs = 1
                    
                        # Detailed Channel Info
                        channel_keywords = channel_branding.get('channel', {}).get('keywords', '')
                        channel_topic_categories = ", ".join([t.split('/')[-1] for t in channel_topics.get('topicCategories', [])])

                        # Calculated Intelligence
                        virality_score = round(views / subs, 2)
                    
                        if virality_score < min_virality_score:
                            continue
                    
                        engagement_rate = round(((likes + comments) / views * 100), 2) if views > 0 else 0
                    
                        # AI Flag
                        full_text = f"{snippet['title']} {snippet['description']} {' '.join(snippet.get('tags', []))}"
                        is_ai_content = check_ai_content(full_text, ai_keywords)
                    
                        # Duration
                        duration_iso = content.get('duration', 'PT0S')
                        duration_seconds = isodate.parse_duration(duration_iso).total_seconds()
                        duration_minutes = round(duration_seconds / 60, 2)

                        # Extra Context
                        video_topics = ", ".join([t.split('/')[-1] for t in topic_details.get('topicCategories', [])])
                        music_detected = detect_music_from_description(snippet['description'])

                        # Transcript
                        transcript_text = "N/A"
                        if enable_transcript:
                            # Use the robust helper module
                            raw_transcript = get_video_transcript(vid_id)
                        
                            if isinstance(raw_transcript, list):
                                if raw_transcript:
                                    # Non-empty list = Success - format manually (dicts with 'text' key)
                                    try:
                                        # Extract text from each segment (handles both dicts and objects)
                                        text_parts = []
                                        for segment in raw_transcript:
                                            if isinstance(segment, dict):
                                                text_parts.append(segment.get('text', ''))
                                            elif hasattr(segment, 'text'):
                                                text_parts.append(str(segment.text))
                                            else:
                                                text_parts.append(str(segment))
                                        transcript_text = ' '.join(text_parts).replace('\n', ' ')
                                    except Exception as fmt_err:
                                        transcript_text = f"Format Error: {fmt_err}"
                                else:
                                    # Empty list = Valid extraction but no content found
                                    transcript_text = "No transcript content found"
                            elif isinstance(raw_transcript, str):
                                # It returned an error string
                                transcript_text = raw_transcript
                            else:
                                 transcript_text = f"Format Error: {type(raw_transcript)}"

                        # OCR
                        ocr_text = "N/A"
                        if enable_ocr:
                            try:
                                thumb_url = snippet['thumbnails'].get('high', snippet['thumbnails'].get('default'))['url']
                                ocr_text = get_ocr_reader().readtext(thumb_url, detail=0)
                                ocr_text = " ".join(ocr_text)
                            except:
                                ocr_text = "OCR Failed"
                            
                            
                        processed_rows.append({
                            # 1. Identity
                            'Video_Title': snippet['title'],
                            'Video_URL': f"https://www.youtube.com/watch?v={vid_id}",
                            'Thumbnail_URL': snippet['thumbnails']['high']['url'],
                            #'Video_ID': vid_id, # Redundant for LLM
                        
                            # 2. Performance Metrics
                            'Virality_Score': virality_score,
                            'Engagement_Rate': engagement_rate,
                            'Views': views,
                            'Likes': likes,
                            'Comments': comments,
                        
                            # 3. Channel Context
                            'Channel_Name': snippet['channelTitle'],
                            'Subscribers': subs,
                            'Channel_Keywords': channel_keywords,
                            #'Channel_Topics': channel_topic_categories, # Often cleaner in Video Topics
                        
                            # 4. Content Metadata
                            'Publish_Date': snippet['publishedAt'],
                            'Duration_Minutes': duration_minutes,
                            'Video_Topics': video_topics,
                        
                            # Removed Low-Signal Technical Columns for LLM Clarity
                            # 'Language': snippet.get('defaultAudioLanguage', 'N/A'),
                            # 'Made_For_Kids': status.get('madeForKids', 'N/A'),
                            # 'Content_Definition': content.get('definition', 'N/A'),
                            # 'Content_Rating': str(content_rating) if content_rating else "None",
                        
                            # 5. AI & Creative
                            # 'AI_Flag': is_ai_content, # Internal metric, maybe not needed for strategy export
                            'Background_Music': music_detected,
                            'Tags': ", ".join(snippet.get('tags', [])),
                        
                            # 6. Deep Content (The Payload)
                            'Thumbnail_OCR_Text': ocr_text,
                            'Description': snippet['description'],
                            'Transcript_Cleaned': transcript_text
                        })
                
                    if not processed_rows:
                        st.warning("No videos passed the filters. Try lowering 'Min Virality Score' or 'Min View Count' in the sidebar.")
                    else:
                        status_container.success(f"Analysis Complete! Generated {len(processed_rows)} strategic insights.")
                
                    # --- Visualization & Export ---
                    # Condensed Column List for Maximum Signal-to-Noise Ratio
                    ordered_columns = [
                        'Video_Title', 'Video_URL', 
                        'Virality_Score', 'Engagement_Rate', 'Views', 
                        'Channel_Name', 'Subscribers', 'Channel_Keywords', 
                        'Publish_Date', 'Duration_Minutes', 'Video_Topics', 
                        'Background_Music', 'Tags',
                        'Thumbnail_OCR_Text', 'Description', 'Transcript_Cleaned'
                    ]
                
                    df = pd.DataFrame(processed_rows)
                    # Ensure all columns exist even if empty data logic missed one (safety)
                    # and reorder
                    df = df.reindex(columns=ordered_columns)
                
                    # Create Tabs
                    tab1, tab2 = st.tabs(["📊 Data Explorer", "🚀 Growth Strategy"])
                
                    with tab1:
                        # 1. Top Performer Card
                        if not df.empty:
                            top_video = df.loc[df['Virality_Score'].idxmax()]
                            st.divider()
                            col1, col2 = st.columns([1, 2])
                            with col1:
                                st.subheader("👑 Top Viral Performer")
                                st.metric(label="Virality Score", value=f"{top_video['Virality_Score']}x")
                                st.metric(label="Views", value=f"{int(top_video['Views']):,}")
                            with col2:
                                st.markdown(f"**{top_video['Video_Title']}**")
                                st.markdown(f"*{top_video['Video_URL']}*")
                                st.info(f"**Why it worked (AI Logic)**: High engagement ({top_video['Engagement_Rate']}%) relative to low subscriber base ({int(top_video['Subscribers']):,}).")

                            # 2. Scatter Plot
                            st.divider()
                            st.subheader("📈 Viral Velocity Map")
                            st.scatter_chart(
                                df,
                                x='Publish_Date',
                                y='Views',
                                color='Virality_Score',
                                size='Virality_Score',
                                height=400
                            )
                        
                            # 3. Data Table
                            st.divider()
                            st.subheader("📊 Strategic Data (Full Context)")
                            st.dataframe(df) # Showing EVERYTHING so user knows it's there
                        
                            # 4. Export
                            csv = df.to_csv(index=False).encode('utf-8')
                            st.download_button(
                                label="💾 Download Strategy Context (LLM Ready CSV)",
                                data=csv,
                                file_name='strategy_context.csv',
                                mime='text/csv',
                                type='primary'
                            )
                
                    with tab2:
                        st.header("🚀 Blueprint for Growth")
                        st.markdown("Replicate the success of these viral videos with these data-backed strategies.")
                    
                        if not df.empty:
                            # Convert Date for analysis
                            df['Publish_DT'] = pd.to_datetime(df['Publish_Date'])
                            df['Day_Of_Week'] = df['Publish_DT'].dt.day_name()
                            df['Hour_Of_Day'] = df['Publish_DT'].dt.hour
                        
                            # A. Best Time to Upload
                            col_a1, col_a2 = st.columns(2)
                            with col_a1:
                                st.subheader("📅 Best Day to Upload")
                                day_counts = df['Day_Of_Week'].value_counts()
                                st.bar_chart(day_counts)
                            with col_a2:
                                st.subheader("⏰ Best Hour to Upload")
                                hour_counts = df['Hour_Of_Day'].value_counts().sort_index()
                                st.bar_chart(hour_counts)
                            
                            # B. Title Hooks (N-Grams)
                            st.divider()
                            st.subheader("🪝 Winning Title Hooks")
                            st.caption("Most common 2-word phrases in these viral titles.")
                        
                            all_titles = " ".join(df['Video_Title'].dropna().tolist())
                            bigrams = get_ngrams(all_titles, 2)
                            trigrams = get_ngrams(all_titles, 3)
                        
                            c_bi = Counter(bigrams).most_common(10)
                        
                            # Display as metrics
                            cols = st.columns(5)
                            for i, (phrase, count) in enumerate(c_bi[:5]):
                                cols[i].metric(label=f"Rank #{i+1}", value=phrase.title(), delta=f"{count} uses")
                            
                            # C. Golden Tags
                            st.divider()
                            st.subheader("🏷️ Golden Tags")
                            st.caption("Topics that consistently appeared in high-performing videos.")
                        
                            all_tags = []
                            for tags_str in df['Tags']:
                                if tags_str:
                                    all_tags.extend([t.strip() for t in tags_str.split(',')])
                        
                            c_tags = Counter(all_tags).most_common(15)
                            tags_df = pd.DataFrame(c_tags, columns=['Tag', 'Count']).set_index('Tag')
                            st.bar_chart(tags_df)
                        
                            # D. Ideal Duration
                            st.divider()
                            st.subheader("⏳ The Perfect Duration")
                            avg_duration = df['Duration_Minutes'].mean()
                            st.metric("Average Viral Duration", f"{avg_duration:.2f} Minutes")
                            st.bar_chart(df['Duration_Minutes'].value_counts(bins=5).sort_index())
                        
                            # E. Thumbnail Text Density
                            st.divider()
                            st.subheader("🖼️ Thumbnail Strategy")
                        
                            df['OCR_Word_Count'] = df['Thumbnail_OCR_Text'].apply(lambda x: len(x.split()) if x != "N/A" and x != "OCR Failed" else 0)
                            avg_ocr_words = df[df['OCR_Word_Count'] > 0]['OCR_Word_Count'].mean()
                        
                            if pd.isna(avg_ocr_words): avg_ocr_words = 0
                        
                            st.info(f"**Insight**: Viral thumbnails in this niche use an average of **{avg_ocr_words:.1f} words** on the image.")
                        
                            # F. Visual Pattern Grid (NEW)
                            st.divider()
                            st.subheader("🎨 Visual Pattern Grid")
                            st.caption("Top 20 Viral Thumbnails. Look for passing colors, face emotions, and arrow placements.")
                        
                            # Sort by Virality and take top 20
                            top_visuals = df.sort_values(by='Virality_Score', ascending=False).head(20)
                        
                            if not top_visuals.empty:
                                cols = st.columns(4) # 4 columns grid
                                for idx, (_, row) in enumerate(top_visuals.iterrows()):
                                    with cols[idx % 4]:
                                        st.image(row['Thumbnail_URL'], use_container_width=True)
                                        st.caption(f"{row['Virality_Score']}x | {row['Views']} views")

                            # G. AI Title Lab (NEW)
                            st.divider()
                            st.subheader("🧠 AI Title Lab")
                            st.caption("Experimental: Generates viral title concepts by remixing the winning N-grams found in this search.")
                        
                            if len(all_titles) > 0:
                                # 1. Get winning starts (First 2 words)
                                starts = [t.split()[:2] for t in df['Video_Title']]
                                starts = [" ".join(s) for s in starts if len(s) >= 2]
                                top_starts = [x[0] for x in Counter(starts).most_common(5)]
                            
                                # 2. Get winning topics (Tags)
                                top_tags = [x[0] for x in c_tags[:5]]
                            
                                # 3. Simple Remix
                                if top_starts and top_tags:
                                    st.markdown("**Generated Concepts:**")
                                    for i in range(min(5, len(top_starts))):
                                        import random
                                        # Simple template logic
                                        start = top_starts[i].title()
                                        tag = top_tags[i % len(top_tags)].title()
                                    
                                        templates = [
                                            f"{start} {tag} (Insane Results)",
                                            f"Why {tag} is the Future of {start}",
                                            f"I Tried {tag} for 30 Days",
                                            f"The {tag} Mistake You're Making",
                                            f"{start}: The Ultimate Guide to {tag}"
                                        ]
                                        suggestion = random.choice(templates)
                                        st.success(f"✨ {suggestion}")
                                else:
                                    st.warning("Not enough data to generate titles.")

            except HttpError as e:
                st.error(f"API Error: {e}")
            except Exception as e:
                st.error(f"System Error: {e}")
