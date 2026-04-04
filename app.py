"""
app.py — Streamlit UI for JobMatch AI
---------------------------------------
This is the frontend. It:
  - Shows a text input for recruiter commands
  - Calls run_agent() from agent.py
  - Displays the result in a clean chat-style layout
  - Shows quick example buttons so the reviewer can demo easily
"""

import streamlit as st
from agent import run_agent

# ─────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="JobMatch AI",
    page_icon="🤖",
    layout="centered"
)

# ─────────────────────────────────────────────
# Custom CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Syne:wght@600;700&family=DM+Sans:wght@300;400;500&display=swap');

    html, body, [class*="css"] {
        font-family: 'DM Sans', sans-serif;
        background: #0f0f14;
        color: #e8e8f0;
    }

    .header-box {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 60%, #0f3460 100%);
        border: 1px solid #2a2a4a;
        border-radius: 16px;
        padding: 2rem 2.5rem;
        margin-bottom: 2rem;
        text-align: center;
    }

    .header-box h1 {
        font-family: 'Syne', sans-serif;
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(90deg, #7eb8f7, #a78bfa);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0 0 0.4rem 0;
    }

    .header-box p {
        color: #8888aa;
        font-size: 0.95rem;
        margin: 0;
    }

    .tag {
        display: inline-block;
        background: #1e1e3a;
        border: 1px solid #3a3a6a;
        color: #a78bfa;
        font-size: 0.75rem;
        padding: 2px 10px;
        border-radius: 20px;
        margin: 0.3rem 0.2rem;
    }

    .section-label {
        font-family: 'Syne', sans-serif;
        font-size: 0.8rem;
        letter-spacing: 0.1em;
        color: #7eb8f7;
        text-transform: uppercase;
        margin-bottom: 0.5rem;
    }

    .result-box {
        background: #13131f;
        border: 1px solid #2a2a4a;
        border-left: 4px solid #7eb8f7;
        border-radius: 12px;
        padding: 1.5rem;
        margin-top: 1.5rem;
        white-space: pre-wrap;
        font-size: 0.9rem;
        line-height: 1.7;
        color: #d0d0e8;
    }

    .stTextArea textarea {
        background: #13131f !important;
        border: 1px solid #2a2a4a !important;
        border-radius: 10px !important;
        color: #e8e8f0 !important;
        font-family: 'DM Sans', sans-serif !important;
        font-size: 0.95rem !important;
    }

    .stButton > button {
        background: linear-gradient(135deg, #1e3a6e, #2d1b69);
        color: #c0d8ff;
        border: 1px solid #3a5a9e;
        border-radius: 8px;
        padding: 0.4rem 1rem;
        font-family: 'DM Sans', sans-serif;
        font-size: 0.85rem;
        transition: all 0.2s;
    }

    .stButton > button:hover {
        background: linear-gradient(135deg, #2a4a8e, #3d2b89);
        border-color: #6a8ace;
        color: #ffffff;
    }

    .run-btn > button {
        background: linear-gradient(135deg, #1a56a0, #7c3aed) !important;
        color: white !important;
        border: none !important;
        font-weight: 500 !important;
        width: 100%;
        padding: 0.6rem !important;
        font-size: 1rem !important;
        border-radius: 10px !important;
    }

    .history-item {
        background: #13131f;
        border: 1px solid #1e1e3a;
        border-radius: 8px;
        padding: 0.8rem 1rem;
        margin-bottom: 0.5rem;
        font-size: 0.85rem;
        color: #8888aa;
    }

    .history-item strong {
        color: #c0c0e0;
    }

    #MainMenu, footer, header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────
st.markdown("""
<div class="header-box">
    <h1>🤖 JobMatch AI</h1>
    <p>Resume Screening Agent — powered by LangGraph + Groq (LLaMA 3.1)</p>
    <br/>
    <span class="tag">ReAct Agent</span>
    <span class="tag">Web Search</span>
    <span class="tag">LLM Scoring</span>
    <span class="tag">SQLite DB</span>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# Session state init
# ─────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []

# FIX: Use a single key for the text area value,
# separate from the widget key to allow programmatic updates.
if "command_text" not in st.session_state:
    st.session_state.command_text = ""


# ─────────────────────────────────────────────
# Example command buttons
# ─────────────────────────────────────────────
st.markdown('<div class="section-label">⚡ Quick Examples</div>', unsafe_allow_html=True)

examples = [
    "Score Rahul Sharma for our Python backend role and save results.",
    "Evaluate Priya Mehta for our Python backend role and save. She knows FastAPI and PostgreSQL.",
    "Show all evaluated candidates.",
    "Who are the top 3 candidates?",
    "Show me Rahul Sharma's record.",
    "Remove Rahul Sharma from the database.",
]

col1, col2 = st.columns(2)
for i, ex in enumerate(examples):
    col = col1 if i % 2 == 0 else col2
    short_label = ex[:50] + "..." if len(ex) > 50 else ex
    # FIX: clicking a button sets command_text and triggers rerun
    if col.button(f"📋 {short_label}", key=f"ex_{i}"):
        st.session_state.command_text = ex
        st.rerun()


# ─────────────────────────────────────────────
# Main input area
# ─────────────────────────────────────────────
st.markdown('<div class="section-label" style="margin-top:1.5rem">✍️ Your Command</div>',
            unsafe_allow_html=True)

# FIX: Do NOT use `key=` on text_area when controlling value via session state.
# Instead read the returned value directly. Use `value=` to set default.
user_input = st.text_area(
    label="Command",
    label_visibility="collapsed",
    value=st.session_state.command_text,
    height=100,
    placeholder='e.g. "Score John Doe for our ML engineer role, search GitHub, save results."',
)

st.markdown('<div class="run-btn">', unsafe_allow_html=True)
run_clicked = st.button("🚀 Run Agent", key="run_btn")
st.markdown('</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────
# Run the agent
# ─────────────────────────────────────────────
if run_clicked:
    if user_input.strip():
        with st.spinner("🧠 Agent is thinking... (Thought → Action → Observation)"):
            try:
                result = run_agent(user_input.strip())
            except Exception as e:
                result = (
                    f"❌ Error: {str(e)}\n\n"
                    "Check your GROQ_API_KEY and TAVILY_API_KEY in the .env file."
                )

        st.session_state.history.insert(0, {
            "command": user_input.strip(),
            "result": result
        })
        # FIX: Clear the text box after successful run
        st.session_state.command_text = ""
        st.rerun()
    else:
        st.warning("Please type a command first.")


# ─────────────────────────────────────────────
# Show results
# ─────────────────────────────────────────────
if st.session_state.history:
    latest = st.session_state.history[0]

    st.markdown(
        '<div class="section-label" style="margin-top:2rem">📊 Agent Response</div>',
        unsafe_allow_html=True
    )
    st.markdown(
        f'<div class="result-box">{latest["result"]}</div>',
        unsafe_allow_html=True
    )

    if len(st.session_state.history) > 1:
        st.markdown(
            '<div class="section-label" style="margin-top:2rem">🕓 Previous Commands</div>',
            unsafe_allow_html=True
        )
        for item in st.session_state.history[1:]:
            preview = item["result"][:120].replace("<", "&lt;").replace(">", "&gt;")
            st.markdown(f"""
            <div class="history-item">
                <strong>Command:</strong> {item['command']}<br/>
                <strong>Result preview:</strong> {preview}...
            </div>
            """, unsafe_allow_html=True)

    if st.button("🗑️ Clear History"):
        st.session_state.history = []
        st.session_state.command_text = ""
        st.rerun()
