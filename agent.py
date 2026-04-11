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
    model="llama-3.3-70b-versatile",
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
