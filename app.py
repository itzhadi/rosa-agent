from __future__ import annotations

import datetime as dt
import json
import os
import re
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

# On Streamlit Cloud, secrets come from st.secrets instead of .env
try:
    for key, value in st.secrets.items():
        if key not in os.environ:
            os.environ[key] = str(value)
except Exception:
    pass

DIGESTS_DIR = Path(__file__).resolve().parent / "rosacea_digests"


def get_digest_files() -> list[Path]:
    if not DIGESTS_DIR.exists():
        return []
    files = sorted(DIGESTS_DIR.glob("digest_*.md"), reverse=True)
    return files


def get_raw_files() -> dict[str, Path]:
    if not DIGESTS_DIR.exists():
        return {}
    return {f.stem.replace("raw_", ""): f for f in DIGESTS_DIR.glob("raw_*.json")}


def extract_date_from_filename(path: Path) -> str:
    match = re.search(r"\d{4}-\d{2}-\d{2}", path.name)
    return match.group(0) if match else path.name


def load_raw_items(date_str: str) -> list[dict]:
    raw_files = get_raw_files()
    if date_str in raw_files:
        try:
            return json.loads(raw_files[date_str].read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def run_agent(days_back: int, pubmed_max: int, news_max: int) -> str:
    from neurogenic_rosacea_agent import (
        PUBMED_TERMS,
        dedupe_new_items,
        ensure_dir,
        load_json,
        render_markdown,
        save_json,
        search_pubmed,
        search_tavily_news,
        summarize_pubmed_ids,
        summarize_with_openai,
        utc_today,
    )

    out_dir = DIGESTS_DIR
    ensure_dir(out_dir)

    seen_path = out_dir / "seen_items.json"
    raw_path = out_dir / f"raw_{utc_today()}.json"
    md_path = out_dir / f"digest_{utc_today()}.md"

    seen_ids = set(load_json(seen_path, []))

    pubmed_ids: list[str] = []
    for term in PUBMED_TERMS:
        try:
            pubmed_ids.extend(search_pubmed(term, days_back=days_back, retmax=pubmed_max))
        except Exception:
            pass
    pubmed_ids = list(dict.fromkeys(pubmed_ids))
    pubmed_items = summarize_pubmed_ids(pubmed_ids)

    try:
        news_items = search_tavily_news(max_results=news_max)
    except Exception:
        news_items = []

    all_items = pubmed_items + news_items
    new_items = dedupe_new_items(all_items, seen_ids)

    summary = summarize_with_openai(new_items)
    save_json(raw_path, new_items)
    md = render_markdown(utc_today(), new_items, summary)
    md_path.write_text(md, encoding="utf-8")

    seen_ids.update(item["id"] for item in new_items if item.get("id"))
    save_json(seen_path, sorted(seen_ids))

    return f"נמצאו {len(new_items)} פריטים חדשים"


# ── Page config ──────────────────────────────────────────────
st.set_page_config(
    page_title="Neurogenic Rosacea Agent",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS ───────────────────────────────────────────────
st.markdown('<meta name="viewport" content="width=device-width, initial-scale=1.0">', unsafe_allow_html=True)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Rubik:wght@300;400;500;600;700&display=swap');

    .stApp {
        font-family: 'Rubik', sans-serif;
        direction: rtl;
    }

    .stMainBlockContainer, .block-container {
        direction: rtl;
        text-align: right;
    }

    /* Sidebar: keep all controls LTR so slider values are visible */
    div[data-testid="stSidebar"] {
        direction: ltr !important;
    }
    div[data-testid="stSidebar"] * {
        direction: ltr !important;
    }
    div[data-testid="stSidebar"] .stMarkdown,
    div[data-testid="stSidebar"] .stMarkdown p,
    div[data-testid="stSidebar"] .stMarkdown h3,
    div[data-testid="stSidebar"] .stMarkdown li {
        direction: rtl !important;
        text-align: right !important;
    }
    /* Force slider thumb value to be visible */
    div[data-testid="stSidebar"] [data-testid="stThumbValue"],
    div[data-testid="stSidebar"] .stSlider [data-testid="stThumbValue"] {
        direction: ltr !important;
        opacity: 1 !important;
        visibility: visible !important;
    }

    /* Markdown content RTL */
    .stMarkdown, .stMarkdown p, .stMarkdown li, .stMarkdown h1,
    .stMarkdown h2, .stMarkdown h3, .stMarkdown h4 {
        direction: rtl;
        text-align: right;
    }

    /* Tabs RTL */
    div[data-testid="stTabs"] > div[role="tablist"] {
        direction: rtl;
        flex-direction: row-reverse;
    }

    .main-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        padding: 2rem 2.5rem;
        border-radius: 16px;
        margin-bottom: 1.5rem;
        color: white;
        box-shadow: 0 8px 32px rgba(15, 52, 96, 0.3);
        direction: rtl;
        text-align: right;
    }
    .main-header h1 {
        margin: 0;
        font-size: 2rem;
        font-weight: 700;
    }
    .main-header p {
        margin: 0.5rem 0 0 0;
        opacity: 0.8;
        font-size: 1rem;
        font-weight: 300;
    }

    .stat-card {
        background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
        border: 1px solid #e9ecef;
        padding: 1.25rem;
        border-radius: 12px;
        text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .stat-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 16px rgba(0,0,0,0.08);
    }
    .stat-number {
        font-size: 2.2rem;
        font-weight: 700;
        color: #0f3460;
        line-height: 1;
    }
    .stat-label {
        font-size: 0.85rem;
        color: #6c757d;
        margin-top: 0.3rem;
        font-weight: 500;
    }

    .digest-card {
        background: #ffffff;
        border: 1px solid #e9ecef;
        border-radius: 12px;
        padding: 1.5rem 2rem;
        margin-bottom: 1rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        direction: rtl;
        text-align: right;
    }

    .item-card {
        background: #f8f9fa;
        border-right: 4px solid #0f3460;
        border-left: none;
        border-radius: 8px 0 0 8px;
        padding: 1rem 1.25rem;
        margin-bottom: 0.75rem;
        transition: border-color 0.2s;
        direction: rtl;
        text-align: right;
    }
    .item-card:hover {
        border-right-color: #e94560;
    }
    .item-card h4 {
        margin: 0 0 0.4rem 0;
        font-size: 1rem;
        color: #1a1a2e;
    }
    .item-card .meta {
        font-size: 0.82rem;
        color: #6c757d;
    }
    .item-card a {
        color: #0f3460;
        text-decoration: none;
        font-weight: 500;
    }
    .item-card a:hover {
        color: #e94560;
        text-decoration: underline;
    }

    .sidebar-section {
        background: rgba(15, 52, 96, 0.05);
        border-radius: 10px;
        padding: 1rem;
        margin-bottom: 1rem;
    }

    div[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #fafbfc 0%, #f0f2f5 100%);
    }

    /* ── Mobile responsive ─────────────────────────── */
    @media (max-width: 768px) {
        .stApp {
            overflow-x: hidden !important;
        }

        .stMainBlockContainer, .block-container {
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            max-width: 100% !important;
        }

        /* Sidebar: overlay on mobile, don't push content */
        div[data-testid="stSidebar"] {
            z-index: 999 !important;
        }

        .main-header {
            padding: 1.2rem 1rem;
            border-radius: 10px;
            margin-bottom: 1rem;
        }
        .main-header h1 {
            font-size: 1.3rem;
            line-height: 1.4;
        }
        .main-header p {
            font-size: 0.85rem;
        }

        /* Stat cards: stack vertically on mobile */
        div[data-testid="stColumns"] {
            flex-direction: column !important;
            gap: 0.5rem !important;
        }
        div[data-testid="stColumns"] > div[data-testid="stColumn"] {
            width: 100% !important;
            flex: 1 1 100% !important;
        }
        .stat-card {
            padding: 1rem;
            border-radius: 10px;
            margin-bottom: 0;
        }
        .stat-number {
            font-size: 1.6rem;
        }
        .stat-label {
            font-size: 0.8rem;
        }

        /* Digest content */
        .digest-card {
            padding: 1rem;
            border-radius: 8px;
            word-wrap: break-word;
            overflow-wrap: break-word;
        }
        .digest-card h1 { font-size: 1.2rem; }
        .digest-card h2 { font-size: 1.05rem; }
        .digest-card h3 { font-size: 0.95rem; }
        .digest-card li, .digest-card p {
            font-size: 0.88rem;
            line-height: 1.7;
        }

        /* Item cards */
        .item-card {
            padding: 0.8rem;
            border-radius: 6px 0 0 6px;
        }
        .item-card h4 { font-size: 0.9rem; }
        .item-card .meta { font-size: 0.75rem; }

        /* Tabs */
        div[data-testid="stTabs"] button {
            font-size: 0.8rem !important;
            padding: 0.4rem 0.5rem !important;
        }
        div[data-testid="stTabs"] > div[role="tablist"] {
            gap: 0 !important;
        }

        /* History: stack columns */
        .stDownloadButton button {
            font-size: 0.8rem !important;
            padding: 0.3rem 0.6rem !important;
        }
    }

    @media (max-width: 400px) {
        .main-header {
            padding: 1rem 0.8rem;
        }
        .main-header h1 {
            font-size: 1.1rem;
        }
        .main-header p {
            font-size: 0.8rem;
        }
        .stMainBlockContainer, .block-container {
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
        }
    }
</style>
""", unsafe_allow_html=True)

# ── Header ───────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <h1>🔬 סוכן מחקר רוזציאה נוירוגנית</h1>
    <p>סיכום יומי של מאמרים מ-PubMed וחדשות הקשורות לרוזציאה נוירוגנית</p>
</div>
""", unsafe_allow_html=True)

