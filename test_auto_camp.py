#!/usr/bin/env python3
"""
Auto camp v3 — scan trang truoc, xac dinh dang o dau, lam het cac buoc cho trang do.
"""
import sys
import time
import pyotp
import requests

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from genlogin_api import connect_selenium
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

# === CONFIG ===
PORT = "62030"
ACCOUNT_ID = "686-725-3911"

res = requests.get("http://localhost:3000/api/campping-vip", timeout=5)
project_data = None
for p in res.json().get("data", []):
    if p["name"] == "viltrox":
        project_data = p
        break
if not project_data:
    print("Khong tim thay project viltrox!")
    sys.exit(1)

config = {
    "name": project_data["name"],
    "budget": str(project_data.get("budget") or "5"),
    "cpc": project_data.get("cpc", ""),
    "keywords": [k.strip() for k in (project_data.get("adsKey") or "").split("|") if k.strip()],
    "final_url": project_data.get("link1", ""),
    "headlines": [h.strip() for h in (project_data.get("headlines") or "").split("|") if h.strip()],
    "descriptions": [d.strip() for d in (project_data.get("descriptions") or "").split("|") if d.strip()],
    "target_locations": [l.strip() for l in (project_data.get("targetLocations") or "").split("|") if l.strip()],
    "exclude_locations": [l.strip() for l in (project_data.get("excludeLocations") or "").split("|") if l.strip()],
}
print(f"Project: {config['name']} | Budget: ${config['budget']} | CPC: ${config['cpc']}")

driver = None

# === HELPERS ===
def log(msg):
    print(f"  {msg}", flush=True)

def js_click(el):
    driver.execute_script("arguments[0].click()", el)

def action_click(el):
    ActionChains(driver).move_to_element(el).pause(0.3).click().perform()

def clear_and_type(el, value):
    el.click()
    time.sleep(0.3)
    el.send_keys(Keys.CONTROL, "a")
    time.sleep(0.2)
    el.send_keys(str(value))
    time.sleep(0.3)

def js_set_textarea(el, value):
    driver.execute_script(
        "arguments[0].value = arguments[1];"
        "arguments[0].dispatchEvent(new Event('input', {bubbles: true}));"
        "arguments[0].dispatchEvent(new Event('change', {bubbles: true}));",
        el, value,
    )

def get_2fa_secret(email):
    try:
        r = requests.get("http://localhost:3000/api/gmail", timeout=10)
        data = r.json()
        items = data.get("data", data) if isinstance(data, dict) else data
        for g in items:
            if g.get("email", "").lower() == email.lower():
                return g.get("twoFactorKey")
    except Exception:
        pass
    return None

def handle_2fa():
    for d in driver.find_elements(By.XPATH, "//material-dialog"):
        try:
            if not d.is_displayed() or "Confirm" not in d.text:
                continue
        except Exception:
            continue
        log("[2FA] Gap popup Confirm...")
        for b in d.find_elements(By.XPATH, ".//material-button | .//button"):
            try:
                if b.is_displayed() and b.text.strip() in ("Confirm", "Try again"):
                    action_click(b)
                    log(f"[2FA] Click {b.text.strip()}")
                    time.sleep(5)
                    break
            except Exception:
                pass
        # Try again lan 2
        for d2 in driver.find_elements(By.XPATH, "//material-dialog"):
            try:
                if d2.is_displayed() and "Try again" in d2.text:
                    for b2 in d2.find_elements(By.XPATH, ".//material-button | .//button"):
                        if b2.is_displayed() and "Try again" in b2.text:
                            action_click(b2)
                            log("[2FA] Click Try again")
                            time.sleep(5)
                            break
                    break
            except Exception:
                pass
        # Tab 2FA
        time.sleep(2)
        if len(driver.window_handles) > 2:
            for h in driver.window_handles:
                driver.switch_to.window(h)
                try:
                    if "Sign in" not in driver.title:
                        continue
                    totp_els = driver.find_elements(By.CSS_SELECTOR, "input#totpPin")
                    if not totp_els or not totp_els[0].is_displayed():
                        continue
                    email = ""
                    for e in driver.find_elements(By.XPATH, "//*[contains(text(), '@gmail.com')]"):
                        if e.is_displayed():
                            email = e.text.strip().lower()
                            break
                    secret = get_2fa_secret(email)
                    if secret:
                        code = pyotp.TOTP(secret).now()
                        log(f"[2FA] {email} -> {code}")
                        totp_els[0].click()
                        time.sleep(0.5)
                        totp_els[0].send_keys(code)
                        time.sleep(1)
                        action_click(driver.find_element(By.CSS_SELECTOR, "#totpNext button"))
                        log("[2FA] OK!")
                        time.sleep(5)
                    break
                except Exception:
                    pass
            for h in driver.window_handles:
                driver.switch_to.window(h)
                try:
                    if "Google Ads" in driver.title:
                        break
                except Exception:
                    pass
        return True
    return False

