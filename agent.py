# """
# agent.py — The brain of JobMatch AI
# ------------------------------------
# This file has 3 things:
#   1. Three tools  → web_search, db_tool, jd_scorer
#   2. The system prompt → tells the LLM how to think and which tool to use when
#   3. The LangGraph ReAct agent → the loop that runs Thought → Action → Observation
# """

# import os
# import sqlite3
# import json
# from datetime import datetime

# from dotenv import load_dotenv
# from langchain_groq import ChatGroq
# from langchain_core.tools import tool
# from langchain_community.tools.tavily_search import TavilySearchResults
# from langchain.agents import create_agent

# # ─────────────────────────────────────────────
# # 0.  Load environment variables & init LLM
# # ─────────────────────────────────────────────
# load_dotenv()

# groq_api_key   = os.getenv("GROQ_API_KEY")
# tavily_api_key = os.getenv("TAVILY_API_KEY")   # free at app.tavily.com

# # The LLM that powers the agent's reasoning
# llm = ChatGroq(
#     model="llama-3.3-70b-versatile",
#     api_key=groq_api_key
# )

# # SQLite DB file — created automatically on first run
# DB_FILE = "candidates.db"


# # ─────────────────────────────────────────────
# # 1.  Database helper  (called inside db_tool)
# # ─────────────────────────────────────────────
# def init_db():
#     """Create the candidates table if it doesn't exist yet."""
#     conn = sqlite3.connect(DB_FILE)
#     conn.execute("""
#         CREATE TABLE IF NOT EXISTS candidates (
#             id        INTEGER PRIMARY KEY AUTOINCREMENT,
#             name      TEXT UNIQUE,
#             score     INTEGER,
#             strengths TEXT,
#             gaps      TEXT,
#             web_url   TEXT,
#             decision  TEXT,
#             timestamp TEXT
#         )
#     """)
#     conn.commit()
#     conn.close()


# init_db()   # run once when the module loads


# # ─────────────────────────────────────────────
# # 2.  TOOL 1 — web_search
# # ─────────────────────────────────────────────
# @tool
# def candidate_search(query: str) -> str:
#     """
#     Search the web for a candidate's LinkedIn, GitHub, or portfolio.

#     Use this FIRST whenever you need to find background info about a candidate.
#     Pass a query like: "John Doe Python developer GitHub LinkedIn"
#     Returns a short summary of what was found.
#     """
#     # TavilySearchResults is a wrapper around the Tavily search API
#     # max_results=3 keeps things short and fast
#     searcher = TavilySearchResults(max_results=3, tavily_api_key=tavily_api_key)
#     results  = searcher.invoke(query)

#     if not results:
#         return "No online profile found for this candidate."

#     # Format the top results into a readable string for the agent
#     summary = ""
#     for r in results:
#         summary += f"URL: {r.get('url', '')}\nSnippet: {r.get('content', '')}\n\n"

#     return summary.strip()


# # ─────────────────────────────────────────────
# # 3.  TOOL 2 — db_tool
# # ─────────────────────────────────────────────
# @tool
# def db_tool(
#     action: str,
#     name: str = "",
#     score: int = 0,
#     strengths: str = "",
#     gaps: str = "",
#     web_url: str = "",
#     decision: str = "",
#     limit: int = 3
# ) -> str:
#     """
#     Save or retrieve candidate data from the SQLite database.

#     action must be one of:
#       INSERT  — save a new candidate record
#       SELECT  — get one candidate's full record by name
#       LIST    — show all candidates with their scores
#       TOP     — show top N candidates ranked by score (uses limit param)
#       DELETE  — remove a candidate by name

#     Always INSERT first, then SELECT to confirm the save worked.

#     IMPORTANT: score must be a plain integer (e.g. 85), never a string (e.g. "85").
#     limit must also be a plain integer (e.g. 3).
#     """
#     # Coerce score and limit to int defensively — LLMs sometimes pass strings
#     try:
#         score = int(score)
#     except (ValueError, TypeError):
#         score = 0
#     try:
#         limit = int(limit)
#     except (ValueError, TypeError):
#         limit = 3

#     conn = sqlite3.connect(DB_FILE)

#     # ── INSERT ──────────────────────────────────
#     if action == "INSERT":
#         try:
#             conn.execute(
#                 """
#                 INSERT OR REPLACE INTO candidates
#                 (name, score, strengths, gaps, web_url, decision, timestamp)
#                 VALUES (?, ?, ?, ?, ?, ?, ?)
#                 """,
#                 (name, score, strengths, gaps, web_url, decision,
#                  datetime.now().strftime("%Y-%m-%d %H:%M"))
#             )
#             conn.commit()
#             return f"✅ Saved: {name} | Score: {score}/100 | Decision: {decision}"
#         except Exception as e:
#             return f"❌ DB insert error: {e}"