# ── Sidebar ──────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ הגדרות סוכן")

    days_back = st.number_input("ימים אחורה (PubMed)", min_value=1, max_value=90, value=30, step=5)
    pubmed_max = st.number_input("מקסימום תוצאות PubMed לכל מונח", min_value=1, max_value=50, value=10, step=1)
    news_max = st.number_input("מקסימום תוצאות חדשות", min_value=1, max_value=30, value=10, step=1)

    st.markdown("---")

    has_keys = bool(os.getenv("OPENAI_API_KEY"))
    if not has_keys:
        st.error("⚠️ OPENAI_API_KEY לא נמצא בקובץ .env")

    if st.button("🚀 הפעל סוכן עכשיו", use_container_width=True, disabled=not has_keys, type="primary"):
        with st.spinner("מריץ את הסוכן... זה עשוי לקחת 1-2 דקות"):
            try:
                result = run_agent(days_back, pubmed_max, news_max)
                st.success(result)
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    st.markdown("---")
    st.markdown("### 📊 מקורות מידע")
    st.markdown("""
    - **PubMed** – מאמרים אקדמיים
    - **Tavily** – חדשות מהרשת
    - **OpenAI** – סיכומי AI
    """)

    tavily_ok = "✅" if os.getenv("TAVILY_API_KEY") else "❌"
    openai_ok = "✅" if os.getenv("OPENAI_API_KEY") else "❌"
    st.markdown(f"""
    | שירות | סטטוס |
    |---------|--------|
    | OpenAI  | {openai_ok} |
    | Tavily  | {tavily_ok} |
    """)

