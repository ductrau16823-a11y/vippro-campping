"""
db_helpers.py — Doc/ghi du lieu tu SQLite (dev.db) cho flow camp.

Flow:
  1. Anh nhap campaign data tren dashboard -> luu vao DB (status='pending')
  2. Code doc DB: get_pending_campaigns() -> lay campaign can chay
  3. Chay xong: update_campaign_status() -> doi status thanh 'published' / 'failed'

Cac ham chinh:
  - get_verified_accounts()        : lay AdsAccount verified + profile + gmail
  - get_account_detail(id)         : lay chi tiet 1 account
  - get_pending_campaigns()        : lay tat ca campaign pending can chay
  - get_campaigns_for_account(id)  : lay campaign cua 1 account
  - get_full_campaign_config(id)   : lay campaign + parse config JSON day du
  - update_campaign_status(id, st) : cap nhat status sau khi chay
  - save_campaign_result(...)      : tao moi 1 campaign record
"""

import sqlite3
import json
import os
import uuid
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "dev.db")


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# =====================================================================
#  DOC THONG TIN ACCOUNT
# =====================================================================

def get_verified_accounts():
    """Lay danh sach AdsAccount co the len camp (verified + paused) kem thong tin Profile + Gmail.

    Return: list of dict {
        accountId, ads_status, profileId,
        profile_name, genloginId, gmailId, gmail_email, proxyId
    }
    """
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT
                a.accountId,
                a.status       AS ads_status,
                a.profileId,
                p.name         AS profile_name,
                p.genloginId,
                p.gmailId,
                g.email        AS gmail_email,
                p.proxyId
            FROM AdsAccount a
            JOIN Profile p ON a.profileId = p.id
            LEFT JOIN Gmail g ON p.gmailId = g.id
            WHERE a.status IN ('verified', 'paused')
            AND a.status NOT IN ('suspended', 'needs_setup', 'failed')
            ORDER BY a.createdAt
        """)
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def get_account_detail(account_id):
    """Lay chi tiet 1 AdsAccount theo accountId (vd: '769-916-1115').

    Return: dict hoac None
    """
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT
                a.accountId,
                a.status       AS ads_status,
                a.profileId,
                p.name         AS profile_name,
                p.genloginId,
                p.gmailId,
                g.email        AS gmail_email,
                p.proxyId
            FROM AdsAccount a
            JOIN Profile p ON a.profileId = p.id
            LEFT JOIN Gmail g ON p.gmailId = g.id
            WHERE a.accountId = ?
        """, (account_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# =====================================================================
#  DOC CAMPAIGN CONFIG TU DB
# =====================================================================

def get_pending_campaigns():
    """Lay tat ca campaign co status='pending' — can chay.

    Return: list of dict, moi dict da parse config JSON thanh cac field rieng:
        {id, name, profileId, adsAccountId, type, status, budget,
         keywords, goal, bidding, adgroup_name, final_url, headlines, descriptions, ...}
    """
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT c.*, a.accountId, p.genloginId, g.email AS gmail_email
            FROM Campaign c
            JOIN Profile p ON c.profileId = p.id
            LEFT JOIN AdsAccount a ON c.adsAccountId = a.accountId
            LEFT JOIN Gmail g ON p.gmailId = g.id
            WHERE c.status = 'pending'
            ORDER BY c.createdAt
        """)
        results = []
        for row in cur.fetchall():
            data = dict(row)
            _parse_config(data)
            _parse_keywords(data)
            results.append(data)
        return results
    finally:
        conn.close()


def get_campaigns_for_account(account_id):
    """Lay tat ca campaign cua 1 account (moi status).

    Return: list of dict
    """
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT *
            FROM Campaign
            WHERE adsAccountId = ?
            ORDER BY createdAt
        """, (account_id,))
        results = []
        for row in cur.fetchall():
            data = dict(row)
            _parse_config(data)
            _parse_keywords(data)
            results.append(data)
        return results
    finally:
        conn.close()


def get_full_campaign_config(campaign_id):
    """Lay 1 campaign theo id, parse day du config JSON.

    Return: dict hoac None
    """
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM Campaign WHERE id = ?", (campaign_id,))
        row = cur.fetchone()
        if not row:
            return None
        data = dict(row)
        _parse_config(data)
        _parse_keywords(data)
        return data
    finally:
        conn.close()


def _parse_config(data):
    """Parse cot 'config' (JSON string) thanh cac field rieng.

    Config JSON co the chua: goal, bidding, adgroup_name, final_url,
    headlines, descriptions, va bat ky field nao khac.
    """
    config_str = data.get("config")
    if config_str:
        try:
            config = json.loads(config_str)
            # Merge config vao data, khong ghi de field da co
            for key, val in config.items():
                if key not in data or data[key] is None:
                    data[key] = val
        except (json.JSONDecodeError, TypeError):
            pass


def _parse_keywords(data):
    """Parse cot 'keywords' — co the la JSON array hoac text xuong dong."""
    kw = data.get("keywords")
    if kw and isinstance(kw, str):
        try:
            parsed = json.loads(kw)
            if isinstance(parsed, list):
                data["keywords"] = parsed
                return
        except (json.JSONDecodeError, TypeError):
            pass
        # Fallback: split theo dong
        data["keywords"] = [line.strip() for line in kw.splitlines() if line.strip()]


# =====================================================================
#  GHI KET QUA CAMPAIGN
# =====================================================================

