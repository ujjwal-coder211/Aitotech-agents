# Aitotech — System Architecture (multi-repo)

यह document बताता है कि आपके अलग-अलग repos एक साथ कैसे काम करते हैं। हर repo
**independently deploy** होता है और दूसरों से **HTTP API + webhooks** के ज़रिए
जुड़ता है। **Supabase एक shared database** (single source of truth) है।

> मूल नियम: repos को merge मत करो। हर एक अपना काम करे, आपस में API से बात करें।

---

## The 4 pieces

| Repo | Role | Tech | Deploy |
|------|------|------|--------|
| **Aitotech** | 🚪 Website / front door | TypeScript (Next.js) | Vercel (`aitotech.vercel.app`) |
| **Aitotech-agents** | 🧠 Brain — orchestrator + agents + API | Python (FastAPI) | Railway |
| **ai-engine** | 🦾 Hands — real actions (email/WhatsApp/CRM) | n8n (Docker) | self-hosted / Railway |
| **Sayra** | 💬 Chat UI / product (TBD) | HTML | Vercel/static |

Supabase = 🗄️ shared memory (tasks, leads, services, logs)।

---

## Agent swarm (connected pipeline + shared memory)

Agents ek connected swarm hai — ek ka output agle ka input. Sab ek **shared
memory** (`company_memory` table) me likhte/padhte hain, isliye poora swarm ek
brain ki tarah kaam karta hai. Har agent ka `next_agents` decide karta hai
chaining:

```
research → opportunity → strategy → product ─┬→ dev → delivery
                                             └→ marketing → sales

standalone: finance, support  (kabhi bhi manually call karo)
```

| Agent | Role |
|-------|------|
| research | Market research, demand signals |
| opportunity | Kya bechna, kisko, kaise, kitne me (money-making) |
| strategy | Go-to-market plan, roadmap, KPIs |
| product | Buildable productised offer + architecture |
| dev | Tech build plan + code |
| marketing | Positioning, content, campaigns |
| sales | Outreach, cold email, closing (+ n8n email action) |
| delivery | Client handoff, QA, onboarding |
| finance | Pricing, margins, profit projection |
| support | Existing client support |

**Kaise chalu karo:**
```
POST /pipeline   { "title": "...", "start_agent": "research", "market": "...", "region": "..." }
POST /orchestrator/tick     # agents ko chalao (ya APScheduler/cron se auto)
GET  /memory?tag=<pipeline_id>   # swarm ne kya kya socha
GET  /opportunities              # paisa-banane wale findings
GET  /pipelines                  # workflow timeline (tasks grouped by pipeline)
```

### Human-in-the-loop (Sayra advisor)

Kuch agents par `review_gate = True` hota hai (abhi `opportunity`). Aise agent ke
baad pipeline **rukti hai** aur ek `advice_request` banta hai — Sayra aapse go/no-go
+ advice maangti hai. Aapka jawab (`POST /advice/{id}/answer`) shared memory me
jaata hai aur pipeline aapki advice ke saath aage badhti hai (human → agents).

```
GET  /advice?status=pending          # jahan aapki zaroorat hai
POST /advice/{id}/answer  { "decision": "Approve & continue", "response": "Focus on fintech SMBs" }
```

### Profit tracking

`deals` table me projected (agent/aap ka estimate) + actual (jab paisa aaye) dono.
Dashboard profit card `/finance/summary` se aata hai.

```
POST /deals   { "title": "...", "projected_revenue": 100000, "projected_cost": 30000 }
PATCH /deals/{id}  { "actual_revenue": 80000, "actual_cost": 25000, "status": "won" }
GET  /finance/summary
```

---

## Data flow

```
┌──────────────┐   contact / inquiry / chat    ┌─────────────────────┐
│  Aitotech    │ ────────────────────────────► │  Aitotech-agents    │
│  (website)   │      POST /public/*           │  FastAPI + Orchestr.│
└──────────────┘                               └──────────┬──────────┘
┌──────────────┐                                          │ tasks/leads/services
│  Sayra (chat)│ ──── POST /public/chat ──────►           ▼
└──────────────┘                               ┌─────────────────────┐
                                               │   Supabase (DB)     │
                                               └─────────────────────┘
                          agent needs an action │ ▲ n8n creates task
                          (email/WhatsApp/...)   ▼ │ POST /webhooks/n8n
                                               ┌─────────────────────┐
                                               │  ai-engine (n8n)    │──► Gmail
                                               │  webhook + workflows│──► WhatsApp
                                               └─────────────────────┘──► Sheets/CRM/Slack
```

### Example: website lead → automatic email
1. Customer `Aitotech` website पर **contact form** भरता है।
2. `Aitotech-agents` एक **lead + sales task** बनाता है (Supabase में)।
3. **Orchestrator** task उठाता है → **Sales agent** एक email *लिखता* है।
4. Agent एक `email` **action** लौटाता है → orchestrator उसे **n8n** पर भेजता है।
5. **n8n** asli email **भेज देता है** (Gmail/SMTP)।
6. Result Supabase में update → **dashboard** पर live दिखता है।

---

## Connection points (किसको क्या call करना है)

### 1. Aitotech (website) → Aitotech-agents
`integrations/aitotech/aitotech-widget.js` को website में एक `<script>` से जोड़ें,
या सीधे call करें:
```
POST {AGENTS_API}/public/contact     # contact form
POST {AGENTS_API}/public/inquiry     # service inquiry
POST {AGENTS_API}/public/chat        # chat widget
GET  {AGENTS_API}/public/services    # services list
```

### 2. Aitotech-agents → ai-engine (n8n)  [outbound actions]
Agents `actions()` लौटाते हैं; orchestrator उन्हें n8n webhook पर भेजता है:
```
POST {N8N_WEBHOOK_URL}
headers: { "x-api-key": N8N_API_KEY }
body:    { "action": "email", "data": { "to", "subject", "body" } }
```
n8n में: **Webhook node → Switch (action के हिसाब से) → Gmail / WhatsApp / Sheets**।

### 3. ai-engine (n8n) → Aitotech-agents  [inbound: नया task]
n8n कोई schedule/trigger पर task बनवा सकता है:
```
POST {AGENTS_API}/webhooks/n8n
headers: { "x-api-key": N8N_API_KEY }
body:    { "title", "agent_type", "payload", "priority" }
```

### 4. Sayra → Aitotech-agents
अगर Sayra एक chat UI है, तो वो `POST /public/chat` से agents से बात कर सकता है
(वही endpoint जो website widget use करता है)।

---

## Environment variables (Aitotech-agents)

```env
SUPABASE_URL=...
SUPABASE_KEY=...                 # service_role key
GROQ_API_KEY=...
GROQ_MODEL=llama-3.3-70b-versatile
WEBSITE_ALLOWED_ORIGINS=https://aitotech.vercel.app
N8N_WEBHOOK_URL=https://<your-n8n>/webhook/aitotech   # ai-engine
N8N_API_KEY=<shared-secret>
PORT=8080
```

---

## क्यों यह तरीका सही है
- **Independent deploys:** website बदलो तो agents redeploy नहीं करने पड़ते।
- **Single source of truth:** सारा data Supabase में — कोई duplication नहीं।
- **Loose coupling:** कोई एक service down हो तो बाकी काम करती रहती हैं।
- **Scalable:** नए agents या नई n8n workflows बिना दूसरों को छुए जोड़ सकते हैं।
- **Safe fallback:** n8n/keys न हों तो actions skip होते हैं, crash नहीं।