#     # ── SELECT ──────────────────────────────────
#     elif action == "SELECT":
#         row = conn.execute(
#             "SELECT * FROM candidates WHERE name=?", (name,)
#         ).fetchone()
#         if row:
#             return (
#                 f"Name: {row[1]} | Score: {row[2]}/100\n"
#                 f"Strengths: {row[3]}\nGaps: {row[4]}\n"
#                 f"Profile: {row[5]}\nDecision: {row[6]}\nDate: {row[7]}"
#             )
#         return f"No record found for '{name}'."

#     # ── LIST ─────────────────────────────────────
#     elif action == "LIST":
#         rows = conn.execute(
#             "SELECT name, score, decision, timestamp FROM candidates ORDER BY score DESC"
#         ).fetchall()
#         if not rows:
#             return "No candidates in the database yet."
#         return "\n".join(
#             [f"{r[0]} | {r[1]}/100 | {r[2]} | {r[3]}" for r in rows]
#         )

#     # ── TOP ──────────────────────────────────────
#     elif action == "TOP":
#         rows = conn.execute(
#             "SELECT name, score, decision FROM candidates ORDER BY score DESC LIMIT ?",
#             (limit,)
#         ).fetchall()
#         if not rows:
#             return "No candidates in the database yet."
#         return "\n".join(
#             [f"#{i+1} {r[0]} — {r[1]}/100 — {r[2]}" for i, r in enumerate(rows)]
#         )

#     # ── DELETE ───────────────────────────────────
#     elif action == "DELETE":
#         affected = conn.execute(
#             "DELETE FROM candidates WHERE name=?", (name,)
#         ).rowcount
#         conn.commit()
#         if affected:
#             return f"🗑️ Deleted record for '{name}'."
#         return f"No record found for '{name}'."

#     else:
#         return f"Unknown action '{action}'. Use INSERT, SELECT, LIST, TOP, or DELETE."


# # ─────────────────────────────────────────────
# # 4.  TOOL 3 — jd_scorer
# # ─────────────────────────────────────────────
# @tool
# def jd_scorer(candidate: str, profile: str, jd: str) -> str:
#     """
#     Score a candidate (0–100) against a Job Description using the LLM.

#     Use this AFTER web_search, passing:
#       candidate — the person's name
#       profile   — what you found (skills, experience, GitHub projects, etc.)
#       jd        — the job description or role title

#     Returns a score, 3 strengths, 2 gaps, and a hire/no-hire decision.
#     If no profile info was found, still return a score between 40–55,
#     and set decision to 'Insufficient Info — Request Resume'.
#     """
#     prompt = f"""
# You are a senior technical recruiter. Score this candidate fairly.

# Candidate: {candidate}
# Profile Info: {profile}
# Job Description: {jd}

# Rules:
# - If profile info is empty or very limited → score between 40–55, decision = "Insufficient Info — Request Resume"
# - If candidate is clearly in the wrong field → score below 30, decision = "Reject"
# - Otherwise score honestly 0–100 based on skill and experience match
# - Always list exactly 3 strengths and 2 gaps
# - Decision must be one of: "Strong Hire", "Interview", "Maybe", "Insufficient Info — Request Resume", "Reject"

# Respond ONLY in this JSON format:
# {{
#   "score": <number>,
#   "strengths": ["...", "...", "..."],
#   "gaps": ["...", "..."],
#   "decision": "..."
# }}
# """
#     # Ask the LLM directly (not the agent — just a plain LLM call)
#     response = llm.invoke(prompt)
#     return response.content


# # ─────────────────────────────────────────────
# # 5.  SYSTEM PROMPT  — The agent's instruction manual
# # ─────────────────────────────────────────────
# SYSTEM_PROMPT = """
# You are JobMatch AI, an expert recruitment agent.
# You help recruiters evaluate candidates using a strict Thought → Action → Observation loop.

# === YOUR TOOLS ===

# 1. candidate_search(query)
#    → Use this FIRST to find a candidate's GitHub, LinkedIn, or portfolio.
#    → Query format: "<candidate name> developer GitHub LinkedIn portfolio"

# 2. jd_scorer(candidate, profile, jd)
#    → Use this AFTER web_search to score the candidate against the job description.
#    → Pass the search results as 'profile'.
#    → If nothing was found online, pass profile="No online profile found" — still score them.

# 3. db_tool(action, ...)
#    → After scoring, always do TWO db_tool calls:
#        a) INSERT  — save the candidate's score, strengths, gaps, decision
#        b) SELECT  — confirm the data was saved correctly
#    → For database queries (LIST, TOP, DELETE, SELECT), call db_tool directly.

# === RULES ===

