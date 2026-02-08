"""チャットボットページ（エンドユーザー向け）"""

import streamlit as st
from lib.auth import check_auth
from lib.core import (
    get_settings, RAGChain, display_image,
)
from lib.chat_logger import log_chat


st.title("Notion チャットボット")
st.caption("社内ドキュメント（Notion）に基づいて質問に答えます")

if not check_auth("chatbot"):
    st.stop()

# セッション状態の初期化
if "messages" not in st.session_state:
    st.session_state.messages = []

# サイドバー: インデックス情報と会話クリア
with st.sidebar:
    st.subheader("インデックス情報")
    if st.session_state.get("vector_store"):
        stats = st.session_state.vector_store.get_stats()
        st.metric("チャンク数", stats.get("total_chunks", 0))
    else:
        st.info("未同期（管理者ページで同期してください）")

    st.divider()

    if st.button("会話をクリア", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# メインエリア
if not st.session_state.get("synced"):
    st.info("管理者ページでデータを同期してください。")

# 過去のメッセージを表示
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("images"):
            for img_path in message["images"]:
                display_image(img_path)
        if message.get("sources"):
            with st.expander("参照元"):
                for source in message["sources"]:
                    st.markdown(f"- [{source['page_title']}]({source['page_url']}) (スコア: {source['score']:.2f})")

# チャット入力
if prompt := st.chat_input("質問を入力してください...", disabled=not st.session_state.get("synced")):
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("回答を生成中..."):
            try:
                settings = get_settings()
                rag_chain = RAGChain(settings['openai_api_key'], st.session_state.vector_store)
                result = rag_chain.chat(prompt)

                st.markdown(result["answer"])

                if result["image_paths"]:
                    st.subheader("関連画像")
                    for img_path in result["image_paths"]:
                        display_image(img_path)

                if result["sources"]:
                    with st.expander("参照元"):
                        for source in result["sources"]:
                            st.markdown(f"- [{source['page_title']}]({source['page_url']}) (スコア: {source['score']:.2f})")

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": result["answer"],
                    "images": result["image_paths"],
                    "sources": result["sources"],
                })

                log_chat(prompt, result["answer"], result["sources"])
            except Exception as e:
                st.error(f"エラー: {e}")
