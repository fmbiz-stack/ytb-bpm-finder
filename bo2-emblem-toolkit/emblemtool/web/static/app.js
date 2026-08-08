// BO2 Emblem Toolkit - control panel frontend.
// Plain JS, no build step, no dependencies - keeps the tool easy to run
// for non-technical users.

const modeHints = {
  off: "The proxy is transparent. Nothing is captured or changed.",
  capture: "Open a player's profile or channel on your console - their emblem is saved below automatically.",
  inject: "Open your own emblem editor on the console. The selected emblem below loads there, ready to save.",
};

let currentStatus = null;
let currentEmblems = [];
let networkInfo = null;
let stopped = false;

async function getJSON(url) {
  const r = await fetch(url);
  return r.json();
}
async function postJSON(url, body) {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  return r.json();
}

// ---------- network / console setup ----------

function renderIpList(info) {
  const list = document.getElementById("ipList");
  const tpl = document.getElementById("ipRowTpl");
  const addresses = info.lan_ips && info.lan_ips.length
    ? info.lan_ips
    : (info.lan_ip ? [{ ip: info.lan_ip, label: "", primary: true }] : []);

  list.innerHTML = "";
  if (!addresses.length) {
    list.innerHTML = '<p class="muted">Couldn\'t detect any usable address. See docs/INSTALL.md for finding it yourself.</p>';
    return;
  }
  for (const entry of addresses) {
    const node = tpl.content.cloneNode(true);
    const row = node.querySelector(".ip-row");
    row.classList.toggle("primary", !!entry.primary);
    node.querySelector(".ip-value").textContent = `${entry.ip} : ${info.proxy_port}`;
    node.querySelector(".ip-label").textContent = entry.label || "";
    list.appendChild(node);
  }
}

function renderConsolePicker(info) {
  const select = document.getElementById("consoleSelect");
  if (!select.options.length) {
    for (const c of info.consoles) {
      const opt = document.createElement("option");
      opt.value = c.key;
      opt.textContent = c.name;
      select.appendChild(opt);
    }
    select.addEventListener("change", async () => {
      await postJSON("/api/console", { console: select.value });
      await loadNetworkInfo();
    });
  }
  select.value = info.console.key;

  document.getElementById("consoleNote").textContent = info.console.note || "";

  const steps = document.getElementById("consoleSteps");
  steps.innerHTML = "";
  for (const step of info.console.proxy_steps) {
    const li = document.createElement("li");
    li.textContent = step;
    steps.appendChild(li);
  }
}

async function loadNetworkInfo() {
  networkInfo = await getJSON("/api/network-info");
  const el = document.getElementById("setupValue");
  el.textContent = networkInfo.lan_ip
    ? `${networkInfo.lan_ip} : ${networkInfo.proxy_port}`
    : "couldn't detect - open Console setup";
  renderIpList(networkInfo);
  renderConsolePicker(networkInfo);
  renderDetection();
}

// Live feedback on whether the console's traffic is actually arriving. Without
// this the only failure signal is "nothing happens", which is the same thing
// a wrong IP, a firewall block and a wrong mode all look like.
function renderDetection() {
  const detected = currentStatus && currentStatus.detected;
  const pill = document.getElementById("detectPill");
  const detail = document.getElementById("detectDetail");
  if (!detected) return;

  if (detected.emblem_host) {
    const who = detected.console_guess ? detected.console_guess.toUpperCase() : "unknown console";
    pill.textContent = `emblem traffic seen · ${who}`;
    pill.classList.add("ok");
    detail.textContent =
      `${detected.requests} emblem request(s) handled, most recently at ${detected.last_seen}. ` +
      `Endpoint: ${detected.emblem_host} (${who}).`;
  } else if (detected.other_demonware && detected.other_demonware.length) {
    pill.textContent = "console connected, no emblem traffic yet";
    pill.classList.remove("ok");
    detail.textContent =
      "Traffic is reaching the proxy, so the network side is set up correctly, but no emblem " +
      "request has come through yet. Open a player's profile (Capture) or your own emblem editor (Show). " +
      "Seen so far: " + detected.other_demonware.join(", ");
  } else {
    pill.textContent = "waiting for emblem traffic";
    pill.classList.remove("ok");
    detail.textContent =
      "Nothing has reached the proxy yet. If the console has been online for a while with the proxy " +
      "set, check the address above and your firewall.";
  }
}

