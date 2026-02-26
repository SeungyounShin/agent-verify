#!/usr/bin/env python3
"""Generate a self-contained HTML viewer from experiment JSONL logs.

Usage:
    python scripts/trace_viewer.py results/qwen_vs_claude/v0_qwen_10.jsonl -o viewer.html
    python scripts/trace_viewer.py results/full_verified/v0_qwen_full.jsonl -o viewer.html
"""

import argparse
import html
import json
import sys
from pathlib import Path


def load_jsonl(path: str) -> list[dict]:
    events = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def group_by_task(events: list[dict]) -> dict[str, list[dict]]:
    """Group events by task_id, preserving order of first appearance."""
    tasks: dict[str, list[dict]] = {}
    for ev in events:
        tid = ev.get("task_id")
        if tid is None:
            continue
        if tid not in tasks:
            tasks[tid] = []
        tasks[tid].append(ev)
    return tasks


def get_task_summary(task_events: list[dict]) -> dict:
    """Extract summary info from a task's events."""
    summary = {
        "resolved": False,
        "completion_reason": "unknown",
        "iterations": 0,
        "total_tokens": 0,
        "tool_calls": 0,
        "wall_clock_seconds": 0,
        "has_content": False,
    }
    for ev in task_events:
        etype = ev.get("event")
        if etype == "run_end":
            result = ev.get("result", {})
            summary["resolved"] = result.get("resolved", False)
            summary["completion_reason"] = result.get("completion_reason", "unknown")
            summary["wall_clock_seconds"] = round(result.get("wall_clock_seconds", 0), 1)
        elif etype == "llm_call":
            summary["iterations"] = max(summary["iterations"], ev.get("iteration", 0))
            summary["total_tokens"] += ev.get("input_tokens", 0) + ev.get("output_tokens", 0)
            if ev.get("assistant_content"):
                summary["has_content"] = True
        elif etype == "tool_call":
            summary["tool_calls"] += 1
            if ev.get("tool_input") or ev.get("tool_result"):
                summary["has_content"] = True
    return summary


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Agent Trace Viewer — {{EXPERIMENT_ID}}</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
:root {
  --bg: #1a1b26; --bg2: #24283b; --bg3: #2f3349;
  --fg: #c0caf5; --fg2: #a9b1d6; --fg3: #565f89;
  --green: #9ece6a; --red: #f7768e; --yellow: #e0af68;
  --blue: #7aa2f7; --cyan: #7dcfff; --purple: #bb9af7;
  --orange: #ff9e64;
  --border: #3b4261;
}
body { font-family: 'SF Mono', 'Cascadia Code', 'Fira Code', monospace; background: var(--bg); color: var(--fg); display: flex; flex-direction: column; height: 100vh; font-size: 13px; }
a { color: var(--blue); }

/* Top stats bar */
.stats-bar { background: var(--bg2); border-bottom: 1px solid var(--border); padding: 10px 20px; display: flex; gap: 30px; align-items: center; flex-shrink: 0; }
.stats-bar .stat { display: flex; flex-direction: column; }
.stats-bar .stat-label { font-size: 10px; color: var(--fg3); text-transform: uppercase; letter-spacing: 1px; }
.stats-bar .stat-value { font-size: 18px; font-weight: bold; }
.stats-bar .stat-value.resolved { color: var(--green); }
.stats-bar .stat-value.failed { color: var(--red); }
.stats-bar h1 { font-size: 16px; color: var(--blue); margin-right: auto; }

/* Main layout */
.main { display: flex; flex: 1; overflow: hidden; }

/* Sidebar */
.sidebar { width: 320px; min-width: 280px; background: var(--bg2); border-right: 1px solid var(--border); display: flex; flex-direction: column; flex-shrink: 0; }
.sidebar-header { padding: 10px; border-bottom: 1px solid var(--border); }
.sidebar-header input { width: 100%; background: var(--bg3); border: 1px solid var(--border); color: var(--fg); padding: 6px 10px; border-radius: 4px; font-family: inherit; font-size: 12px; }
.sidebar-header input:focus { outline: none; border-color: var(--blue); }
.filter-row { display: flex; gap: 6px; margin-top: 6px; }
.filter-btn { background: var(--bg3); border: 1px solid var(--border); color: var(--fg3); padding: 3px 8px; border-radius: 3px; cursor: pointer; font-size: 11px; font-family: inherit; }
.filter-btn.active { border-color: var(--blue); color: var(--blue); }
.task-list { overflow-y: auto; flex: 1; }
.task-item { padding: 8px 12px; border-bottom: 1px solid var(--border); cursor: pointer; display: flex; align-items: center; gap: 8px; }
.task-item:hover { background: var(--bg3); }
.task-item.selected { background: var(--bg3); border-left: 3px solid var(--blue); }
.task-item .badge { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.task-item .badge.resolved { background: var(--green); }
.task-item .badge.failed { background: var(--red); }
.task-item .task-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; }
.task-item .task-meta { color: var(--fg3); font-size: 10px; white-space: nowrap; }

