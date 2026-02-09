"""管理者ページ（同期・設定・ログ閲覧）"""

import streamlit as st
from lib.auth import check_auth
from lib.core import (
    get_settings, extract_page_id_from_url,
    NotionLoader, ImageProcessor, Chunker, VectorStore,
    save_page_ids, load_page_ids,
)
from lib.chat_logger import read_logs, get_log_stats


st.title("管理者ページ")

if not check_auth("admin"):
    st.stop()

tab_sync, tab_settings, tab_logs = st.tabs(["データ同期", "API設定", "チャットログ"])

# ==================== データ同期タブ ====================
with tab_sync:
    st.subheader("Notion データ同期")

    settings = get_settings()
    can_sync = settings.get('notion_token') and settings.get('openai_api_key') and settings.get('notion_page_ids')

    if st.button("Notionデータを同期", use_container_width=True, disabled=not can_sync):
        with st.spinner("同期中..."):
            try:
                page_ids = []
                for line in settings['notion_page_ids'].strip().split("\n"):
                    line = line.strip()
                    if line:
                        page_id = extract_page_id_from_url(line)
                        if page_id:
                            page_ids.append(page_id)

                if not page_ids:
                    page_ids = [p.strip() for p in settings['notion_page_ids'].split(",") if p.strip()]

                loader = NotionLoader(settings['notion_token'], page_ids)
                pages = loader.load_all_pages()
                st.info(f"{len(pages)}ページを取得")

                image_processor = ImageProcessor(settings['openai_api_key'])
                for page in pages:
                    for image in page.images:
                        image_processor.process_image(image)

                chunker = Chunker()
                all_chunks = []
                for page in pages:
                    chunks = chunker.chunk_page(page)
                    all_chunks.extend(chunks)

                vector_store = VectorStore(settings['openai_api_key'])
                vector_store.clear()
                vector_store.add_chunks(all_chunks)
                st.session_state.vector_store = vector_store
                st.session_state.synced = True

                st.success(f"同期完了: {len(all_chunks)}チャンク")
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
    st.subheader("API設定（一時変更）")
    st.caption("ここでの変更はセッション中のみ有効です。永続化するには secrets.toml を編集してください。")

    try:
        has_secrets = st.secrets.get('NOTION_TOKEN') and st.secrets.get('OPENAI_API_KEY')
    except Exception:
        has_secrets = False

    notion_token = st.text_input(
        "Notion Integration Token",
        type="password",
        value=st.session_state.get('notion_token', ''),
        placeholder="ntn_xxx または secret_xxx",
        help="https://www.notion.so/my-integrations で取得",
    )
    if notion_token:
        st.session_state.notion_token = notion_token

    openai_api_key = st.text_input(
        "OpenAI API Key",
        type="password",
        value=st.session_state.get('openai_api_key', ''),
        placeholder="sk-xxx",
        help="https://platform.openai.com/api-keys で取得",
    )
    if openai_api_key:
        st.session_state.openai_api_key = openai_api_key

    st.divider()
    st.subheader("Notionページ設定")
    st.caption("ここでの変更はアプリ再起動後も保持されます。")

    current_page_ids = load_page_ids() or get_settings().get('notion_page_ids', '')
    notion_pages_input = st.text_area(
        "読み込むNotionページ（1行に1つ）",
        value=current_page_ids,
        placeholder="https://www.notion.so/PageName-xxxxx",
        height=100,
        key="notion_page_ids_input",
    )
    if st.button("ページ設定を保存", use_container_width=True):
        save_page_ids(notion_pages_input)
        st.success("ページ設定を保存しました。")

    if has_secrets:
        st.success("secrets.toml からAPI設定が読み込まれています。")

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