function renderProxyError() {
  const existing = document.getElementById("proxyError");
  const message = currentStatus && currentStatus.proxy_error;
  if (!message) {
    if (existing) existing.remove();
    return;
  }
  const box = existing || document.createElement("div");
  box.id = "proxyError";
  box.className = "error-box";
  box.textContent = message;
  if (!existing) document.querySelector("main").prepend(box);
}

// ---------- mode ----------

function renderMode() {
  document.querySelectorAll(".mode-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.mode === currentStatus.mode);
  });
  document.getElementById("modeHint").textContent = modeHints[currentStatus.mode] || "";
}

async function setMode(mode) {
  await postJSON("/api/mode", { mode });
  await refreshStatus();
}

document.querySelectorAll(".mode-btn").forEach((btn) => {
  btn.addEventListener("click", () => setMode(btn.dataset.mode));
});

// ---------- quit ----------
// A packaged app has no terminal window to Ctrl+C, so the panel needs its own
// way to stop the proxy.
document.getElementById("quitBtn").addEventListener("click", async () => {
  if (!confirm("Stop the proxy and control panel?\n\nSet your console's proxy back to Off first, or it will lose its internet connection.")) return;
  stopped = true;
  try {
    await postJSON("/api/quit", {});
  } catch (e) {
    // The server closing the connection mid-reply is a normal outcome here.
  }
  document.body.innerHTML =
    '<div class="stopped-screen"><h1>Stopped</h1>' +
    "<p>The proxy and control panel have shut down. Remember to set your console's " +
    "proxy setting back to Do Not Use.</p></div>";
});

// ---------- emblem list (flat, single-select) ----------

function fmtDate(s) {
  if (!s) return "";
  return s.replace(" ", " · ").slice(0, 16);
}

function isSelected(e) {
  const sel = currentStatus.selected;
  return sel && sel.group === e.group && sel.slot === e.slot;
}

function renderEmblems() {
  const list = document.getElementById("emblemList");
  const empty = document.getElementById("emblemsEmpty");
  list.innerHTML = "";
  empty.style.display = currentEmblems.length ? "none" : "";

  const tpl = document.getElementById("emblemCardTpl");
  for (const e of currentEmblems) {
    const node = tpl.content.cloneNode(true);
    const card = node.querySelector(".emblem-card");
    card.classList.toggle("selected", isSelected(e));

    node.querySelector(".emblem-thumb").src = `/api/render/${encodeURIComponent(e.group)}/${e.slot}.png`;
    node.querySelector(".emblem-date").textContent = fmtDate(e.captured_at);

    const labelInput = node.querySelector(".emblem-label-input");
    labelInput.value = e.label || `Emblem from ${fmtDate(e.captured_at)}`;
    labelInput.addEventListener("click", (evt) => evt.stopPropagation());
    labelInput.addEventListener("change", async () => {
      await postJSON(`/api/emblems/${encodeURIComponent(e.group)}/${e.slot}/label`, { label: labelInput.value });
    });

    card.addEventListener("click", async () => {
      await postJSON("/api/select", { group: e.group, slot: e.slot });
      await refreshStatus();
    });

    list.appendChild(node);
  }
}

document.getElementById("refreshBtn").addEventListener("click", refreshAll);

// ---------- refresh loop ----------

async function refreshStatus() {
  currentStatus = await getJSON("/api/status");
  renderMode();
  renderDetection();
  renderProxyError();
  if (currentEmblems.length) renderEmblems();
}

async function refreshAll() {
  if (stopped) return;
  [currentStatus, currentEmblems] = await Promise.all([
    getJSON("/api/status"),
    getJSON("/api/emblems"),
  ]);
  renderMode();
  renderDetection();
  renderProxyError();
  renderEmblems();
}

refreshAll().then(loadNetworkInfo);
setInterval(() => {
  refreshAll().catch(() => {});
}, 5000);
