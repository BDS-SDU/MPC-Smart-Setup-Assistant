const state = {
  sessionId: null,
  lastResponse: null,
  backendPlan: null,
  schema: null,
  sending: false,
};

const elements = {
  serviceStatus: document.querySelector("#serviceStatus"),
  sessionLabel: document.querySelector("#sessionLabel"),
  messages: document.querySelector("#messages"),
  chatForm: document.querySelector("#chatForm"),
  messageInput: document.querySelector("#messageInput"),
  requestState: document.querySelector("#requestState"),
  sendButton: document.querySelector("#sendButton"),
  resetButton: document.querySelector("#resetButton"),
  clearOptionsButton: document.querySelector("#clearOptionsButton"),
  refreshBackendButton: document.querySelector("#refreshBackendButton"),
  schemaButton: document.querySelector("#schemaButton"),
  closeSchemaButton: document.querySelector("#closeSchemaButton"),
  copyButton: document.querySelector("#copyButton"),
  downloadButton: document.querySelector("#downloadButton"),
  schemaDialog: document.querySelector("#schemaDialog"),
  schemaOutput: document.querySelector("#schemaOutput"),
  toast: document.querySelector("#toast"),
  metricParties: document.querySelector("#metricParties"),
  metricCircuit: document.querySelector("#metricCircuit"),
  metricAdversary: document.querySelector("#metricAdversary"),
  metricConfidence: document.querySelector("#metricConfidence"),
  recommendationText: document.querySelector("#recommendationText"),
  targetList: document.querySelector("#targetList"),
  securityList: document.querySelector("#securityList"),
  missingList: document.querySelector("#missingList"),
  conflictList: document.querySelector("#conflictList"),
  questionList: document.querySelector("#questionList"),
  backendName: document.querySelector("#backendName"),
  backendProtocol: document.querySelector("#backendProtocol"),
  backendScore: document.querySelector("#backendScore"),
  backendReasons: document.querySelector("#backendReasons"),
  backendSteps: document.querySelector("#backendSteps"),
  detailGrid: document.querySelector("#detailGrid"),
  jsonOutput: document.querySelector("#jsonOutput"),
  optionControls: document.querySelectorAll(".options-pane select, .options-pane input"),
  optionFields: {
    participant_scale: document.querySelector("#participantScaleSelect"),
    number_of_parties: document.querySelector("#partyCountInput"),
    circuit_form: document.querySelector("#circuitFormSelect"),
    math_structure: document.querySelector("#mathStructureSelect"),
    secret_sharing: document.querySelector("#secretSharingSelect"),
    preprocessing: document.querySelector("#preprocessingSelect"),
    adversary_behavior: document.querySelector("#adversaryBehaviorSelect"),
    corruption_strategy: document.querySelector("#corruptionStrategySelect"),
    network_model: document.querySelector("#networkModelSelect"),
    channel_model: document.querySelector("#channelModelSelect"),
    corruption_threshold: document.querySelector("#corruptionThresholdSelect"),
    security_goal: document.querySelector("#securityGoalSelect"),
  },
  tabs: document.querySelectorAll(".tab"),
  panels: {
    overview: document.querySelector("#overviewPanel"),
    details: document.querySelector("#detailsPanel"),
    json: document.querySelector("#jsonPanel"),
  },
};

function valueOrDash(value) {
  if (value === null || value === undefined || value === "") return "-";
  if (Array.isArray(value)) return value.length ? value.join(", ") : "-";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value);
}

function prettyJson(value) {
  return JSON.stringify(value ?? {}, null, 2);
}

function showToast(message) {
  elements.toast.textContent = message;
  elements.toast.classList.add("show");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    elements.toast.classList.remove("show");
  }, 2600);
}

function setBusy(isBusy) {
  state.sending = isBusy;
  elements.sendButton.disabled = isBusy;
  elements.resetButton.disabled = isBusy;
  elements.messageInput.disabled = isBusy;
  elements.clearOptionsButton.disabled = isBusy;
  for (const control of elements.optionControls) {
    control.disabled = isBusy;
  }
  elements.requestState.textContent = isBusy ? "Generating" : "Ready";
}

