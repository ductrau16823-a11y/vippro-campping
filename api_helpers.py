"""
API helpers cho vippro campping — giao tiep voi dashboard API.
"""

import requests

DASHBOARD_API = "http://localhost:3000/api"


def upsert_campaign(ads_account_id, campaign_name, campaign_id=None, status="created", notes=None):
    """Luu/update campaign vao DB sau khi tao thanh cong.

    API POST /api/campaigns can: name, profileId (bat buoc), adsAccountId, status, notes.
    Tu ads_account_id (dang XXX-XXX-XXXX), tim profileId qua API ads-accounts.

    Return: dict hoac None
    """
    profile_id = None
    ads_db_id = None
    try:
        res = requests.get(f"{DASHBOARD_API}/ads-accounts", params={"accountId": ads_account_id}, timeout=10)
        if res.ok:
            items = res.json().get("data", [])
            for item in items:
                if item.get("accountId") == ads_account_id:
                    profile_id = item.get("profileId")
                    ads_db_id = item.get("id")
                    break
    except Exception:
        pass

    if not profile_id:
        print(f"[!] Khong tim duoc profileId cho account {ads_account_id} — skip upsert campaign")
        return None

    payload = {
        "name": campaign_name,
        "profileId": profile_id,
        "status": status,
    }
    if ads_db_id:
        payload["adsAccountId"] = ads_db_id
    if notes:
        payload["notes"] = notes

    try:
        res = requests.post(f"{DASHBOARD_API}/campaigns", json=payload, timeout=15)
        res.raise_for_status()
        data = res.json().get("data", {})
        print(f"[API] Upsert campaign '{campaign_name}' (account={ads_account_id}) -> id={data.get('id')}")
        return data
    except Exception as e:
        print(f"[!] Loi upsert campaign: {e}")
        return None


def fetch_ads_account_by_id(account_id):
    """Lay thong tin 1 TK Ads tu DB theo accountId."""
    try:
        res = requests.get(f"{DASHBOARD_API}/ads-accounts", params={"accountId": account_id}, timeout=10)
        if res.ok:
            items = res.json().get("data", [])
            for item in items:
                if item.get("accountId") == account_id:
                    return item
    except Exception:
        pass
    return None
