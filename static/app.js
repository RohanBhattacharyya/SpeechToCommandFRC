const state = {
  config: null,
  commands: [],
};

const els = {
  summary: document.getElementById("summary"),
  speechStatus: document.getElementById("speechStatus"),
  ntStatus: document.getElementById("ntStatus"),
  sequence: document.getElementById("sequence"),
  startButton: document.getElementById("startButton"),
  stopButton: document.getElementById("stopButton"),
  saveButton: document.getElementById("saveButton"),
  addCommandForm: document.getElementById("addCommandForm"),
  newCommand: document.getElementById("newCommand"),
  commandList: document.getElementById("commandList"),
  teamNumber: document.getElementById("teamNumber"),
  server: document.getElementById("server"),
  tableName: document.getElementById("tableName"),
  modelPath: document.getElementById("modelPath"),
  debounce: document.getElementById("debounce"),
  sampleRate: document.getElementById("sampleRate"),
  lastText: document.getElementById("lastText"),
  partialText: document.getElementById("partialText"),
  testForm: document.getElementById("testForm"),
  testText: document.getElementById("testText"),
};

async function api(path, payload = {}) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok || data.ok === false) {
    throw new Error(data.error || `Request failed: ${path}`);
  }
  return data;
}

async function loadState() {
  const response = await fetch("/api/state");
  applyState(await response.json());
}

function applyState(next) {
  if (next.config) {
    state.config = next.config;
    state.commands = [...next.config.commands];
    fillSettings(next.config);
    renderCommands();
  }

  const speech = next.speech || {};
  const nt = next.networkTables || {};
  els.speechStatus.textContent = speech.message || "Idle";
  els.speechStatus.className = speech.listening ? "ok" : "";
  els.ntStatus.textContent = nt.connected ? "Connected" : nt.message || "Disconnected";
  els.ntStatus.className = nt.connected ? "ok" : "warn";
  els.sequence.textContent = String(nt.sequence || 0);
  els.summary.textContent = speech.listening ? "Listening for configured commands" : speech.message || "Idle";

  if (speech.lastText) {
    els.lastText.textContent = speech.lastText;
  }
  els.partialText.textContent = speech.partial ? `... ${speech.partial}` : "";
}

function fillSettings(config) {
  els.teamNumber.value = config.team_number || "";
  els.server.value = config.server || "";
  els.tableName.value = config.table_name || "SpeechToCommand";
  els.modelPath.value = config.vosk_model_path || "";
  els.debounce.value = config.debounce_seconds ?? 1.5;
  els.sampleRate.value = config.sample_rate || 16000;
}

function collectConfig() {
  return {
    ...state.config,
    commands: state.commands,
    team_number: Number.parseInt(els.teamNumber.value || "0", 10),
    server: els.server.value.trim(),
    table_name: els.tableName.value.trim() || "SpeechToCommand",
    vosk_model_path: els.modelPath.value.trim(),
    debounce_seconds: Number.parseFloat(els.debounce.value || "1.5"),
    sample_rate: Number.parseInt(els.sampleRate.value || "16000", 10),
  };
}

async function saveConfig() {
  const nextConfig = collectConfig();
  const nextState = await api("/api/config", nextConfig);
  applyState(nextState);
}

function renderCommands() {
  els.commandList.replaceChildren();

  if (!state.commands.length) {
    const empty = document.createElement("li");
    empty.className = "command-row";
    empty.innerHTML = '<span class="command-name">No commands</span>';
    els.commandList.append(empty);
    return;
  }

  state.commands.forEach((command, index) => {
    const row = document.createElement("li");
    row.className = "command-row";
    row.dataset.command = command;

    const name = document.createElement("span");
    name.className = "command-name";
    name.textContent = command;

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "remove-button";
    remove.title = `Remove ${command}`;
    remove.textContent = "X";
    remove.addEventListener("click", async () => {
      state.commands.splice(index, 1);
      renderCommands();
      await saveConfig();
    });

    row.append(name, remove);
    els.commandList.append(row);
  });
}

function flashCommand(command) {
  const row = [...els.commandList.querySelectorAll(".command-row")]
    .find((candidate) => candidate.dataset.command === command);
  if (!row) return;

  row.classList.add("heard");
  window.setTimeout(() => row.classList.remove("heard"), 1200);
}

els.addCommandForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const command = els.newCommand.value.trim();
  if (!command) return;

  const exists = state.commands.some((item) => item.toLowerCase() === command.toLowerCase());
  if (!exists) {
    state.commands.push(command);
    renderCommands();
    await saveConfig();
  }
  els.newCommand.value = "";
});

els.saveButton.addEventListener("click", async () => {
  await saveConfig();
});

els.startButton.addEventListener("click", async () => {
  await saveConfig();
  const nextState = await api("/api/start");
  applyState(nextState);
});

els.stopButton.addEventListener("click", async () => {
  const nextState = await api("/api/stop");
  applyState(nextState);
});

els.testForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = els.testText.value.trim();
  if (!text) return;

  els.lastText.textContent = text;
  const result = await api("/api/test", { text });
  result.matches.forEach(flashCommand);
});

const events = new EventSource("/api/events");
events.onmessage = (message) => {
  const event = JSON.parse(message.data);
  if (event.type === "state") {
    applyState(event);
  } else if (event.type === "heard") {
    flashCommand(event.command);
    els.lastText.textContent = event.text;
    els.summary.textContent = event.publishMessage;
  } else if (event.type === "transcript") {
    els.lastText.textContent = event.text;
  }
};

loadState().catch((error) => {
  els.summary.textContent = error.message;
});
