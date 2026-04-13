"""
API helpers: Lay du lieu TK Ads va campaign tu dashboard API.
"""

import requests

DASHBOARD_API = "http://localhost:3000/api"


def fetch_ads_accounts(status=None):
    """Lay danh sach TK Ads tu DB.

    Args:
        status: Loc theo status (vd: 'verified', 'active'). None = lay het.

    Return: list of dict {id, accountId, gmailEmail, status, ...}
    """
    try:
        params = {}
        if status:
            params["status"] = status
        res = requests.get(f"{DASHBOARD_API}/ads-accounts", params=params, timeout=15)
        res.raise_for_status()
        return res.json().get("data", []) or []
    except Exception as e:
        print(f"[!] Loi fetch ads accounts: {e}")
        return []


def fetch_ads_account_by_id(account_id):
    """Lay thong tin 1 TK Ads theo accountId (XXX-XXX-XXXX).

    Return: dict hoac None
    """
    try:
        res = requests.get(
            f"{DASHBOARD_API}/ads-accounts",
            params={"accountId": account_id},
            timeout=15,
        )
        res.raise_for_status()
        data = res.json().get("data", [])
        if data:
            return data[0]
        return None
    except Exception as e:
        print(f"[!] Loi fetch ads account {account_id}: {e}")
        return None


def fetch_campaign_data(ads_account_id):
    """Lay data campaign can tao cho 1 TK Ads.

    Return: dict voi campaign settings, keywords, ads copy, budget...
    Hien tai tra ve None (chua co API endpoint) - se bo sung sau.
    """
    # TODO: Implement khi co API endpoint cho campaign data
    try:
        res = requests.get(
            f"{DASHBOARD_API}/campaigns",
            params={"adsAccountId": ads_account_id},
            timeout=15,
        )
        res.raise_for_status()
        return res.json().get("data", []) or []
    except Exception as e:
        print(f"[!] Loi fetch campaign data: {e}")
        return []


def upsert_campaign(ads_account_id, campaign_name, campaign_id=None, status="created", notes=None):
    """Luu/update campaign vao DB sau khi tao thanh cong.

    Return: dict hoac None
    """
    payload = {
        "adsAccountId": ads_account_id,
        "campaignName": campaign_name,
        "status": status,
    }
    if campaign_id:
        payload["campaignId"] = campaign_id
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


def fetch_gmail_profiles():
    """Lay danh sach Gmail + GenLogin profile tu DB.

    Return: list of dict {email, profileId, ...}
    """
    try:
        res = requests.get(f"{DASHBOARD_API}/profiles", timeout=15)
        res.raise_for_status()
        return res.json().get("data", []) or []
    except Exception as e:
        print(f"[!] Loi fetch gmail profiles: {e}")
        return []
