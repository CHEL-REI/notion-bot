"""パスワード認証（admin/chatbot別）"""

import streamlit as st


def check_auth(role: str) -> bool:
    """指定ロールの認証状態を確認。未認証ならログインフォームを表示しFalseを返す。"""
    session_key = f"authenticated_{role}"

    if st.session_state.get(session_key):
        return True

    secret_key = "ADMIN_PASSWORD" if role == "admin" else "CHATBOT_PASSWORD"
    try:
        correct_password = st.secrets[secret_key]
    except (KeyError, FileNotFoundError):
        st.error(f"`{secret_key}` が secrets.toml に設定されていません。")
        return False

    label = "管理者" if role == "admin" else "チャットボット"
    st.subheader(f"{label} ログイン")

    with st.form(f"login_form_{role}"):
        password = st.text_input("パスワード", type="password")
        submitted = st.form_submit_button("ログイン")

    if submitted:
        if password == correct_password:
            st.session_state[session_key] = True
            st.rerun()
        else:
            st.error("パスワードが正しくありません。")

    return False
