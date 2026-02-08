"""Streamlit チャットUI"""

import re
from pathlib import Path

import httpx
import streamlit as st

# APIのベースURL
API_BASE_URL = "http://localhost:8000"


def display_image(img_path: str):
    """画像を表示"""
    local_path = Path(img_path)
    if local_path.exists():
        st.image(str(local_path), use_container_width=True)
    else:
        # APIから取得を試みる
        filename = local_path.name
        st.image(f"{API_BASE_URL}/images/{filename}", use_container_width=True)


def extract_images_from_answer(answer: str) -> tuple[str, list[str]]:
    """回答から [IMAGE: パス] 形式の画像参照を抽出"""
    pattern = r'\[IMAGE:\s*([^\]]+)\]'
    image_paths = re.findall(pattern, answer)
    clean_answer = re.sub(pattern, '', answer).strip()
    return clean_answer, image_paths


def extract_page_id_from_url(url: str) -> str:
    """NotionのURLからページIDを抽出"""
    # https://www.notion.so/PageName-xxxxx or https://notion.so/xxxxx
    url = url.strip().rstrip("/")
    # 最後の部分を取得
    last_part = url.split("/")[-1]
    # ハイフンで分割して最後の32文字がIDの場合
    if "-" in last_part:
        potential_id = last_part.split("-")[-1]
        if len(potential_id) == 32:
            return potential_id
    # 32文字のIDの場合
    if len(last_part) == 32:
        return last_part
    return url


# ページ設定
st.set_page_config(
    page_title="Notion チャットボット",
    page_icon="📚",
    layout="wide",
)

st.title("📚 Notion チャットボット")
st.caption("社内ドキュメント（Notion）に基づいて質問に答えます")

