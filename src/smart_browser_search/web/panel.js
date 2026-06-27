/* Smart Browser Search — panel controller (JS side of the pycmd bridge). */
(function () {
  "use strict";

  var cfg = {};
  var el = {};

  function $(id) { return document.getElementById(id); }
  function cmd(s) { if (window.pycmd) { window.pycmd(s); } }

  function make(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  function esc(s) { var d = document.createElement("div"); d.textContent = s == null ? "" : s; return d.innerHTML; }

  function nearBottom() {
    var m = el.messages;
    return m.scrollHeight - m.scrollTop - m.clientHeight < 120;
  }
  function scrollDown(force) {
    if (force || nearBottom()) {
      requestAnimationFrame(function () { el.messages.scrollTop = el.messages.scrollHeight; });
    }
  }
  function hideEmpty() { if (el.empty) el.empty.classList.add("sbs-hidden"); }

  /* ---------------- sending ---------------- */
  function sendText(text) {
    text = (text || "").trim();
    if (!text) return;
    hideEmpty();
    addUser(text);
    cmd("send:" + text);
  }
  function sendFromInput() {
    var text = el.input.value;
    if (!text.trim()) return;
    el.input.value = "";
    autosize();
    sendText(text);
  }

  /* ---------------- message rendering ---------------- */
  function addUser(text) {
    var wrap = make("div", "sbs-msg user");
    var b = make("div", "sbs-bubble", text);
    wrap.appendChild(b);
    el.messages.appendChild(wrap);
    scrollDown(true);
  }

  var thinkingNode = null;
  function setThinking(on) {
    if (on) {
      if (thinkingNode) return;
      thinkingNode = make("div", "sbs-msg assistant");
      var b = make("div", "sbs-bubble");
      var sk = make("div", "sbs-skel");
      sk.appendChild(make("div", "sbs-skel-line w2"));
      sk.appendChild(make("div", "sbs-skel-line w1"));
      sk.appendChild(make("div", "sbs-skel-line w3"));
      b.appendChild(sk);
      thinkingNode.appendChild(b);
      el.messages.appendChild(thinkingNode);
      scrollDown(true);
    } else if (thinkingNode) {
      thinkingNode.remove();
      thinkingNode = null;
    }
  }

  function addAssistant(p) {
    setThinking(false);
    var wrap = make("div", "sbs-msg assistant");

    if (p.reply) wrap.appendChild(make("div", "sbs-bubble", p.reply));

    if (p.clarifying_question) {
      wrap.appendChild(make("div", "sbs-bubble", p.clarifying_question));
      if (p.quick_replies && p.quick_replies.length) {
        var row = make("div", "sbs-chiprow");
        p.quick_replies.forEach(function (q) {
          var c = make("button", "sbs-chip", q);
          c.onclick = function () { sendText(q); };
          row.appendChild(c);
        });
        wrap.appendChild(row);
      }
    }

    if (p.search_string) wrap.appendChild(searchCard(p.search_string, p.runnable_string));

    if (p.results && p.results.length) wrap.appendChild(resultsBlock(p.results));

    if (p.related && p.related.length) wrap.appendChild(relatedBlock(p.related));

    if (p.show_latency) {
      var bits = [];
      if (p.counts && p.counts.shown != null) bits.push(p.counts.shown + " card" + (p.counts.shown === 1 ? "" : "s"));
      if (p.timing_ms) bits.push(p.timing_ms + " ms");
      if (p.model) bits.push(p.model);
      if (bits.length) wrap.appendChild(make("div", "sbs-foot", bits.join(" · ")));
    }

    el.messages.appendChild(wrap);
    scrollDown();
  }

  function searchCard(query, runnable) {
    var card = make("div", "sbs-searchcard");
    card.appendChild(make("div", "sbs-query", query));
    var actions = make("div", "sbs-actions");
    var copy = make("button", "sbs-btn", "Copy");
    copy.onclick = function () {
      try { if (navigator.clipboard) navigator.clipboard.writeText(query); } catch (e) {}
      cmd("copy:" + query);
      copy.textContent = "Copied ✓"; copy.classList.add("copied");
      setTimeout(function () { copy.textContent = "Copy"; copy.classList.remove("copied"); }, 1300);
    };
    var run = make("button", "sbs-btn primary", "Run in Browser ▶");
    run.onclick = function () { cmd("run_search:" + (runnable || query)); };
    actions.appendChild(copy);
    actions.appendChild(run);
    card.appendChild(actions);
    return card;
  }

  var FLAG_COLORS = { 1: "#e25555", 2: "#e8983a", 3: "#3aa55d", 4: "#3f7fd6", 5: "#c071d6", 6: "#3bb6b6", 7: "#9b8d83" };

  function resultsBlock(results) {
    var box = make("div", "sbs-results");
    box.appendChild(make("div", "sbs-results-head", "Results"));
    results.forEach(function (r) {
      var card = make("div", "sbs-result");
      card.onclick = function () { if (r.card_id) cmd("reveal_card:" + r.card_id); };
      var title = make("div", "sbs-result-title");
      if (r.is_image_hit) { var ib = make("span", "sbs-badge", "🖼"); title.appendChild(ib); }
      else if (r.has_image) { var hb = make("span", "sbs-badge", "🖼"); hb.style.opacity = ".5"; title.appendChild(hb); }
      title.appendChild(make("span", null, r.title || "(untitled)"));
      card.appendChild(title);
      if (r.snippet) card.appendChild(make("div", "sbs-result-snippet", r.snippet));
      var meta = make("div", "sbs-result-meta");
      if (r.flag && FLAG_COLORS[r.flag]) {
        var dot = make("span", "sbs-flagdot");
        dot.style.background = FLAG_COLORS[r.flag];
        meta.appendChild(dot);
      }
      if (r.deck) meta.appendChild(make("span", null, r.deck));
      if (r.note_type) meta.appendChild(make("span", null, "· " + r.note_type));
      (r.tags || []).slice(0, 4).forEach(function (t) {
        meta.appendChild(make("span", "sbs-tag", t));
      });
      if (meta.childNodes.length) card.appendChild(meta);
      box.appendChild(card);
    });
    return box;
  }

  function relatedBlock(related) {
    var box = make("div", "sbs-relwrap");
    box.appendChild(make("div", "sbs-rel-label", "Related concepts"));
    related.forEach(function (c) {
      var pill = make("button", "sbs-pill", c);
      pill.onclick = function () { sendText(c); };
      box.appendChild(pill);
    });
    return box;
  }

  function addError(p) {
    setThinking(false);
    var wrap = make("div", "sbs-msg assistant");
    var b = make("div", "sbs-bubble");
    if (p.kind === "offline") {
      b.appendChild(make("div", null, "⚠ Local AI isn’t responding."));
      b.appendChild(make("div", "sbs-muted", "Make sure your model server (e.g. Ollama) is running."));
      var row = make("div", "sbs-chiprow");
      var start = make("button", "sbs-chip", "Start Ollama");
      start.onclick = function () { cmd("start_ai"); };
      var retry = make("button", "sbs-chip", "Retry");
      retry.onclick = function () { cmd("retry_conn"); };
      row.appendChild(start); row.appendChild(retry);
      b.appendChild(row);
    } else {
      b.appendChild(make("div", null, "Something went wrong."));
      if (p.text) b.appendChild(make("div", "sbs-muted", p.text));
    }
    wrap.appendChild(b);
    el.messages.appendChild(wrap);
    scrollDown(true);
  }

  /* ---------------- banner / connection ---------------- */
  function showBanner(html, warn) {
    el.banner.innerHTML = html;
    el.banner.classList.toggle("warn", !!warn);
    el.banner.classList.remove("sbs-hidden");
    wireBanner();
  }
  function hideBanner() { el.banner.classList.add("sbs-hidden"); }
  function wireBanner() {
    var s = el.banner.querySelector("[data-act=start]");
    if (s) s.onclick = function () { cmd("start_ai"); };
    var r = el.banner.querySelector("[data-act=retry]");
    if (r) r.onclick = function () { cmd("retry_conn"); };
    var b = el.banner.querySelector("[data-act=build]");
    if (b) b.onclick = function () { cmd("build_index"); };
  }

  function onConnection(d) {
    if (d.online) { hideBanner(); }
    else {
      showBanner("<span>⚠ Local AI offline.</span>" +
        "<button data-act=start>Start Ollama</button>" +
        "<button data-act=retry>Retry</button>", true);
    }
  }
  function onMissingModels(d) {
    var list = (d.models || []).join(", ");
    showBanner("<span>Model not installed: <b>" + esc(list) +
      "</b>. Run <code>ollama pull " + esc((d.models || [])[0] || "") + "</code></span>" +
      "<button data-act=retry>Recheck</button>", true);
  }

  /* ---------------- image attach ---------------- */
  function onImagePending(d) {
    el.attachName.textContent = "Reading " + (d.name || "image") + "…";
    el.attach.classList.remove("sbs-hidden");
  }
  function onImageAttached(d) {
    el.attachName.textContent = d.name || "image attached";
    el.attach.classList.remove("sbs-hidden");
  }
  function onImageCleared() { el.attach.classList.add("sbs-hidden"); el.attachName.textContent = ""; }

  /* ---------------- toast ---------------- */
  var toastNode = null, toastTimer = null;
  function toast(text) {
    if (!toastNode) { toastNode = make("div", "sbs-toast"); document.body.appendChild(toastNode); }
    toastNode.textContent = text;
    toastNode.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toastNode.classList.remove("show"); }, 1900);
  }

  function clearChat() {
    el.messages.querySelectorAll(".sbs-msg").forEach(function (n) { n.remove(); });
    if (el.empty) el.empty.classList.remove("sbs-hidden");
    onImageCleared();
  }

  /* ---------------- dispatch from Python ---------------- */
  function handle(type, data) {
    data = data || {};
    switch (type) {
      case "init": cfg = data.config || {}; break;
      case "connection": onConnection(data); break;
      case "missing_models": onMissingModels(data); break;
      case "thinking": setThinking(!!data.on); break;
      case "assistant": addAssistant(data); break;
      case "error": addError(data); break;
      case "echo_user": addUser(data.text || ""); break;
      case "toast": toast(data.text || ""); break;
      case "image_pending": onImagePending(data); break;
      case "image_attached": onImageAttached(data); break;
      case "image_cleared": onImageCleared(); break;
      case "cleared": clearChat(); break;
      case "index_done": toast("Index updated ✓"); break;
      case "copied": break;
      case "theme": break;
      default: break;
    }
  }

  /* ---------------- input handling ---------------- */
  function autosize() {
    var t = el.input;
    t.style.height = "auto";
    t.style.height = Math.min(t.scrollHeight, 140) + "px";
  }

  function init() {
    el.root = $("sbs-root");
    el.messages = $("sbs-messages");
    el.empty = $("sbs-empty");
    el.banner = $("sbs-banner");
    el.input = $("sbs-input");
    el.attach = $("sbs-attach");
    el.attachName = $("sbs-attach-name");

    $("sbs-send").onclick = sendFromInput;
    $("sbs-newchat").onclick = function () { cmd("new_chat"); };
    $("sbs-settings").onclick = function () { cmd("open_settings"); };
    $("sbs-pick-image").onclick = function () { cmd("pick_image"); };
    $("sbs-attach-clear").onclick = function () { cmd("clear_image"); };

    el.input.addEventListener("input", autosize);
    el.input.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendFromInput(); }
    });

    var samples = $("sbs-samples");
    if (samples) {
      samples.querySelectorAll("[data-q]").forEach(function (b) {
        b.onclick = function () { sendText(b.getAttribute("data-q")); };
      });
    }

    el.input.focus();
    cmd("ready");
  }

  window.SmartSearch = { handle: handle, sendText: sendText };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
