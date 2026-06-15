const form = document.getElementById("configForm");
const submitBtn = document.getElementById("submitBtn");
const clearBtn = document.getElementById("clearBtn");
const statusEl = document.getElementById("status");
const runModeHintEl = document.getElementById("runModeHint");
const resultPanel = document.getElementById("resultPanel");
const optionGroupsEl = document.getElementById("optionGroups");

const parsedResult = document.getElementById("parsedResult");
const candidateResult = document.getElementById("candidateResult");
const deepseekResult = document.getElementById("deepseekResult");
const finalResult = document.getElementById("finalResult");
const execResult = document.getElementById("execResult");

const summaryProtocol = document.getElementById("summaryProtocol");
const summaryDeepseek = document.getElementById("summaryDeepseek");
const summaryExecution = document.getElementById("summaryExecution");
const summaryTimestamp = document.getElementById("summaryTimestamp");

const insightMain = document.getElementById("insightMain");
const insightCompatibility = document.getElementById("insightCompatibility");
const insightExecution = document.getElementById("insightExecution");
const insightDeepseek = document.getElementById("insightDeepseek");
const insightNext = document.getElementById("insightNext");

const exampleButtons = document.querySelectorAll(".example-btn[data-example]");

const requirementEl = document.getElementById("requirement");
const partiesEl = document.getElementById("parties");
const executeEl = document.getElementById("execute");
const runtimeBackendEl = document.getElementById("runtime_backend");
const mpspdzHomeEl = document.getElementById("mpspdz_home");
const spuHomeEl = document.getElementById("spu_home");
const spuPythonEl = document.getElementById("spu_python");
const programNameEl = document.getElementById("program_name");
const timeoutEl = document.getElementById("timeout_seconds");
const mpcProgramEl = document.getElementById("mpc_program");

const EXAMPLES = {
  sum: "3 方联合求和，恶意安全，希望在线阶段带宽更省，最好支持预处理。",
  compare: "two-party millionaire comparison with malicious security and low latency",
  ml: "多方隐私推理，希望以算术电路为主，带宽敏感，优先选择可工程化部署的协议。",
};

const PROTOCOL_LABELS = {
  mascot: "MASCOT（多方、恶意安全、算术计算）",
  yao: "Yao（两方、低延迟、布尔电路）",
  bmr: "BMR（多方、布尔电路、常数轮）",
  shamir: "Shamir/BGW（多方、诚实多数）",
  semi2k: "Semi2k（多方、半诚实、环上算术）",
  gmw: "GMW（多方、布尔/算术混合）",
  spu_aby3: "SecretFlow SPU ABY3（3PC、半诚实、replicated）",
  spu_cheetah: "SecretFlow SPU Cheetah（2PC、半诚实、高速）",
  spu_semi2k: "SecretFlow SPU Semi2k（半诚实、多方、调试向）",
};

const EXEC_STATUS_LABELS = {
  skipped: "未执行（仅生成配置）",
  success: "执行成功",
  compile_only_success: "编译成功（未执行）",
  compile_failed: "编译失败",
  run_failed: "运行失败",
  error: "执行前检查失败",
};

const BACKEND_LABELS = {
  mp_spdz: "MP-SPDZ",
  secretflow_spu: "SecretFlow SPU",
};

let optionGroups = [];

function pretty(value) {
  return JSON.stringify(value, null, 2);
}

function setStatus(text, state = "idle") {
  statusEl.textContent = text;
  statusEl.dataset.state = state;
}

function updateRunModeHint() {
  const backend = runtimeBackendEl?.value || "auto";
  if (executeEl.value === "true") {
    if (backend === "secretflow_spu") {
      runModeHintEl.textContent = "将执行 SecretFlow SPU：通过独立 Python 环境调用 SPU 模拟器运行，需提供可用的 spu_python。";
    } else {
      runModeHintEl.textContent = "将执行 MP-SPDZ：会编译并运行协议脚本，耗时取决于程序复杂度。";
    }
  } else {
    runModeHintEl.textContent = "仅生成配置，不执行运行时后端，返回会更快。";
  }
}

function readableProtocol(protocolId) {
  if (!protocolId) return "-";
  return PROTOCOL_LABELS[protocolId] || protocolId;
}