# ── Load data ────────────────────────────────────────────────
digest_files = get_digest_files()
raw_map = get_raw_files()

# ── Stats row ────────────────────────────────────────────────
total_digests = len(digest_files)
total_seen = 0
seen_path = DIGESTS_DIR / "seen_items.json"
if seen_path.exists():
    try:
        total_seen = len(json.loads(seen_path.read_text(encoding="utf-8")))
    except Exception:
        pass

latest_date = extract_date_from_filename(digest_files[0]) if digest_files else "—"

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(f"""
    <div class="stat-card">
        <div class="stat-number">{total_digests}</div>
        <div class="stat-label">סיכומים שנוצרו</div>
    </div>
    """, unsafe_allow_html=True)
with col2:
    st.markdown(f"""
    <div class="stat-card">
        <div class="stat-number">{total_seen}</div>
        <div class="stat-label">סה"כ פריטים שנמצאו</div>
    </div>
    """, unsafe_allow_html=True)
with col3:
    st.markdown(f"""
    <div class="stat-card">
        <div class="stat-number">{latest_date}</div>
        <div class="stat-label">סיכום אחרון</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Main content ─────────────────────────────────────────────
if not digest_files:
    st.info("אין סיכומים עדיין. לחץ על **הפעל סוכן עכשיו** בסרגל הצד כדי ליצור את הראשון!")
else:
    tab_digest, tab_items, tab_history = st.tabs(["📄 סיכום אחרון", "🗂️ פרטי פריטים", "📚 היסטוריה"])

    # ── Latest Digest tab ────────────────────────────────────
    with tab_digest:
        selected_idx = 0
        if len(digest_files) > 1:
            date_options = [extract_date_from_filename(f) for f in digest_files]
            selected_date = st.selectbox("בחר תאריך סיכום", date_options, index=0)
            selected_idx = date_options.index(selected_date)

        digest_content = digest_files[selected_idx].read_text(encoding="utf-8")
        st.markdown(
            f'<div class="digest-card">\n\n{digest_content}\n\n</div>',
            unsafe_allow_html=True,
        )

    # ── Items Detail tab ─────────────────────────────────────
    with tab_items:
        date_for_items = extract_date_from_filename(digest_files[selected_idx if 'selected_idx' in dir() else 0])
        items = load_raw_items(date_for_items)

        if not items:
            st.info("אין נתוני פריטים גולמיים לתאריך זה.")
        else:
            st.markdown(f"**{len(items)} פריטים** נמצאו בתאריך {date_for_items}")
            for item in items:
                source_badge = item.get("source", "Unknown")
                title = item.get("title", "Untitled")
                url = item.get("url", "")
                published = item.get("published", "")
                journal = item.get("journal", "")
                authors = item.get("authors", [])
                content = item.get("content", "")

                link_html = f'<a href="{url}" target="_blank">{title}</a>' if url else title
                meta_parts = []
                if source_badge:
                    meta_parts.append(f"📰 {source_badge}")
                if published:
                    meta_parts.append(f"📅 {published}")
                if journal:
                    meta_parts.append(f"📖 {journal}")
                if authors:
                    meta_parts.append(f"✍️ {', '.join(authors[:3])}")

                st.markdown(f"""
                <div class="item-card">
                    <h4>{link_html}</h4>
                    <div class="meta">{' &nbsp;|&nbsp; '.join(meta_parts)}</div>
                    {f'<p style="margin-top:0.5rem;font-size:0.9rem;color:#495057">{content[:300]}...</p>' if content else ''}
                </div>
                """, unsafe_allow_html=True)

    # ── History tab ──────────────────────────────────────────
    with tab_history:
        st.markdown("### כל הסיכומים")
        for f in digest_files:
            date_str = extract_date_from_filename(f)
            raw_items = load_raw_items(date_str)
            item_count = len(raw_items)

            col_a, col_b, col_c = st.columns([3, 1, 1])
            with col_a:
                st.markdown(f"**{date_str}**")
            with col_b:
                st.markdown(f"{item_count} פריטים")
            with col_c:
                with open(f, "r", encoding="utf-8") as fh:
                    st.download_button(
                        "⬇️ הורדה",
                        fh.read(),
                        file_name=f.name,
                        mime="text/markdown",
                        key=f"dl_{date_str}",
                    )
