const workflowListEl = document.getElementById("workflow-list");
const emptyStateEl = document.getElementById("empty-state");
const detailEl = document.getElementById("workflow-detail");
const workspaceEl = document.getElementById("workspace");
const btnRefresh = document.getElementById("btn-refresh");
const issueModal = document.getElementById("issue-modal");
const modalClose = document.getElementById("modal-close");

let activeSlug = null;

const STATUS_LABELS = {
  pending: "等待",
  in_progress: "进行中",
  done: "完成",
  blocked: "阻塞",
  skipped: "跳过",
};

async function fetchJson(url) {
  const res = await fetch(url);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

function statusClass(status) {
  return `status-${status.replace("-", "_")}`;
}

function renderWorkflowList(workflows) {
  workflowListEl.innerHTML = "";
  if (!workflows.length) {
    workflowListEl.innerHTML =
      '<li class="workflow-item-meta" style="padding:0.75rem">暂无工作流<br>运行 agent prd 创建</li>';
    return;
  }
  for (const wf of workflows) {
    const li = document.createElement("li");
    li.className = "workflow-item" + (wf.slug === activeSlug ? " active" : "");
    li.dataset.slug = wf.slug;
    li.innerHTML = `
      <div class="workflow-item-title">${escapeHtml(wf.title)}</div>
      <div class="workflow-item-meta">${wf.issue_done}/${wf.issue_total} Issues · ${wf.current_step}</div>
      <div class="progress-bar"><div class="progress-fill" style="width:${wf.progress_percent}%"></div></div>
    `;
    li.addEventListener("click", () => selectWorkflow(wf.slug));
    workflowListEl.appendChild(li);
  }
}

function renderSteps(steps) {
  const container = document.getElementById("steps");
  container.innerHTML = steps
    .map(
      (s, index) => `
    <div class="step-wrap">
      <div class="step ${s.status}" data-step="${escapeHtml(s.key)}">
        <div class="step-num">${index + 1}</div>
        <div class="step-label">${escapeHtml(s.label)}</div>
        <div class="step-status">${STATUS_LABELS[s.status] || s.status}</div>
        <div class="step-detail">${escapeHtml(s.detail || "")}</div>
      </div>
      ${index < steps.length - 1 ? '<div class="step-connector" aria-hidden="true"></div>' : ""}
    </div>
  `
    )
    .join("");
}

function renderLoopBanner(checkpoint) {
  const banner = document.getElementById("loop-banner");
  if (!checkpoint || !checkpoint.completed || !checkpoint.completed.length) {
    banner.classList.add("hidden");
    banner.innerHTML = "";
    return;
  }
  banner.classList.remove("hidden");
  banner.innerHTML = `
    <strong>Loop Checkpoint</strong>
    已完成 ${checkpoint.completed.length} 个 Issue
    (${checkpoint.completed.join(", ")})
    · 更新于 ${escapeHtml(checkpoint.updated_at || "—")}
  `;
}

function renderIssues(issues) {
  const tbody = document.getElementById("issues-body");
  if (!issues.length) {
    tbody.innerHTML = '<tr><td colspan="8" style="color:var(--text-muted)">暂无 Issue</td></tr>';
    return;
  }
  tbody.innerHTML = issues
    .map(
      (issue) => `
    <tr>
      <td><code>${escapeHtml(issue.id)}</code></td>
      <td>${escapeHtml(issue.title)}</td>
      <td><span class="status-pill ${statusClass(issue.status)}">${issue.status}</span></td>
      <td>${issue.review_status || "—"}</td>
      <td>${issue.qa_status || "—"}</td>
      <td>${issue.approved ? "✓" : "—"}</td>
      <td>${issue.iteration_count}${issue.last_iteration_status ? ` (${issue.last_iteration_status})` : ""}${issue.resume_available ? ` <span class="resume-badge">↻${issue.resume_from_iteration || "?"}</span>` : ""}</td>
      <td><button type="button" class="btn-link" data-issue="${escapeHtml(issue.id)}">详情</button></td>
    </tr>
  `
    )
    .join("");

  tbody.querySelectorAll("[data-issue]").forEach((btn) => {
    btn.addEventListener("click", () => showIssueDetail(btn.dataset.issue));
  });
}

async function selectWorkflow(slug) {
  activeSlug = slug;
  emptyStateEl.classList.add("hidden");
  detailEl.classList.remove("hidden");

  document.querySelectorAll(".workflow-item").forEach((el) => {
    el.classList.toggle("active", el.dataset.slug === slug);
  });

  const data = await fetchJson(`/api/workflows/${encodeURIComponent(slug)}`);
  document.getElementById("wf-title").textContent = data.title;
  document.getElementById("wf-slug").textContent = data.slug;
  document.getElementById("wf-desc").textContent = data.description || "";
  const archivedBadge = document.getElementById("wf-archived");
  if (data.archived) {
    archivedBadge.classList.remove("hidden");
  } else {
    archivedBadge.classList.add("hidden");
  }
  renderSteps(data.steps);
  renderLoopBanner(data.loop_checkpoint);
  renderIssues(data.issues);
}

async function showIssueDetail(issueId) {
  const data = await fetchJson(`/api/issues/${encodeURIComponent(issueId)}`);
  document.getElementById("modal-title").textContent = `${issueId}: ${data.issue.title}`;
  const body = document.getElementById("modal-body");

  let html = `
    <p><strong>状态:</strong> ${data.issue.status} · <strong>验证:</strong> <code>${escapeHtml(data.issue.verify_command)}</code></p>
    <h4>描述</h4><p>${escapeHtml(data.description)}</p>
    <h4>验收标准</h4><ul>${(data.acceptance_criteria || []).map((c) => `<li>${escapeHtml(c)}</li>`).join("")}</ul>
  `;

  if (data.review) {
    html += `<h4>Review (${data.review.status})</h4><pre>${escapeHtml(JSON.stringify(data.review.findings, null, 2))}</pre>`;
  }
  if (data.qa) {
    html += `<h4>QA (${data.qa.status})</h4><p>${escapeHtml(data.qa.summary || "")}</p>`;
  }
  if (data.iterations && data.iterations.length) {
    html += `<h4>Autoresearch 迭代 (${data.iterations.length})</h4>`;
    html += data.iterations
      .map(
        (it) =>
          `<div class="iter-row iter-${it.status}">#${it.iteration} ${it.status} exit=${it.exit_code} ${escapeHtml((it.error_summary || "").slice(0, 80))}</div>`
      )
      .join("");
  }
  if (data.autoresearch_state && Object.keys(data.autoresearch_state).length) {
    html += `<h4>Checkpoint</h4><pre>${escapeHtml(JSON.stringify(data.autoresearch_state, null, 2))}</pre>`;
    if (data.autoresearch_state.status === "running") {
      html += `<p class="resume-hint">可运行: <code>agent research resume ${escapeHtml(issueId)}</code></p>`;
    }
  }
  if (data.issue.approved) {
    html += `<p><strong>Approve:</strong> 已授权</p>`;
  }

  body.innerHTML = html;
  issueModal.showModal();
}

function escapeHtml(text) {
  if (text == null) return "";
  const div = document.createElement("div");
  div.textContent = String(text);
  return div.innerHTML;
}

async function loadDashboard() {
  const health = await fetchJson("/api/health");
  workspaceEl.textContent = health.workspace;

  const { workflows } = await fetchJson("/api/workflows");
  renderWorkflowList(workflows);

  if (activeSlug) {
    await selectWorkflow(activeSlug);
  } else if (workflows.length === 1) {
    await selectWorkflow(workflows[0].slug);
  }
}

btnRefresh.addEventListener("click", loadDashboard);
modalClose.addEventListener("click", () => issueModal.close());
issueModal.addEventListener("click", (e) => {
  if (e.target === issueModal) issueModal.close();
});

loadDashboard().catch((err) => {
  workspaceEl.textContent = "加载失败: " + err.message;
});

setInterval(loadDashboard, 15000);
