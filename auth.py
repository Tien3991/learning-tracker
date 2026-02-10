import hmac
import os
import streamlit as st


def _get_password() -> str | None:
    """Read password from st.secrets or environment variable."""
    try:
        return st.secrets["TRACKER_PASSWORD"]
    except (KeyError, FileNotFoundError):
        return os.environ.get("TRACKER_PASSWORD")


def check_auth() -> bool:
    """Show password gate. Returns True if authenticated or no password configured."""
    password = _get_password()
    if not password:
        return True

    if st.session_state.get("authenticated"):
        return True

    st.title("Learning Tracker")
    entered = st.text_input("Password", type="password", key="auth_password_input")
    if st.button("Login", key="auth_login_btn"):
        if hmac.compare_digest(entered, password):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    return False
