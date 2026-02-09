"""管理者ページ（同期・設定・ログ閲覧）"""

import streamlit as st
from lib.auth import check_auth
from lib.core import (
    get_settings, VectorStore, run_sync,
    save_page_ids, load_page_ids,
    save_notion_token, load_notion_token,
)
from lib.chat_logger import read_logs, get_log_stats


st.title("管理者ページ")

if not check_auth("admin"):
    st.stop()

tab_sync, tab_settings, tab_logs = st.tabs(["データ同期", "Notion設定", "チャットログ"])

# ==================== データ同期タブ ====================
with tab_sync:
    st.subheader("Notion データ同期")

    settings = get_settings()
    can_sync = settings.get('notion_token') and settings.get('openai_api_key') and settings.get('notion_page_ids')

    if st.button("Notionデータを同期", use_container_width=True, disabled=not can_sync):
        with st.spinner("同期中..."):
            try:
                st.session_state.vector_store = run_sync(settings)
                st.session_state.synced = True
            except Exception as e:
                st.error(f"同期エラー: {e}")

    if not can_sync:
        st.warning("API設定を完了してください")

    st.divider()
    st.subheader("インデックス統計")
    if st.session_state.get("vector_store"):
        stats = st.session_state.vector_store.get_stats()
        st.metric("チャンク数", stats.get("total_chunks", 0))
    else:
        st.info("未同期")

# ==================== API設定タブ ====================
with tab_settings:
    st.subheader("Notion設定")
    st.caption("ここでの変更はアプリ再起動後も保持されます。")

    current_token = load_notion_token() or get_settings().get('notion_token', '')
    notion_token = st.text_input(
        "Notion Integration Token",
        type="password",
        value=current_token,
        placeholder="ntn_xxx または secret_xxx",
        help="https://www.notion.so/my-integrations で取得",
        key="notion_token_input",
    )

    st.divider()
    st.subheader("Notionページ設定")

    current_page_ids = load_page_ids() or get_settings().get('notion_page_ids', '')
    notion_pages_input = st.text_area(
        "読み込むNotionページ（1行に1つ）",
        value=current_page_ids,
        placeholder="https://www.notion.so/PageName-xxxxx",
        height=100,
        key="notion_page_ids_input",
    )
    if st.button("Notion設定を保存", use_container_width=True):
        save_notion_token(notion_token)
        save_page_ids(notion_pages_input)
        st.success("Notion Token・ページ設定を保存しました。")


# ==================== チャットログタブ ====================
with tab_logs:
    st.subheader("チャットログ")

    log_stats = get_log_stats()
    col1, col2, col3 = st.columns(3)
    col1.metric("総数", log_stats["total"])
    col2.metric("最古", log_stats["oldest"][:10] if log_stats["oldest"] else "-")
    col3.metric("最新", log_stats["newest"][:10] if log_stats["newest"] else "-")

    st.divider()

    logs = read_logs()
    if logs:
        for entry in reversed(logs):
            with st.expander(f"{entry.get('timestamp', '?')[:19]}  {entry.get('question', '')[:60]}"):
                st.markdown(f"**質問:** {entry.get('question', '')}")
                st.markdown(f"**回答:** {entry.get('answer', '')}")
                if entry.get("sources"):
                    st.markdown(f"**参照元:** {', '.join(entry['sources'])}")
    else:
        st.info("ログはまだありません。")