# サイドバー
with st.sidebar:
    # 設定セクション
    st.header("🔑 API設定")

    # 現在の設定を取得
    current_settings = None
    try:
        response = httpx.get(f"{API_BASE_URL}/settings", timeout=5.0)
        if response.status_code == 200:
            current_settings = response.json()
    except Exception:
        pass

    with st.expander("API設定を編集", expanded=not (current_settings and current_settings.get("notion_token_set") and current_settings.get("openai_api_key_set"))):
        # Notion Token
        notion_token_status = "✅ 設定済み" if current_settings and current_settings.get("notion_token_set") else "❌ 未設定"
        st.caption(f"Notion Token: {notion_token_status}")
        notion_token = st.text_input(
            "Notion Integration Token",
            type="password",
            placeholder="ntn_xxx または secret_xxx",
            help="https://www.notion.so/my-integrations で取得",
        )

        # OpenAI API Key
        openai_status = "✅ 設定済み" if current_settings and current_settings.get("openai_api_key_set") else "❌ 未設定"
        st.caption(f"OpenAI API Key: {openai_status}")
        openai_api_key = st.text_input(
            "OpenAI API Key",
            type="password",
            placeholder="sk-xxx",
            help="https://platform.openai.com/api-keys で取得",
        )

        # Notion Page IDs
        current_page_ids = current_settings.get("notion_page_ids", "") if current_settings else ""
        st.caption("Notion ページURL または ID")
        notion_pages_input = st.text_area(
            "読み込むページ（1行に1つ）",
            value=current_page_ids.replace(",", "\n") if current_page_ids else "",
            placeholder="https://www.notion.so/PageName-xxxxx\nまたは ページID",
            height=100,
            help="NotionページのURLまたはIDを入力。複数ページは改行で区切る",
        )

        # 保存ボタン
        if st.button("💾 設定を保存", use_container_width=True):
            # ページIDを抽出
            page_ids = []
            for line in notion_pages_input.strip().split("\n"):
                line = line.strip()
                if line:
                    page_id = extract_page_id_from_url(line)
                    if page_id:
                        page_ids.append(page_id)

            settings_data = {}
            if notion_token:
                settings_data["notion_token"] = notion_token
            if openai_api_key:
                settings_data["openai_api_key"] = openai_api_key
            settings_data["notion_page_ids"] = ",".join(page_ids)

            try:
                response = httpx.post(
                    f"{API_BASE_URL}/settings",
                    json=settings_data,
                    timeout=10.0,
                )
                if response.status_code == 200:
                    st.success("設定を保存しました")
                    st.rerun()
                else:
                    st.error("設定の保存に失敗しました")
            except Exception as e:
                st.error(f"エラー: {e}")

    st.divider()

    # 同期セクション
    st.header("🔄 データ同期")

    # 同期ボタン
    if st.button("📥 Notionデータを同期", use_container_width=True):
        with st.spinner("同期を開始しています..."):
            try:
                response = httpx.post(f"{API_BASE_URL}/sync", timeout=10.0)
                if response.status_code == 200:
                    st.success("同期を開始しました")
                else:
                    st.error("同期の開始に失敗しました")
            except Exception as e:
                st.error(f"エラー: {e}")

    # 同期ステータス確認
    if st.button("📊 同期ステータスを確認", use_container_width=True):
        try:
            response = httpx.get(f"{API_BASE_URL}/sync/status", timeout=10.0)
            if response.status_code == 200:
                status = response.json()
                st.info(f"ステータス: {status['status']}")
                st.info(f"メッセージ: {status['message']}")
                if status.get("stats"):
                    st.json(status["stats"])
        except Exception as e:
            st.error(f"エラー: {e}")

    st.divider()

    # インデックス統計
    st.subheader("📈 インデックス情報")
    try:
        response = httpx.get(f"{API_BASE_URL}/sync/stats", timeout=10.0)
        if response.status_code == 200:
            stats = response.json()
            st.metric("チャンク数", stats.get("total_chunks", 0))
    except Exception:
        st.warning("API接続に失敗しました")

    st.divider()

    # 会話クリア
    if st.button("🗑️ 会話をクリア", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# チャット履歴の初期化
if "messages" not in st.session_state:
    st.session_state.messages = []

# 設定チェック
if current_settings and not (current_settings.get("notion_token_set") and current_settings.get("openai_api_key_set")):
    st.warning("⚠️ 左側のサイドバーでAPI設定を完了してください")

# 過去のメッセージを表示
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

        # 画像を表示
        if message.get("images"):
            for img_path in message["images"]:
                display_image(img_path)

        # ソースを表示
        if message.get("sources"):
            with st.expander("📄 参照元"):
                for source in message["sources"]:
                    st.markdown(
                        f"- [{source['page_title']}]({source['page_url']}) "
                        f"(スコア: {source['score']:.2f})"
                    )

# チャット入力
if prompt := st.chat_input("質問を入力してください..."):
    # ユーザーメッセージを追加
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    # APIにリクエスト
    with st.chat_message("assistant"):
        with st.spinner("回答を生成中..."):
            try:
                # 会話履歴を構築
                history = [
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.messages[:-1]
                ]

                response = httpx.post(
                    f"{API_BASE_URL}/chat",
                    json={"message": prompt, "history": history},
                    timeout=60.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    answer = data["answer"]
                    sources = data["sources"]
                    image_paths = data["image_paths"]

                    # 回答から画像参照を抽出
                    clean_answer, referenced_images = extract_images_from_answer(answer)

                    # すべての画像パスを統合
                    all_images = list(set(image_paths + referenced_images))

                    st.markdown(clean_answer)

                    # 画像を表示
                    if all_images:
                        st.subheader("📷 関連画像")
                        for img_path in all_images:
                            display_image(img_path)

                    # ソースを表示
                    if sources:
                        with st.expander("📄 参照元"):
                            for source in sources:
                                st.markdown(
                                    f"- [{source['page_title']}]({source['page_url']}) "
                                    f"(スコア: {source['score']:.2f})"
                                )

                    # セッションに保存
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": clean_answer,
                        "images": all_images,
                        "sources": sources,
                    })

                else:
                    st.error(f"APIエラー: {response.status_code}")
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": "申し訳ありませんが、エラーが発生しました。",
                    })

            except httpx.TimeoutException:
                st.error("タイムアウトしました。再度お試しください。")
            except Exception as e:
                st.error(f"エラー: {e}")