function readableExecStatus(status) {
  if (!status) return "-";
  return EXEC_STATUS_LABELS[status] || status;
}

function readableBackend(backend) {
  if (!backend) return "-";
  return BACKEND_LABELS[backend] || backend;
}

function readableDeepseekSummary(deepseek) {
  if (!deepseek || !deepseek.enabled) {
    return "未启用（未配置 API Key 或未开启）";
  }
  if (deepseek.used) {
    return "已启用并参与决策";
  }
  return `已启用但未生效（${deepseek.reason || "未返回原因"}）`;
}

function normalizeReasonText(value) {
  if (value === null || value === undefined) return "";
  return String(value).replace(/\s+/g, " ").trim();
}

function isLauncherOnlyText(text) {
  const lines = String(text)
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  if (lines.length === 0) return false;

  const hasExplicitErrorSignal = /(error|failed|not found|timed out|traceback|exception|invalid|denied|too high|no such file|connection refused)/i.test(
    text,
  );
  if (hasExplicitErrorSignal) return false;

  return lines.every((line) => /^running\s+/i.test(line));
}

function pickExecutionReason(exec) {
  const candidates = [
    exec?.reason,
    exec?.run?.stderr,
    exec?.run?.stdout,
    exec?.compile?.stderr,
    exec?.compile?.stdout,
  ]
    .map(normalizeReasonText)
    .filter(Boolean);

  const meaningful = candidates.find((item) => !isLauncherOnlyText(item));
  return meaningful || candidates[0] || "请查看下方执行信息。";
}

function uniqueTexts(items) {
  return [...new Set(items.map((item) => normalizeReasonText(item)).filter(Boolean))];
}

function buildCompatibilitySummary(data) {
  const parsedNotes = Array.isArray(data?.parsed_requirement?.compatibility_notes)
    ? data.parsed_requirement.compatibility_notes
    : [];
  const finalNotes = Array.isArray(data?.final_configuration?.compatibility_notes)
    ? data.final_configuration.compatibility_notes
    : [];
  return uniqueTexts([...parsedNotes, ...finalNotes]);
}

function formatCompatibilitySummary(notes) {
  if (!notes.length) {
    return "当前未发现明显的结构化约束冲突。";
  }
  return notes.slice(0, 3).join("；");
}

function buildHumanInsights(data, requestedExecute) {
  const protocolId = data.final_configuration?.protocol_id || "-";
  const protocolLabel = readableProtocol(protocolId);
  const backend = data.final_configuration?.runner_backend || data.execution?.backend || "mp_spdz";
  const backendLabel = readableBackend(backend);
  const parties = data.parsed_requirement?.parties ?? "-";
  const security = data.parsed_requirement?.security_model || "-";
  const exec = data.execution || {};
  const execStatus = exec.status || "-";
  const execLabel = readableExecStatus(execStatus);
  const compatibilityNotes = buildCompatibilitySummary(data);

  insightMain.textContent = `系统推荐 ${protocolLabel}，执行后端为 ${backendLabel}。该结果综合考虑了 ${parties} 方、${security} 安全需求，以及你在结构化选项里给出的 MPC 约束。`;
  insightCompatibility.textContent = formatCompatibilitySummary(compatibilityNotes);

  if (execStatus === "success") {
    insightExecution.textContent = `本次任务已经完成真实执行，当前 ${backendLabel} 配置可以直接复用。`;
  } else if (execStatus === "skipped") {
    insightExecution.textContent = `本次仅生成配置，未触发 ${backendLabel} 执行。`;
  } else {
    const reason = pickExecutionReason(exec);
    insightExecution.textContent = `执行状态：${execLabel}。原因：${String(reason).slice(0, 180)}`;
  }

  insightDeepseek.textContent = readableDeepseekSummary(data.deepseek);

  if (compatibilityNotes.length > 0) {
    insightNext.textContent = "建议先处理兼容性提示里的约束冲突，再重新生成协议配置，这样候选排序会更稳定。";
    return;
  }

  if (!requestedExecute) {
    insightNext.textContent = "如果你要验证真实运行效果，可以把“是否立即执行运行时后端”切换为“是”后重新提交。";
    return;
  }
  if (execStatus === "success") {
    insightNext.textContent = "建议把当前 final_configuration 保存成模板，后续同类 MPC 任务可以直接复用。";
  } else if (execStatus === "compile_failed") {
    insightNext.textContent = "优先检查 mpc_program 语法和 compile.stderr，再重新提交。";
  } else if (execStatus === "run_failed") {
    insightNext.textContent = "优先检查运行脚本、参与方数量和 run.stderr/run.stdout；必要时先用 compile_only 验证编译链路。";
  } else if (execStatus === "error") {
    const reason = normalizeReasonText(exec?.reason).toLowerCase();
    if (backend === "secretflow_spu" && (reason.includes("spu_python") || reason.includes("no module named") || reason.includes("jax"))) {
      insightNext.textContent = "当前 SecretFlow SPU 环境还不可执行。请确认 `spu_python` 指向 Python 3.10/3.11，并且该环境已经安装 `spu`、`jax` 及其依赖。";
    } else if (reason.includes("not launchable") || reason.includes("missing protocol launch scripts")) {
      insightNext.textContent = "当前 MP-SPDZ 环境缺少所选协议的启动脚本或运行支持。可以改为仅生成配置，或补齐 Scripts/ 和对应 runtime binary。";
    } else {
      insightNext.textContent = backend === "secretflow_spu"
        ? "优先检查 SecretFlow SPU 路径、`spu_python` 解释器以及该解释器中的 `spu/jax` 安装情况。"
        : "优先检查 MP-SPDZ 路径、Programs/Source 目录以及环境变量 MPSPDZ_HOME。";
    }
  } else {
    insightNext.textContent = "如需排查，请查看下方原始执行信息中的 reason、stderr、stdout 字段。";
  }
}

