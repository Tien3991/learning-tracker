import hashlib
import hmac
import os
import time

import streamlit as st
from streamlit_cookies_controller import CookieController

_COOKIE_NAME = "tracker_auth"
_COOKIE_MAX_AGE = 30 * 24 * 60 * 60  # 30 days


def _get_password() -> str | None:
    """Read password from st.secrets or environment variable."""
    try:
        return st.secrets["TRACKER_PASSWORD"]
    except (KeyError, FileNotFoundError):
        return os.environ.get("TRACKER_PASSWORD")


def _get_cookie_secret() -> str | None:
    """Read cookie secret from st.secrets or environment variable."""
    try:
        return st.secrets["COOKIE_SECRET"]
    except (KeyError, FileNotFoundError):
        return os.environ.get("COOKIE_SECRET")


def _make_auth_token(password: str) -> str:
    """Create HMAC-SHA256 token from the password and cookie secret."""
    secret = _get_cookie_secret()
    if not secret:
        return ""
    return hmac.new(
        secret.encode(), password.encode(), hashlib.sha256
    ).hexdigest()


def _verify_auth_token(token: str) -> bool:
    """Timing-safe comparison of the token against the expected value."""
    password = _get_password()
    if not password:
        return False
    expected = _make_auth_token(password)
    if not expected:
        return False
    return hmac.compare_digest(token, expected)


def check_auth() -> bool:
    """Show password gate. Returns True if authenticated or no password configured."""
    password = _get_password()
    if not password:
        return True

    # Fast path: already authenticated in this session
    if st.session_state.get("authenticated"):
        return True

    # Hide the invisible iframe rendered by CookieController
    st.markdown(
        "<style>iframe[title='streamlit_cookies_controller.cookie_controller']"
        "{display:none}</style>",
        unsafe_allow_html=True,
    )
    controller = CookieController()

    # Check cookie for persistent auth
    token = controller.get(_COOKIE_NAME)
    if token and _verify_auth_token(token):
        st.session_state["authenticated"] = True
        return True

    # Show login form
    st.title("Learning Tracker")
    entered = st.text_input("Password", type="password", key="auth_password_input")
    if st.button("Login", key="auth_login_btn"):
        if hmac.compare_digest(entered, password):
            st.session_state["authenticated"] = True
            # Persist auth via cookie
            cookie_secret = _get_cookie_secret()
            if cookie_secret:
                controller.set(
                    _COOKIE_NAME,
                    _make_auth_token(password),
                    path="/",
                    same_site="lax",
                    max_age=_COOKIE_MAX_AGE,
                )
                time.sleep(0.5)
            st.rerun()
        else:
            st.error("Incorrect password.")
    return False