def handle_popups():
    for d in driver.find_elements(By.XPATH, "//material-dialog"):
        try:
            if not d.is_displayed() or not d.text.strip():
                continue
            if "Conversion goals" in d.text:
                for cb in d.find_elements(By.XPATH, ".//material-button[contains(@aria-label, 'Close')]"):
                    if cb.is_displayed():
                        js_click(cb)
                        log("[POPUP] Dong Conversion goals")
                        time.sleep(2)
                        break
            elif "Exit guide" in d.text:
                for b in d.find_elements(By.XPATH, ".//material-button | .//button"):
                    if b.is_displayed() and "Leave" in b.text:
                        js_click(b)
                        log("[POPUP] Leave")
                        time.sleep(3)
                        break
        except Exception:
            pass

def handle_draft():
    for d in driver.find_elements(By.XPATH, "//material-dialog"):
        try:
            if not d.is_displayed() or "draft" not in d.text.lower():
                continue
            log("[DRAFT] Gap dialog draft...")
            for n in d.find_elements(By.XPATH, ".//campaign-name-cell//div[contains(@class, 'name')]"):
                if n.is_displayed():
                    if n.text.strip() == config["name"]:
                        js_click(n)
                        log(f"[DRAFT] Click vao '{n.text.strip()}'")
                        time.sleep(5)
                    else:
                        for b in d.find_elements(By.XPATH, ".//material-button | .//button"):
                            if b.is_displayed() and "Start new" in b.text:
                                js_click(b)
                                log("[DRAFT] Start new")
                                time.sleep(3)
                                break
                    return True
        except Exception:
            pass
    return False

def check_all():
    handle_2fa()
    handle_popups()
    handle_draft()

