"""Reusable UI components for the Streamlit dashboard."""
import streamlit as st
import dropbox
import hashlib
from requests.exceptions import ConnectionError, Timeout
from dashboard.utils import load_latest_backup_engine


def apply_global_styles():
    """Inject global CSS for dark theme, cards, sidebar, and hide native nav."""
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200');

   .material-symbols-outlined {
        font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
    }

    .dashboard-title {
        font-size: 2.2rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        margin-top: 0 !important;
        padding-top: 0 !important;
        color: #ffffff;
    }
    section[data-testid="stMain"] {
        padding-top: 0.5rem !important;
    }
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        font-size: 0.9rem;
        margin-bottom: 1.5rem;
    }
    .status-badge.loaded {
        background: rgba(0, 200, 83, 0.15);
        border: 1px solid rgba(0, 200, 83, 0.3);
        color: #69f0ae;
    }
    .status-badge.not-loaded {
        background: rgba(255, 82, 82, 0.15);
        border: 1px solid rgba(255, 82, 82, 0.3);
        color: #ff8a80;
    }
    .card-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 1rem;
        margin-top: 1.5rem;
    }
    .quick-card {
        background: linear-gradient(135deg, #1e1e2f 0%, #2a2a3e 100%);
        border: 1px solid #3a3a4e;
        border-radius: 14px;
        padding: 1.5rem;
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        transition: all 0.2s ease;
        text-decoration: none;
        color: #e0e0e0;
    }
    .quick-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 20px rgba(0,0,0,0.3);
        border-color: #5a5a7a;
    }
    .quick-card h3 {
        margin: 0 0 0.5rem 0;
        font-size: 1.1rem;
        color: #ffffff;
    }
    .quick-card p {
        margin: 0;
        font-size: 0.85rem;
        color: #aaa;
        line-height: 1.4;
    }
    .card-icon {
        font-size: 1.5rem;
        margin-bottom: 0.5rem;
    }
    @media (max-width: 768px) {
        .card-grid {
            grid-template-columns: repeat(2, 1fr);
        }
    }
    @media (max-width: 480px) {
        .card-grid {
            grid-template-columns: 1fr;
        }
    }

    /* Global heading styles */
    h1 {
        font-size: 2rem;
        font-weight: 700;
        color: #ffffff;
        border-bottom: 2px solid rgba(255,255,255,0.08);
        padding-bottom: 0.5rem;
        margin-bottom: 1rem;
    }
    h2 {
        font-size: 1.3rem;
        font-weight: 600;
        color: #bbbbdd;
        border-bottom: 1px solid rgba(255,255,255,0.05);
        padding-bottom: 0.3rem;
        margin-top: 2rem;
        margin-bottom: 0.8rem;
    }
    h3 {
        font-size: 1rem;
        font-weight: 600;
        color: #999;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-top: 1.5rem;
        margin-bottom: 0.5rem;
    }

    /* Sidebar dark theme alignment */
    [data-testid="stSidebar"] {
        background-color: #161625;
        border-right: 1px solid rgba(255, 255, 255, 0.06);
        padding-top: 1rem;
    }

    [data-testid="stSidebar"] .stHeader {
        color: #bbbbdd !important;
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        padding-bottom: 0.3rem;
        margin-bottom: 0.8rem;
        font-size: 1rem !important;
        font-weight: 600 !important;
    }

    [data-testid="stSidebar"] .stSubheader {
        color: #999 !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        font-size: 0.8rem !important;
        font-weight: 600 !important;
        margin-top: 1.2rem !important;
        margin-bottom: 0.5rem !important;
        border-bottom: none !important;
    }

    [data-testid="stSidebar"] .stButton button {
        background-color: #1e1e30 !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 8px !important;
        color: #ffffff !important;
        font-weight: 500 !important;
        width: 100% !important;
        padding: 0.4rem 0.8rem !important;
        transition: all 0.2s ease !important;
    }

    [data-testid="stSidebar"] .stButton button:hover {
        background-color: #2a2a40 !important;
        border-color: #5a5a7a !important;
    }

    [data-testid="stSidebar"] .stAlert {
        background-color: transparent !important;
        border: none !important;
        padding: 0.25rem 0 !important;
        font-size: 0.85rem !important;
    }

    [data-testid="stSidebar"] .stAlert.stAlert-success {
        color: #69f0ae !important;
    }

    [data-testid="stSidebar"] .stAlert.stAlert-info {
        color: #bbbbdd !important;
    }

    [data-testid="stSidebar"] .stPageLink {
        padding: 0 !important;
        margin-bottom: 0.1rem !important;
    }

    [data-testid="stSidebar"] .stPageLink a {
        color: #999 !important;
        text-decoration: none !important;
        font-size: 0.9rem !important;
        display: flex !important;
        align-items: center !important;
        gap: 8px !important;
        padding: 0.25rem 0.5rem !important;
        border-radius: 6px !important;
        transition: all 0.15s ease !important;
    }

    [data-testid="stSidebar"] .stPageLink a:hover {
        background-color: rgba(187, 187, 221, 0.08) !important;
        color: #ffffff !important;
    }

    /* Hide the default Streamlit page navigation (top of sidebar) */
    [data-testid="stSidebarNav"] {
        display: none !important;
    }
    </style>
    """, unsafe_allow_html=True)

def render_sidebar():
    """Render the full sidebar with Pages, Backup, and Xquik navigation."""
    with st.sidebar:
        # --- Pages Navigation ---
        st.subheader("Pages")
        st.page_link("app.py", label=":material/home: Dashboard")
        st.page_link("pages/Drafts.py", label=":material/newspaper: Drafts & Queue")
        st.page_link("pages/Live_Check.py", label=":material/search: Live Check")
        st.page_link("pages/Performance.py", label=":material/bar_chart: Performance")
        st.page_link("pages/Source_Health.py", label=":material/satellite_alt: Source Health")
        st.page_link("pages/Rule_Manager.py", label=":material/rule: Rule Manager")
        st.page_link("pages/Backup_Browser.py", label=":material/folder_open: Backup Browser")
        st.page_link("pages/Database_Stats.py", label=":material/database: Database Stats")

        st.divider()

        # --- Backup Section ---
        st.header("Load Backup")

        if st.button("Load latest backup from Dropbox"):
            st.cache_resource.clear()
            try:
                engine = load_latest_backup_engine()
                if engine:
                    st.session_state.backup_loaded = True
                    st.session_state.db_engine = engine
                    st.success(":material/check_circle: Backup loaded – analytics pages are active.")
                else:
                    st.error(":material/error: Failed to load backup – the file may be corrupted or missing.")
            except ConnectionError:
                st.error(":material/wifi_off: Could not connect to Dropbox. Please check your internet connection and try again.")
            except Timeout:
                st.error(":material/timer_off: Dropbox is taking too long. Check your connection and try again.")
            except dropbox.exceptions.AuthError:
                st.error(":material/key_off: Dropbox token is invalid or expired. Please update it in your .env file.")
            except Exception as e:
                st.error(f":material/error: Something went wrong: {e}")

        # Auto-load on startup
        if "backup_loaded" not in st.session_state:
            try:
                engine = load_latest_backup_engine()
                if engine:
                    st.session_state.backup_loaded = True
                    st.session_state.db_engine = engine
                else:
                    st.session_state.backup_loaded = False
            except ConnectionError:
                st.error(":material/wifi_off: Could not reach Dropbox – please check your internet.")
                st.session_state.backup_loaded = False
            except Timeout:
                st.error(":material/timer_off: Dropbox request timed out – try again later.")
                st.session_state.backup_loaded = False
            except dropbox.exceptions.AuthError:
                st.error(":material/key_off: Dropbox token is invalid or expired. Update it in .env.")
                st.session_state.backup_loaded = False
            except Exception:
                st.error(":material/error: Could not load backup automatically. Use the button above.")
                st.session_state.backup_loaded = False

        if st.session_state.get("backup_loaded"):
            if not st.session_state.get("_backup_msg_shown"):
                st.success(":material/check_circle: Backup loaded – analytics pages are active.")
                st.session_state._backup_msg_shown = True
        else:
            st.info(":material/folder_open: Load a backup to view analytics.")

        st.divider()

        # --- Logout ---
        if st.session_state.get("authenticated"):
            if st.button("Log out"):
                st.session_state.authenticated = False
                st.experimental_set_query_params()   # clear token from URL
                st.rerun()

def require_auth():
    """Block access until the user enters the correct password. Uses a URL token
    to persist authentication across full page refreshes."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    # 1. If already authenticated in this session, skip everything
    if st.session_state.authenticated:
        return

    try:
        PASSWORD = st.secrets["PASSWORD"]
    except KeyError:
        st.error("No PASSWORD secret set. Contact admin.")
        st.stop()

    # 2. Generate the expected token (SHA‑256 of password)
    expected_token = hashlib.sha256(PASSWORD.encode()).hexdigest()

    # 3. Check if a valid token is already in the URL
    query_params = st.experimental_get_query_params()
    token_from_url = query_params.get("auth_token", [None])[0]

    if token_from_url == expected_token:
        # Token is valid → authenticate without showing login
        st.session_state.authenticated = True
        # Clean up the URL (optional – remove token to hide it)
        st.experimental_set_query_params()
        st.rerun()

    # 4. Show login form (no token, or token invalid)
    st.title("Dashboard Access")
    pwd = st.text_input("Enter password", type="password")

    if st.button("Log in"):
        if pwd == PASSWORD:
            st.session_state.authenticated = True
            # Put the token into the URL so it survives a refresh
            st.experimental_set_query_params(auth_token=expected_token)
            st.rerun()
        else:
            st.error("Incorrect password")
    st.stop()