# - Always think before acting. Explain your reasoning in each Thought.
# - Follow the flow: web_search → jd_scorer → db_tool INSERT → db_tool SELECT → FINAL ANSWER
# - NEVER give a candidate a score of 0 just because they have no online presence.
# - Stop after 8 iterations maximum. If you hit the limit, write FINAL ANSWER with what you have.
# - Use any skills the user mentioned in their command when scoring — they take priority over search results.

# === FINAL ANSWER FORMAT ===

# Always end with a clean summary like this:
# ---
# ✅ FINAL ANSWER
# Candidate: <name>
# Score: <X>/100
# Strengths: <list>
# Gaps: <list>
# Decision: <decision>
# Profile URL: <url or "Not found">
# ---
# """


# # ─────────────────────────────────────────────
# # 6.  BUILD THE REACT AGENT
# # ─────────────────────────────────────────────
# # create_react_agent from LangGraph wires everything together:
# #  - It gives the LLM the tools
# #  - It runs the Thought → Action → Observation loop automatically
# #  - It stops when the LLM says it's done or hits max iterations

# tools = [candidate_search, db_tool, jd_scorer]

# agent = create_react_agent(
#     model=llm,
#     tools=tools,
#     prompt=SYSTEM_PROMPT
# )


# # ─────────────────────────────────────────────
# # 7.  RUN FUNCTION — called by app.py (Streamlit)
# # ─────────────────────────────────────────────
# def run_agent(user_input: str) -> str:
#     """
#     Run the agent with a recruiter's command.
#     Returns the agent's final response as a string.
#     """
#     result = agent.invoke({
#         "messages": [{"role": "user", "content": user_input}]
#     })

#     # The agent returns a list of messages — the last one is the final answer
#     final_message = result["messages"][-1]
#     return final_message.content

"""
agent.py — The brain of JobMatch AI
------------------------------------
This file contains:

1. Tools:
   - candidate_search
   - db_tool
   - jd_scorer

2. System Prompt:
   - Instructions that guide agent reasoning

3. Agent:
   - Built using create_agent (NEW API)
"""
"""
agent.py — JobMatch AI Agent

Includes:
1. Web search tool
2. Database tool
3. JD scoring tool
4. Modern create_agent API
"""

import os
import sqlite3
from datetime import datetime

from dotenv import load_dotenv

from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from langchain_tavily import TavilySearch


# ─────────────────────────────────────────────
# Load Environment Variables
# ─────────────────────────────────────────────

load_dotenv()

groq_api_key = os.getenv("GROQ_API_KEY")
tavily_api_key = os.getenv("TAVILY_API_KEY")

DB_FILE = "candidates.db"


# ─────────────────────────────────────────────
# Initialize LLM
# ─────────────────────────────────────────────

llm = ChatGroq(
    model="llama-3.1-8b-instant",
    api_key=groq_api_key,
    temperature=0
)


# ─────────────────────────────────────────────
# Database Initialization
# ─────────────────────────────────────────────

def init_db():
    """Create database table if not exists."""

    conn = sqlite3.connect(DB_FILE)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            score INTEGER,
            strengths TEXT,
            gaps TEXT,
            web_url TEXT,
            decision TEXT,
            timestamp TEXT
        )
    """)

    conn.commit()
    conn.close()


init_db()


# ─────────────────────────────────────────────
# TOOL 1 — candidate_search
# ─────────────────────────────────────────────

@tool
def candidate_search(query: str) -> str:
    """
    Search the web for candidate information.

    Use this tool to find LinkedIn, GitHub,
    or portfolio information.

    Input:
        query — candidate name + role

    Returns:
        Search summary text.
    """

    searcher = TavilySearch(
        max_results=1,
        tavily_api_key=tavily_api_key
    )

    results = searcher.invoke(query)

    if not results:
        return "No online profile found."

    summary = ""

    for r in results:
        if isinstance(r, dict):
            summary += (
                f"URL: {r.get('url','')}\n"
                f"Snippet: {r.get('content','')}\n\n"
            )
        else:
            summary += f"{r}\n\n"

    return summary.strip()


# ─────────────────────────────────────────────
# TOOL 2 — db_tool
# ─────────────────────────────────────────────

@tool
def db_tool(
    action: str,
    name: str = "",
    score: int = 0,
    strengths: str = "",
    gaps: str = "",
    web_url: str = "",
    decision: str = "",
    limit: int = 3
) -> str:
    """
    Save and retrieve candidate records.

    Actions supported:

    INSERT — Save candidate
    SELECT — Retrieve candidate
    LIST — List all candidates
    TOP — Show top candidates
    DELETE — Remove candidate
    """

    try:
        score = int(score)
    except:
        score = 0

    try:
        limit = int(limit)
    except:
        limit = 3

    conn = sqlite3.connect(DB_FILE)

    # INSERT
    if action == "INSERT":

        conn.execute(
            """
            INSERT OR REPLACE INTO candidates
            (name, score, strengths, gaps,
             web_url, decision, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                score,
                strengths,
                gaps,
                web_url,
                decision,
                datetime.now().strftime("%Y-%m-%d %H:%M")
            )
        )

        conn.commit()

        return f"Saved: {name} | Score: {score}/100"


    # SELECT
    elif action == "SELECT":

        row = conn.execute(
            "SELECT * FROM candidates WHERE name=?",
            (name,)
        ).fetchone()

        if row:

            return (
                f"Name: {row[1]} | Score: {row[2]}/100\n"
                f"Strengths: {row[3]}\n"
                f"Gaps: {row[4]}\n"
                f"Decision: {row[6]}"
            )

        return "Candidate not found."


    # LIST
    elif action == "LIST":

        rows = conn.execute(
            "SELECT name, score, decision FROM candidates ORDER BY score DESC"
        ).fetchall()

        if not rows:
            return "No candidates."

        return "\n".join(
            [f"{r[0]} | {r[1]}/100 | {r[2]}" for r in rows]
        )


    # TOP
    elif action == "TOP":

        rows = conn.execute(
            "SELECT name, score FROM candidates ORDER BY score DESC LIMIT ?",
            (limit,)
        ).fetchall()

        return "\n".join(
            [f"{r[0]} — {r[1]}" for r in rows]
        )


    # DELETE
    elif action == "DELETE":

        conn.execute(
            "DELETE FROM candidates WHERE name=?",
            (name,)
        )

        conn.commit()

        return f"Deleted {name}"

    return "Invalid DB action."