function resetOutputs() {
  parsedResult.textContent = "";
  candidateResult.textContent = "";
  deepseekResult.textContent = "";
  finalResult.textContent = "";
  execResult.textContent = "";

  summaryProtocol.textContent = "-";
  summaryDeepseek.textContent = "-";
  summaryExecution.textContent = "-";
  summaryTimestamp.textContent = "-";

  insightMain.textContent = "-";
  insightCompatibility.textContent = "-";
  insightExecution.textContent = "-";
  insightDeepseek.textContent = "-";
  insightNext.textContent = "-";
}

function updateSummary(data) {
  summaryProtocol.textContent = readableProtocol(data.final_configuration?.protocol_id || "-");
  summaryDeepseek.textContent = data.deepseek?.enabled
    ? data.deepseek.used
      ? "已使用"
      : "未使用"
    : "未启用";
  summaryExecution.textContent = readableExecStatus(data.execution?.status || "-");
  summaryTimestamp.textContent = data.timestamp
    ? new Date(data.timestamp * 1000).toLocaleString()
    : "-";
}

function applyExample(key) {
  const text = EXAMPLES[key];
  if (!text) return;
  requirementEl.value = text;
  requirementEl.focus();
}

function resetStructuredSelections() {
  optionGroups.forEach((group) => {
    const select = form.elements[group.id];
    if (select) {
      select.value = "auto";
      updateOptionMeta(group.id);
    }
  });
}

function updateOptionMeta(groupId) {
  const select = form.elements[groupId];
  const hintEl = document.querySelector(`[data-option-hint="${groupId}"]`);
  const group = optionGroups.find((item) => item.id === groupId);
  if (!select || !hintEl || !group) return;
  const current = group.options.find((option) => option.value === select.value) || group.options[0];
  hintEl.textContent = current?.description || group.help || "";
}

