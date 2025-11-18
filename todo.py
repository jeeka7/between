import streamlit as st
import sys

st.set_page_config(layout="wide")
st.title("App Import Test")
st.write(f"Running on Python version: {sys.version}")

try:
    import streamlit as st
    st.success("1. Streamlit: OK")
except Exception as e:
    st.error("FAILED on Streamlit import.")
    st.exception(e)

try:
    from libsql_client import create_client_sync
    st.success("2. LibSQL Client: OK")
except Exception as e:
    st.error("FAILED on LibSQL Client import.")
    st.exception(e)

try:
    import pandas as pd
    st.success("3. Pandas: OK")
except Exception as e:
    st.error("FAILED on Pandas import.")
    st.exception(e)

try:
    from weasyprint import HTML
    st.success("4. WeasyPrint: OK")
except Exception as e:
    st.error("FAILED on WeasyPrint import.")
    st.exception(e)

try:
    import streamlit_authenticator as stauth
    st.success("5. Streamlit Authenticator: OK")
except Exception as e:
    st.error("FAILED on Streamlit Authenticator import.")
    st.exception(e)

st.info("Test complete. The error is with the last 'FAILED' item above.")
