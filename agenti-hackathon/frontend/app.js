const state = {
  incidents: [],
  stats: {},
  selectedId: null,
  loading: false,
  notice: "Ready.",
  noticeType: "",
};

const els = {
  connection: document.querySelector("#connection"),
  incidentList: document.querySelector("#incidentList"),
  incidentCount: document.querySelector("#incidentCount"),
  detailPanel: document.querySelector("#detailPanel"),
  agentGridPanel: document.querySelector("#agentGridPanel"),
  totalCount: document.querySelector("#totalCount"),
  openCount: document.querySelector("#openCount"),
  investigatingCount: document.querySelector("#investigatingCount"),
  mitigatedCount: document.querySelector("#mitigatedCount"),
  attentionCount: document.querySelector("#attentionCount"),
  notice: document.querySelector("#notice"),
  refreshBtn: document.querySelector("#refreshBtn"),
  agentsSection: document.querySelector("#agents"),
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function setNotice(message, type = "") {
  state.notice = message;
  state.noticeType = type;
  if (els.notice) {
    els.notice.querySelector('.notice-text').textContent = message;
    els.notice.className = `notice-bar ${type}`.trim();
  }
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const text = await response.text();
  const payload = text ? JSON.parse(text) : {};
  if (!response.ok) {
    throw new Error(payload.error || `API request failed: ${response.status}`);
  }
  return payload;
}

async function refresh() {
  state.loading = true;
  render();
  try {
    const payload = await api("/api/incidents");
    applySnapshot(payload);
    setNotice("Incident data refreshed.");
  } catch (error) {
    setNotice(error.message, "error");
  } finally {
    state.loading = false;
    render();
  }
}

function applySnapshot(payload) {
  state.incidents = payload.incidents || [];
  state.stats = payload.stats || {};
  if (!state.selectedId && state.incidents.length) {
    state.selectedId = state.incidents[0].id;
  }
  if (!state.incidents.some((incident) => incident.id === state.selectedId)) {
    state.selectedId = state.incidents[0]?.id || null;
  }
  render();
}

function selectedIncident() {
  return state.incidents.find((incident) => incident.id === state.selectedId);
}

function listHtml(items, emptyMessage, className = "detail-list") {
  const values = Array.isArray(items) ? items.filter(Boolean) : [];
  if (!values.length) {
    return `<p class="empty-copy">${escapeHtml(emptyMessage)}</p>`;
  }
  return `<ul class="${className}">${values.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
}

function impactHtml(impact) {
  const entries = Object.entries(impact || {});
  if (!entries.length) {
    return "";
  }
  return `
    <dl class="impact-list">
      ${entries
        .map(
          ([key, value]) => `
            <div>
              <dt>${escapeHtml(key.replaceAll("_", " "))}</dt>
              <dd>${escapeHtml(value)}</dd>
            </div>
          `,
        )
        .join("")}
    </dl>
  `;
}

function planGroupHtml(title, items) {
  if (!Array.isArray(items) || !items.length) {
    return "";
  }
  return `
    <div class="plan-group">
      <strong>${escapeHtml(title)}</strong>
      ${listHtml(items, "", "detail-list compact")}
    </div>
  `;
}

function auditLogHtml(auditLog) {
  if (!Array.isArray(auditLog) || !auditLog.length) {
    return '<p class="empty-copy">No remediation simulation has been recorded yet.</p>';
  }
  return `
    <ul class="audit-list">
      ${auditLog
        .map(
          (entry) => `
            <li>
              <strong>${escapeHtml(entry.title)}</strong>
              <span>${escapeHtml(entry.applied_at)}</span>
              <p>${escapeHtml(entry.result)}</p>
            </li>
          `,
        )
        .join("")}
    </ul>
  `;
}

function recommendationHtml(rec) {
  return `
    <div class="recommendation">
      <div class="recommendation-header">
        <h3>${escapeHtml(rec.title)}</h3>
        <span class="risk ${escapeHtml(rec.risk)}">${escapeHtml(rec.risk)} risk</span>
      </div>
      <p>${escapeHtml(rec.rationale)}</p>
      <div class="safety-score"><strong>Safety score:</strong> ${Math.round(Number(rec.safety_score || 0) * 100)}%</div>
      <code>${escapeHtml(rec.command)}</code>
      ${impactHtml(rec.expected_impact)}
      ${planGroupHtml("Blast-radius risks", rec.blast_radius)}
      ${planGroupHtml("Staged rollout plan", rec.rollout_plan)}
      ${planGroupHtml("Post-action checks", rec.verification_checks)}
      <div class="recommendation-footer">
        <button class="secondary-button apply-btn" type="button" data-rec="${escapeHtml(rec.id)}" ${rec.applied ? "disabled" : ""}>
          ${rec.applied ? "Applied" : "Apply"}
        </button>
      </div>
    </div>
  `;
}

function render() {
  els.totalCount.textContent = state.stats.total ?? state.incidents.length;
  els.openCount.textContent = state.stats.open ?? 0;
  els.investigatingCount.textContent = state.stats.investigating ?? 0;
  els.mitigatedCount.textContent = state.stats.mitigated ?? 0;
  els.attentionCount.textContent = state.stats.needs_attention ?? state.stats.critical ?? 0;
  els.incidentCount.textContent = `${state.incidents.length} total`;
  els.refreshBtn.disabled = state.loading;
  
  if (els.notice.querySelector('.notice-text').textContent !== state.notice) {
    setNotice(state.notice, state.noticeType);
  }
  renderIncidentList();
  renderDetailAndAgents();
}

function renderIncidentList() {
  if (!state.incidents.length) {
    els.incidentList.innerHTML = '<div class="empty-state" style="min-height:200px">No incidents found.</div>';
    return;
  }
  els.incidentList.innerHTML = state.incidents
    .map(
      (incident) => `
        <button class="incident-row ${incident.id === state.selectedId ? "selected" : ""}" type="button" data-id="${escapeHtml(incident.id)}">
          <div class="row-title">
            <strong>${escapeHtml(incident.title)}</strong>
            <span class="severity ${escapeHtml(incident.severity).toLowerCase()}">${escapeHtml(incident.severity)}</span>
          </div>
          <div class="meta">
            <span>${escapeHtml(incident.service)}</span>
            <span>${escapeHtml(incident.region)}</span>
            <span class="status ${escapeHtml(incident.status).toLowerCase()}">${escapeHtml(incident.status)}</span>
          </div>
        </button>
      `,
    )
    .join("");

  els.incidentList.querySelectorAll(".incident-row").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedId = button.dataset.id;
      render();
    });
  });
}

function renderDetailAndAgents() {
  const incident = selectedIncident();
  if (!incident) {
    els.detailPanel.innerHTML = '<div class="empty-state">Select an incident to inspect the RCA evidence chain.</div>';
    els.agentsSection.style.display = "none";
    return;
  }

  const rootCause = incident.root_causes?.[0];
  const confidence = Math.round((rootCause?.confidence || 0) * 100);
  const progress = `${confidence}%`;
  const evidence = rootCause?.evidence?.length ? rootCause.evidence : ["Run investigation to generate evidence chain."];
  const affected = rootCause?.affected_services?.join(", ") || incident.service;
  const factors = rootCause?.confidence_factors || {};
  const alternatives = rootCause?.alternatives || [];
  const timeline = incident.timeline?.length ? incident.timeline : ["Run investigation to build the correlation timeline."];

  // Detail Panel HTML
  els.detailPanel.innerHTML = `
    <div class="detail-header">
      <div>
        <h2>${escapeHtml(incident.title)}</h2>
        <p>${escapeHtml(incident.summary)}</p>
        <div class="meta">
          <span>${escapeHtml(incident.id)}</span>
          <span>${escapeHtml(incident.team)}</span>
          <span>${escapeHtml(incident.started_at)}</span>
          <span class="status ${escapeHtml(incident.status).toLowerCase()}">${escapeHtml(incident.status)}</span>
        </div>
      </div>
      <div class="confidence" style="--progress: ${progress}">
        <div class="confidence-inner">
          <span class="value">${confidence}%</span>
          <span class="label">Confidence</span>
        </div>
      </div>
    </div>

    <section class="detail-section">
      <h3>Root Cause</h3>
      <p>${escapeHtml(rootCause?.hypothesis || "Investigation has not run yet.")}</p>
      <p class="meta" style="margin-top:8px">Affected services: ${escapeHtml(affected)}</p>
      <button id="investigateBtn" class="primary-button-glow" type="button" style="margin-top:16px">${incident.agent_findings?.length ? "Re-run investigation" : "Investigate"}</button>
    </section>

    <section class="detail-section">
      <h3>Confidence Factors</h3>
      <div class="agent-grid" style="grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));">
        ${
          Object.entries(factors)
            .map(
              ([key, value]) => `
                <div class="agent" style="padding:10px;">
                  <strong style="margin-bottom:4px;display:block">${escapeHtml(key.replaceAll("_", " "))}</strong>
                  <div class="agent-stats">
                     <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
                     ${Math.round(Number(value) * 100)}%
                  </div>
                </div>
              `,
            )
            .join("") || '<div class="agent"><strong>Pending</strong><p>Run investigation to calculate confidence factors.</p></div>'
        }
      </div>
    </section>

    <section class="detail-section" id="timeline">
      <h3>Correlation Timeline</h3>
      ${listHtml(timeline, "Run investigation to build the correlation timeline.", "timeline")}
    </section>

    <section class="detail-section">
      <h3>Evidence Chain</h3>
      ${listHtml(evidence, "Run investigation to generate evidence chain.", "evidence")}
    </section>

    <section class="detail-section">
      <h3>Alternative Hypotheses</h3>
      ${listHtml(alternatives, "No alternative hypotheses have been generated yet.", "evidence")}
    </section>

    <section class="detail-section" id="actions">
      <h3>Recommended Actions</h3>
      <div class="recommendation-grid">
        ${(incident.recommendations || [])
          .map((rec) => recommendationHtml(rec))
          .join("") || '<div class="recommendation"><h3>No actions yet</h3><p>Run investigation to generate remediation options.</p></div>'}
      </div>
    </section>

    <section class="detail-section">
      <h3>Audit Log</h3>
      ${auditLogHtml(incident.audit_log)}
    </section>
  `;

  // Agent Grid Panel HTML (Bottom Section)
  const agentIcons = {
    "Alert Intake Agent": `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"></path></svg>`,
    "Logs Intelligence Agent": `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="8" y1="13" x2="16" y2="13"></line><line x1="8" y1="17" x2="13" y2="17"></line></svg>`,
    "Metrics Analysis Agent": `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg>`,
    "Distributed Trace Agent": `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="18" cy="18" r="3"></circle><circle cx="6" cy="6" r="3"></circle><path d="M13 6h3a2 2 0 0 1 2 2v7"></path><line x1="6" y1="9" x2="6" y2="21"></line></svg>`,
    "Deployment Analysis Agent": `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path></svg>`,
    "Correlation Engine Agent": `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"></circle><line x1="3" y1="12" x2="9" y2="12"></line><line x1="15" y1="12" x2="21" y2="12"></line><line x1="12" y1="3" x2="12" y2="9"></line><line x1="12" y1="15" x2="12" y2="21"></line></svg>`,
    "Root Cause Analysis Agent": `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><circle cx="12" cy="12" r="6"></circle><circle cx="12" cy="12" r="2"></circle></svg>`,
    "Recommendation Agent": `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18h6M10 22h4M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path></svg>`
  };

  const getAgentIcon = (name) => agentIcons[name] || agentIcons["Recommendation Agent"];

  els.agentsSection.style.display = "block";
  els.agentGridPanel.innerHTML = `
    <div class="agent-grid">
      ${(incident.agent_findings || [])
        .map(
          (finding) => `
            <div class="agent">
              <div class="agent-header">
                <div class="agent-icon">${getAgentIcon(finding.agent)}</div>
                <strong>${escapeHtml(finding.agent)}</strong>
              </div>
              <p>${escapeHtml(finding.summary)}</p>
              <div class="agent-stats">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
                ${Math.round(finding.confidence * 100)}% <span>&middot; ${Number(finding.duration_ms || 0)}ms</span>
              </div>
              ${finding.error ? `<p style="color:var(--danger)">${escapeHtml(finding.error)}</p>` : ""}
            </div>
          `,
        )
        .join("") || '<div class="empty-state" style="grid-column: 1 / -1; min-height:100px;">Run investigation to activate the multi-agent workflow.</div>'}
    </div>
  `;

  // Attach event listeners
  document.querySelector("#investigateBtn").addEventListener("click", async () => {
    try {
      setNotice("Investigation running.");
      const updated = await api(`/api/incidents/${incident.id}/investigate`, { method: "POST" });
      state.selectedId = updated.id;
      await refresh();
      setNotice("Investigation completed with RCA evidence.", "success");
    } catch (error) {
      setNotice(error.message, "error");
    }
  });

  document.querySelectorAll(".apply-btn").forEach((button) => {
    button.addEventListener("click", async () => {
      const recommendation = incident.recommendations.find((item) => item.id === button.dataset.rec);
      const confirmed = window.confirm(`Record simulated remediation for "${recommendation?.title || "this action"}"? No infrastructure command will be executed.`);
      if (!confirmed) {
        return;
      }
      try {
        const idempotencyKey = window.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`;
        await api("/api/remediate", {
          method: "POST",
          body: JSON.stringify({
            incident_id: incident.id,
            recommendation_id: button.dataset.rec,
            idempotency_key: idempotencyKey,
          }),
        });
        await refresh();
        setNotice("Remediation simulation recorded in the audit log.", "success");
      } catch (error) {
        setNotice(error.message, "error");
      }
    });
  });
}

function connectWebSocket() {
  const socket = new WebSocket(`ws://${window.location.host}/ws`);
  socket.addEventListener("open", () => {
    els.connection.innerHTML = `<span class="status-dot"></span>Live updates connected <svg class="wifi-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.55a11 11 0 0 1 14.08 0"></path><path d="M1.42 9a16 16 0 0 1 21.16 0"></path><path d="M8.53 16.11a6 6 0 0 1 6.95 0"></path><line x1="12" y1="20" x2="12.01" y2="20"></line></svg>`;
  });
  socket.addEventListener("message", (event) => {
    applySnapshot(JSON.parse(event.data));
  });
  socket.addEventListener("close", () => {
    els.connection.innerHTML = `<span class="status-dot" style="background:var(--warning); box-shadow:none; animation:none"></span>Reconnecting... <svg class="wifi-icon" style="color:var(--warning)" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="1" y1="1" x2="23" y2="23"></line><path d="M16.72 11.06A10.94 10.94 0 0 1 19 12.55"></path><path d="M5 12.55a10.94 10.94 0 0 1 5.17-2.39"></path><path d="M10.71 5.05A16 16 0 0 1 22.58 9"></path><path d="M1.42 9a15.91 15.91 0 0 1 4.7-2.88"></path><path d="M8.53 16.11a6 6 0 0 1 6.95 0"></path><line x1="12" y1="20" x2="12.01" y2="20"></line></svg>`;
    setTimeout(connectWebSocket, 1200);
  });
  socket.addEventListener("error", () => {
    // handled by close
  });
}

document.querySelectorAll(".sidebar nav a").forEach((link) => {
  link.addEventListener("click", (event) => {
    const targetId = link.getAttribute("href")?.slice(1);
    const target = targetId ? document.getElementById(targetId) : null;
    if (target) {
      event.preventDefault();
      target.scrollIntoView({ behavior: "smooth", block: "start" });
      history.replaceState(null, "", `#${targetId}`);
    }
    document.querySelectorAll(".sidebar nav a").forEach((item) => item.classList.remove("active"));
    link.classList.add("active");
  });
});

els.refreshBtn.addEventListener("click", refresh);
refresh();
connectWebSocket();