/* Content area */
.content { flex: 1; overflow-y: auto; padding: 20px; }
.content .placeholder { color: var(--fg3); text-align: center; margin-top: 100px; font-size: 14px; }

/* Task header */
.task-header { margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid var(--border); }
.task-header h2 { color: var(--blue); font-size: 16px; margin-bottom: 6px; }
.task-header .meta-row { display: flex; gap: 16px; font-size: 11px; color: var(--fg3); flex-wrap: wrap; }
.task-header .meta-row span { display: flex; align-items: center; gap: 4px; }

/* Event cards */
.event-card { margin-bottom: 8px; border: 1px solid var(--border); border-radius: 6px; overflow: hidden; }
.event-card .event-header { padding: 8px 12px; display: flex; align-items: center; gap: 8px; cursor: pointer; user-select: none; }
.event-card .event-header:hover { background: var(--bg3); }
.event-card .event-header .arrow { transition: transform 0.15s; color: var(--fg3); font-size: 10px; }
.event-card .event-header .arrow.open { transform: rotate(90deg); }
.event-card .event-header .event-type { font-weight: bold; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; padding: 2px 6px; border-radius: 3px; }
.event-card .event-header .event-info { flex: 1; font-size: 12px; color: var(--fg2); }
.event-card .event-header .event-time { color: var(--fg3); font-size: 10px; }
.event-body { padding: 12px; border-top: 1px solid var(--border); display: none; }
.event-body.open { display: block; }

/* Event type colors */
.et-run_start { background: var(--bg3); color: var(--purple); }
.et-llm_call { background: rgba(122,162,247,0.15); color: var(--blue); }
.et-tool_call { background: rgba(224,175,104,0.15); color: var(--yellow); }
.et-verification { background: rgba(158,206,106,0.15); color: var(--green); }
.et-verification.failed { background: rgba(247,118,142,0.15); color: var(--red); }
.et-recovery { background: rgba(255,158,100,0.15); color: var(--orange); }
.et-run_end { background: var(--bg3); color: var(--purple); }

/* Code blocks */
pre.code-block { background: var(--bg); border: 1px solid var(--border); border-radius: 4px; padding: 10px; overflow-x: auto; font-size: 12px; line-height: 1.5; white-space: pre-wrap; word-break: break-all; max-height: 500px; overflow-y: auto; color: var(--fg2); }
pre.code-block.diff .add { color: var(--green); }
pre.code-block.diff .del { color: var(--red); }

/* Content blocks within events */
.content-block { margin-top: 8px; }
.content-block .block-label { font-size: 10px; color: var(--fg3); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }
.content-block .text-content { color: var(--fg); line-height: 1.6; white-space: pre-wrap; word-break: break-word; }
.tool-use-block { background: var(--bg); border: 1px solid var(--border); border-radius: 4px; padding: 8px; margin-top: 6px; }
.tool-use-block .tool-name { color: var(--yellow); font-weight: bold; font-size: 12px; }

/* Config panel */
.config-panel { background: var(--bg); border-radius: 4px; padding: 10px; font-size: 11px; }
.config-panel .config-row { display: flex; gap: 8px; margin-bottom: 2px; }
.config-panel .config-key { color: var(--purple); min-width: 180px; }
.config-panel .config-val { color: var(--fg2); }

/* Keyboard nav hint */
.nav-hint { position: fixed; bottom: 10px; right: 10px; background: var(--bg2); border: 1px solid var(--border); padding: 6px 10px; border-radius: 4px; font-size: 10px; color: var(--fg3); }
</style>
</head>
<body>

