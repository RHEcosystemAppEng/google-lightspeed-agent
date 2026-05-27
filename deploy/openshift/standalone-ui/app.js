(function () {
  "use strict";

  const config = window.CONFIG || {
    agentUrl: "http://localhost:8000",
    ssoIssuerUrl: "https://sso.redhat.com/auth/realms/redhat-external",
  };

  let state = {
    orderId: null,
    accountId: null,
    clientId: null,
    clientSecret: null,
    accessToken: null,
    messageId: 0,
  };

  // --- DOM refs ---
  const $ = (sel) => document.querySelector(sel);
  const step1 = $("#step1");
  const step2 = $("#step2");
  const step3 = $("#step3");

  // --- Utility ---

  function showError(containerId, message) {
    const el = $(containerId);
    el.textContent = message;
    el.hidden = false;
  }

  function hideError(containerId) {
    $(containerId).hidden = true;
  }

  function setStepCompleted(stepEl, statusEl) {
    stepEl.classList.remove("active");
    stepEl.classList.add("completed");
    statusEl.textContent = "Complete";
  }

  function enableStep(stepEl) {
    stepEl.classList.remove("disabled");
    stepEl.classList.add("active");
  }

  function generateUUID() {
    return crypto.randomUUID
      ? crypto.randomUUID()
      : "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
          const r = (Math.random() * 16) | 0;
          return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
        });
  }

  // --- Copy to clipboard ---
  document.addEventListener("click", function (e) {
    const btn = e.target.closest(".btn-copy");
    if (!btn) return;
    const targetId = btn.dataset.copy;
    const el = document.getElementById(targetId);
    if (!el) return;
    const text = el.textContent;
    navigator.clipboard.writeText(text).then(function () {
      btn.textContent = "Copied";
      btn.classList.add("copied");
      setTimeout(function () {
        btn.textContent = "Copy";
        btn.classList.remove("copied");
      }, 1500);
    });
  });

  // --- JWT helpers (Web Crypto API) ---

  function base64UrlEncode(buf) {
    const bytes = buf instanceof ArrayBuffer ? new Uint8Array(buf) : buf;
    let binary = "";
    for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
    return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  }

  let _rsaKeyPair = null;

  async function getRsaKeyPair() {
    if (_rsaKeyPair) return _rsaKeyPair;
    _rsaKeyPair = await crypto.subtle.generateKey(
      { name: "RSASSA-PKCS1-v1_5", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256" },
      false,
      ["sign"]
    );
    return _rsaKeyPair;
  }

  async function buildSoftwareStatement(audience) {
    const keyPair = await getRsaKeyPair();
    const now = Math.floor(Date.now() / 1000);
    const header = { alg: "RS256", typ: "JWT", kid: "standalone-ui-key" };
    var redirectUris = (config.redirectUris || "https://vertexaisearch.cloud.google.com/oauth-redirect").split(",");
    const payload = {
      iss: "standalone-ui@localhost",
      iat: now,
      exp: now + 3600,
      aud: audience,
      sub: state.accountId || generateUUID(),
      auth_app_redirect_uris: redirectUris,
      google: { order: state.orderId || generateUUID() },
    };

    const enc = new TextEncoder();
    const headerB64 = base64UrlEncode(enc.encode(JSON.stringify(header)));
    const payloadB64 = base64UrlEncode(enc.encode(JSON.stringify(payload)));
    const sigInput = enc.encode(headerB64 + "." + payloadB64);
    const sig = await crypto.subtle.sign("RSASSA-PKCS1-v1_5", keyPair.privateKey, sigInput);
    return headerB64 + "." + payloadB64 + "." + base64UrlEncode(sig);
  }

  // --- Step 1: Order mode toggle ---

  function setOrderMode(mode) {
    var createMode = $("#order-create-mode");
    var existingMode = $("#order-existing-mode");
    var btnCreate = $("#btn-mode-create");
    var btnExisting = $("#btn-mode-existing");

    if (mode === "existing") {
      createMode.hidden = true;
      existingMode.hidden = false;
      btnCreate.classList.remove("active");
      btnExisting.classList.add("active");
    } else {
      createMode.hidden = false;
      existingMode.hidden = true;
      btnCreate.classList.add("active");
      btnExisting.classList.remove("active");
    }
  }

  function useExistingCredentials() {
    var orderId = $("#input-existing-order-id").value.trim();
    var clientId = $("#input-existing-client-id").value.trim();
    var clientSecret = $("#input-existing-client-secret").value.trim();
    var errorEl = "#existing-error";
    hideError(errorEl);

    if (!orderId || !clientId || !clientSecret) {
      showError(errorEl, "All three fields are required.");
      return;
    }

    state.orderId = orderId;
    state.accountId = "existing";
    state.clientId = clientId;
    state.clientSecret = clientSecret;

    $("#client-id").textContent = clientId;
    $("#client-secret").textContent = clientSecret;
    $("#dcr-result").hidden = false;

    setStepCompleted(step1, $("#step1-status"));
    $("#reset-section").hidden = false;
    enableStep(step2);
    showAuthUrl();
  }

  // --- Step 1: Order Provisioning & DCR ---

  async function sendPubSubEvent(eventType, orderId, accountId) {
    var data = {
      eventType: eventType,
      entitlement: { id: orderId, newPlan: "standalone" },
      account: { id: accountId },
    };
    var dataB64 = btoa(JSON.stringify(data));
    var resp = await fetch("/api/handler/dcr", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: {
          messageId: "standalone-" + generateUUID(),
          data: dataB64,
        },
      }),
    });
    if (!resp.ok) {
      var body = await resp.text();
      throw new Error("HTTP " + resp.status + ": " + body);
    }
    return await resp.json();
  }

  async function createOrder() {
    var btn = $("#btn-create-order");
    var errorEl = "#order-error";
    hideError(errorEl);
    btn.disabled = true;
    btn.textContent = "Creating...";

    try {
      state.orderId = generateUUID();
      state.accountId = generateUUID();

      // 1. Create entitlement
      await sendPubSubEvent("ENTITLEMENT_CREATION_REQUESTED", state.orderId, state.accountId);
      // 2. Activate entitlement
      await sendPubSubEvent("ENTITLEMENT_ACTIVE", state.orderId, state.accountId);

      // Show order info
      $("#order-id").textContent = state.orderId;
      $("#order-result").hidden = false;
      $("#btn-register").disabled = false;
    } catch (err) {
      state.orderId = null;
      state.accountId = null;
      showError(errorEl, "Order creation failed: " + err.message);
    } finally {
      btn.disabled = false;
      btn.textContent = "Create Order";
    }
  }

  async function fetchAgentCard() {
    const loadingEl = $("#agent-card-loading");
    const errorEl = "#agent-card-error";
    const infoEl = $("#agent-card-info");

    hideError(errorEl);

    try {
      const url = "/api/agent/.well-known/agent.json";
      const resp = await fetch(url);
      if (!resp.ok) throw new Error("HTTP " + resp.status + ": " + resp.statusText);

      const card = await resp.json();
      loadingEl.hidden = true;
      infoEl.hidden = false;

      $("#agent-name").textContent = card.name || "Unknown";
      $("#agent-description").textContent = card.description || "N/A";
      $("#agent-version").textContent = card.version || "N/A";

      let caps = "N/A";
      if (card.capabilities) {
        const capList = [];
        if (card.capabilities.streaming) capList.push("Streaming");
        if (card.capabilities.pushNotifications) capList.push("Push Notifications");
        if (card.capabilities.stateTransitionHistory) capList.push("State Transition History");
        caps = capList.length > 0 ? capList.join(", ") : "Standard";
      }
      $("#agent-capabilities").textContent = caps;
    } catch (err) {
      loadingEl.hidden = true;
      showError(errorEl, "Failed to fetch agent card: " + err.message);
    }
  }

  async function registerClient() {
    const btn = $("#btn-register");
    const errorEl = "#dcr-error";
    hideError(errorEl);
    btn.disabled = true;
    btn.textContent = "Registering...";

    try {
      const audience = config.agentUrl.replace(/\/+$/, "");
      const softwareStatement = await buildSoftwareStatement(audience);
      var url = "/api/handler/dcr";  // nginx proxy to internal handler service
      const resp = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          software_statement: softwareStatement,
        }),
      });

      if (!resp.ok) {
        const body = await resp.text();
        throw new Error("HTTP " + resp.status + ": " + body);
      }

      const data = await resp.json();
      if (!data.client_id || !data.client_secret) {
        throw new Error("Response missing client_id or client_secret");
      }

      state.clientId = data.client_id;
      state.clientSecret = data.client_secret;

      $("#client-id").textContent = data.client_id;
      $("#client-secret").textContent = data.client_secret;
      $("#dcr-result").hidden = false;

      setStepCompleted(step1, $("#step1-status"));
      $("#reset-section").hidden = false;
      enableStep(step2);
      showAuthUrl();
    } catch (err) {
      showError(errorEl, "DCR failed: " + err.message);
    } finally {
      btn.disabled = false;
      btn.textContent = "Register Client";
    }
  }

  async function resetRegistration() {
    var btn = $("#btn-reset");
    btn.disabled = true;
    btn.textContent = "Resetting...";

    try {
      // Cancel the entitlement if we have an order
      if (state.orderId) {
        await sendPubSubEvent("ENTITLEMENT_CANCELLED", state.orderId, state.accountId);
      }
    } catch (err) {
      // Best-effort cleanup — continue even if cancel fails
      console.warn("Entitlement cancellation failed:", err);
    }

    // Clear all state
    state.orderId = null;
    state.accountId = null;
    state.clientId = null;
    state.clientSecret = null;
    state.accessToken = null;
    state.messageId = 0;

    // Reset UI
    setOrderMode("create");
    $("#order-result").hidden = true;
    $("#dcr-result").hidden = true;
    $("#btn-register").disabled = true;
    $("#input-existing-order-id").value = "";
    $("#input-existing-client-id").value = "";
    $("#input-existing-client-secret").value = "";
    step1.classList.remove("completed");
    step1.classList.add("active");
    $("#step1-status").textContent = "";
    step2.classList.remove("completed", "active");
    step2.classList.add("disabled");
    $("#step2-status").textContent = "";
    $("#token-result").hidden = true;
    $("#token-cors-fallback").hidden = true;
    step3.classList.remove("completed", "active");
    step3.classList.add("disabled");
    $("#step3-status").textContent = "";
    $("#conversation").innerHTML = "";
    $("#reset-section").hidden = true;

    btn.disabled = false;
    btn.textContent = "Reset";
  }

  // --- Step 2: Get Access Token (Authorization Code Flow) ---

  function buildAuthUrl() {
    var base = config.ssoIssuerUrl.replace(/\/+$/, "");
    return (
      base +
      "/protocol/openid-connect/auth?" +
      "client_id=" + encodeURIComponent(state.clientId) +
      "&response_type=code" +
      "&scope=" + encodeURIComponent("api.console api.ocm")
    );
  }

  function showAuthUrl() {
    var el = $("#auth-url");
    if (el) el.textContent = buildAuthUrl();
  }

  function buildCurlCommand(code) {
    var tokenUrl =
      config.ssoIssuerUrl.replace(/\/+$/, "") + "/protocol/openid-connect/token";
    return (
      "curl -sk -X POST '" +
      tokenUrl +
      "' \\\n" +
      "  --data-urlencode 'grant_type=authorization_code' \\\n" +
      "  --data-urlencode 'client_id=" + state.clientId + "' \\\n" +
      "  --data-urlencode 'client_secret=" + state.clientSecret + "' \\\n" +
      "  --data-urlencode 'code=" + code + "'"
    );
  }

  function exchangeCode() {
    var errorEl = "#token-error";
    var code = $("#input-auth-code").value.trim();
    if (!code) {
      showError(errorEl, "Please paste the authorization code from the redirect URL.");
      return;
    }
    hideError(errorEl);
    $("#token-result").hidden = true;
    $("#curl-command").textContent = buildCurlCommand(code);
    $("#token-cors-fallback").hidden = false;
  }

  function applyToken(token, expiresIn) {
    if (!token) {
      showError("#token-error", "No access_token found in response.");
      return;
    }

    state.accessToken = token;
    // Clear sensitive credentials from the DOM after token acquisition
    const secretEl = $("#client-secret");
    if (secretEl) secretEl.textContent = "••••••••";
    $("#access-token").textContent = token;
    $("#token-result").hidden = false;
    $("#token-cors-fallback").hidden = true;
    hideError("#token-error");

    if (expiresIn) {
      const mins = Math.floor(expiresIn / 60);
      $("#token-expiry").textContent = "Expires in " + mins + " minutes (" + expiresIn + "s)";
    } else {
      $("#token-expiry").textContent = "";
    }

    setStepCompleted(step2, $("#step2-status"));
    enableStep(step3);
    $("#input-message").focus();
  }

  function useManualToken() {
    const raw = $("#input-manual-token").value.trim();
    if (!raw) {
      showError("#token-error", "Please paste the access token.");
      return;
    }

    // Try to parse as JSON (full response) or use as-is (just the token)
    let token = raw;
    try {
      const parsed = JSON.parse(raw);
      if (parsed.access_token) {
        token = parsed.access_token;
        applyToken(token, parsed.expires_in);
        return;
      }
    } catch (_) {
      // Not JSON — treat as raw token
    }
    applyToken(token, null);
  }

  // --- Step 3: A2A Client ---

  // --- Markdown rendering ---

  function sanitizeHtml(html) {
    var tmp = document.createElement("div");
    tmp.innerHTML = html;
    var scripts = tmp.querySelectorAll("script,iframe,object,embed,form,style,svg,math");
    for (var i = 0; i < scripts.length; i++) scripts[i].remove();
    var all = tmp.querySelectorAll("*");
    for (var j = 0; j < all.length; j++) {
      var attrs = Array.from(all[j].attributes);
      for (var k = 0; k < attrs.length; k++) {
        if (attrs[k].name.startsWith("on")) all[j].removeAttribute(attrs[k].name);
      }
      if (all[j].hasAttribute("href")) {
        var href = all[j].getAttribute("href") || "";
        if (href.trim().toLowerCase().startsWith("javascript:")) all[j].removeAttribute("href");
      }
      if (all[j].hasAttribute("src")) {
        var src = all[j].getAttribute("src") || "";
        if (src.trim().toLowerCase().startsWith("data:") && !src.trim().toLowerCase().startsWith("data:image/")) {
          all[j].removeAttribute("src");
        }
      }
    }
    return tmp.innerHTML;
  }

  function renderMarkdown(text) {
    if (typeof marked !== "undefined" && marked.parse) {
      return sanitizeHtml(marked.parse(text));
    }
    var escaped = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    return "<p>" + escaped.replace(/\n\n+/g, "</p><p>").replace(/\n/g, "<br>") + "</p>";
  }

  // --- A2UI rendering ---

  function resolveA2UIValue(val) {
    if (!val) return "";
    if (typeof val === "string") return val;
    if (val.literalString) return val.literalString;
    if (val.literalNumber !== undefined) return String(val.literalNumber);
    if (val.literalBoolean !== undefined) return String(val.literalBoolean);
    if (val.path) return "(data: " + val.path + ")";
    return "";
  }

  function renderA2UIComponent(comp, componentsById) {
    var wrapper = comp.component;
    var type = Object.keys(wrapper)[0];
    var props = wrapper[type];

    if (type === "Text") {
      var el = document.createElement("div");
      el.className = "a2ui-text";
      var hint = props.usageHint || "body";
      if (hint === "h1" || hint === "h2" || hint === "h3" || hint === "h4" || hint === "h5") {
        el = document.createElement(hint);
        el.className = "a2ui-heading";
      } else if (hint === "caption") {
        el.classList.add("a2ui-caption");
      }
      var textContent = resolveA2UIValue(props.text);
      if (typeof marked !== "undefined" && marked.parse) {
        el.innerHTML = sanitizeHtml(marked.parse(textContent));
      } else {
        el.textContent = textContent;
      }
      return el;
    }

    if (type === "Card") {
      var card = document.createElement("div");
      card.className = "a2ui-card";
      if (props.child && componentsById[props.child]) {
        card.appendChild(renderA2UIComponent(componentsById[props.child], componentsById));
      }
      return card;
    }

    if (type === "Row") {
      var row = document.createElement("div");
      row.className = "a2ui-row";
      if (props.distribution) row.style.justifyContent = cssJustify(props.distribution);
      if (props.alignment) row.style.alignItems = cssAlign(props.alignment);
      renderChildren(props.children, row, componentsById);
      return row;
    }

    if (type === "Column") {
      var col = document.createElement("div");
      col.className = "a2ui-column";
      if (props.distribution) col.style.justifyContent = cssJustify(props.distribution);
      if (props.alignment) col.style.alignItems = cssAlign(props.alignment);
      renderChildren(props.children, col, componentsById);
      return col;
    }

    if (type === "List") {
      var list = document.createElement("div");
      list.className = "a2ui-list";
      if (props.direction === "horizontal") list.classList.add("a2ui-list-horizontal");
      renderChildren(props.children, list, componentsById);
      return list;
    }

    if (type === "Button") {
      var btn = document.createElement("button");
      btn.className = "a2ui-button";
      if (props.primary) btn.classList.add("a2ui-button-primary");
      if (props.child && componentsById[props.child]) {
        btn.appendChild(renderA2UIComponent(componentsById[props.child], componentsById));
      }
      btn.disabled = true;
      return btn;
    }

    if (type === "Image") {
      var img = document.createElement("img");
      img.className = "a2ui-image";
      img.src = resolveA2UIValue(props.url);
      img.alt = resolveA2UIValue(props.altText) || "";
      return img;
    }

    if (type === "Divider") {
      var hr = document.createElement("hr");
      hr.className = "a2ui-divider";
      if (props.axis === "vertical") hr.classList.add("a2ui-divider-vertical");
      return hr;
    }

    if (type === "Tabs") {
      var tabs = document.createElement("div");
      tabs.className = "a2ui-tabs";
      var tabBar = document.createElement("div");
      tabBar.className = "a2ui-tab-bar";
      var tabContent = document.createElement("div");
      tabContent.className = "a2ui-tab-content";
      if (props.tabItems) {
        props.tabItems.forEach(function (item, idx) {
          var tabBtn = document.createElement("button");
          tabBtn.className = "a2ui-tab-btn" + (idx === 0 ? " active" : "");
          tabBtn.textContent = resolveA2UIValue(item.title);
          tabBtn.dataset.tabIdx = idx;
          tabBar.appendChild(tabBtn);
          var pane = document.createElement("div");
          pane.className = "a2ui-tab-pane" + (idx === 0 ? " active" : "");
          pane.dataset.tabIdx = idx;
          if (item.child && componentsById[item.child]) {
            pane.appendChild(renderA2UIComponent(componentsById[item.child], componentsById));
          }
          tabContent.appendChild(pane);
        });
        tabBar.addEventListener("click", function (e) {
          var t = e.target.closest(".a2ui-tab-btn");
          if (!t) return;
          tabBar.querySelectorAll(".a2ui-tab-btn").forEach(function (b) { b.classList.remove("active"); });
          tabContent.querySelectorAll(".a2ui-tab-pane").forEach(function (p) { p.classList.remove("active"); });
          t.classList.add("active");
          tabContent.querySelector('[data-tab-idx="' + t.dataset.tabIdx + '"]').classList.add("active");
        });
      }
      tabs.appendChild(tabBar);
      tabs.appendChild(tabContent);
      return tabs;
    }

    // Fallback: show type name
    var fallback = document.createElement("div");
    fallback.className = "a2ui-unknown";
    fallback.textContent = "[" + type + " component]";
    return fallback;
  }

  function renderChildren(children, container, componentsById) {
    if (!children) return;
    var ids = children.explicitList || [];
    ids.forEach(function (childId) {
      if (componentsById[childId]) {
        var childEl = renderA2UIComponent(componentsById[childId], componentsById);
        if (componentsById[childId].weight) {
          childEl.style.flexGrow = componentsById[childId].weight;
        }
        container.appendChild(childEl);
      }
    });
  }

  function cssJustify(dist) {
    var map = { center: "center", end: "flex-end", start: "flex-start", spaceBetween: "space-between", spaceAround: "space-around", spaceEvenly: "space-evenly" };
    return map[dist] || dist;
  }

  function cssAlign(align) {
    var map = { center: "center", end: "flex-end", start: "flex-start", stretch: "stretch" };
    return map[align] || align;
  }

  function renderA2UISurface(messages) {
    var container = document.createElement("div");
    container.className = "a2ui-surface";
    var componentsById = {};
    var rootId = null;

    messages.forEach(function (msg) {
      if (msg.surfaceUpdate && msg.surfaceUpdate.components) {
        msg.surfaceUpdate.components.forEach(function (c) {
          componentsById[c.id] = c;
        });
      }
      if (msg.beginRendering) {
        rootId = msg.beginRendering.root;
      }
    });

    if (rootId && componentsById[rootId]) {
      container.appendChild(renderA2UIComponent(componentsById[rootId], componentsById));
    } else {
      var ids = Object.keys(componentsById);
      if (ids.length > 0) {
        container.appendChild(renderA2UIComponent(componentsById[ids[0]], componentsById));
      }
    }
    return container;
  }

  // --- Message display ---

  function addMessage(role, text) {
    var conv = $("#conversation");
    var div = document.createElement("div");
    div.className = "message " + role;
    div.textContent = text;
    conv.appendChild(div);
    conv.scrollTop = conv.scrollHeight;
    return div;
  }

  function addRichMessage(role, htmlContent) {
    var conv = $("#conversation");
    var div = document.createElement("div");
    div.className = "message " + role + " rich";
    div.innerHTML = htmlContent;
    conv.appendChild(div);
    conv.scrollTop = conv.scrollHeight;
    return div;
  }

  function addElementMessage(role, element) {
    var conv = $("#conversation");
    var div = document.createElement("div");
    div.className = "message " + role + " rich";
    div.appendChild(element);
    conv.appendChild(div);
    conv.scrollTop = conv.scrollHeight;
    return div;
  }

  function extractA2UIBlocks(text) {
    var blocks = [];
    var remaining = text;
    var re = /<a2ui-json>([\s\S]*?)<\/a2ui-json>/g;
    var match;
    var lastIdx = 0;
    var parts = [];
    while ((match = re.exec(text)) !== null) {
      if (match.index > lastIdx) {
        parts.push({ type: "text", content: text.slice(lastIdx, match.index) });
      }
      try {
        var parsed = JSON.parse(match[1].trim());
        var messages = Array.isArray(parsed) ? parsed : [parsed];
        parts.push({ type: "a2ui", content: messages });
      } catch (e) {
        parts.push({ type: "text", content: match[0] });
      }
      lastIdx = match.index + match[0].length;
    }
    if (lastIdx < text.length) {
      parts.push({ type: "text", content: text.slice(lastIdx) });
    }
    return parts.length > 0 ? parts : [{ type: "text", content: text }];
  }

  function renderPart(part) {
    if (part.kind === "data" || (part.metadata && part.metadata.mimeType === "application/json+a2ui")) {
      var a2uiData = part.data;
      if (a2uiData) {
        var messages = Array.isArray(a2uiData) ? a2uiData : [a2uiData];
        addElementMessage("agent", renderA2UISurface(messages));
      }
      return;
    }

    var text = part.text;
    if (text === undefined || text === null) return;

    var blocks = extractA2UIBlocks(text);
    if (blocks.length === 1 && blocks[0].type === "text") {
      addRichMessage("agent", renderMarkdown(blocks[0].content.trim()));
      return;
    }
    blocks.forEach(function (block) {
      if (block.type === "a2ui") {
        addElementMessage("agent", renderA2UISurface(block.content));
      } else {
        var trimmed = block.content.trim();
        if (trimmed) addRichMessage("agent", renderMarkdown(trimmed));
      }
    });
  }

  function collectParts(result) {
    var answerParts = [];
    var thoughtParts = [];

    // Collect answer parts from primary sources
    if (result.artifacts) {
      result.artifacts.forEach(function (artifact) {
        if (artifact.parts) answerParts = answerParts.concat(artifact.parts);
      });
    }
    if (result.parts) {
      answerParts = answerParts.concat(result.parts);
    }
    if (result.status && result.status.message && result.status.message.parts) {
      answerParts = answerParts.concat(result.status.message.parts);
    }

    // History: if primary answer parts exist, treat history agent messages as
    // thinking (they are intermediate reasoning steps). Otherwise fall back to
    // history as the answer source.
    if (result.history) {
      var agentMsgs = result.history.filter(function (m) {
        return m.role === "agent" && m.parts;
      });
      if (answerParts.length === 0) {
        agentMsgs.forEach(function (msg) {
          answerParts = answerParts.concat(msg.parts);
        });
      } else {
        agentMsgs.forEach(function (msg) {
          thoughtParts = thoughtParts.concat(msg.parts);
        });
      }
    }

    // Separate parts flagged as thoughts by the model.
    // ADK sets metadata.adk_thought on A2A parts for Gemini thinking content.
    var filtered = [];
    answerParts.forEach(function (p) {
      var isThought = p.thought ||
        (p.metadata && (p.metadata.adk_thought || p.metadata.thought));
      if (isThought) {
        thoughtParts.push(p);
      } else {
        filtered.push(p);
      }
    });

    return { answer: filtered, thinking: thoughtParts };
  }

  async function sendMessage() {
    var input = $("#input-message");
    var text = input.value.trim();
    if (!text) return;

    var btn = $("#btn-send");
    var errorEl = "#a2a-error";
    hideError(errorEl);

    input.value = "";
    addMessage("user", text);

    state.messageId++;
    var thinkingEl = addMessage("agent", "Thinking...");
    thinkingEl.classList.add("thinking");
    btn.disabled = true;

    try {
      var url = "/api/agent/";
      var resp = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer " + state.accessToken,
        },
        body: JSON.stringify({
          jsonrpc: "2.0",
          method: "message/send",
          id: String(state.messageId),
          params: {
            message: {
              role: "user",
              parts: [{ kind: "text", text: text }],
              messageId: generateUUID(),
            },
          },
        }),
      });

      thinkingEl.remove();

      if (!resp.ok) {
        var body = await resp.text();
        throw new Error("HTTP " + resp.status + ": " + body);
      }

      var data = await resp.json();

      if (data.error) {
        throw new Error(data.error.message || JSON.stringify(data.error));
      }

      var result = data.result;
      var collected = collectParts(result);

      var showThinking = $("#toggle-thinking") && $("#toggle-thinking").checked;
      if (showThinking && collected.thinking.length > 0) {
        var details = document.createElement("details");
        details.className = "thinking-details";
        var summary = document.createElement("summary");
        summary.textContent = "Thinking (" + collected.thinking.length + " part" + (collected.thinking.length > 1 ? "s" : "") + ")";
        details.appendChild(summary);
        var inner = document.createElement("div");
        collected.thinking.forEach(function (part) {
          var text = part.text;
          if (text) {
            var p = document.createElement("div");
            p.innerHTML = renderMarkdown(text.trim());
            inner.appendChild(p);
          }
        });
        details.appendChild(inner);
        addElementMessage("agent", details);
      }

      if (collected.answer.length > 0) {
        collected.answer.forEach(renderPart);
      } else if (result && result.status) {
        addMessage("agent", "Status: " + (result.status.state || "unknown"));
      } else {
        addRichMessage("agent", "<pre>" + JSON.stringify(data, null, 2).replace(/</g, "&lt;") + "</pre>");
      }
    } catch (err) {
      thinkingEl.remove();
      showError(errorEl, "Request failed: " + err.message);
    } finally {
      btn.disabled = false;
      input.focus();
    }
  }

  // --- Event listeners ---

  $("#btn-mode-create").addEventListener("click", function () { setOrderMode("create"); });
  $("#btn-mode-existing").addEventListener("click", function () { setOrderMode("existing"); });
  $("#btn-create-order").addEventListener("click", createOrder);
  $("#btn-register").addEventListener("click", registerClient);
  $("#btn-use-existing").addEventListener("click", useExistingCredentials);
  $("#btn-reset").addEventListener("click", resetRegistration);
  $("#btn-exchange-code").addEventListener("click", exchangeCode);
  $("#btn-use-manual-token").addEventListener("click", useManualToken);
  $("#btn-send").addEventListener("click", sendMessage);

  $("#input-message").addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  // --- Init ---
  fetchAgentCard();
})();
