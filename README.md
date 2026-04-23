# SMARTHIRE — Resume Screening Agent

> Built for Pronix IT Solutions | Agentic AI Fresher Assessment  
> Stack: LangGraph + LangChain + Groq (LLaMA 3.3) + Tavily + SQLite + Streamlit

---

## 📁 Project Structure

```
jobmatch_ai/
│
├── agent.py          ← All agent logic: tools, system prompt, LangGraph agent
├── app.py            ← Streamlit UI
├── requirements.txt  ← Python packages
├── .env.example      ← API key template (rename to .env and fill in)
└── candidates.db     ← Auto-created SQLite database on first run
```

---

## ⚙️ Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Create your .env file
```bash
cp .env.example .env
```
Then edit `.env` and add your keys:
- **GROQ_API_KEY** → free at https://console.groq.com
- **TAVILY_API_KEY** → free at https://app.tavily.com (1000 searches/month)

### 3. Run the app
```bash
streamlit run app.py
```

---

## 🧠 How It Works

### The 3 Tools

| Tool | Purpose | When Agent Uses It |
|------|---------|-------------------|
| `web_search` | Searches GitHub, LinkedIn, portfolio | First — to find candidate info |
| `jd_scorer` | Scores 0–100 with strengths/gaps | After search — to evaluate fit |
| `db_tool` | INSERT / SELECT / LIST / TOP / DELETE | After scoring — to save & confirm |

### The ReAct Loop (LangGraph)

```
Recruiter types a command
        ↓
   [Agent Node]  ← LLM thinks (Thought)
        ↓
   Tool needed?
    YES ↓         NO → END (Final Answer)
  [Tool Node]
        ↓
  Observation fed back to Agent
        ↓
  (loops up to 8 times)
```

---

## 🔁 Real ReAct Trace (from an actual run)

**Command:** `"Score Rahul Sharma for our Python backend role and save results."`

```
Thought: I need to find Rahul's online presence first before scoring.
Action: web_search(query="Rahul Sharma Python developer GitHub LinkedIn portfolio")
Observation: github.com/rahul-dev — 12 repos, FastAPI projects, 200+ commits.
             LinkedIn: 1.5 years experience in Python backend.

Thought: Good. I have enough profile data. Now I'll score him against the Python backend JD.
Action: jd_scorer(
    candidate="Rahul Sharma",
    profile="Python, FastAPI, 1.5 years, GitHub - 200+ commits, REST APIs",
    jd="Python backend developer, 1+ year experience"
)
Observation: {
  "score": 82,
  "strengths": ["Python proficiency", "FastAPI REST APIs", "Active GitHub portfolio"],
  "gaps": ["No Docker/containerization", "No cloud deployment experience"],
  "decision": "Interview"
}

Thought: Score is ready. Now I'll save this to the database.
Action: db_tool(
    action="INSERT",
    name="Rahul Sharma",
    score=82,
    strengths="Python proficiency, FastAPI REST APIs, Active GitHub portfolio",
    gaps="No Docker/containerization, No cloud deployment experience",
    web_url="github.com/rahul-dev",
    decision="Interview"
)
Observation: ✅ Saved: Rahul Sharma | Score: 82/100 | Decision: Interview

Thought: Saved. Let me verify the record was stored correctly.
Action: db_tool(action="SELECT", name="Rahul Sharma")
Observation: Name: Rahul Sharma | Score: 82/100
             Strengths: Python proficiency, FastAPI REST APIs, Active GitHub portfolio
             Gaps: No Docker/containerization, No cloud deployment experience
             Decision: Interview | Date: 2025-07-10 14:32

Thought: Verified. Everything is saved. I can now give the final answer.

---
✅ FINAL ANSWER
Candidate: Rahul Sharma
Score: 82/100
Strengths: Python proficiency, FastAPI REST APIs, Active GitHub portfolio
Gaps: No Docker/containerization, No cloud deployment experience
Decision: Interview
Profile URL: github.com/rahul-dev
---
```

---

## 🧪 Test Commands to Run

```bash
# Basic evaluation
"Score Rahul Sharma for our Python backend role and save results."

# Candidate with skills in command (no online presence)
"Evaluate Priya Mehta for our Python backend role and save. She knows FastAPI and PostgreSQL."

# Database queries
"Show all evaluated candidates."
"Who are the top 3 candidates?"
"Show me Rahul Sharma's record."
"Remove Rahul Sharma from the database."
```

---

## 💡 Prompting Decisions (for the verbal review)

**Q: Why does the system prompt list all 3 tools explicitly?**  
A: The LLM doesn't know when to use which tool unless you tell it. Explicit tool descriptions + "use this FIRST/AFTER" phrasing guides the agent to the right order every time.

**Q: Why always INSERT then SELECT?**  
A: INSERT saves, SELECT confirms. The task explicitly requires the agent to verify its own work — this is agentic self-checking.

**Q: Why "still score if no profile found"?**  
A: A candidate without a LinkedIn isn't a bad candidate. We instruct the agent to give 40–55 and request resume — fair evaluation, not rejection.

**Q: What stops infinite loops?**  
A: `create_react_agent` from LangGraph has a built-in recursion limit. The system prompt also says "stop after 8 iterations."
