"""Notion チャットボット - エントリポイント"""

import streamlit as st

st.set_page_config(
    page_title="Notion チャットボット",
    page_icon="📚",
    layout="wide",
)

chatbot_page = st.Page("pages/chatbot.py", title="チャットボット", icon="💬", default=True)
admin_page = st.Page("pages/admin.py", title="管理者", icon="⚙️")

nav = st.navigation([chatbot_page, admin_page])
nav.run()