def scan_page():
    """Scan trang — tra ve danh sach features hien co."""
    features = set()
    # Buttons
    for b in driver.find_elements(By.XPATH, "//button | //material-button"):
        try:
            if b.is_displayed() and b.text.strip():
                t = b.text.strip()
                if t in ("Continue", "Next", "Skip", "Publish campaign"):
                    features.add(f"btn:{t}")
        except Exception:
            pass
    # Checkboxes
    for c in driver.find_elements(By.XPATH, "//mat-checkbox | //material-checkbox"):
        try:
            if c.is_displayed():
                txt = c.text[:60]
                if "Website visits" in txt:
                    features.add("cb:website_visits")
                if "Search Partners" in txt or "search-checkbox" in (c.get_attribute("class") or ""):
                    features.add("cb:search_partners")
                if "Display Network" in txt or "display-checkbox" in (c.get_attribute("class") or ""):
                    features.add("cb:display_network")
                if "maximum cost per click" in txt:
                    features.add("cb:max_cpc")
        except Exception:
            pass
    # Inputs
    for inp in driver.find_elements(By.XPATH, "//input"):
        try:
            if inp.is_displayed():
                label = inp.get_attribute("aria-label") or ""
                if "Campaign name" in label:
                    features.add("input:campaign_name")
                if "Final URL" in label:
                    features.add("input:final_url")
                if "budget" in label.lower():
                    features.add("input:budget")
        except Exception:
            pass
    # Textareas
    for ta in driver.find_elements(By.XPATH, "//textarea"):
        try:
            if ta.is_displayed():
                label = ta.get_attribute("aria-label") or ""
                if "keyword" in label.lower():
                    features.add("ta:keywords")
                if "Description" in label:
                    features.add("ta:description")
        except Exception:
            pass
    # Sections
    for el in driver.find_elements(By.XPATH, "//section[contains(@class, 'headline')]//input"):
        try:
            if el.is_displayed():
                features.add("input:headlines")
                break
        except Exception:
            pass
    # Goal cards
    for el in driver.find_elements(By.XPATH, "//span[contains(@class, 'unified-goals-card-title')]"):
        try:
            if el.is_displayed():
                if "without guidance" in el.text.lower():
                    features.add("card:without_guidance")
                if el.text.strip().lower() == "search":
                    features.add("card:search")
        except Exception:
            pass
    # Page view
    for el in driver.find_elements(By.XPATH, "//*[contains(text(), 'Page view')]"):
        try:
            if el.is_displayed():
                features.add("goal:page_view")
                break
        except Exception:
            pass
    # Bidding dropdown items
    for el in driver.find_elements(By.XPATH, "//material-select-dropdown-item"):
        try:
            if el.is_displayed() and el.text.strip() == "Clicks":
                features.add("dd:clicks")
                break
        except Exception:
            pass
    # Bidding section
    for el in driver.find_elements(By.XPATH, "//div[contains(@class, 'bidding')]"):
        try:
            if el.is_displayed() and ("Bidding" in el.text or "focus" in el.text):
                features.add("section:bidding")
                break
        except Exception:
            pass
    # Locations
    for el in driver.find_elements(By.XPATH, "//*[contains(text(), 'Enter another location')]"):
        try:
            if el.is_displayed():
                features.add("link:locations")
                break
        except Exception:
            pass
    # Create button / New campaign
    for el in driver.find_elements(By.XPATH, "//uber-create-fab//material-fab | //material-fab[contains(@class, 'new-entity')] | //uber-create | //material-button[@aria-label='New campaign']"):
        try:
            if el.is_displayed():
                features.add("btn:create_fab")
                break
        except Exception:
            pass
    # Radio Set custom budget
    for r in driver.find_elements(By.TAG_NAME, "material-radio"):
        try:
            if r.is_displayed() and "Set custom budget" in r.text:
                features.add("radio:custom_budget")
                break
        except Exception:
            pass
    # Publish
    for b in driver.find_elements(By.XPATH, "//material-button | //button"):
        try:
            if b.is_displayed() and "Publish campaign" in b.text:
                features.add("btn:publish")
                break
        except Exception:
            pass
    return features


def detect_page(features):
    """Xac dinh dang o trang nao dua tren features."""
    title = driver.title.lower()
    # Dashboard / Overview — co nut Create
    if "btn:create_fab" in features and ("overview" in title or "campaigns" in title):
        return "dashboard"
    # Objective — co card without guidance / search
    if "card:without_guidance" in features or "card:search" in features:
        return "objective"
    # Goals + name — co checkbox website visits HOAC campaign name input
    if "input:campaign_name" in features or "cb:website_visits" in features:
        return "goals_name"
    # Bidding — co section bidding
    if "section:bidding" in features:
        return "bidding"
    # Settings — co search partners / display / locations
    if "cb:search_partners" in features or "cb:display_network" in features or "link:locations" in features:
        return "settings"
    # Keywords + Ads
    if "ta:keywords" in features or "input:final_url" in features or "input:headlines" in features:
        return "keywords_ads"
    # Budget
    if "radio:custom_budget" in features or "input:budget" in features:
        return "budget"
    # Review
    if "btn:publish" in features:
        return "review"
    return "unknown"