def update_campaign_status(campaign_id, status, notes=None):
    """Cap nhat status cua campaign sau khi chay.

    Args:
        campaign_id: id cua campaign record
        status: 'published' | 'failed' | 'running' | ...
        notes: ghi chu them (loi, ket qua...)
    """
    conn = _connect()
    try:
        now = datetime.now(timezone.utc).isoformat()
        if notes is not None:
            conn.execute("""
                UPDATE Campaign SET status = ?, notes = ?, updatedAt = ? WHERE id = ?
            """, (status, notes, now, campaign_id))
        else:
            conn.execute("""
                UPDATE Campaign SET status = ?, updatedAt = ? WHERE id = ?
            """, (status, now, campaign_id))
        conn.commit()
        print(f"[DB] Campaign {campaign_id} -> status={status}")
    finally:
        conn.close()


def save_campaign_result(account_id, profile_id, campaign_name,
                         campaign_type="search", budget=None, keywords=None,
                         config=None, status="published", notes=None):
    """Tao moi 1 campaign record trong DB.

    Return: id cua record moi
    """
    conn = _connect()
    try:
        now = datetime.now(timezone.utc).isoformat()
        record_id = str(uuid.uuid4())

        keywords_str = json.dumps(keywords, ensure_ascii=False) if keywords else None
        config_str = json.dumps(config, ensure_ascii=False) if config else None

        conn.execute("""
            INSERT INTO Campaign
                (id, name, profileId, adsAccountId, type, status,
                 budget, keywords, config, notes, createdAt, updatedAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (record_id, campaign_name, profile_id, account_id,
              campaign_type, status, budget, keywords_str, config_str,
              notes, now, now))
        conn.commit()
        print(f"[DB] Saved campaign '{campaign_name}' (account={account_id}) -> id={record_id}")
        return record_id
    finally:
        conn.close()


# =====================================================================
#  PROJECT — CRUD + TONG HOP
# =====================================================================

def get_all_projects():
    """Lay tat ca project."""
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM Project ORDER BY createdAt DESC")
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def get_project(project_id):
    """Lay 1 project theo id."""
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM Project WHERE id = ?", (project_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_project(name, link1=None, link2=None, status="running",
                    cpc=None, bidding=None, bid_value=None, budget=None,
                    ads_key=None, target_locations=None,
                    exclude_locations=None, devices=None, age_range=None,
                    gender=None, headlines=None, descriptions=None):
    """Tao moi 1 project. Return: id."""
    conn = _connect()
    try:
        now = datetime.now(timezone.utc).isoformat()
        project_id = str(uuid.uuid4())
        conn.execute("""
            INSERT INTO Project
                (id, name, link1, link2, status, cpc, bidding, bid_value,
                 budget, ads_key, target_locations, exclude_locations,
                 devices, age_range, gender, headlines, descriptions,
                 createdAt, updatedAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (project_id, name, link1, link2, status, cpc, bidding,
              bid_value, budget, ads_key, target_locations,
              exclude_locations, devices, age_range, gender,
              headlines, descriptions, now, now))
        conn.commit()
        print(f"[DB] Created project '{name}' -> id={project_id}")
        return project_id
    finally:
        conn.close()


def update_project(project_id, **fields):
    """Cap nhat project. fields co the la: name, link1, link2, status."""
    conn = _connect()
    try:
        now = datetime.now(timezone.utc).isoformat()
        allowed = {"name", "link1", "link2", "status", "cpc",
                   "target_locations", "exclude_locations", "devices",
                   "age_range", "gender", "headlines", "descriptions",
                   "bidding", "bid_value", "budget", "ads_key"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return
        updates["updatedAt"] = now
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [project_id]
        conn.execute(f"UPDATE Project SET {set_clause} WHERE id = ?", values)
        conn.commit()
        print(f"[DB] Updated project {project_id}")
    finally:
        conn.close()


def delete_project(project_id):
    """Xoa project."""
    conn = _connect()
    try:
        conn.execute("DELETE FROM Project WHERE id = ?", (project_id,))
        conn.commit()
    finally:
        conn.close()


def get_project_summary():
    """Tong hop: danh sach du an dang chay + so TK can tien (campaign published) cho moi du an.

    Return: list of dict {
        project_id, project_name, link1, link2, project_status,
        total_accounts (so TK co campaign published)
    }
    """
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT
                p.id            AS project_id,
                p.name          AS project_name,
                p.link1,
                p.link2,
                p.status        AS project_status,
                COUNT(DISTINCT c.adsAccountId) AS total_accounts
            FROM Project p
            LEFT JOIN Campaign c ON c.projectId = p.id AND c.status = 'published'
            WHERE p.status = 'running'
            GROUP BY p.id
            ORDER BY p.name
        """)
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def get_campaigns_by_project(project_id):
    """Lay tat ca campaign cua 1 project, kem thong tin account."""
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT c.*, a.accountId, p.genloginId
            FROM Campaign c
            LEFT JOIN AdsAccount a ON c.adsAccountId = a.accountId
            LEFT JOIN Profile p ON c.profileId = p.id
            WHERE c.projectId = ?
            ORDER BY c.createdAt
        """, (project_id,))
        results = []
        for row in cur.fetchall():
            data = dict(row)
            _parse_config(data)
            _parse_keywords(data)
            results.append(data)
        return results
    finally:
        conn.close()


# =====================================================================
#  QUICK TEST
# =====================================================================

if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    # Test 1: Lay TK verified
    accounts = get_verified_accounts()
    print(f"=== {len(accounts)} TK Ads verified ===\n")
    for acc in accounts:
        print(f"  {acc['accountId']}  |  genloginId={acc['genloginId']}  |  gmail={acc['gmail_email']}")

    # Test 2: Lay pending campaigns
    pending = get_pending_campaigns()
    print(f"\n=== {len(pending)} campaigns pending ===")
    for c in pending:
        print(f"  {c['name']}  |  account={c.get('adsAccountId')}  |  type={c['type']}")