<div class="stats-bar" id="statsBar"></div>
<div class="main">
  <div class="sidebar">
    <div class="sidebar-header">
      <input type="text" id="searchInput" placeholder="Search task ID...">
      <div class="filter-row">
        <button class="filter-btn active" data-filter="all">All</button>
        <button class="filter-btn" data-filter="resolved">Resolved</button>
        <button class="filter-btn" data-filter="failed">Failed</button>
      </div>
    </div>
    <div class="task-list" id="taskList"></div>
  </div>
  <div class="content" id="content">
    <div class="placeholder">Select a task from the sidebar<br><br><small>&#x2190; &#x2192; or click to navigate &middot; &#x2191; &#x2193; to switch tasks</small></div>
  </div>
</div>
<div class="nav-hint">&#x2191;&#x2193; switch task &middot; Click event to expand</div>

<script>
const DATA = {{DATA_JSON}};

// Parse and organize
const tasks = {};
const taskOrder = [];
for (const ev of DATA) {
  const tid = ev.task_id;
  if (!tid) continue;
  if (!tasks[tid]) { tasks[tid] = []; taskOrder.push(tid); }
  tasks[tid].push(ev);
}

// Compute summaries
const summaries = {};
let totalResolved = 0;
for (const tid of taskOrder) {
  const evts = tasks[tid];
  const s = { resolved: false, completion_reason: 'unknown', iterations: 0, total_tokens: 0, tool_calls: 0, wall_clock_seconds: 0, has_content: false };
  for (const ev of evts) {
    if (ev.event === 'run_end') {
      const r = ev.result || {};
      s.resolved = r.resolved || false;
      s.completion_reason = r.completion_reason || 'unknown';
      s.wall_clock_seconds = Math.round((r.wall_clock_seconds || 0) * 10) / 10;
    } else if (ev.event === 'llm_call') {
      s.iterations = Math.max(s.iterations, ev.iteration || 0);
      s.total_tokens += (ev.input_tokens || 0) + (ev.output_tokens || 0);
      if (ev.assistant_content) s.has_content = true;
    } else if (ev.event === 'tool_call') {
      s.tool_calls++;
      if (ev.tool_input || ev.tool_result) s.has_content = true;
    }
  }
  summaries[tid] = s;
  if (s.resolved) totalResolved++;
}

// Render stats bar
const avgTokens = taskOrder.length ? Math.round(taskOrder.reduce((a, t) => a + summaries[t].total_tokens, 0) / taskOrder.length) : 0;
const avgIter = taskOrder.length ? Math.round(taskOrder.reduce((a, t) => a + summaries[t].iterations, 0) / taskOrder.length * 10) / 10 : 0;
const expId = DATA.length > 0 ? (DATA[0].experiment_id || 'unknown') : 'unknown';
document.getElementById('statsBar').innerHTML = `
  <h1>${esc(expId)}</h1>
  <div class="stat"><span class="stat-label">Tasks</span><span class="stat-value">${taskOrder.length}</span></div>
  <div class="stat"><span class="stat-label">Resolved</span><span class="stat-value resolved">${totalResolved}</span></div>
  <div class="stat"><span class="stat-label">Failed</span><span class="stat-value failed">${taskOrder.length - totalResolved}</span></div>
  <div class="stat"><span class="stat-label">Resolve Rate</span><span class="stat-value">${taskOrder.length ? Math.round(totalResolved/taskOrder.length*100) : 0}%</span></div>
  <div class="stat"><span class="stat-label">Avg Tokens</span><span class="stat-value">${avgTokens.toLocaleString()}</span></div>
  <div class="stat"><span class="stat-label">Avg Iterations</span><span class="stat-value">${avgIter}</span></div>
`;
document.title = `Trace Viewer — ${expId}`;

// Render sidebar
let currentFilter = 'all';
let currentSearch = '';
let selectedIdx = -1;
let visibleTasks = [...taskOrder];

function renderTaskList() {
  visibleTasks = taskOrder.filter(tid => {
    if (currentSearch && !tid.toLowerCase().includes(currentSearch.toLowerCase())) return false;
    if (currentFilter === 'resolved' && !summaries[tid].resolved) return false;
    if (currentFilter === 'failed' && summaries[tid].resolved) return false;
    return true;
  });
  const list = document.getElementById('taskList');
  list.innerHTML = visibleTasks.map((tid, i) => {
    const s = summaries[tid];
    const sel = i === selectedIdx ? ' selected' : '';
    return `<div class="task-item${sel}" data-idx="${i}" onclick="selectTask(${i})">
      <span class="badge ${s.resolved ? 'resolved' : 'failed'}"></span>
      <span class="task-name">${esc(tid)}</span>
      <span class="task-meta">${s.iterations}it ${s.tool_calls}tc</span>
    </div>`;
  }).join('');
}

