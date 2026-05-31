/**
 * Aitotech AI Widget
 * -------------------
 * किसी भी website (HTML / WordPress / React) में एक <script> tag से जुड़ने वाला
 * lightweight chat + contact widget। ये आपके FastAPI backend के /public/* endpoints
 * से बात करता है, ताकि visitor के सवाल और contact requests अपने-आप agents के पास जाएँ।
 *
 * इस्तेमाल (किसी भी page के <body> के अंत में):
 *
 *   <script
 *     src="https://YOUR_CDN/aitotech-widget.js"
 *     data-api="https://your-backend.com"
 *     defer
 *   ></script>
 *
 * data-api = आपके FastAPI backend का base URL (बिना trailing slash)।
 */
(function () {
  "use strict";

  var script = document.currentScript;
  var API = (script && script.getAttribute("data-api")) || "http://localhost:8000";
  API = API.replace(/\/$/, "");

  var STYLE = [
    ".aitt-btn{position:fixed;bottom:22px;right:22px;z-index:99998;width:58px;height:58px;border-radius:50%;border:none;cursor:pointer;background:linear-gradient(135deg,#6d8bff,#9b6dff);color:#fff;font-size:24px;box-shadow:0 8px 24px rgba(0,0,0,.25)}",
    ".aitt-panel{position:fixed;bottom:92px;right:22px;z-index:99999;width:340px;max-width:calc(100vw - 32px);height:480px;max-height:calc(100vh - 130px);background:#fff;border-radius:16px;box-shadow:0 16px 48px rgba(0,0,0,.28);display:none;flex-direction:column;overflow:hidden;font-family:system-ui,Segoe UI,Roboto,sans-serif}",
    ".aitt-panel.open{display:flex}",
    ".aitt-head{background:linear-gradient(135deg,#6d8bff,#9b6dff);color:#fff;padding:14px 16px;font-weight:600}",
    ".aitt-head small{display:block;font-weight:400;opacity:.85;font-size:12px;margin-top:2px}",
    ".aitt-body{flex:1;overflow-y:auto;padding:14px;background:#f5f7fb}",
    ".aitt-msg{margin-bottom:10px;display:flex}",
    ".aitt-msg.user{justify-content:flex-end}",
    ".aitt-bubble{max-width:80%;padding:9px 12px;border-radius:12px;font-size:14px;line-height:1.4;white-space:pre-wrap}",
    ".aitt-msg.bot .aitt-bubble{background:#fff;color:#1a2336;border:1px solid #e3e8f2}",
    ".aitt-msg.user .aitt-bubble{background:#6d8bff;color:#fff}",
    ".aitt-foot{display:flex;gap:8px;padding:10px;border-top:1px solid #eef1f7;background:#fff}",
    ".aitt-foot input{flex:1;border:1px solid #dde3ef;border-radius:10px;padding:9px 11px;font-size:14px;outline:none}",
    ".aitt-foot button{border:none;background:#6d8bff;color:#fff;border-radius:10px;padding:0 14px;cursor:pointer;font-weight:600}",
    ".aitt-foot button:disabled{opacity:.5;cursor:not-allowed}",
  ].join("");

  function injectStyle() {
    var s = document.createElement("style");
    s.textContent = STYLE;
    document.head.appendChild(s);
  }

  function el(tag, cls, html) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    return e;
  }

  function build() {
    var btn = el("button", "aitt-btn", "💬");
    btn.setAttribute("aria-label", "Chat with Aitotech AI");

    var panel = el("div", "aitt-panel");
    var head = el(
      "div",
      "aitt-head",
      "Aitotech AI<small>हमारी services के बारे में पूछें</small>"
    );
    var body = el("div", "aitt-body");
    var foot = el("div", "aitt-foot");
    var input = el("input");
    input.type = "text";
    input.placeholder = "अपना सवाल लिखें…";
    var send = el("button", null, "Send");

    foot.appendChild(input);
    foot.appendChild(send);
    panel.appendChild(head);
    panel.appendChild(body);
    panel.appendChild(foot);
    document.body.appendChild(btn);
    document.body.appendChild(panel);

    function addMsg(text, who) {
      var m = el("div", "aitt-msg " + who);
      m.appendChild(el("div", "aitt-bubble", null)).textContent = text;
      body.appendChild(m);
      body.scrollTop = body.scrollHeight;
      return m;
    }

    addMsg("नमस्ते! 👋 मैं Aitotech का AI assistant हूँ। कैसे मदद करूँ?", "bot");

    function toggle() {
      panel.classList.toggle("open");
      if (panel.classList.contains("open")) input.focus();
    }
    btn.addEventListener("click", toggle);

    async function ask() {
      var text = input.value.trim();
      if (!text) return;
      input.value = "";
      addMsg(text, "user");
      send.disabled = true;
      var thinking = addMsg("सोच रहा हूँ…", "bot");
      try {
        var res = await fetch(API + "/public/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: text, agent_type: "sales" }),
        });
        var data = await res.json();
        thinking.querySelector(".aitt-bubble").textContent =
          data.answer || data.detail || "माफ़ कीजिए, अभी जवाब नहीं दे पाया।";
      } catch (e) {
        thinking.querySelector(".aitt-bubble").textContent =
          "Connection error — कृपया बाद में कोशिश करें।";
      } finally {
        send.disabled = false;
        body.scrollTop = body.scrollHeight;
      }
    }

    send.addEventListener("click", ask);
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter") ask();
    });
  }

  // global helper: contact form को connect करने के लिए
  // Aitotech.submitContact({name,email,message,...}) -> Promise
  window.Aitotech = {
    api: API,
    submitContact: function (payload) {
      return fetch(API + "/public/contact", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }).then(function (r) {
        return r.json();
      });
    },
    submitInquiry: function (payload) {
      return fetch(API + "/public/inquiry", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }).then(function (r) {
        return r.json();
      });
    },
    getServices: function () {
      return fetch(API + "/public/services").then(function (r) {
        return r.json();
      });
    },
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      injectStyle();
      build();
    });
  } else {
    injectStyle();
    build();
  }
})();