# === PAGE HANDLERS ===

def do_dashboard():
    """Trang dashboard — click Create > Campaign hoac New campaign."""
    log("Trang: Dashboard — tao campaign moi")
    # Thu nut New campaign truoc (nhanh hon)
    try:
        new_btn = driver.find_element(By.XPATH, "//material-button[@aria-label='New campaign']")
        if new_btn.is_displayed():
            action_click(new_btn)
            log("OK — click New campaign")
            time.sleep(5)
            return
    except Exception:
        pass
    # Fallback: Create fab > Campaign
    try:
        fab = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//uber-create//material-fab | //material-fab"))
        )
        js_click(fab)
        time.sleep(2)
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//material-select-item[@aria-label='Campaign'] | //material-select-item[.//span[contains(text(), 'Campaign')]]"))
        ).click()
        time.sleep(5)
        log("OK — Create > Campaign")
    except Exception as e:
        log(f"LOI: {e}")


def do_objective():
    """Trang chon objective — without guidance + Search."""
    log("Trang: Objective — chon without guidance + Search")
    try:
        el = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//*[@data-value='No objective'] | //span[contains(@class, 'unified-goals-card-title') and contains(text(), 'without guidance')]"))
        )
        js_click(el)
        time.sleep(3)
        log("OK — without guidance")
    except Exception:
        log("Skip — without guidance")
    try:
        el = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//*[@data-value='SEARCH']"))
        )
        js_click(el)
        time.sleep(3)
        log("OK — Search")
    except Exception:
        log("Skip — Search")


def do_goals_name():
    """Trang goals + campaign name — tick Website visits, Page view, dien ten, Continue."""
    log("Trang: Goals + Campaign name")
    # Tick Website visits
    for c in driver.find_elements(By.XPATH, "//mat-checkbox | //material-checkbox"):
        try:
            if c.is_displayed() and "Website visits" in c.text:
                js_click(c)
                log("OK — tick Website visits")
                time.sleep(1)
                break
        except Exception:
            pass
    # Page view
    try:
        for el in driver.find_elements(By.XPATH, "//conversion-goal-card[.//span[contains(text(), 'Page view')]] | //*[contains(text(), 'Page view')]"):
            if el.is_displayed():
                js_click(el)
                log("OK — Page view")
                time.sleep(1)
                break
    except Exception:
        pass
    # Campaign name
    try:
        name_input = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//input[@aria-label='Campaign name']"))
        )
        clear_and_type(name_input, config["name"])
        log(f"OK — Campaign name: {config['name']}")
    except Exception:
        log("LOI — Campaign name")
    time.sleep(1)
    # Enhanced conversions
    for cb in driver.find_elements(By.XPATH, "//enhanced-conversions-view//mat-checkbox"):
        try:
            if cb.is_displayed() and "checked" in (cb.get_attribute("class") or ""):
                js_click(cb)
                log("OK — bo Enhanced conversions")
                break
        except Exception:
            pass


def do_bidding():
    """Trang bidding — chon Clicks + CPC."""
    log("Trang: Bidding")
    # Chon Clicks
    items = driver.find_elements(By.XPATH, "//material-select-dropdown-item")
    visible = [i for i in items if i.is_displayed()]
    if visible:
        for item in visible:
            if item.text.strip() == "Clicks":
                js_click(item)
                log("OK — chon Clicks")
                time.sleep(2)
                break
    # CPC
    if config["cpc"]:
        for c in driver.find_elements(By.XPATH, "//mat-checkbox | //material-checkbox"):
            try:
                if c.is_displayed() and "maximum cost per click" in c.text:
                    js_click(c)
                    time.sleep(1)
                    break
            except Exception:
                pass
        for s in driver.find_elements(By.XPATH, "//div[contains(@class, 'max-bid-container')] | //section[.//span[contains(text(), 'Maximum CPC')]]"):
            try:
                if s.is_displayed():
                    for inp in s.find_elements(By.XPATH, ".//input"):
                        if inp.is_displayed():
                            clear_and_type(inp, config["cpc"])
                            log(f"OK — CPC: {config['cpc']}")
                            break
                    break
            except Exception:
                pass


