"""
dashboard_campaign.py — Tao file HTML dashboard hien thi tong hop du an + chi tiet campaign.
Chay: python dashboard_campaign.py  -> mo file dashboard.html trong browser.
"""

import json
import webbrowser
import os
from db_helpers import get_project_summary, get_campaigns_by_project, get_all_projects

HTML_PATH = os.path.join(os.path.dirname(__file__), "dashboard.html")


def _esc(text):
    """Escape HTML."""
    if not text:
        return ""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _link_btn(url, label):
    if not url:
        return ""
    return f'<a href="{_esc(url)}" target="_blank" class="link-btn">{_esc(label)}</a>'


def _parse_list(val):
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
        return [line.strip() for line in val.splitlines() if line.strip()]
    return []


def generate_html():
    projects = get_all_projects()
    summary = get_project_summary()
    summary_map = {s["project_id"]: s for s in summary}

    # Tinh tong so lieu
    total_projects_running = len([p for p in projects if p["status"] == "running"])
    total_accounts = sum(s.get("total_accounts", 0) for s in summary)
    all_campaigns = []
    for proj in projects:
        all_campaigns.extend(get_campaigns_by_project(proj["id"]))
    total_campaigns = len(all_campaigns)
    total_budget = sum(c.get("budget", 0) or 0 for c in all_campaigns)

    # Collect unique statuses for filter
    all_statuses = sorted(set(c.get("status", "draft") for c in all_campaigns))

    html = """<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Campaign Vippro Dashboard</title>
<style>
:root {
    --bg-primary: #0b1120;
    --bg-card: #131c31;
    --bg-card-alt: #1a2540;
    --bg-hover: #1e2d4a;
    --bg-input: #0f172a;
    --border: #1e3050;
    --border-light: #2a3f5f;
    --text-primary: #e8edf5;
    --text-secondary: #8899b4;
    --text-muted: #5a6b85;
    --accent: #3b82f6;
    --accent-hover: #60a5fa;
    --accent-glow: rgba(59, 130, 246, 0.15);
    --yellow: #eab308;
    --green: #22c55e;
    --red: #ef4444;
    --cyan: #06b6d4;
}

* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: var(--bg-primary); color: var(--text-primary);
    min-height: 100vh;
}

/* === HEADER === */
.header {
    background: linear-gradient(135deg, #0f1729 0%, #162040 100%);
    border-bottom: 1px solid var(--border);
    padding: 20px 32px;
    display: flex; align-items: center; justify-content: space-between;
}
.header-left { display: flex; align-items: center; gap: 16px; }
.logo {
    width: 40px; height: 40px; background: linear-gradient(135deg, var(--accent), #8b5cf6);
    border-radius: 10px; display: flex; align-items: center; justify-content: center;
    font-weight: 800; font-size: 18px; color: #fff;
}
.header h1 { font-size: 20px; font-weight: 700; color: var(--text-primary); }
.header h1 span { color: var(--accent); }
.header-actions { display: flex; gap: 10px; }

/* === DROPDOWN === */
.dropdown {
    position: relative; display: inline-block;
}
.dropdown-toggle {
    background: var(--bg-card); border: 1px solid var(--border);
    color: var(--text-primary); padding: 8px 16px; border-radius: 8px;
    cursor: pointer; font-size: 13px; font-weight: 500;
    display: flex; align-items: center; gap: 8px;
    transition: all 0.2s;
}
.dropdown-toggle:hover { border-color: var(--accent); background: var(--bg-card-alt); }
.dropdown-toggle .arrow { font-size: 10px; opacity: 0.6; transition: transform 0.2s; }
.dropdown.open .dropdown-toggle .arrow { transform: rotate(180deg); }
.dropdown-menu {
    display: none; position: absolute; top: calc(100% + 6px); left: 0;
    background: var(--bg-card); border: 1px solid var(--border-light);
    border-radius: 10px; min-width: 200px; padding: 6px;
    box-shadow: 0 12px 40px rgba(0,0,0,0.5); z-index: 100;
}
.dropdown.open .dropdown-menu { display: block; }
.dropdown-item {
    display: flex; align-items: center; gap: 10px; padding: 9px 14px;
    border-radius: 6px; cursor: pointer; font-size: 13px;
    color: var(--text-secondary); transition: all 0.15s;
}
.dropdown-item:hover { background: var(--bg-hover); color: var(--text-primary); }
.dropdown-item.active { color: var(--accent); }
.dropdown-divider { height: 1px; background: var(--border); margin: 4px 8px; }

/* === STATS CARDS === */
.content { padding: 24px 32px; max-width: 1400px; margin: 0 auto; }
.stats-grid {
    display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px;
    margin-bottom: 28px;
}
.stat-card {
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: 12px; padding: 20px;
    transition: all 0.2s;
}
.stat-card:hover { border-color: var(--border-light); transform: translateY(-1px); }
.stat-label { font-size: 12px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1px; font-weight: 600; margin-bottom: 8px; }
.stat-value { font-size: 28px; font-weight: 700; }
.stat-value.blue { color: var(--accent); }
.stat-value.yellow { color: var(--yellow); }
.stat-value.green { color: var(--green); }
.stat-value.cyan { color: var(--cyan); }

/* === SUMMARY BOX === */
.summary-box {
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: 14px; padding: 24px; margin-bottom: 28px;
}
.section-header {
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 18px;
}
.section-title {
    font-size: 14px; font-weight: 700; color: var(--text-secondary);
    text-transform: uppercase; letter-spacing: 1.2px;
}
.summary-row {
    display: flex; align-items: center; gap: 14px; padding: 14px 18px;
    background: var(--bg-primary); border-radius: 10px; margin-bottom: 8px;
    border: 1px solid transparent;
    transition: all 0.2s;
}
.summary-row:hover { border-color: var(--border); background: var(--bg-card-alt); }
.summary-row:last-child { margin-bottom: 0; }
.proj-icon {
    width: 36px; height: 36px; border-radius: 8px;
    background: linear-gradient(135deg, #1e40af, #3b82f6);
    display: flex; align-items: center; justify-content: center;
    font-weight: 700; font-size: 14px; color: #fff; flex-shrink: 0;
}
.proj-info { flex: 1; }
.proj-name { font-weight: 600; color: var(--text-primary); font-size: 15px; }
.proj-meta { font-size: 12px; color: var(--text-muted); margin-top: 2px; }
.proj-accounts {
    background: rgba(234, 179, 8, 0.12); color: var(--yellow);
    padding: 4px 12px; border-radius: 20px; font-size: 13px;
    font-weight: 600; white-space: nowrap;
}
.link-btn {
    display: inline-flex; align-items: center; gap: 4px;
    padding: 5px 14px; border-radius: 6px;
    background: var(--accent); color: #fff; text-decoration: none;
    font-size: 12px; font-weight: 600; transition: all 0.2s;
}
.link-btn:hover { background: var(--accent-hover); transform: translateY(-1px); }
.link-btn.secondary { background: transparent; border: 1px solid var(--border-light); color: var(--text-secondary); }
.link-btn.secondary:hover { border-color: var(--accent); color: var(--accent); background: var(--accent-glow); }

/* === PROJECT SECTION === */
.project-section {
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: 14px; margin-bottom: 20px;
    overflow: hidden;
}
.project-header {
    display: flex; align-items: center; gap: 14px; padding: 18px 24px;
    border-bottom: 1px solid var(--border);
    cursor: pointer; transition: background 0.2s;
}
.project-header:hover { background: var(--bg-card-alt); }
.project-header h3 { font-size: 16px; font-weight: 600; flex: 1; }
.toggle-icon { color: var(--text-muted); font-size: 12px; transition: transform 0.3s; }
.project-section.collapsed .toggle-icon { transform: rotate(-90deg); }
.project-section.collapsed .project-body { display: none; }
.project-body { padding: 0; }

/* === STATUS BADGES === */
.badge {
    display: inline-flex; align-items: center; gap: 5px;
    padding: 3px 10px; border-radius: 20px; font-size: 11px;
    font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;
}
.badge::before {
    content: ''; width: 6px; height: 6px; border-radius: 50%;
}
.badge-running, .badge-published { background: rgba(34,197,94,0.1); color: #4ade80; }
.badge-running::before, .badge-published::before { background: #4ade80; }
.badge-paused { background: rgba(234,179,8,0.1); color: #facc15; }
.badge-paused::before { background: #facc15; }
.badge-pending { background: rgba(59,130,246,0.1); color: #60a5fa; }
.badge-pending::before { background: #60a5fa; }
.badge-failed { background: rgba(239,68,68,0.1); color: #f87171; }
.badge-failed::before { background: #f87171; }
.badge-draft { background: rgba(148,163,184,0.1); color: #94a3b8; }
.badge-draft::before { background: #94a3b8; }

/* === TABLE === */
table { width: 100%; border-collapse: collapse; }
thead th {
    background: var(--bg-primary); color: var(--text-muted); padding: 12px 18px;
    text-align: left; font-weight: 600; text-transform: uppercase;
    font-size: 11px; letter-spacing: 0.8px;
    border-bottom: 1px solid var(--border);
    position: sticky; top: 0;
}
tbody td {
    padding: 14px 18px; border-bottom: 1px solid rgba(30,48,80,0.5);
    font-size: 13px; vertical-align: top;
}
tbody tr { transition: background 0.15s; }
tbody tr:hover { background: var(--bg-hover); }
.cell-account { font-family: 'JetBrains Mono', 'Fira Code', monospace; font-weight: 600; color: var(--cyan); font-size: 13px; }
.cell-campaign { font-weight: 500; }
.cell-budget { font-family: 'JetBrains Mono', monospace; color: var(--green); font-weight: 600; }
.cell-bid { font-family: 'JetBrains Mono', monospace; color: var(--yellow); }
.cell-headline { color: #a5b4fc; line-height: 1.6; }
.cell-desc { color: var(--text-muted); font-size: 12px; line-height: 1.6; }

/* === EMPTY === */
.empty-msg {
    color: var(--text-muted); text-align: center; padding: 40px;
    font-size: 14px;
}

/* === RESPONSIVE === */
@media (max-width: 900px) {
    .stats-grid { grid-template-columns: repeat(2, 1fr); }
    .content { padding: 16px; }
    .header { padding: 16px; }
    .summary-row { flex-wrap: wrap; }
}
</style>
</head>
<body>

<!-- HEADER -->
<div class="header">
    <div class="header-left">
        <div class="logo">V</div>
        <h1><span>Vippro</span> Campaign Dashboard</h1>
    </div>
    <div class="header-actions">

        <!-- Dropdown: Loc du an -->
        <div class="dropdown" id="dd-project">
            <button class="dropdown-toggle" onclick="toggleDropdown('dd-project')">
                <span>Du an</span>
                <span class="arrow">&#9660;</span>
            </button>
            <div class="dropdown-menu">
                <div class="dropdown-item active" onclick="filterProject('all')">Tat ca du an</div>
                <div class="dropdown-divider"></div>
"""

    # Dropdown project items
    for proj in projects:
        html += f'                <div class="dropdown-item" onclick="filterProject(\'{_esc(proj["id"])}\')">{_esc(proj["name"])}</div>\n'

    html += """            </div>
        </div>

        <!-- Dropdown: Loc status -->
        <div class="dropdown" id="dd-status">
            <button class="dropdown-toggle" onclick="toggleDropdown('dd-status')">
                <span>Status</span>
                <span class="arrow">&#9660;</span>
            </button>
            <div class="dropdown-menu">
                <div class="dropdown-item active" onclick="filterStatus('all')">Tat ca status</div>
                <div class="dropdown-divider"></div>
"""

    for st in all_statuses:
        html += f'                <div class="dropdown-item" onclick="filterStatus(\'{_esc(st)}\')">{_esc(st).title()}</div>\n'

    html += """            </div>
        </div>

        <!-- Dropdown: Sap xep -->
        <div class="dropdown" id="dd-sort">
            <button class="dropdown-toggle" onclick="toggleDropdown('dd-sort')">
                <span>Sap xep</span>
                <span class="arrow">&#9660;</span>
            </button>
            <div class="dropdown-menu">
                <div class="dropdown-item active" onclick="sortBy('default')">Mac dinh</div>
                <div class="dropdown-divider"></div>
                <div class="dropdown-item" onclick="sortBy('budget-desc')">Budget cao - thap</div>
                <div class="dropdown-item" onclick="sortBy('budget-asc')">Budget thap - cao</div>
                <div class="dropdown-item" onclick="sortBy('name-asc')">Ten A - Z</div>
                <div class="dropdown-item" onclick="sortBy('name-desc')">Ten Z - A</div>
            </div>
        </div>

    </div>
</div>

<div class="content">
"""

    # === STATS CARDS ===
    html += f"""
<div class="stats-grid">
    <div class="stat-card">
        <div class="stat-label">Du An Dang Chay</div>
        <div class="stat-value blue">{total_projects_running}</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">TK Can Tien</div>
        <div class="stat-value yellow">{total_accounts}</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">Tong Campaign</div>
        <div class="stat-value cyan">{total_campaigns}</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">Tong Budget</div>
        <div class="stat-value green">${total_budget:,.2f}</div>
    </div>
</div>
"""

    # === TONG HOP ===
    html += '<div class="summary-box">\n'
    html += '<div class="section-header"><span class="section-title">Tong Hop Du An</span></div>\n'

    running_projects = [p for p in projects if p["status"] == "running"]
    if not running_projects:
        html += '<div class="empty-msg">Chua co du an nao dang chay</div>\n'
    else:
        for i, proj in enumerate(running_projects):
            s = summary_map.get(proj["id"], {})
            total = s.get("total_accounts", 0)
            initials = proj["name"][:2].upper()
            html += f'<div class="summary-row" data-project-id="{_esc(proj["id"])}">\n'
            html += f'  <div class="proj-icon">{_esc(initials)}</div>\n'
            html += f'  <div class="proj-info"><div class="proj-name">{_esc(proj["name"])}</div>'
            html += f'  <div class="proj-meta">Project ID: {_esc(proj["id"][:8])}...</div></div>\n'
            html += f'  <span class="proj-accounts">{total} TK can tien</span>\n'
            html += f'  {_link_btn(proj.get("link1"), "Link 1")}\n'
            if proj.get("link2"):
                html += f'  {_link_btn(proj.get("link2"), "Link 2").replace("link-btn", "link-btn secondary")}\n'
            html += '</div>\n'

    html += '</div>\n'

    # === CHI TIET TUNG DU AN ===
    for proj in projects:
        campaigns = get_campaigns_by_project(proj["id"])
        status_cls = proj["status"]

        html += f'<div class="project-section" data-project-id="{_esc(proj["id"])}" data-project-status="{_esc(proj["status"])}">\n'
        html += f'<div class="project-header" onclick="toggleSection(this)">\n'
        html += f'  <div class="proj-icon">{_esc(proj["name"][:2].upper())}</div>\n'
        html += f'  <h3>{_esc(proj["name"])}</h3>\n'
        html += f'  <span class="badge badge-{status_cls}">{_esc(proj["status"])}</span>\n'
        html += f'  {_link_btn(proj.get("link1"), "Link 1")}\n'
        if proj.get("link2"):
            html += f'  {_link_btn(proj.get("link2"), "Link 2").replace("link-btn", "link-btn secondary")}\n'
        html += f'  <span style="margin-left:auto;color:var(--text-muted);font-size:12px;">{len(campaigns)} campaigns</span>\n'
        html += '  <span class="toggle-icon">&#9660;</span>\n'
        html += '</div>\n'
        html += '<div class="project-body">\n'

        if not campaigns:
            html += '<div class="empty-msg">Chua co campaign nao</div>\n'
        else:
            html += """<table>
<thead><tr>
    <th>Key (Account)</th>
    <th>Campaign</th>
    <th>Status</th>
    <th>Budget</th>
    <th>Gia Thau</th>
    <th>Tieu De</th>
    <th>Mo Ta</th>
</tr></thead>
<tbody>
"""
            for c in campaigns:
                st = c.get("status", "draft")
                bidding = c.get("bidding", "")
                if isinstance(bidding, dict):
                    bidding = json.dumps(bidding, ensure_ascii=False)

                headlines = _parse_list(c.get("headlines", []))
                descriptions = _parse_list(c.get("descriptions", []))

                html += f'<tr data-status="{_esc(st)}" data-budget="{c.get("budget", 0) or 0}" data-name="{_esc(c.get("name", ""))}">\n'
                html += f'  <td class="cell-account">{_esc(c.get("adsAccountId", "—"))}</td>\n'
                html += f'  <td class="cell-campaign">{_esc(c.get("name", ""))}</td>\n'
                html += f'  <td><span class="badge badge-{st}">{_esc(st)}</span></td>\n'
                html += f'  <td class="cell-budget">${c.get("budget", 0) or 0:.2f}</td>\n'
                html += f'  <td class="cell-bid">{_esc(bidding)}</td>\n'
                html += f'  <td class="cell-headline">{"<br>".join(_esc(h) for h in headlines[:3])}</td>\n'
                html += f'  <td class="cell-desc">{"<br>".join(_esc(d) for d in descriptions[:2])}</td>\n'
                html += "</tr>\n"

            html += "</tbody></table>\n"

        html += '</div>\n</div>\n'

    # === JAVASCRIPT ===
    html += """
</div>

<script>
// Close dropdowns when clicking outside
document.addEventListener('click', function(e) {
    document.querySelectorAll('.dropdown').forEach(function(dd) {
        if (!dd.contains(e.target)) dd.classList.remove('open');
    });
});

function toggleDropdown(id) {
    event.stopPropagation();
    var dd = document.getElementById(id);
    // Close others
    document.querySelectorAll('.dropdown').forEach(function(d) {
        if (d.id !== id) d.classList.remove('open');
    });
    dd.classList.toggle('open');
}

function toggleSection(header) {
    header.parentElement.classList.toggle('collapsed');
}

function filterProject(projectId) {
    var sections = document.querySelectorAll('.project-section');
    var summaryRows = document.querySelectorAll('.summary-row');

    sections.forEach(function(s) {
        if (projectId === 'all' || s.dataset.projectId === projectId) {
            s.style.display = '';
        } else {
            s.style.display = 'none';
        }
    });
    summaryRows.forEach(function(r) {
        if (projectId === 'all' || r.dataset.projectId === projectId) {
            r.style.display = '';
        } else {
            r.style.display = 'none';
        }
    });

    // Update active
    var menu = document.querySelector('#dd-project .dropdown-menu');
    menu.querySelectorAll('.dropdown-item').forEach(function(item) { item.classList.remove('active'); });
    event.target.classList.add('active');
    document.getElementById('dd-project').classList.remove('open');

    // Update toggle label
    document.querySelector('#dd-project .dropdown-toggle span:first-child').textContent =
        projectId === 'all' ? 'Du an' : event.target.textContent;
}

function filterStatus(status) {
    var rows = document.querySelectorAll('tbody tr');
    rows.forEach(function(r) {
        if (status === 'all' || r.dataset.status === status) {
            r.style.display = '';
        } else {
            r.style.display = 'none';
        }
    });

    var menu = document.querySelector('#dd-status .dropdown-menu');
    menu.querySelectorAll('.dropdown-item').forEach(function(item) { item.classList.remove('active'); });
    event.target.classList.add('active');
    document.getElementById('dd-status').classList.remove('open');

    document.querySelector('#dd-status .dropdown-toggle span:first-child').textContent =
        status === 'all' ? 'Status' : event.target.textContent;
}

function sortBy(mode) {
    document.querySelectorAll('tbody').forEach(function(tbody) {
        var rows = Array.from(tbody.querySelectorAll('tr'));
        rows.sort(function(a, b) {
            if (mode === 'budget-desc') return parseFloat(b.dataset.budget) - parseFloat(a.dataset.budget);
            if (mode === 'budget-asc') return parseFloat(a.dataset.budget) - parseFloat(b.dataset.budget);
            if (mode === 'name-asc') return (a.dataset.name || '').localeCompare(b.dataset.name || '');
            if (mode === 'name-desc') return (b.dataset.name || '').localeCompare(a.dataset.name || '');
            return 0;
        });
        rows.forEach(function(r) { tbody.appendChild(r); });
    });

    var menu = document.querySelector('#dd-sort .dropdown-menu');
    menu.querySelectorAll('.dropdown-item').forEach(function(item) { item.classList.remove('active'); });
    event.target.classList.add('active');
    document.getElementById('dd-sort').classList.remove('open');

    document.querySelector('#dd-sort .dropdown-toggle span:first-child').textContent =
        mode === 'default' ? 'Sap xep' : event.target.textContent;
}
</script>

</body>
</html>"""

    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Dashboard saved: {HTML_PATH}")
    return HTML_PATH


if __name__ == "__main__":
    path = generate_html()
    webbrowser.open(f"file:///{os.path.abspath(path).replace(os.sep, '/')}")
    print("Opened in browser.")