function selectTask(idx) {
  if (idx < 0 || idx >= visibleTasks.length) return;
  selectedIdx = idx;
  renderTaskList();
  renderContent(visibleTasks[idx]);
  // Scroll sidebar item into view
  const items = document.querySelectorAll('.task-item');
  if (items[idx]) items[idx].scrollIntoView({ block: 'nearest' });
}

document.getElementById('searchInput').addEventListener('input', e => {
  currentSearch = e.target.value;
  selectedIdx = -1;
  renderTaskList();
});

document.querySelectorAll('.filter-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentFilter = btn.dataset.filter;
    selectedIdx = -1;
    renderTaskList();
  });
});

// Keyboard navigation
document.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT') return;
  if (e.key === 'ArrowDown' || e.key === 'j') { e.preventDefault(); selectTask(Math.min(selectedIdx + 1, visibleTasks.length - 1)); }
  if (e.key === 'ArrowUp' || e.key === 'k') { e.preventDefault(); selectTask(Math.max(selectedIdx - 1, 0)); }
});

// Group events into "turns": each turn = llm_call + following tool_calls until next llm_call
function groupIntoTurns(evts) {
  const groups = [];
  let current = null;
  for (const ev of evts) {
    if (ev.event === 'run_start' || ev.event === 'run_end' || ev.event === 'verification' || ev.event === 'recovery') {
      if (current) { groups.push(current); current = null; }
      groups.push({ type: ev.event, events: [ev] });
    } else if (ev.event === 'llm_call') {
      if (current) groups.push(current);
      current = { type: 'turn', llm: ev, tools: [] };
    } else if (ev.event === 'tool_call') {
      if (current && current.type === 'turn') {
        current.tools.push(ev);
      } else {
        // orphan tool_call
        groups.push({ type: 'tool_call', events: [ev] });
      }
    }
  }
  if (current) groups.push(current);
  return groups;
}

// Render content
function renderContent(tid) {
  const evts = tasks[tid];
  const s = summaries[tid];
  const content = document.getElementById('content');

  let html = `<div class="task-header">
    <h2>${esc(tid)}</h2>
    <div class="meta-row">
      <span><b style="color:${s.resolved ? 'var(--green)' : 'var(--red)'}">${s.resolved ? 'RESOLVED' : 'FAILED'}</b></span>
      <span>Reason: ${esc(s.completion_reason)}</span>
      <span>Iterations: ${s.iterations}</span>
      <span>Tools: ${s.tool_calls}</span>
      <span>Tokens: ${s.total_tokens.toLocaleString()}</span>
      <span>Time: ${s.wall_clock_seconds}s</span>
      ${s.has_content ? '<span style="color:var(--green)">&#x2714; Full Trace</span>' : '<span style="color:var(--fg3)">Metadata Only</span>'}
    </div>
  </div>`;

  const groups = groupIntoTurns(evts);
  for (const g of groups) {
    if (g.type === 'turn') {
      html += renderTurn(g);
    } else {
      html += renderEvent(g.events[0]);
    }
  }

  content.innerHTML = html;
  content.scrollTop = 0;
}