function renderOptionGroups(groups) {
  optionGroups = Array.isArray(groups) ? groups : [];
  optionGroupsEl.innerHTML = "";

  optionGroups.forEach((group) => {
    const card = document.createElement("article");
    card.className = "option-card";

    const title = document.createElement("h3");
    title.textContent = group.label;
    card.appendChild(title);

    const help = document.createElement("p");
    help.className = "option-help";
    help.textContent = group.help || "";
    card.appendChild(help);

    const select = document.createElement("select");
    select.name = group.id;
    select.id = group.id;
    select.className = "option-select";
    select.dataset.optionField = group.id;

    (group.options || []).forEach((option) => {
      const optionEl = document.createElement("option");
      optionEl.value = option.value;
      optionEl.textContent = option.label;
      select.appendChild(optionEl);
    });

    select.addEventListener("change", () => updateOptionMeta(group.id));
    card.appendChild(select);

    const meta = document.createElement("p");
    meta.className = "select-meta";
    meta.dataset.optionHint = group.id;
    card.appendChild(meta);

    optionGroupsEl.appendChild(card);
    updateOptionMeta(group.id);
  });
}

async function loadRequirementOptions() {
  try {
    const response = await fetch("/api/requirement-options");
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data?.error || "加载结构化选项失败");
    }
    renderOptionGroups(data.option_groups || []);
  } catch (error) {
    optionGroupsEl.innerHTML = `<div class="structured-empty">结构化选项加载失败：${error.message}</div>`;
  }
}

function collectStructuredPayload() {
  return optionGroups.reduce((payload, group) => {
    const select = form.elements[group.id];
    if (!select) return payload;
    const value = String(select.value || "").trim();
    if (value && value !== "auto") {
      payload[group.id] = value;
    }
    return payload;
  }, {});
}

function hasStructuredSelection(payload) {
  return Object.keys(payload).length > 0;
}

exampleButtons.forEach((btn) => {
  btn.addEventListener("click", () => applyExample(btn.dataset.example));
});

executeEl.addEventListener("change", updateRunModeHint);
runtimeBackendEl.addEventListener("change", updateRunModeHint);

clearBtn.addEventListener("click", () => {
  form.reset();
  resetStructuredSelections();
  updateRunModeHint();
  resetOutputs();
  setStatus("已清空输入，请重新填写需求。", "idle");
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  submitBtn.disabled = true;

  const structuredPayload = collectStructuredPayload();
  const requirement = requirementEl.value.trim();
  if (!requirement && !hasStructuredSelection(structuredPayload)) {
    setStatus("请至少填写一段需求描述，或选择一项结构化 MPC 属性。", "error");
    submitBtn.disabled = false;
    return;
  }

  setStatus("正在分析需求并生成配置，请稍候...", "loading");

  const payload = {
    requirement,
    execute: executeEl.value === "true",
    ...structuredPayload,
  };

  const parties = partiesEl.value.trim();
  if (parties) payload.parties = Number(parties);

  const mpspdzHome = mpspdzHomeEl.value.trim();
  if (mpspdzHome) payload.mpspdz_home = mpspdzHome;

  const runtimeBackend = runtimeBackendEl.value.trim();
  if (runtimeBackend && runtimeBackend !== "auto") payload.runtime_backend = runtimeBackend;

  const spuHome = spuHomeEl.value.trim();
  if (spuHome) payload.spu_home = spuHome;

  const spuPython = spuPythonEl.value.trim();
  if (spuPython) payload.spu_python = spuPython;

  const programName = programNameEl.value.trim();
  if (programName) payload.program_name = programName;

  const timeout = timeoutEl.value.trim();
  if (timeout) payload.timeout_seconds = Number(timeout);

  const program = mpcProgramEl.value.trim();
  if (program) payload.mpc_program = program;

  try {
    const response = await fetch("/api/configure", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(pretty(data));
    }

    parsedResult.textContent = pretty(data.parsed_requirement);
    candidateResult.textContent = pretty(data.candidates);
    deepseekResult.textContent = pretty(data.deepseek);
    finalResult.textContent = pretty(data.final_configuration);
    execResult.textContent = pretty(data.execution);

    updateSummary(data);
    buildHumanInsights(data, payload.execute);

    const execStatus = data.execution?.status || "unknown";
    if (payload.execute && execStatus !== "success") {
      setStatus(`已返回配置，但执行状态为 ${readableExecStatus(execStatus)}。`, "warning");
    } else {
      setStatus("完成：已生成结果。", "success");
    }

    resultPanel.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    setStatus(`请求失败：${error.message}`, "error");
  } finally {
    submitBtn.disabled = false;
  }
});

resetOutputs();
updateRunModeHint();
loadRequirementOptions();
