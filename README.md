# AI Business Enterprise (20–25 Agents)

एक multi-agent AI business platform का बेसिक आर्किटेक्चर। **FastAPI + Supabase + Groq/LangChain** बैकएंड और एक **Next.js dashboard**।

एक central **orchestrator** Supabase की `tasks` टेबल को poll करता है और हर task को उसके `agent_type` के हिसाब से सही agent पर भेजता है।

---

## 📁 Project structure

```
company Ai/
├── requirements.txt          # Python dependencies
├── .env.example              # env template (copy → .env)
├── .gitignore
├── README.md
├── supabase/
│   └── schema.sql            # Supabase टेबल्स (tasks, agents, task_logs)
├── src/
│   ├── config.py             # env से settings load
│   ├── database.py           # Supabase connection + helpers
│   ├── orchestrator.py       # tasks poll करके सही agent trigger करता है
│   ├── main.py               # FastAPI REST API
│   └── agents/
│       ├── base.py           # BaseAgent (LLM call logic यहीं centralize)
│       ├── __init__.py       # AGENT_REGISTRY (agent_type → class)
│       ├── research/         # Market research
│       ├── strategy/         # Business strategy
│       ├── dev/              # Engineering
│       ├── sales/            # Sales & outreach
│       └── delivery/         # Delivery & client success
└── dashboard/                # Next.js (App Router) control panel
    ├── app/page.tsx          # main dashboard UI
    └── lib/api.ts            # FastAPI client
```

> अभी 5 core agents हैं। 20–25 तक पहुँचने के लिए बस नए folders + `AGENT_REGISTRY` में entry जोड़ें (नीचे देखें)।

---

## 🚀 Setup

### 1. Supabase
1. [supabase.com](https://supabase.com) पर project बनाएँ।
2. **SQL Editor** में `supabase/schema.sql` paste करके Run करें।
3. **Project Settings → API** से `URL` और `key` कॉपी करें।

### 2. Backend (Python)
```bash
# venv बनाएँ
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # Windows PowerShell
# source .venv/bin/activate         # macOS/Linux

pip install -r requirements.txt

# env सेट करें
copy .env.example .env              # Windows
# cp .env.example .env              # macOS/Linux
# फिर .env में SUPABASE_URL, SUPABASE_KEY, GROQ_API_KEY भरें
```

API चलाएँ:
```bash
uvicorn src.main:app --reload
# http://localhost:8000/docs पर interactive API docs
```

Orchestrator चलाएँ (अलग terminal में):
```bash
python -m src.orchestrator           # लगातार poll loop
python -m src.orchestrator --once    # सिर्फ एक batch
```

### 3. Dashboard (Next.js)
```bash
cd dashboard
npm install
copy .env.local.example .env.local   # और values भरें
npm run dev
# http://localhost:3000
```

---

## 🔄 कैसे काम करता है (flow)

1. Dashboard या API से एक **task** बनता है → `tasks` टेबल में `status='pending'`।
2. **Orchestrator** हर N सेकंड में pending tasks उठाता है।
3. Task को `in_progress` claim करता है (race-safe)।
4. `agent_type` के हिसाब से `AGENT_REGISTRY` से सही agent चुनता है।
5. `agent.run(task)` → Groq LLM call → result।
6. Result `completed`/`failed` status के साथ DB में वापस।
7. Dashboard auto-refresh होकर live status दिखाता है।

> **बिना API key के भी चलता है:** `GROQ_API_KEY` न हो तो agents एक safe "stub" response देते हैं ताकि पूरा pipeline test हो सके।

---

## ➕ नया agent कैसे जोड़ें

1. `src/agents/<naya_agent>/` folder बनाएँ, उसमें `agent.py`:
   ```python
   from ..base import BaseAgent

   class MarketingAgent(BaseAgent):
       name = "marketing"
       role = "Marketing Specialist"
       system_prompt = "You are a marketing specialist..."
   ```
2. `src/agents/<naya_agent>/__init__.py` में export करें।
3. `src/agents/__init__.py` के `AGENT_REGISTRY` में entry जोड़ें:
   ```python
   "marketing": MarketingAgent,
   ```
4. (Optional) `supabase/schema.sql` के seed में उसे जोड़ें।

बस — orchestrator और dashboard अपने-आप उसे support करने लगेंगे।

---

## 🔌 API endpoints

| Method | Path                   | काम                              |
|--------|------------------------|----------------------------------|
| GET    | `/`                    | health + config status           |
| GET    | `/agents`              | available agents                 |
| GET    | `/tasks?status=`       | tasks list                       |
| POST   | `/tasks`               | नया task बनाओ                    |
| POST   | `/tasks/{id}/run`      | एक task तुरंत process करो        |
| POST   | `/orchestrator/tick`   | एक orchestrator batch चलाओ       |

---

## 🛠 Tech stack
- **Backend:** FastAPI, Uvicorn, Pydantic
- **DB:** Supabase (Postgres)
- **LLM:** Groq + LangChain
- **Frontend:** Next.js 15 (App Router), React 19, TypeScript