function renderTurn(turn) {
  const ev = turn.llm;
  const tokens = (ev.input_tokens || 0) + (ev.output_tokens || 0);
  const toolNames = turn.tools.map(t => t.tool_name).join(', ');
  const toolSuffix = toolNames ? ` &rarr; ${toolNames}` : '';
  const headerInfo = `Iteration ${ev.iteration} &middot; ${tokens.toLocaleString()} tok (in:${(ev.input_tokens||0).toLocaleString()} out:${(ev.output_tokens||0).toLocaleString()}) &middot; ${ev.stop_reason}${toolSuffix}`;

  let bodyHtml = '';

  // Assistant content (reasoning + text + tool_use requests)
  if (ev.assistant_content) {
    bodyHtml += renderAssistantContent(ev.assistant_content);
  } else {
    bodyHtml += '<div style="color:var(--fg3);font-style:italic;margin-bottom:8px">No assistant content logged (metadata only)</div>';
  }

  // Tool results inline
  for (const tc of turn.tools) {
    bodyHtml += `<div class="content-block" style="margin-top:12px;padding-top:10px;border-top:1px dashed var(--border)">`;
    bodyHtml += `<div class="block-label" style="color:var(--yellow)">Tool Response: <b>${esc(tc.tool_name)}</b> (${(tc.duration_seconds || 0).toFixed(3)}s)</div>`;
    if (tc.tool_result) {
      const result = typeof tc.tool_result === 'string' ? tc.tool_result : JSON.stringify(tc.tool_result, null, 2);
      const isDiff = result.includes('diff --git') || (result.startsWith('---') && result.includes('+++'));
      if (isDiff) {
        bodyHtml += `<pre class="code-block diff">${renderDiff(result)}</pre>`;
      } else {
        bodyHtml += `<pre class="code-block">${esc(result)}</pre>`;
      }
    } else if (tc.tool_input) {
      bodyHtml += `<pre class="code-block">${esc(typeof tc.tool_input === 'string' ? tc.tool_input : JSON.stringify(tc.tool_input, null, 2))}</pre>`;
      bodyHtml += '<div style="color:var(--fg3);font-style:italic;margin-top:4px">No result logged</div>';
    } else {
      bodyHtml += '<div style="color:var(--fg3);font-style:italic">Metadata only</div>';
    }
    bodyHtml += '</div>';
  }

  return `<div class="event-card">
    <div class="event-header" onclick="toggleEvent(this)">
      <span class="arrow">\u25B6</span>
      <span class="event-type et-llm_call">turn</span>
      <span class="event-info">${headerInfo}</span>
    </div>
    <div class="event-body">${bodyHtml}</div>
  </div>`;
}

function renderEvent(ev) {
  const etype = ev.event;
  let headerInfo = '';
  let bodyHtml = '';
  let extraClass = '';

  switch (etype) {
    case 'run_start': {
      headerInfo = 'Configuration';
      const cfg = ev.config || {};
      bodyHtml = renderConfig(cfg);
      // Problem statement
      if (ev.problem_statement) {
        bodyHtml = `<div class="content-block" style="margin-bottom:12px"><div class="block-label" style="color:var(--cyan)">Problem Statement (User Prompt)</div><pre class="code-block" style="border-color:var(--cyan);max-height:400px">${esc(ev.problem_statement)}</pre></div>` + bodyHtml;
      }
      break;
    }
    case 'verification': {
      extraClass = ev.passed ? '' : ' failed';
      headerInfo = `${ev.passed ? '&#x2714; PASSED' : '&#x2718; FAILED'} &middot; ${esc(ev.method || '')}`;
      bodyHtml = `<div class="content-block"><div class="block-label">Message</div><pre class="code-block">${esc(ev.message || '')}</pre></div>`;
      if (ev.token_cost) bodyHtml += `<div style="margin-top:6px;color:var(--fg3)">Token cost: ${ev.token_cost}</div>`;
      break;
    }
    case 'recovery': {
      headerInfo = `Strategy: ${esc(ev.strategy || '')} &middot; Attempt ${ev.attempt || 0}`;
      break;
    }
    case 'run_end': {
      const r = ev.result || {};
      headerInfo = `<b style="color:${r.resolved ? 'var(--green)' : 'var(--red)'}">${r.resolved ? 'RESOLVED' : 'FAILED'}</b> &middot; ${esc(r.completion_reason || '')} &middot; ${Math.round(r.wall_clock_seconds || 0)}s`;
      bodyHtml = `<pre class="code-block">${esc(JSON.stringify(r, null, 2))}</pre>`;
      break;
    }
    default:
      headerInfo = JSON.stringify(ev).substring(0, 100);
  }

  return `<div class="event-card">
    <div class="event-header" onclick="toggleEvent(this)">
      <span class="arrow">\u25B6</span>
      <span class="event-type et-${etype}${extraClass}">${etype}</span>
      <span class="event-info">${headerInfo}</span>
    </div>
    <div class="event-body">${bodyHtml}</div>
  </div>`;
}

