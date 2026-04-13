"""
dashboard_server.py — Local server cho Campaign Dashboard.
Chay: python dashboard_server.py  -> mo http://localhost:5050
"""

import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
import webbrowser

sys.path.insert(0, os.path.dirname(__file__))
from db_helpers import (
    get_all_projects, get_project_summary, get_campaigns_by_project,
    create_project, update_project, delete_project
)

PORT = 5050


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/dashboard"):
            self._serve_html()
        elif path == "/api/projects":
            self._json_response(get_all_projects())
        elif path == "/api/summary":
            self._json_response(get_project_summary())
        elif path.startswith("/api/campaigns/"):
            project_id = path.split("/")[-1]
            self._json_response(get_campaigns_by_project(project_id))
        else:
            self.send_error(404)

    def do_POST(self):
        path = urlparse(self.path).path
        body = self._read_body()

        if path == "/api/projects":
            pid = create_project(
                name=body.get("name", "Untitled"),
                link1=body.get("link1"), link2=body.get("link2"),
                status=body.get("status", "running"),
                cpc=body.get("cpc"), bidding=body.get("bidding"),
                bid_value=body.get("bid_value"), budget=body.get("budget"),
                ads_key=body.get("ads_key"),
                target_locations=body.get("target_locations"),
                exclude_locations=body.get("exclude_locations"),
                devices=body.get("devices"), age_range=body.get("age_range"),
                gender=body.get("gender"),
                headlines=body.get("headlines"),
                descriptions=body.get("descriptions"),
            )
            self._json_response({"id": pid, "ok": True})
        elif path.startswith("/api/projects/") and path.endswith("/update"):
            project_id = path.split("/")[-2]
            update_project(project_id, **body)
            self._json_response({"ok": True})
        elif path.startswith("/api/projects/") and path.endswith("/delete"):
            project_id = path.split("/")[-2]
            delete_project(project_id)
            self._json_response({"ok": True})
        else:
            self.send_error(404)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except Exception:
            return {}

    def _json_response(self, data):
        body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _serve_html(self):
        html = DASHBOARD_HTML
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Campaign Vippro Dashboard</title>
<style>
:root {
    --bg:#0b1120;--card:#131c31;--alt:#1a2540;--hover:#1e2d4a;
    --input:#0f172a;--bdr:#1e3050;--bdr2:#2a3f5f;
    --t1:#e8edf5;--t2:#8899b4;--t3:#5a6b85;
    --acc:#3b82f6;--acc2:#60a5fa;--glow:rgba(59,130,246,.12);
    --yel:#eab308;--grn:#22c55e;--red:#ef4444;--cyn:#06b6d4;
    --org:#f97316;--pur:#a78bfa;
}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Inter','Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--t1);min-height:100vh}