function getStructuredOptions() {
  const options = {};
  for (const [key, element] of Object.entries(elements.optionFields)) {
    if (!element) continue;
    const rawValue = element.value.trim();
    if (!rawValue) continue;
    options[key] = key === "number_of_parties" ? Number(rawValue) : rawValue;
  }
  return options;
}

function hasStructuredOptions(options) {
  return Object.values(options).some((value) => value !== null && value !== undefined && value !== "");
}

function structuredOptionsSummary(options) {
  const labels = {
    participant_scale: "Participant scale",
    number_of_parties: "Number of parties",
    circuit_form: "Circuit",
    math_structure: "Math structure",
    secret_sharing: "Secret Sharing",
    preprocessing: "Preprocessing",
    adversary_behavior: "Adversary",
    corruption_strategy: "Corruption strategy",
    network_model: "Network",
    channel_model: "Channel",
    corruption_threshold: "Threshold",
    security_goal: "Security goal",
  };
  const parts = Object.entries(options).map(([key, value]) => `${labels[key]}=${value}`);
  return parts.length ? `Structured options: ${parts.join("; ")}` : "";
}

function clearStructuredOptions() {
  for (const control of elements.optionControls) {
    control.value = "";
  }
  elements.requestState.textContent = elements.messageInput.value.trim() ? "Ready to send" : "Waiting for input";
  showToast("Options cleared");
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || `${response.status} ${response.statusText}`);
  }
  return payload;
}

function addMessage(role, text) {
  const item = document.createElement("article");
  item.className = `message ${role}`;
  const paragraph = document.createElement("p");
  paragraph.textContent = text;
  item.append(paragraph);
  elements.messages.append(item);
  elements.messages.scrollTop = elements.messages.scrollHeight;
}

function setList(container, items) {
  container.innerHTML = "";
  if (!items || items.length === 0) {
    container.textContent = "None";
    container.classList.add("empty");
    return;
  }
  container.classList.remove("empty");
  for (const item of items) {
    const row = document.createElement("div");
    row.className = "list-item";
    row.textContent = item;
    container.append(row);
  }
}

function setChips(container, items) {
  container.innerHTML = "";
  for (const item of items || []) {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.textContent = item;
    container.append(chip);
  }
}

function setKeyValues(container, entries) {
  container.innerHTML = "";
  for (const [label, value] of entries) {
    const row = document.createElement("div");
    row.className = "field-row";
    const name = document.createElement("span");
    name.textContent = label;
    const content = document.createElement("strong");
    content.textContent = valueOrDash(value);
    row.append(name, content);
    container.append(row);
  }
}

function flattenedFields(config) {
  if (!config) return [];
  return [
    ["Task intent", config.task_intent],
    ["Number of parties", config.participant_scale?.number_of_parties],
    ["Party roles", config.participant_scale?.party_roles],
    ["Input owners", config.participant_scale?.input_owners],
    ["Compute parties", config.participant_scale?.compute_parties],
    ["Output recipients", config.participant_scale?.output_recipients],
    ["Circuit form", config.circuit?.form],
    ["Circuit representation", config.circuit?.representation],
    ["Gate types", config.circuit?.gate_types],
    ["Math structure", config.math_structure?.structure],
    ["Modulus", config.math_structure?.modulus],
    ["Bit length", config.math_structure?.bit_length],
    ["Numeric domain", config.math_structure?.numeric_domain],
    ["Secret sharing", config.secret_sharing?.scheme],
    ["Sharing threshold", config.secret_sharing?.threshold],
    ["Authentication", config.secret_sharing?.mac_or_authentication],
    ["Preprocessing", config.preprocessing?.enabled],
    ["Preprocessing materials", config.preprocessing?.materials],
    ["Generation method", config.preprocessing?.generation_method],
    ["Adversary behavior", config.adversary?.behavior_model],
    ["Corruption strategy", config.adversary?.corruption_strategy],
    ["Corruption threshold", config.adversary?.corruption_threshold],
    ["Network model", config.network?.synchrony],
    ["Channels", config.network?.channels],
    ["Topology", config.network?.topology],
    ["Privacy", config.security_goals?.privacy],
    ["Correctness", config.security_goals?.correctness],
    ["Robustness", config.security_goals?.robustness],
    ["Fairness", config.security_goals?.fairness],
    ["Composability", config.security_goals?.composability],
    ["Protocol family", config.recommendation?.family],
  ];
}