function renderAssistantContent(content) {
  if (!Array.isArray(content)) return `<pre class="code-block">${esc(String(content))}</pre>`;
  // Reorder: reasoning first, then text, then tool_use
  const reasoning = content.filter(b => b.type === '_reasoning');
  const text = content.filter(b => b.type === 'text');
  const toolUse = content.filter(b => b.type === 'tool_use');
  const ordered = [...reasoning, ...text, ...toolUse];
  let html = '';
  for (const block of ordered) {
    if (block.type === '_reasoning') {
      html += `<div class="content-block"><div class="block-label" style="color:var(--purple)">Reasoning (thinking)</div><pre class="code-block" style="border-color:var(--purple);max-height:300px">${esc(block.reasoning || '')}</pre></div>`;
    } else if (block.type === 'text') {
      html += `<div class="content-block"><div class="block-label">Assistant Text</div><div class="text-content">${esc(block.text)}</div></div>`;
    } else if (block.type === 'tool_use') {
      html += `<div class="content-block"><div class="tool-use-block">
        <div class="tool-name">Tool Request: ${esc(block.name)}</div>
        <pre class="code-block">${esc(JSON.stringify(block.input, null, 2))}</pre>
      </div></div>`;
    }
  }
  return html || '<div style="color:var(--fg3)">Empty content</div>';
}

function renderDiff(text) {
  return text.split('\n').map(line => {
    if (line.startsWith('+') && !line.startsWith('+++')) return `<span class="add">${esc(line)}</span>`;
    if (line.startsWith('-') && !line.startsWith('---')) return `<span class="del">${esc(line)}</span>`;
    return esc(line);
  }).join('\n');
}

function renderConfig(cfg) {
  const llm = cfg.llm || {};
  const rows = [
    ['LLM Provider', llm.provider],
    ['Model', llm.model],
    ['Max Tokens', llm.max_tokens],
    ['Temperature', llm.temperature],
    ['Verification', cfg.verification_method],
    ['Granularity', cfg.verification_granularity],
    ['Recovery', cfg.recovery_strategy],
    ['Max Iterations', cfg.max_iterations],
    ['Token Budget', cfg.max_tokens_budget],
    ['Timeout', cfg.timeout_seconds + 's'],
  ].filter(([, v]) => v !== undefined);

  let html = '<div class="config-panel">';
  for (const [k, v] of rows) {
    html += `<div class="config-row"><span class="config-key">${esc(k)}</span><span class="config-val">${esc(String(v))}</span></div>`;
  }
  html += '</div>';

  if (cfg.system_prompt) {
    html += `<div class="content-block" style="margin-top:8px"><div class="block-label">System Prompt</div><pre class="code-block" style="max-height:200px">${esc(cfg.system_prompt)}</pre></div>`;
  }
  return html;
}

function toggleEvent(header) {
  const arrow = header.querySelector('.arrow');
  const body = header.nextElementSibling;
  const isOpen = body.classList.toggle('open');
  arrow.classList.toggle('open', isOpen);
}

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

// Initial render
renderTaskList();
if (visibleTasks.length > 0) selectTask(0);
</script>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="Generate HTML trace viewer from JSONL logs")
    parser.add_argument("jsonl", help="Path to JSONL log file")
    parser.add_argument("-o", "--output", default=None, help="Output HTML file (default: <input>.html)")
    args = parser.parse_args()

    jsonl_path = Path(args.jsonl)
    if not jsonl_path.exists():
        print(f"Error: {jsonl_path} not found", file=sys.stderr)
        sys.exit(1)

    print(f"Loading {jsonl_path}...")
    events = load_jsonl(str(jsonl_path))
    print(f"  {len(events)} events loaded")

    tasks = group_by_task(events)
    print(f"  {len(tasks)} tasks found")

    # Count tasks with full content
    content_count = sum(1 for tid in tasks if any(
        ev.get("assistant_content") or ev.get("tool_input") or ev.get("tool_result")
        for ev in tasks[tid]
    ))
    if content_count:
        print(f"  {content_count} tasks have full trace content")
    else:
        print("  No full trace content (metadata only — re-run experiments after logger update for full traces)")

    # Generate HTML
    data_json = json.dumps(events, ensure_ascii=False, default=str)
    experiment_id = events[0].get("experiment_id", "unknown") if events else "unknown"

    output_html = HTML_TEMPLATE.replace("{{DATA_JSON}}", data_json).replace("{{EXPERIMENT_ID}}", html.escape(experiment_id))

    output_path = Path(args.output) if args.output else jsonl_path.with_suffix(".html")
    output_path.write_text(output_html, encoding="utf-8")
    print(f"  Written to {output_path} ({output_path.stat().st_size / 1024 / 1024:.1f} MB)")
    print(f"\nOpen in browser: file://{output_path.resolve()}")


if __name__ == "__main__":
    main()