.header{background:linear-gradient(135deg,#0f1729,#162040);border-bottom:1px solid var(--bdr);padding:14px 28px;display:flex;align-items:center;justify-content:space-between}
.header-left{display:flex;align-items:center;gap:14px}
.logo{width:36px;height:36px;background:linear-gradient(135deg,var(--acc),#8b5cf6);border-radius:10px;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:16px;color:#fff}
.header h1{font-size:17px;font-weight:700} .header h1 span{color:var(--acc)}
.header-actions{display:flex;gap:8px}

/* Dropdown */
.dropdown{position:relative;display:inline-block}
.dd-btn{background:var(--card);border:1px solid var(--bdr);color:var(--t1);padding:7px 14px;border-radius:8px;cursor:pointer;font-size:12px;font-weight:500;display:flex;align-items:center;gap:6px;transition:all .2s}
.dd-btn:hover{border-color:var(--acc)}
.dd-btn .arr{font-size:9px;opacity:.5;transition:transform .2s}
.dropdown.open .arr{transform:rotate(180deg)}
.dd-menu{display:none;position:absolute;top:calc(100% + 4px);left:0;background:var(--card);border:1px solid var(--bdr2);border-radius:10px;min-width:180px;padding:5px;box-shadow:0 12px 40px rgba(0,0,0,.5);z-index:100}
.dropdown.open .dd-menu{display:block}
.dd-item{display:flex;align-items:center;gap:8px;padding:8px 12px;border-radius:6px;cursor:pointer;font-size:12px;color:var(--t2);transition:all .15s}
.dd-item:hover{background:var(--hover);color:var(--t1)}
.dd-item.active{color:var(--acc)}
.dd-sep{height:1px;background:var(--bdr);margin:3px 6px}

.content{padding:20px 28px;max-width:1440px;margin:0 auto}

/* Stats */
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:20px}
.stat{background:var(--card);border:1px solid var(--bdr);border-radius:12px;padding:16px 20px;transition:all .2s}
.stat:hover{border-color:var(--bdr2);transform:translateY(-1px)}
.stat-label{font-size:11px;color:var(--t3);text-transform:uppercase;letter-spacing:.8px;font-weight:600;margin-bottom:6px}
.stat-val{font-size:26px;font-weight:700}
.blue{color:var(--acc)}.yellow{color:var(--yel)}.green{color:var(--grn)}.cyanc{color:var(--cyn)}

/* Form box */
.add-box{background:var(--card);border:1px solid var(--bdr);border-radius:14px;padding:20px;margin-bottom:20px}
.sec-title{font-size:13px;font-weight:700;color:var(--t2);text-transform:uppercase;letter-spacing:1px;margin-bottom:14px;display:flex;align-items:center;gap:8px}
.sec-title .icon{color:var(--grn);font-size:16px}
.form-row{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px;margin-bottom:10px}
.fg{display:flex;flex-direction:column;gap:4px}
.fg label{font-size:11px;color:var(--t3);text-transform:uppercase;letter-spacing:.5px;font-weight:600}
.fg input,.fg select,.fg textarea{background:var(--input);border:1px solid var(--bdr);color:var(--t1);padding:8px 12px;border-radius:8px;font-size:13px;outline:none;transition:border .2s;font-family:inherit}
.fg input:focus,.fg select:focus,.fg textarea:focus{border-color:var(--acc)}
.fg select{cursor:pointer}
.fg textarea{resize:vertical}
.form-actions{display:flex;gap:8px;margin-top:12px}
.btn{padding:9px 20px;border-radius:8px;border:none;font-size:13px;font-weight:600;cursor:pointer;transition:all .2s}
.btn-primary{background:var(--acc);color:#fff}.btn-primary:hover{background:var(--acc2)}
.btn-danger{background:transparent;border:1px solid var(--red);color:var(--red)}.btn-danger:hover{background:rgba(239,68,68,.1)}
.btn-ghost{background:transparent;border:1px solid var(--bdr2);color:var(--t2)}.btn-ghost:hover{border-color:var(--acc);color:var(--acc)}

/* Collapsible group in form */
.fgroup{border:1px solid var(--bdr);border-radius:10px;margin-bottom:10px;overflow:hidden}
.fgroup-hdr{display:flex;align-items:center;gap:8px;padding:10px 14px;cursor:pointer;background:var(--alt);font-size:12px;font-weight:600;color:var(--t2);transition:background .2s}
.fgroup-hdr:hover{background:var(--hover)}
.fgroup-hdr .fg-arrow{font-size:9px;opacity:.5;transition:transform .2s}
.fgroup.open .fg-arrow{transform:rotate(90deg)}
.fgroup-body{display:none;padding:12px 14px;background:var(--card)}
.fgroup.open .fgroup-body{display:block}
.fgroup-hdr .fg-preview{color:var(--t3);font-weight:400;margin-left:auto;font-size:11px;max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}

/* Summary */
.summary-box{background:var(--card);border:1px solid var(--bdr);border-radius:14px;padding:20px;margin-bottom:20px}
.sec-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px}
.sum-row{display:flex;align-items:center;gap:12px;padding:12px 16px;background:var(--bg);border-radius:10px;margin-bottom:6px;border:1px solid transparent;transition:all .2s}
.sum-row:hover{border-color:var(--bdr)}
.picon{width:34px;height:34px;border-radius:8px;background:linear-gradient(135deg,#1e40af,#3b82f6);display:flex;align-items:center;justify-content:center;font-weight:700;font-size:13px;color:#fff;flex-shrink:0}
.pinfo{flex:1}.pname{font-weight:600;font-size:14px}.pmeta{font-size:11px;color:var(--t3);margin-top:1px}
.ptag{background:rgba(234,179,8,.1);color:var(--yel);padding:3px 10px;border-radius:16px;font-size:12px;font-weight:600;white-space:nowrap}
.link-btn{display:inline-flex;align-items:center;gap:3px;padding:4px 12px;border-radius:6px;background:var(--acc);color:#fff;text-decoration:none;font-size:11px;font-weight:600;transition:all .2s}
.link-btn:hover{background:var(--acc2);transform:translateY(-1px)}
.link-btn.sec{background:transparent;border:1px solid var(--bdr2);color:var(--t2)}
.link-btn.sec:hover{border-color:var(--acc);color:var(--acc);background:var(--glow)}

/* Project section */
.proj-sec{background:var(--card);border:1px solid var(--bdr);border-radius:14px;margin-bottom:16px;overflow:hidden}
.proj-hdr{display:flex;align-items:center;gap:12px;padding:14px 20px;border-bottom:1px solid var(--bdr);cursor:pointer;transition:background .2s}
.proj-hdr:hover{background:var(--alt)}
.proj-hdr h3{font-size:15px;font-weight:600;flex:1}
.toggle{color:var(--t3);font-size:11px;transition:transform .3s}
.proj-sec.closed .toggle{transform:rotate(-90deg)}
.proj-sec.closed .proj-body{display:none}
.proj-sec.closed .targeting-bar{display:none}
.proj-sec.closed .ads-preview{display:none}
.proj-sec.closed .tg-edit{display:none !important}

/* Targeting bar */
.targeting-bar{display:flex;flex-wrap:wrap;gap:6px;padding:10px 20px;background:var(--bg);border-bottom:1px solid var(--bdr);align-items:center}
.tg-chip{display:inline-flex;align-items:center;gap:4px;padding:3px 9px;border-radius:6px;font-size:11px;font-weight:500;background:var(--alt);border:1px solid var(--bdr);color:var(--t2)}
.tg-label{color:var(--t3);font-weight:600;text-transform:uppercase;font-size:9px;letter-spacing:.3px}
.tg-val{color:var(--t1)}
.tg-chip.cpc .tg-val{color:var(--grn)}
.tg-chip.bid .tg-val{color:var(--org)}
.tg-chip.loc .tg-val{color:var(--cyn)}
.tg-chip.loc .tg-exc{color:var(--red);font-size:10px;margin-left:4px}
.tg-chip.device .tg-val{color:var(--pur)}
.tg-chip.age .tg-val{color:var(--org)}
.tg-chip.gender .tg-val{color:var(--acc2)}
.tg-chip.links .tg-val a{color:var(--acc);text-decoration:none;font-weight:600}
.tg-chip.links .tg-val a:hover{text-decoration:underline}
.tg-chip.links .tg-val .lsep{color:var(--t3);margin:0 4px;font-size:9px}
.edit-tg-btn{margin-left:auto;background:transparent;border:1px solid var(--bdr2);color:var(--t3);padding:3px 10px;border-radius:6px;font-size:10px;cursor:pointer;transition:all .2s}
.edit-tg-btn:hover{border-color:var(--acc);color:var(--acc)}

/* Ads preview */
.ads-preview{padding:10px 20px;background:var(--bg);border-bottom:1px solid var(--bdr);display:flex;gap:24px;flex-wrap:wrap}
.ads-col{flex:1;min-width:180px}
.ads-col-title{font-size:10px;color:var(--t3);text-transform:uppercase;letter-spacing:.8px;font-weight:700;margin-bottom:4px}
.ads-col ul{list-style:none;padding:0}
.ads-col li{font-size:12px;padding:2px 0;line-height:1.4}
.ads-col li::before{content:'';display:inline-block;width:4px;height:4px;border-radius:50%;margin-right:6px;vertical-align:middle}
.ads-col.hl li::before{background:#a5b4fc}.ads-col.hl li{color:#c4b5fd}
.ads-col.desc li::before{background:var(--t3)}.ads-col.desc li{color:var(--t2)}

/* Edit form inline */
.tg-edit{display:none;padding:14px 20px;background:var(--bg);border-bottom:1px solid var(--bdr)}
.tg-edit.open{display:block}

/* Badge */
.badge{display:inline-flex;align-items:center;gap:4px;padding:2px 9px;border-radius:16px;font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.4px}
.badge::before{content:'';width:5px;height:5px;border-radius:50%}
.badge-running,.badge-published{background:rgba(34,197,94,.08);color:#4ade80}.badge-running::before,.badge-published::before{background:#4ade80}
.badge-paused{background:rgba(234,179,8,.08);color:#facc15}.badge-paused::before{background:#facc15}
.badge-pending{background:rgba(59,130,246,.08);color:#60a5fa}.badge-pending::before{background:#60a5fa}
.badge-failed{background:rgba(239,68,68,.08);color:#f87171}.badge-failed::before{background:#f87171}
.badge-draft{background:rgba(148,163,184,.08);color:#94a3b8}.badge-draft::before{background:#94a3b8}

/* Table */
table{width:100%;border-collapse:collapse}
thead th{background:var(--bg);color:var(--t3);padding:10px 16px;text-align:left;font-weight:600;text-transform:uppercase;font-size:10px;letter-spacing:.7px;border-bottom:1px solid var(--bdr)}
tbody td{padding:12px 16px;border-bottom:1px solid rgba(30,48,80,.4);font-size:12px;vertical-align:top}
tbody tr{transition:background .15s}tbody tr:hover{background:var(--hover)}
.mono{font-family:'JetBrains Mono','Fira Code',monospace}
.c-acct{font-weight:600;color:var(--cyn)}.c-budget{color:var(--grn);font-weight:600}
.c-bid{color:var(--yel)}.c-hl{color:#a5b4fc;line-height:1.5}.c-desc{color:var(--t3);font-size:11px;line-height:1.5}
.empty{color:var(--t3);text-align:center;padding:32px;font-size:13px}

.toast{position:fixed;bottom:24px;right:24px;background:#166534;color:#4ade80;padding:12px 20px;border-radius:10px;font-size:13px;font-weight:600;box-shadow:0 8px 30px rgba(0,0,0,.4);transform:translateY(80px);opacity:0;transition:all .3s;z-index:999}
.toast.show{transform:translateY(0);opacity:1}

@media(max-width:900px){.stats{grid-template-columns:repeat(2,1fr)}.content{padding:14px}.form-row{grid-template-columns:1fr 1fr}}
</style>
</head>
<body>

<div class="header">
    <div class="header-left">
        <div class="logo">V</div>
        <h1><span>Vippro</span> Campaign</h1>
    </div>
    <div class="header-actions">
        <div class="dropdown" id="dd-proj">
            <button class="dd-btn" onclick="toggleDD('dd-proj')"><span id="dd-proj-label">Du an</span><span class="arr">&#9660;</span></button>
            <div class="dd-menu" id="dd-proj-menu"></div>
        </div>
        <div class="dropdown" id="dd-status">
            <button class="dd-btn" onclick="toggleDD('dd-status')"><span id="dd-status-label">Status</span><span class="arr">&#9660;</span></button>
            <div class="dd-menu" id="dd-status-menu"></div>
        </div>
        <div class="dropdown" id="dd-sort">
            <button class="dd-btn" onclick="toggleDD('dd-sort')"><span>Sap xep</span><span class="arr">&#9660;</span></button>
            <div class="dd-menu">
                <div class="dd-item active" onclick="sortBy('default',this)">Mac dinh</div>
                <div class="dd-sep"></div>
                <div class="dd-item" onclick="sortBy('budget-desc',this)">Budget cao - thap</div>
                <div class="dd-item" onclick="sortBy('budget-asc',this)">Budget thap - cao</div>
                <div class="dd-item" onclick="sortBy('name-asc',this)">Ten A - Z</div>
                <div class="dd-item" onclick="sortBy('name-desc',this)">Ten Z - A</div>
            </div>
        </div>
    </div>
</div>

<div class="content">
    <div class="stats" id="stats-grid"></div>

    <!-- ADD PROJECT -->
    <div class="add-box">
        <div class="sec-title"><span class="icon">+</span> Them Du An Moi</div>

        <!-- Row 1: Basic info -->
        <div class="form-row">
            <div class="fg"><label>Ten du an *</label><input id="f-name" placeholder="VD: Dien May Xanh"></div>
            <div class="fg"><label>Ngan sach ngay</label><input id="f-budget" placeholder="VD: 200000 VND"></div>
        </div>
        <div class="form-row" style="grid-template-columns:1fr">
            <div class="fg"><label>Tu khoa (moi dong 1 tu khoa)</label><textarea id="f-key" rows="3" placeholder="dien may&#10;dien may xanh&#10;mua dien may gia re"></textarea></div>
        </div>
        <div class="form-row">
            <div class="fg"><label>Chien luoc gia thau</label>
                <select id="f-bidding" onchange="updateBidInput()">
                    <option value="Toi da luot nhan chuot">Toi da luot nhan chuot</option>
                    <option value="Toi da luot chuyen doi">Toi da luot chuyen doi</option>
                    <option value="CPC thu cong">CPC thu cong</option>
                    <option value="CPA muc tieu">CPA muc tieu</option>
                    <option value="ROAS muc tieu">ROAS muc tieu</option>
                </select>
            </div>
            <div class="fg" id="f-bid-group">
                <label id="f-bid-label">CPC toi da (khong bat buoc)</label>
                <input id="f-cpc" placeholder="VD: 5000 VND">
            </div>
        </div>

        <!-- Nhom: Links du an -->
        <div class="fgroup open" id="fg-links">
            <div class="fgroup-hdr" onclick="toggleFG('fg-links')">
                <span class="fg-arrow">&#9654;</span> Duong dan du an
                <span class="fg-preview" id="fg-links-preview"></span>
            </div>
            <div class="fgroup-body">
                <div class="form-row">
                    <div class="fg"><label>Link chinh</label><input id="f-link1" placeholder="https://..." oninput="updateLinkPreview()"></div>
                    <div class="fg"><label>Link phu (khong bat buoc)</label><input id="f-link2" placeholder="https://..." oninput="updateLinkPreview()"></div>
                </div>
            </div>
        </div>

        <!-- Nhom: Quoc gia -->
        <div class="fgroup open" id="fg-location">
            <div class="fgroup-hdr" onclick="toggleFG('fg-location')">
                <span class="fg-arrow">&#9654;</span> Quoc gia muc tieu
                <span class="fg-preview" id="fg-loc-preview"></span>
            </div>
            <div class="fgroup-body">
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
                    <div class="fg"><label>Quoc gia nham den (moi dong 1 quoc gia)</label><textarea id="f-target" rows="3" placeholder="Viet Nam&#10;Thai Lan&#10;Campuchia" oninput="updateLocPreview()"></textarea></div>
                    <div class="fg"><label>Quoc gia loai tru (moi dong 1)</label><textarea id="f-exclude" rows="3" placeholder="Trung Quoc&#10;An Do" oninput="updateLocPreview()"></textarea></div>
                </div>
            </div>
        </div>

        <!-- Nhom: Doi tuong -->
        <div class="fgroup" id="fg-audience">
            <div class="fgroup-hdr" onclick="toggleFG('fg-audience')">
                <span class="fg-arrow">&#9654;</span> Doi tuong (Thiet bi, Do tuoi, Gioi tinh)
                <span class="fg-preview" id="fg-aud-preview"></span>
            </div>
            <div class="fgroup-body">
                <div class="form-row">
                    <div class="fg"><label>Thiet bi</label>
                        <select id="f-devices"><option value="Tat ca">Tat ca</option><option value="Di dong">Di dong</option><option value="May tinh">May tinh</option><option value="May tinh bang">May tinh bang</option></select>
                    </div>
                    <div class="fg"><label>Do tuoi</label>
                        <select id="f-age"><option value="18-65+">Tat ca (18-65+)</option><option value="18-24">18-24</option><option value="25-34">25-34</option><option value="25-44">25-44</option><option value="25-54">25-54</option><option value="35-54">35-54</option><option value="45-65+">45-65+</option></select>
                    </div>
                    <div class="fg"><label>Gioi tinh</label>
                        <select id="f-gender"><option value="Tat ca">Tat ca</option><option value="Nam">Nam</option><option value="Nu">Nu</option></select>
                    </div>
                </div>
            </div>
        </div>

        <!-- Nhom: Noi dung quang cao -->
        <div class="fgroup" id="fg-ads">
            <div class="fgroup-hdr" onclick="toggleFG('fg-ads')">
                <span class="fg-arrow">&#9654;</span> Noi dung quang cao (Tieu de, Mo ta)
                <span class="fg-preview" id="fg-ads-preview"></span>
            </div>
            <div class="fgroup-body">
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
                    <div class="fg"><label>Tieu de (moi dong 1, toi da 15)</label><textarea id="f-headlines" rows="4" placeholder="Noi That Cao Cap&#10;Giam 30% Hom Nay&#10;Mien Phi Van Chuyen"></textarea></div>
                    <div class="fg"><label>Mo ta (moi dong 1, toi da 4)</label><textarea id="f-descriptions" rows="4" placeholder="Noi that dep gia tot&#10;Chat luong cao, bao hanh 5 nam"></textarea></div>
                </div>
            </div>
        </div>

        <div class="form-actions">
            <button class="btn btn-primary" onclick="addProject()">Tao du an</button>
        </div>
    </div>

    <!-- SUMMARY -->
    <div class="summary-box">
        <div class="sec-header"><span class="sec-title">Tong Hop Du An</span></div>
        <div id="summary-list"></div>
    </div>

    <div id="project-list"></div>
</div>

<div class="toast" id="toast"></div>

<script>
let DATA = {projects:[],summary:[],campaigns:{}};

async function api(url,method,body){
    const o={method:method||'GET',headers:{'Content-Type':'application/json'}};
    if(body)o.body=JSON.stringify(body);
    return (await fetch(url,o)).json();
}

function toast(msg){const t=document.getElementById('toast');t.textContent=msg;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2500)}
function esc(s){if(!s)return '';return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;')}
function pipeSplit(s){if(!s)return [];return s.split('|').map(x=>x.trim()).filter(x=>x)}
function pipeToLines(s){if(!s)return '';return esc(s.split('|').map(x=>x.trim()).filter(x=>x).join('\n'))}
function linesToPipe(id){const v=document.getElementById(id).value.trim();if(!v)return null;return v.split('\n').map(x=>x.trim()).filter(x=>x).join('|')}
function parseList(v){if(Array.isArray(v))return v;if(typeof v==='string'){try{const p=JSON.parse(v);if(Array.isArray(p))return p}catch(e){}return v.split('\n').filter(x=>x.trim())}return []}

// === GIA THAU LOGIC ===
const BID_CONFIG = {
    'Toi da luot nhan chuot': {label:'CPC toi da (khong bat buoc)', placeholder:'VD: 5000 VND', show:true},
    'CPC thu cong':           {label:'Gia CPC moi click', placeholder:'VD: 5000 VND', show:true},
    'CPA muc tieu':           {label:'CPA muc tieu', placeholder:'VD: 50000 VND', show:true},
    'Toi da luot chuyen doi': {label:'', placeholder:'', show:false},
    'ROAS muc tieu':          {label:'ROAS muc tieu (%)', placeholder:'VD: 400', show:true},
};
function updateBidInput(){
    const strategy=document.getElementById('f-bidding').value;
    const cfg=BID_CONFIG[strategy]||{show:false};
    const grp=document.getElementById('f-bid-group');
    if(!cfg.show){grp.style.display='none';return}
    grp.style.display='';
    document.getElementById('f-bid-label').textContent=cfg.label;
    document.getElementById('f-cpc').placeholder=cfg.placeholder;
}
function updateEditBidInput(pid){
    const strategy=document.getElementById('e-bid-'+pid).value;
    const cfg=BID_CONFIG[strategy]||{show:false};
    const grp=document.getElementById('e-bid-group-'+pid);
    if(!cfg.show){grp.style.display='none';return}
    grp.style.display='';
    document.getElementById('e-bid-label-'+pid).textContent=cfg.label;
    document.getElementById('e-cpc-'+pid).placeholder=cfg.placeholder;
}

function initBidInputs(){
    updateBidInput();
    DATA.projects.forEach(p=>updateEditBidInput(p.id));
}

// === FORM GROUPS ===
function toggleFG(id){document.getElementById(id).classList.toggle('open')}
function updateLinkPreview(){
    const l1=document.getElementById('f-link1').value.trim();
    const l2=document.getElementById('f-link2').value.trim();
    let t=[];if(l1)t.push(l1.substring(0,30));if(l2)t.push(l2.substring(0,30));
    document.getElementById('fg-links-preview').textContent=t.join(' | ')||'';
}
function updateLocPreview(){
    const t=document.getElementById('f-target').value.trim();
    const e=document.getElementById('f-exclude').value.trim();
    let s=t||'';if(e)s+=' | Loai: '+e;
    document.getElementById('fg-loc-preview').textContent=s;
}

// === LOAD & RENDER ===
async function loadAll(){
    DATA.projects=await api('/api/projects');
    DATA.summary=await api('/api/summary');
    const r=await Promise.all(DATA.projects.map(p=>api('/api/campaigns/'+p.id).then(c=>[p.id,c])));
    DATA.campaigns={};r.forEach(([id,c])=>DATA.campaigns[id]=c);
    render();
}
function render(){renderStats();renderDropdowns();renderSummary();renderProjects();initBidInputs()}

function renderStats(){
    const running=DATA.projects.filter(p=>p.status==='running').length;
    let tAcc=0;DATA.summary.forEach(s=>tAcc+=s.total_accounts||0);
    let tCamp=0,tBudget=0;
    Object.values(DATA.campaigns).forEach(a=>{tCamp+=a.length;a.forEach(c=>tBudget+=c.budget||0)});
    document.getElementById('stats-grid').innerHTML=`
        <div class="stat"><div class="stat-label">Du An Dang Chay</div><div class="stat-val blue">${running}</div></div>
        <div class="stat"><div class="stat-label">TK Can Tien</div><div class="stat-val yellow">${tAcc}</div></div>
        <div class="stat"><div class="stat-label">Tong Campaign</div><div class="stat-val cyanc">${tCamp}</div></div>
        <div class="stat"><div class="stat-label">Tong Budget</div><div class="stat-val green">$${tBudget.toFixed(2)}</div></div>`;
}

function renderDropdowns(){
    let ph='<div class="dd-item active" onclick="filterProject(\'all\',this)">Tat ca</div><div class="dd-sep"></div>';
    DATA.projects.forEach(p=>{ph+=`<div class="dd-item" onclick="filterProject('${p.id}',this)">${esc(p.name)}</div>`});
    document.getElementById('dd-proj-menu').innerHTML=ph;
    const sts=new Set();Object.values(DATA.campaigns).forEach(a=>a.forEach(c=>sts.add(c.status||'draft')));
    let sh='<div class="dd-item active" onclick="filterStatus(\'all\',this)">Tat ca</div><div class="dd-sep"></div>';
    [...sts].sort().forEach(s=>{sh+=`<div class="dd-item" onclick="filterStatus('${s}',this)">${esc(s)}</div>`});
    document.getElementById('dd-status-menu').innerHTML=sh;
}

function renderSummary(){
    const running=DATA.projects.filter(p=>p.status==='running');
    const smap={};DATA.summary.forEach(s=>smap[s.project_id]=s);
    if(!running.length){document.getElementById('summary-list').innerHTML='<div class="empty">Chua co du an nao</div>';return}
    let h='';
    running.forEach(p=>{
        const s=smap[p.id]||{};const total=s.total_accounts||0;
        h+=`<div class="sum-row" data-pid="${p.id}">
            <div class="picon">${esc(p.name.substring(0,2).toUpperCase())}</div>
            <div class="pinfo"><div class="pname">${esc(p.name)}</div><div class="pmeta">${esc(p.id.substring(0,8))}...</div></div>
            <span class="ptag">${total} TK can tien</span>
            ${p.link1?`<a href="${esc(p.link1)}" target="_blank" class="link-btn">Link 1</a>`:''}
            ${p.link2?`<a href="${esc(p.link2)}" target="_blank" class="link-btn sec">Link 2</a>`:''}
        </div>`;
    });
    document.getElementById('summary-list').innerHTML=h;
}

function renderProjects(){
    let h='';
    DATA.projects.forEach(p=>{
        const camps=DATA.campaigns[p.id]||[];
        const ini=p.name.substring(0,2).toUpperCase();

        h+=`<div class="proj-sec" data-pid="${p.id}" data-pstatus="${p.status}">`;

        // Header
        h+=`<div class="proj-hdr" onclick="toggleSec(this)">
            <div class="picon">${esc(ini)}</div>
            <h3>${esc(p.name)}</h3>
            <span class="badge badge-${p.status}">${esc(p.status)}</span>
            <span style="margin-left:auto;color:var(--t3);font-size:11px">${camps.length} campaigns</span>
            <span class="toggle">&#9660;</span>
        </div>`;

        // Targeting bar — compact chips
        h+=`<div class="targeting-bar">`;
        if(p.ads_key){
            const keys=pipeSplit(p.ads_key);
            h+=chip('cpc','TU KHOA',keys.join(', '));
        }
        // Links chip
        if(p.link1||p.link2){
            let lhtml='';
            if(p.link1)lhtml+=`<a href="${esc(p.link1)}" target="_blank">Link 1</a>`;
            if(p.link1&&p.link2)lhtml+=`<span class="lsep">|</span>`;
            if(p.link2)lhtml+=`<a href="${esc(p.link2)}" target="_blank">Link 2</a>`;
            h+=`<div class="tg-chip links"><span class="tg-label">LINKS:</span><span class="tg-val">${lhtml}</span></div>`;
        }
        // Gia thau: chien luoc + gia gop 1 chip
        let bidDisplay=p.bidding||'—';
        if(p.cpc)bidDisplay+=' — '+p.cpc;
        h+=chip('bid','GIA THAU',bidDisplay);
        if(p.budget)h+=chip('cpc','NGAN SACH',p.budget);
        // Location chip (gop target + loai tru)
        if(p.target_locations||p.exclude_locations){
            let tgt=p.target_locations?pipeSplit(p.target_locations).join(', '):'—';
            let lv=esc(tgt);
            if(p.exclude_locations){
                let exc=pipeSplit(p.exclude_locations).join(', ');
                lv+=`<span class="tg-exc"> | Loai: ${esc(exc)}</span>`;
            }
            h+=`<div class="tg-chip loc"><span class="tg-label">QG:</span><span class="tg-val">${lv}</span></div>`;
        } else {
            h+=chip('loc','QG','—');
        }
        h+=chip('device','THIET BI',p.devices);
        h+=chip('age','TUOI',p.age_range);
        h+=chip('gender','G.TINH',p.gender);
        h+=`<button class="edit-tg-btn" onclick="event.stopPropagation();toggleEdit('${p.id}')">Chinh sua</button>`;
        h+=`</div>`;

        // Ads preview
        const hls=pipeSplit(p.headlines);const descs=pipeSplit(p.descriptions);
        if(hls.length||descs.length){
            h+=`<div class="ads-preview">`;
            if(hls.length)h+=`<div class="ads-col hl"><div class="ads-col-title">Tieu de (${hls.length})</div><ul>${hls.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></div>`;
            if(descs.length)h+=`<div class="ads-col desc"><div class="ads-col-title">Mo ta (${descs.length})</div><ul>${descs.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></div>`;
            h+=`</div>`;
        }

        // Edit form (hidden)
        h+=`<div class="tg-edit" id="tedit-${p.id}">
            <div class="form-row">
                <div class="fg"><label>Link chinh</label><input id="e-link1-${p.id}" value="${esc(p.link1||'')}"></div>
                <div class="fg"><label>Link phu</label><input id="e-link2-${p.id}" value="${esc(p.link2||'')}"></div>
                <div class="fg"><label>Ngan sach ngay</label><input id="e-budget-${p.id}" value="${esc(p.budget||'')}" placeholder="VD: 200000 VND"></div>
            </div>
            <div class="form-row">
                <div class="fg"><label>Chien luoc gia thau</label>
                    <select id="e-bid-${p.id}" onchange="updateEditBidInput('${p.id}')">
                        ${[['Toi da luot nhan chuot','Toi da luot nhan chuot'],['Toi da luot chuyen doi','Toi da luot chuyen doi'],['CPC thu cong','CPC thu cong'],['CPA muc tieu','CPA muc tieu'],['ROAS muc tieu','ROAS muc tieu']].map(([v,t])=>`<option value="${v}" ${p.bidding===v?'selected':''}>${t}</option>`).join('')}
                    </select>
                </div>
                <div class="fg" id="e-bid-group-${p.id}">
                    <label id="e-bid-label-${p.id}">Gia thau</label>
                    <input id="e-cpc-${p.id}" value="${esc(p.cpc||'')}">
                </div>
            </div>
            <div class="form-row">
                <div class="fg"><label>QG nham den (moi dong 1)</label><textarea rows="2" style="background:var(--input);border:1px solid var(--bdr);color:var(--t1);padding:8px 12px;border-radius:8px;font-size:12px;outline:none;resize:vertical;font-family:inherit" id="e-target-${p.id}">${pipeToLines(p.target_locations)}</textarea></div>
                <div class="fg"><label>QG loai tru (moi dong 1)</label><textarea rows="2" style="background:var(--input);border:1px solid var(--bdr);color:var(--t1);padding:8px 12px;border-radius:8px;font-size:12px;outline:none;resize:vertical;font-family:inherit" id="e-exclude-${p.id}">${pipeToLines(p.exclude_locations)}</textarea></div>
                <div class="fg"><label>Thiet bi</label>
                    <select id="e-devices-${p.id}">${[['Tat ca','Tat ca'],['Di dong','Di dong'],['May tinh','May tinh'],['May tinh bang','May tinh bang']].map(([v,t])=>`<option value="${v}" ${p.devices===v?'selected':''}>${v}</option>`).join('')}</select>
                </div>
                <div class="fg"><label>Do tuoi</label>
                    <select id="e-age-${p.id}">${['18-65+','18-24','25-34','25-44','25-54','35-54','45-65+'].map(a=>`<option value="${a}" ${p.age_range===a?'selected':''}>${a}</option>`).join('')}</select>
                </div>
                <div class="fg"><label>Gioi tinh</label>
                    <select id="e-gender-${p.id}">${[['Tat ca','Tat ca'],['Nam','Nam'],['Nu','Nu']].map(([v,t])=>`<option value="${v}" ${p.gender===v?'selected':''}>${v}</option>`).join('')}</select>
                </div>
            </div>
            <div style="margin-top:8px">
                <div class="fg"><label>Tu khoa (moi dong 1 tu khoa)</label><textarea rows="3" style="background:var(--input);border:1px solid var(--bdr);color:var(--t1);padding:8px 12px;border-radius:8px;font-size:12px;outline:none;resize:vertical;font-family:inherit;width:100%" id="e-key-${p.id}">${pipeToLines(p.ads_key)}</textarea></div>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:8px">
                <div class="fg"><label>Tieu de (moi dong 1)</label><textarea rows="4" style="background:var(--input);border:1px solid var(--bdr);color:var(--t1);padding:8px 12px;border-radius:8px;font-size:12px;outline:none;resize:vertical;font-family:inherit" id="e-hl-${p.id}">${pipeToLines(p.headlines)}</textarea></div>
                <div class="fg"><label>Mo ta (moi dong 1)</label><textarea rows="4" style="background:var(--input);border:1px solid var(--bdr);color:var(--t1);padding:8px 12px;border-radius:8px;font-size:12px;outline:none;resize:vertical;font-family:inherit" id="e-desc-${p.id}">${pipeToLines(p.descriptions)}</textarea></div>
            </div>
            <div class="form-actions">
                <button class="btn btn-primary" onclick="saveTargeting('${p.id}')">Luu</button>
                <button class="btn btn-danger" onclick="toggleEdit('${p.id}')">Huy</button>
            </div>
        </div>`;

        // Campaign table
        h+='<div class="proj-body">';
        if(!camps.length){h+='<div class="empty">Chua co campaign nao</div>'}
        else{
            h+=`<table><thead><tr><th>Key (Account)</th><th>Campaign</th><th>Status</th><th>Budget</th><th>Gia Thau</th><th>Tieu De</th><th>Mo Ta</th></tr></thead><tbody>`;
            camps.forEach(c=>{
                const st=c.status||'draft';let bid=c.bidding||'';if(typeof bid==='object')bid=JSON.stringify(bid);
                const hls2=parseList(c.headlines).slice(0,3);const descs2=parseList(c.descriptions).slice(0,2);
                h+=`<tr data-status="${esc(st)}" data-budget="${c.budget||0}" data-name="${esc(c.name||'')}">
                    <td class="mono c-acct">${esc(c.adsAccountId||'—')}</td><td>${esc(c.name||'')}</td>
                    <td><span class="badge badge-${st}">${esc(st)}</span></td>
                    <td class="mono c-budget">$${(c.budget||0).toFixed(2)}</td>
                    <td class="mono c-bid">${esc(bid)}</td>
                    <td class="c-hl">${hls2.map(esc).join('<br>')}</td>
                    <td class="c-desc">${descs2.map(esc).join('<br>')}</td></tr>`;
            });
            h+='</tbody></table>';
        }
        h+='</div></div>';
    });
    document.getElementById('project-list').innerHTML=h;
}

function chip(cls,label,val){
    return `<div class="tg-chip ${cls}"><span class="tg-label">${label}:</span><span class="tg-val">${esc(val)||'—'}</span></div>`;
}

// === ACTIONS ===
async function addProject(){
    const name=document.getElementById('f-name').value.trim();
    if(!name){toast('Nhap ten du an!');return}
    await api('/api/projects','POST',{
        name,
        ads_key:linesToPipe('f-key'),
        link1:document.getElementById('f-link1').value.trim()||null,
        link2:document.getElementById('f-link2').value.trim()||null,
        cpc:document.getElementById('f-cpc').value.trim()||null,
        bidding:document.getElementById('f-bidding').value,
        budget:document.getElementById('f-budget').value.trim()||null,
        target_locations:linesToPipe('f-target'),
        exclude_locations:linesToPipe('f-exclude'),
        devices:document.getElementById('f-devices').value,
        age_range:document.getElementById('f-age').value,
        gender:document.getElementById('f-gender').value,
        headlines:linesToPipe('f-headlines'),
        descriptions:linesToPipe('f-descriptions'),
    });
    ['f-name','f-link1','f-link2','f-cpc','f-budget'].forEach(id=>document.getElementById(id).value='');
    ['f-key','f-target','f-exclude','f-headlines','f-descriptions'].forEach(id=>document.getElementById(id).value='');
    ['f-headlines','f-descriptions'].forEach(id=>document.getElementById(id).value='');
    toast('Da tao du an: '+name);
    await loadAll();
}

function toggleEdit(pid){document.getElementById('tedit-'+pid).classList.toggle('open')}

async function saveTargeting(pid){
    await api('/api/projects/'+pid+'/update','POST',{
        ads_key:linesToPipe('e-key-'+pid),
        cpc:document.getElementById('e-cpc-'+pid).value.trim()||null,
        bidding:document.getElementById('e-bid-'+pid).value,
        budget:document.getElementById('e-budget-'+pid).value.trim()||null,
        target_locations:linesToPipe('e-target-'+pid),
        exclude_locations:linesToPipe('e-exclude-'+pid),
        devices:document.getElementById('e-devices-'+pid).value,
        age_range:document.getElementById('e-age-'+pid).value,
        gender:document.getElementById('e-gender-'+pid).value,
        link1:document.getElementById('e-link1-'+pid).value.trim()||null,
        link2:document.getElementById('e-link2-'+pid).value.trim()||null,
        headlines:linesToPipe('e-hl-'+pid),
        descriptions:linesToPipe('e-desc-'+pid),
    });
    toast('Da luu!');await loadAll();
}

// === DROPDOWN / FILTER ===
document.addEventListener('click',e=>{document.querySelectorAll('.dropdown').forEach(d=>{if(!d.contains(e.target))d.classList.remove('open')})});
function toggleDD(id){event.stopPropagation();const d=document.getElementById(id);document.querySelectorAll('.dropdown').forEach(x=>{if(x.id!==id)x.classList.remove('open')});d.classList.toggle('open')}
function toggleSec(hdr){hdr.parentElement.classList.toggle('closed')}

function filterProject(pid,el){
    document.querySelectorAll('.proj-sec').forEach(s=>{s.style.display=(pid==='all'||s.dataset.pid===pid)?'':'none'});
    document.querySelectorAll('.sum-row').forEach(r=>{r.style.display=(pid==='all'||r.dataset.pid===pid)?'':'none'});
    document.querySelectorAll('#dd-proj-menu .dd-item').forEach(i=>i.classList.remove('active'));
    if(el)el.classList.add('active');
    document.getElementById('dd-proj-label').textContent=pid==='all'?'Du an':(el?el.textContent:'Du an');
    document.getElementById('dd-proj').classList.remove('open');
}
function filterStatus(st,el){
    document.querySelectorAll('tbody tr').forEach(r=>{r.style.display=(st==='all'||r.dataset.status===st)?'':'none'});
    document.querySelectorAll('#dd-status-menu .dd-item').forEach(i=>i.classList.remove('active'));
    if(el)el.classList.add('active');
    document.getElementById('dd-status-label').textContent=st==='all'?'Status':(el?el.textContent:'Status');
    document.getElementById('dd-status').classList.remove('open');
}
function sortBy(mode,el){
    document.querySelectorAll('tbody').forEach(tb=>{
        const rows=Array.from(tb.querySelectorAll('tr'));
        rows.sort((a,b)=>{
            if(mode==='budget-desc')return(parseFloat(b.dataset.budget)||0)-(parseFloat(a.dataset.budget)||0);
            if(mode==='budget-asc')return(parseFloat(a.dataset.budget)||0)-(parseFloat(b.dataset.budget)||0);
            if(mode==='name-asc')return(a.dataset.name||'').localeCompare(b.dataset.name||'');
            if(mode==='name-desc')return(b.dataset.name||'').localeCompare(a.dataset.name||'');
            return 0;
        });
        rows.forEach(r=>tb.appendChild(r));
    });
    document.querySelectorAll('#dd-sort .dd-item').forEach(i=>i.classList.remove('active'));
    if(el)el.classList.add('active');
    document.getElementById('dd-sort').classList.remove('open');
}

loadAll();
</script>
</body>
</html>"""


if __name__ == "__main__":
    print(f"Starting dashboard at http://localhost:{PORT}")
    webbrowser.open(f"http://localhost:{PORT}")
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()