function renderResponse(data) {
  state.lastResponse = data;
  state.sessionId = data.session_id;

  const config = data.current_mpc_config || data.config || {};
  elements.sessionLabel.textContent = state.sessionId ? `Session ${state.sessionId}` : "New session";
  elements.metricParties.textContent = valueOrDash(config.participant_scale?.number_of_parties);
  elements.metricCircuit.textContent = valueOrDash(config.circuit?.form);
  elements.metricAdversary.textContent = valueOrDash(config.adversary?.behavior_model);
  elements.metricConfidence.textContent =
    config.confidence === null || config.confidence === undefined
      ? "-"
      : `${Math.round(config.confidence * 100)}%`;

  const recommendation = config.recommendation || {};
  elements.recommendationText.textContent =
    recommendation.rationale || recommendation.family || "Not generated yet.";
  setChips(elements.targetList, recommendation.implementation_targets);

  setKeyValues(elements.securityList, [
    ["Privacy", config.security_goals?.privacy],
    ["Correctness", config.security_goals?.correctness],
    ["Robustness", config.security_goals?.robustness],
    ["Fairness", config.security_goals?.fairness],
    ["Guaranteed output", config.security_goals?.guaranteed_output_delivery],
  ]);

  setList(elements.missingList, data.missing_fields || []);
  setList(elements.conflictList, config.conflicts || []);
  setList(elements.questionList, data.clarifying_questions || []);
  setKeyValues(elements.detailGrid, flattenedFields(config));
  elements.jsonOutput.textContent = prettyJson(config);
  loadBackendPlan();
}

function renderBackendPlan(plan) {
  state.backendPlan = plan;
  const selected = plan?.selected;
  elements.backendName.textContent = valueOrDash(selected?.display_name);
  elements.backendProtocol.textContent = valueOrDash(selected?.protocol);
  elements.backendScore.textContent =
    selected?.score === null || selected?.score === undefined
      ? "-"
      : `${Math.round(selected.score * 100)}%`;
  const reasons = [
    ...(selected?.reasons || []),
    ...(selected?.warnings || []).map((warning) => `Warning: ${warning}`),
  ];
  setList(elements.backendReasons, reasons);
  setList(elements.backendSteps, plan?.execution_plan?.steps || []);
}

async function loadBackendPlan() {
  if (!state.sessionId) {
    renderBackendPlan(null);
    return;
  }
  try {
    const plan = await fetchJson(`/sessions/${state.sessionId}/backend-plan`, {
      method: "POST",
      body: JSON.stringify({}),
    });
    renderBackendPlan(plan);
  } catch (error) {
    setList(elements.backendReasons, [`Backend selection failed: ${error.message}`]);
    setList(elements.backendSteps, []);
  }
}

async function loadHealth() {
  try {
    const health = await fetchJson("/health");
    elements.serviceStatus.textContent = `${health.status} · ${health.model}`;
  } catch (error) {
    elements.serviceStatus.textContent = "Service unavailable";
    showToast(error.message);
  }
}

