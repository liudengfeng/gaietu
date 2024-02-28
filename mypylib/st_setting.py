# 所有配置

import os
import streamlit as st


def general_config():
    # LangSmith
    if "LANGCHAIN_TRACING_V2" not in os.environ:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
    if "LANGCHAIN_API_KEY" not in os.environ:
        os.environ["LANGCHAIN_API_KEY"] = st.secrets["LANGCHAIN_API_KEY"]
    if "TAVILY_API_KEY" not in os.environ:
        os.environ["TAVILY_API_KEY"] = st.secrets["TAVILY_API_KEY"]
    if "SERPAPI_API_KEY" not in os.environ:
        os.environ["SERPAPI_API_KEY"] = st.secrets["SERPAPI_API_KEY"]
    if "LANGCHAIN_PROJECT" not in os.environ:
        os.environ["LANGCHAIN_PROJECT"] = "ReWOO"
