#!/usr/bin/env python3
"""
=== GENLOGIN API MODULE ===
Module dung chung - copy tu project auto-report.
Quan ly: token, start/stop profile, connect Selenium.
"""

import os
import json
import requests
import urllib.parse
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("GENLOGIN_BASE_URL", "http://localhost:55550")

_cached_token = None


def get_token():
    global _cached_token
    if _cached_token:
        return _cached_token

    email = os.getenv("GENLOGIN_EMAIL", "").strip()
    password = os.getenv("GENLOGIN_PASSWORD", "").strip()

    if not email or not password:
        raise ValueError(
            "Thieu cau hinh Email/Pass GenLogin trong file .env\n"
            "Mo file .env va dien:\n"
            "  GENLOGIN_EMAIL=email@gmail.com\n"
            "  GENLOGIN_PASSWORD=password"
        )

    url = f"{BASE_URL}/backend/auth/login"
    payload = {"username": email, "password": password}

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            print(f"[API] Dang lay token GenLogin... (lan {attempt})")
            res = requests.post(url, json=payload, timeout=15)
            res.raise_for_status()
            data = res.json()
            token = data.get("data", {}).get("access_token")
            if not token:
                raise Exception(f"Response khong co access_token: {json.dumps(data)[:300]}")
            _cached_token = token
            print(f"[API] Lay token thanh cong!")
            return token
        except requests.exceptions.ConnectionError:
            raise Exception(
                f"Khong ket noi duoc GenLogin tai {BASE_URL}\n"
                "Hay mo GenLogin truoc roi chay lai!"
            )
        except requests.exceptions.HTTPError as e:
            if res.status_code == 429:
                if attempt < max_retries:
                    wait = attempt * 5
                    print(f"[API] Rate limit (429), cho {wait}s roi thu lai...")
                    import time
                    time.sleep(wait)
                    continue
                raise Exception(f"GenLogin rate limit (429) sau {max_retries} lan thu.")
            elif res.status_code in (401, 403):
                raise Exception(f"Sai email/password GenLogin: {e}")
            else:
                raise Exception(f"Loi dang nhap GenLogin ({res.status_code}): {e}")
        except Exception as e:
            raise Exception(f"Khong the lay token GenLogin: {e}")


def clear_token_cache():
    global _cached_token
    _cached_token = None


def _headers(token=None):
    t = token or get_token()
    return {"Authorization": f"Bearer {t}"}


def resolve_profile_id(identifier, token=None):
    identifier = str(identifier).strip()
    if not identifier:
        return None
    if identifier.isdigit():
        return identifier

    t = token or get_token()
    headers = _headers(t)
    encoded_name = urllib.parse.quote(identifier)
    try:
        url = f"{BASE_URL}/backend/profiles?keyword={encoded_name}&limit=20"
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            data_json = res.json()
            data_val = data_json.get("data")
            items = []
            if isinstance(data_val, list):
                items = data_val
            elif isinstance(data_val, dict):
                items = data_val.get("data", data_val.get("items", []))
            for p in items:
                p_name = (
                    p.get("profile_data", {}).get("name", "").strip()
                    or p.get("name", "").strip()
                )
                if p_name.lower() == identifier.lower():
                    return str(p.get("id"))
    except Exception as e:
        print(f"[!] Loi khi giai ma ID tu Ten ho so '{identifier}': {e}")
    return None


def start_profile(profile_id, token=None):
    t = token or get_token()
    headers = _headers(t)
    url = f"{BASE_URL}/backend/profiles/{profile_id}/start"

    try:
        print(f"[API] Dang start profile {profile_id}...")
        res = requests.put(url, headers=headers, timeout=30)
        res.raise_for_status()
        data = res.json()
        print(f"[API] Start profile thanh cong!")
        return data
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else "?"
        body = e.response.text[:300] if e.response is not None else ""
        if status == 401:
            print(f"[API] Token het han! Dang lay token moi...")
            clear_token_cache()
            try:
                t2 = get_token()
                headers2 = _headers(t2)
                res2 = requests.put(url, headers=headers2, timeout=30)
                res2.raise_for_status()
                return res2.json()
            except Exception as e2:
                raise Exception(f"Loi start profile sau khi refresh token: {e2}")
        raise Exception(f"Loi start profile {profile_id} (HTTP {status}): {body}")
    except requests.exceptions.ConnectionError:
        raise Exception(f"Khong ket noi duoc GenLogin tai {BASE_URL}")
    except Exception as e:
        raise Exception(f"Loi khoi dong profile {profile_id}: {e}")


def stop_profile(profile_id, token=None):
    t = token or get_token()
    headers = _headers(t)
    url = f"{BASE_URL}/backend/profiles/{profile_id}/stop"
    try:
        requests.put(url, headers=headers, timeout=10)
        print(f"[API] Profile {profile_id} da duoc tat an toan.")
    except Exception as e:
        print(f"[API] Loi khi tat profile {profile_id}: {e}")


def get_debugger_address(start_result):
    if not isinstance(start_result, dict):
        return None
    data = start_result.get("data", start_result)
    if not isinstance(data, dict):
        return None

    port = data.get("port")
    if port:
        return f"127.0.0.1:{port}"

    ws = data.get("wsEndpoint") or data.get("ws_endpoint")
    if isinstance(ws, str) and ws.strip():
        try:
            from urllib.parse import urlparse
            parsed = urlparse(ws)
            if parsed.hostname and parsed.port:
                return f"{parsed.hostname}:{parsed.port}"
        except Exception:
            pass

    rpu = data.get("remotePortUrl")
    if isinstance(rpu, str) and rpu.strip():
        try:
            from urllib.parse import urlparse
            parsed = urlparse(rpu)
            if parsed.hostname and parsed.port:
                return f"{parsed.hostname}:{parsed.port}"
        except Exception:
            pass

    address_keys = (
        "http_address", "debuggerAddress",
        "remote_address", "debug_address", "browser_address",
    )
    for key in address_keys:
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def connect_selenium(debugger_address, browser_version=None):
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service

    options = Options()
    options.add_experimental_option("debuggerAddress", debugger_address)

    try:
        from webdriver_manager.chrome import ChromeDriverManager
        if browser_version:
            service = Service(ChromeDriverManager(driver_version=browser_version).install())
        else:
            service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
    except Exception:
        try:
            driver = webdriver.Chrome(options=options)
        except Exception as e:
            raise Exception(
                f"Khong ket noi duoc Selenium vao {debugger_address}: {e}"
            )

    driver.set_page_load_timeout(300)
    driver.set_script_timeout(120)
    return driver


def get_browser_version(start_result):
    if not isinstance(start_result, dict):
        return None
    data = start_result.get("data", start_result)
    if isinstance(data, dict):
        return data.get("browser_version")
    return None