# ─────────────────────────────────────────────
# TOOL 3 — jd_scorer
# ─────────────────────────────────────────────

@tool
def jd_scorer(
    candidate: str,
    profile: str,
    jd: str
) -> str:
    """
    Score a candidate against a job description.

    Inputs:
        candidate — candidate name
        profile — profile or search result
        jd — job description

    Returns:
        JSON with:
        score, strengths, gaps, decision
    """

    prompt = f"""
Score this candidate.

Candidate: {candidate}

Profile:
{profile}

Job Description:
{jd}

Return JSON:

{{
 "score": number,
 "strengths": ["...", "...", "..."],
 "gaps": ["...", "..."],
 "decision": "..."
}}
"""

    response = llm.invoke(prompt)

    return response.content


# ─────────────────────────────────────────────
# SYSTEM PROMPT
# ─────────────────────────────────────────────

SYSTEM_PROMPT = """
You are JobMatch AI, an expert recruitment agent.
You MUST follow every step below without skipping.

=== STRICT WORKFLOW ===

Step 1: Use candidate_search tool
  → Query: "<candidate name> GitHub LinkedIn developer portfolio"
  → Do NOT skip this step.

Step 2: Use jd_scorer tool
  → Pass candidate name, search results, and job role as jd
  → Always score even if no profile found

Step 3: Use db_tool with action=INSERT
  → Save name, score, strengths, gaps, decision

Step 4: Use db_tool with action=SELECT
  → Confirm the record was saved

Step 5: Write FINAL ANSWER in this format:
---
✅ FINAL ANSWER
Candidate: <name>
Score: <X>/100
Strengths: <list>
Gaps: <list>
Decision: <Strong Hire / Interview / Maybe / Reject>
Profile URL: <url or Not found>
---

=== RULES ===
- Never skip any step
- Never say "hiring process is complete" without running all 4 tools
- Always call all tools before writing FINAL ANSWER
- If no GitHub found, still score based on role requirements
"""


# ─────────────────────────────────────────────
# CREATE AGENT (UPDATED)
# ─────────────────────────────────────────────

tools = [
    candidate_search,
    db_tool,
    jd_scorer
]

agent = create_react_agent(
    model=llm,
    tools=tools,
    prompt=SYSTEM_PROMPT
)


# ─────────────────────────────────────────────
# RUN FUNCTION
# ─────────────────────────────────────────────

def run_agent(user_input: str) -> str:
    """
    Execute the agent.

    Returns final response text.
    """

    result = agent.invoke({
        "messages": [
            {
                "role": "user",
                "content": user_input
            }
        ]
    })

    final_message = result["messages"][-1]

    return final_message.content


# ─────────────────────────────────────────────
# CLI Mode
# ─────────────────────────────────────────────

if __name__ == "__main__":

    print("JobMatch AI Ready")

    while True:

        user_input = input("\nEnter command: ")

        if user_input.lower() in ["exit", "quit"]:
            break

        output = run_agent(user_input)

        print("\n", output)