def do_settings():
    """Trang settings — bo tick, locations, languages."""
    log("Trang: Campaign Settings")
    # Bo tick Search Partners + Display Network
    for cls in ["search-checkbox", "display-checkbox"]:
        for c in driver.find_elements(By.XPATH, f"//material-checkbox[contains(@class, '{cls}')]"):
            try:
                if c.is_displayed() and "checked" in (c.get_attribute("class") or ""):
                    js_click(c)
                    time.sleep(0.5)
            except Exception:
                pass
    log("OK — bo tick Search/Display")

    # Locations
    if config["target_locations"] or config["exclude_locations"]:
        try:
            WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Enter another location')]"))
            ).click()
            time.sleep(2)
            WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Advanced search')]"))
            ).click()
            time.sleep(3)
            bulk_cb = driver.find_element(By.XPATH, "//material-checkbox[contains(@class, 'bulk-locations-checkbox')]")
            if bulk_cb.get_attribute("aria-checked") != "true":
                js_click(bulk_cb)
                time.sleep(1)

            BULK_TA = "//bulk-location-input//textarea[contains(@class, 'textarea')]"
            SEARCH_BTN = "//bulk-location-input//material-button[contains(@class, 'search-button')]"
            TARGET_ALL = "//material-button[.//div[contains(text(), 'Target all')] or .//span[contains(text(), 'Target all')]]"
            EXCLUDE_ALL = "//material-button[.//div[contains(text(), 'Exclude all')] or .//span[contains(text(), 'Exclude all')]]"

            if config["target_locations"]:
                ta = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, BULK_TA)))
                ta.click()
                time.sleep(0.5)
                js_set_textarea(ta, "\n".join(config["target_locations"]))
                time.sleep(2)
                WebDriverWait(driver, 15).until(lambda d: d.find_element(By.XPATH, SEARCH_BTN).get_attribute("aria-disabled") != "true")
                js_click(driver.find_element(By.XPATH, SEARCH_BTN))
                time.sleep(8)
                WebDriverWait(driver, 15).until(EC.element_to_be_clickable((By.XPATH, TARGET_ALL)))
                js_click(driver.find_element(By.XPATH, TARGET_ALL))
                time.sleep(3)
                log(f"OK — target {len(config['target_locations'])} locations")

            if config["exclude_locations"]:
                ta = driver.find_element(By.XPATH, BULK_TA)
                ta.click()
                time.sleep(0.5)
                js_set_textarea(ta, "")
                time.sleep(1)
                js_set_textarea(ta, "\n".join(config["exclude_locations"]))
                time.sleep(2)
                WebDriverWait(driver, 15).until(lambda d: d.find_element(By.XPATH, SEARCH_BTN).get_attribute("aria-disabled") != "true")
                js_click(driver.find_element(By.XPATH, SEARCH_BTN))
                time.sleep(8)
                WebDriverWait(driver, 15).until(EC.element_to_be_clickable((By.XPATH, EXCLUDE_ALL)))
                js_click(driver.find_element(By.XPATH, EXCLUDE_ALL))
                time.sleep(3)
                log(f"OK — exclude {len(config['exclude_locations'])} locations")

            time.sleep(2)
            for b in driver.find_elements(By.XPATH, "//material-button | //button"):
                try:
                    if b.is_displayed() and b.text.strip() == "Save":
                        js_click(b)
                        log("OK — Save locations")
                        time.sleep(5)
                        break
                except Exception:
                    pass
        except Exception as e:
            log(f"LOI locations: {e}")

    # Xoa English
    for r in driver.find_elements(By.XPATH, "//div[@aria-label='English remove']"):
        try:
            if r.is_displayed():
                js_click(r)
                log("OK — xoa English")
                time.sleep(1)
                break
        except Exception:
            pass


