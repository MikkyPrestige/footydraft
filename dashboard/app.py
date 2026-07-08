"""FootyDraft – Streamlit Dashboard (multi‑page)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import streamlit as st
import os
os.makedirs("/tmp/data", exist_ok=True)
from dashboard.ui_components import apply_global_styles, render_sidebar, require_auth

st.set_page_config(
    page_title="FootyDraft Dashboard",
    layout="wide",
    page_icon="dashboard/static/favicon.ico"
)

# Inject global styles, render sidebar and authentication check
apply_global_styles()
render_sidebar()
require_auth()

# --- Main Home Page Content ---
st.markdown('<div class="dashboard-title">FootyDraft Dashboard</div>', unsafe_allow_html=True)

# Status badge
if st.session_state.get("backup_loaded"):
    st.markdown(
        '<div class="status-badge loaded">'
        '<span class="material-symbols-outlined">check_circle</span> Backup loaded – analytics pages are ready.'
        '</div>',
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        '<div class="status-badge not-loaded">'
        '<span class="material-symbols-outlined">error</span> No backup loaded – use the sidebar to load one.'
        '</div>',
        unsafe_allow_html=True,
    )

# Quick‑action cards
st.subheader("Quick Actions")

cards = [
    ("bar_chart", "Performance", "Engagement charts, persona breakdown, top tweets", "Performance"),
    ("satellite_alt", "Source Health", "Status of all news feeds", "Source_Health"),
    ("rule", "Rule Manager", "View, accept, and add style rules", "Rule_Manager"),
    ("folder_open", "Backup Browser", "Browse, download, and load backups", "Backup_Browser"),
    ("newspaper", "Drafts & Queue", "View and manage generated drafts", "Drafts"),
    ("search", "Live Check", "Fetch live match events instantly", "Live_Check"),
]

# Build the card grid HTML
cards_html = '<div class="card-grid">'
for icon, title, desc, page in cards:
    cards_html += (
        f'<a href="{page}" target="_self" class="quick-card">'
        f'<div>'
        f'<div class="card-icon"><span class="material-symbols-outlined">{icon}</span></div>'
        f'<h3>{title}</h3>'
        f'<p>{desc}</p>'
        f'</div>'
        f'</a>'
    )
cards_html += '</div>'

st.markdown(cards_html, unsafe_allow_html=True)

# Footer
if st.session_state.get("backup_loaded"):
    st.divider()
    st.caption("Backup loaded – use the sidebar to reload a fresh snapshot.")