async function sendMessage(message, structuredOptions) {
  setBusy(true);
  const optionSummary = structuredOptionsSummary(structuredOptions);
  addMessage("user", [message, optionSummary].filter(Boolean).join("\n") || "Submitted structured options");
  try {
    const payload = {
      message,
      session_id: state.sessionId,
      reset: false,
    };
    if (hasStructuredOptions(structuredOptions)) {
      payload.structured_options = structuredOptions;
    }
    const data = await fetchJson("/chat", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    renderResponse(data);
    addMessage("assistant", data.agent_reply?.message || data.summary || "Configuration updated.");
    elements.messageInput.value = "";
    showToast("Configuration generated");
  } catch (error) {
    addMessage("assistant", `Request failed: ${error.message}`);
    showToast("Request failed");
  } finally {
    setBusy(false);
  }
}

async function resetSession() {
  if (!state.sessionId) {
    state.lastResponse = null;
    state.backendPlan = null;
    elements.sessionLabel.textContent = "New session";
    elements.messages.innerHTML = "";
    addMessage("assistant", "New session is ready.");
    renderBackendPlan(null);
    showToast("Reset complete");
    return;
  }

  try {
    await fetchJson(`/sessions/${state.sessionId}/reset`, { method: "POST" });
    state.sessionId = null;
    state.lastResponse = null;
    state.backendPlan = null;
    elements.sessionLabel.textContent = "New session";
    elements.messages.innerHTML = "";
    addMessage("assistant", "New session is ready.");
    renderBackendPlan(null);
    showToast("Reset complete");
  } catch (error) {
    showToast(error.message);
  }
}

async function openSchema() {
  try {
    if (!state.schema) {
      state.schema = await fetchJson("/schema");
    }
    elements.schemaOutput.textContent = prettyJson(state.schema);
    elements.schemaDialog.showModal();
  } catch (error) {
    showToast(error.message);
  }
}

async function copyConfig() {
  const config = state.lastResponse?.current_mpc_config || state.lastResponse?.config;
  if (!config) {
    showToast("No configuration yet");
    return;
  }
  await navigator.clipboard.writeText(prettyJson(config));
  showToast("JSON copied");
}

function downloadConfig() {
  const config = state.lastResponse?.current_mpc_config || state.lastResponse?.config;
  if (!config) {
    showToast("No configuration yet");
    return;
  }
  const blob = new Blob([prettyJson(config)], {
    type: "application/json;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `mpc-config-${state.sessionId || "draft"}.json`;
  link.click();
  URL.revokeObjectURL(url);
}

function setActiveTab(name) {
  for (const tab of elements.tabs) {
    const active = tab.dataset.tab === name;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", String(active));
  }
  for (const [panelName, panel] of Object.entries(elements.panels)) {
    panel.classList.toggle("hidden", panelName !== name);
  }
}

elements.chatForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const message = elements.messageInput.value.trim();
  const structuredOptions = getStructuredOptions();
  if ((!message && !hasStructuredOptions(structuredOptions)) || state.sending) {
    showToast("Enter a requirement or choose options");
    return;
  }
  sendMessage(message, structuredOptions);
});

elements.resetButton.addEventListener("click", resetSession);
elements.clearOptionsButton.addEventListener("click", clearStructuredOptions);
elements.refreshBackendButton.addEventListener("click", loadBackendPlan);
elements.schemaButton.addEventListener("click", openSchema);
elements.closeSchemaButton.addEventListener("click", () => elements.schemaDialog.close());
elements.copyButton.addEventListener("click", copyConfig);
elements.downloadButton.addEventListener("click", downloadConfig);

for (const tab of elements.tabs) {
  tab.addEventListener("click", () => setActiveTab(tab.dataset.tab));
}

elements.messageInput.addEventListener("input", () => {
  elements.requestState.textContent = elements.messageInput.value.trim() ? "Ready to send" : "Waiting for input";
});

for (const control of elements.optionControls) {
  control.addEventListener("change", () => {
    const options = getStructuredOptions();
    elements.requestState.textContent =
      elements.messageInput.value.trim() || hasStructuredOptions(options) ? "Ready to send" : "Waiting for input";
  });
}

loadHealth();