def do_keywords_ads():
    """Trang keywords + ads."""
    log("Trang: Keywords + Ads")
    # Keywords
    if config["keywords"]:
        try:
            kw_ta = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//textarea[contains(@aria-label, "Enter or paste keywords")]'))
            )
            kw_ta.click()
            time.sleep(0.5)
            kw_ta.send_keys("\n".join(config["keywords"]))
            log(f"OK — {len(config['keywords'])} keywords")
        except Exception as e:
            log(f"LOI keywords: {e}")
        time.sleep(1)
    # Final URL
    if config["final_url"]:
        try:
            url_input = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//input[@aria-label="Final URL"]'))
            )
            clear_and_type(url_input, config["final_url"])
            log("OK — Final URL")
        except Exception as e:
            log(f"LOI Final URL: {e}")
        time.sleep(1)
    # Headlines
    if config["headlines"]:
        try:
            HL = '//section[contains(@class, "headline")]//input'
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, HL)))
            time.sleep(2)
            section = driver.find_element(By.XPATH, '//section[contains(@class, "headline")]')
            filled = 0
            for hl in config["headlines"]:
                inps = [i for i in section.find_elements(By.XPATH, ".//input") if i.is_displayed()]
                if filled >= len(inps):
                    try:
                        for ad in section.find_elements(By.XPATH, ".//div[contains(@class, 'add')]"):
                            if ad.is_displayed() and "Headline" in ad.text:
                                js_click(ad)
                                time.sleep(1)
                                break
                        inps = [i for i in section.find_elements(By.XPATH, ".//input") if i.is_displayed()]
                    except Exception:
                        break
                if filled < len(inps):
                    clear_and_type(inps[filled], hl)
                    filled += 1
                    time.sleep(0.5)
            log(f"OK — {filled}/{len(config['headlines'])} headlines")
        except Exception as e:
            log(f"LOI headlines: {e}")
    # Descriptions
    if config["descriptions"]:
        try:
            visible = [d for d in driver.find_elements(By.XPATH, '//textarea[@aria-label="Description"]') if d.is_displayed()]
            filled = 0
            for desc in config["descriptions"]:
                if filled >= len(visible):
                    try:
                        for ad in driver.find_elements(By.XPATH, '//section[contains(@class, "description")]//div[contains(@class, "add")]'):
                            if ad.is_displayed() and "Description" in ad.text:
                                js_click(ad)
                                time.sleep(1)
                                break
                        visible = [d for d in driver.find_elements(By.XPATH, '//textarea[@aria-label="Description"]') if d.is_displayed()]
                    except Exception:
                        break
                if filled < len(visible):
                    clear_and_type(visible[filled], desc)
                    filled += 1
                    time.sleep(0.5)
            log(f"OK — {filled}/{len(config['descriptions'])} descriptions")
        except Exception as e:
            log(f"LOI descriptions: {e}")


def do_budget():
    """Trang budget."""
    log("Trang: Budget")
    # Click Set custom budget
    for r in driver.find_elements(By.TAG_NAME, "material-radio"):
        try:
            if r.is_displayed() and "Set custom budget" in r.text:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'})", r)
                time.sleep(0.5)
                action_click(r)
                time.sleep(2)
                break
        except Exception:
            pass
    # Expand panel
    for p in reversed(driver.find_elements(By.XPATH, "//proactive-budget-recommendation-picker//material-expansionpanel")):
        try:
            if p.is_displayed() and "Set custom" in p.text:
                header = p.find_element(By.XPATH, ".//div[contains(@class, 'header')]")
                action_click(header)
                time.sleep(3)
                break
        except Exception:
            pass
    # Dien budget
    try:
        inp = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//input[contains(@aria-label, 'budget') or contains(@aria-label, 'Budget')]"))
        )
        clear_and_type(inp, config["budget"])
        log(f"OK — Budget: ${config['budget']}")
    except Exception:
        log("LOI — budget input")


