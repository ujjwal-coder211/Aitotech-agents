# Aitotech Website ↔ AI Enterprise — Integration

आपकी मौजूदा website **Aitotech** को इस AI system से जोड़ने का गाइड। इसके बाद
website से आने वाले **contact**, **service inquiry** और **chat** सीधे agents
के पास task बनकर पहुँचेंगे, और orchestrator उन्हें auto-handle करेगा।

```
Aitotech website  ──HTTP──►  FastAPI /public/*  ──►  leads + tasks (Supabase)
                                                          │
                                                  Orchestrator picks task
                                                          │
                                              Sales / Research agent handles it
```

---

## 1. Public API endpoints (backend में पहले से बने हैं)

| Method | Endpoint           | काम                                                   |
|--------|--------------------|-------------------------------------------------------|
| GET    | `/public/services` | active services की list (website पर दिखाने)           |
| POST   | `/public/contact`  | contact form → lead + **sales** task                  |
| POST   | `/public/inquiry`  | service inquiry → lead + **research** task            |
| POST   | `/public/chat`     | visitor का सवाल → agent का तुरंत जवाब (services-aware) |

### Request examples

**Contact:**
```json
POST /public/contact
{
  "name": "Rahul Sharma",
  "email": "rahul@example.com",
  "phone": "+91...",
  "company": "ABC Pvt Ltd",
  "message": "मुझे AI automation चाहिए",
  "service_slug": "ai-automation",
  "source": "aitotech"
}
```

**Chat:**
```json
POST /public/chat
{ "message": "आपकी chatbot service की कीमत क्या है?", "agent_type": "sales" }
```

---

## 2. Website में जोड़ने के 3 तरीके

### तरीका A — सबसे आसान (कोई भी website: HTML / WordPress / Wix)
अपनी site के हर page के `</body>` से ठीक पहले यह एक line डालें:

```html
<script
  src="https://YOUR_HOST/aitotech-widget.js"
  data-api="https://your-backend.com"
  defer
></script>
```

- नीचे-दाएँ एक 💬 **chat widget** आ जाएगा (services-aware AI जवाब देगा)।
- साथ में `window.Aitotech` global मिलता है जिससे अपने मौजूदा contact form को
  जोड़ सकते हैं:

```html
<script>
  document.querySelector("#myContactForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const res = await Aitotech.submitContact({
      name: form.name.value,
      email: form.email.value,
      message: form.message.value,
      source: "aitotech",
    });
    alert(res.message);
  });
</script>
```

> `aitotech-widget.js` और एक live `demo.html` इसी folder में हैं — पहले demo
> locally खोलकर टेस्ट कर सकते हैं।

### तरीका B — React / Next.js Aitotech site
```tsx
async function submitContact(data) {
  const res = await fetch(`${process.env.NEXT_PUBLIC_AI_API}/public/contact`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...data, source: "aitotech" }),
  });
  return res.json();
}
```

### तरीका C — सीधे API call (mobile app / server-side)
ऊपर दिए गए endpoints को किसी भी HTTP client से call करें।

---

## 3. Backend setup (एक बार)

1. `supabase/schema.sql` फिर से Run करें — इसमें अब `services` और `leads`
   tables भी हैं (existing tables पर असर नहीं पड़ेगा)।
2. `.env` में अपनी website का domain डालें (production में ज़रूरी):
   ```env
   WEBSITE_ALLOWED_ORIGINS=https://aitotech.com,https://www.aitotech.com
   ```
3. Backend चलाएँ: `uvicorn src.main:app --reload`
4. Orchestrator चलाएँ: `python -m src.orchestrator`

बस — अब Aitotech से आने वाला हर lead/सवाल agents तक अपने-आप पहुँचेगा और
dashboard (`localhost:3000`) पर live दिखेगा।

---

## 4. Local में टेस्ट कैसे करें
1. Backend चालू करें (`uvicorn ...`)।
2. इस folder की `demo.html` को browser में खोलें।
3. Services list दिखेगी, contact form भरें, और 💬 widget से chat करें।
4. Dashboard पर नया task आता हुआ देखें।

> Note: `demo.html` का `data-api` अभी `http://localhost:8000` है — deploy करते
> समय इसे अपने live backend URL से बदलें।