def do_review():
    """Trang review — click Publish."""
    log("Trang: Review — click Publish!")
    for b in driver.find_elements(By.XPATH, "//material-button | //button"):
        try:
            if b.is_displayed() and "Publish campaign" in b.text:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'})", b)
                time.sleep(1)
                action_click(b)
                log("Da click Publish campaign!")
                time.sleep(10)
                break
        except Exception:
            pass


def click_next_or_continue():
    """Click Continue hoac Next — tuy vao trang."""
    for text in ["Continue", "Next", "Skip"]:
        for b in driver.find_elements(By.XPATH, "//button | //material-button"):
            try:
                if b.is_displayed() and b.text.strip() == text:
                    action_click(b)
                    log(f"Click {text}")
                    return text
            except Exception:
                pass
    return None


# ========================================
# MAIN LOOP
# ========================================
print(f"\n{'='*50}")
print(f"LEN CAMP: {config['name']} tren TK {ACCOUNT_ID}")
print(f"{'='*50}")

driver = connect_selenium(f"127.0.0.1:{PORT}", browser_version="145")
log(f"Title: {driver.title}")

# Vao TK neu can
if "/selectaccount" in driver.current_url:
    for item in driver.find_elements(By.CSS_SELECTOR, "material-list-item"):
        if ACCOUNT_ID in item.text and "Setup in progress" not in item.text:
            item.click()
            break
    WebDriverWait(driver, 30).until(lambda d: ACCOUNT_ID in d.title or "Campaigns" in d.title or "Overview" in d.title)
    time.sleep(5)

check_all()

# Page handlers
PAGE_HANDLERS = {
    "dashboard": do_dashboard,
    "objective": do_objective,
    "goals_name": do_goals_name,
    "bidding": do_bidding,
    "settings": do_settings,
    "keywords_ads": do_keywords_ads,
    "budget": do_budget,
    "review": do_review,
}

MAX_ROUNDS = 20
done = False

for round_num in range(1, MAX_ROUNDS + 1):
    time.sleep(3)
    check_all()

    # Scan
    features = scan_page()
    page = detect_page(features)
    print(f"\n--- Round {round_num} | Page: {page} | Features: {sorted(features)[:8]} ---")

    if page == "unknown":
        title = driver.title
        # Chi coi la xong neu da qua review (round > 10) va ve Overview
        if "Overview" in title and round_num > 10:
            log("Da ve Overview — HOAN THANH!")
            done = True
            break
        log(f"Unknown page, doi them... Title: {title}")
        time.sleep(5)
        click_next_or_continue()
        time.sleep(5)
        continue

    # Xu ly trang
    handler = PAGE_HANDLERS.get(page)
    if handler:
        handler()
        time.sleep(3)

    # Sau khi xu ly, click Next/Continue de sang trang tiep
    if page not in ("review", "dashboard"):
        time.sleep(2)
        check_all()
        clicked = click_next_or_continue()
        if clicked:
            time.sleep(8)

    # Check da publish xong chua
    check_all()
    title = driver.title
    if page == "review" and "New campaign" not in title and "Search campaign" not in title:
        log("Publish thanh cong!")
        # Dong Google Tag neu co
        time.sleep(5)
        try:
            close_btn = driver.find_element(By.XPATH, "//material-button[@aria-label='Close']")
            if close_btn.is_displayed():
                action_click(close_btn)
                log("Dong Google Tag")
                time.sleep(3)
        except Exception:
            pass
        done = True
        break

if done:
    print(f"\n{'='*50}")
    print(f"THANH CONG! Title: {driver.title}")
    print(f"{'='*50}")
else:
    print(f"\n{'='*50}")
    print(f"CHUA XONG sau {MAX_ROUNDS} rounds. Title: {driver.title}")
    print(f"{'='*50}")
