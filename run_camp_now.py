#!/usr/bin/env python3
"""
Chay len camp tu dong — muot tu dau den cuoi.
Scan trang truoc moi buoc, xu ly moi truong hop.
"""
import sys, time, pyotp, requests

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

# ===== CONFIG =====
PORT = "62030"
ACCOUNT_ID = "686-725-3911"
CAMP_INDEX = 2  # Camp thu 2 ComfiLife

# Lay config tu DB
res = requests.get("http://localhost:3000/api/campping-vip", timeout=5)
P = None
for p in res.json().get("data", []):
    if p["name"] == "ComfiLife":
        P = p
        break
if not P:
    print("Khong tim thay project!")
    sys.exit(1)

CFG = {
    "name": f"{P['name']} {CAMP_INDEX}" if CAMP_INDEX > 1 else P["name"],
    "budget": str(P.get("budget") or "5"),
    "cpc": P.get("cpc", ""),
    "keywords": [k.strip() for k in (P.get("adsKey") or "").split("|") if k.strip()],
    "final_url": P.get("link1", ""),
    "headlines": [h.strip() for h in (P.get("headlines") or "").split("|") if h.strip()],
    "descriptions": [d.strip() for d in (P.get("descriptions") or "").split("|") if d.strip()],
    "target_locs": [l.strip() for l in (P.get("targetLocations") or "").split("|") if l.strip()],
    "exclude_locs": [l.strip() for l in (P.get("excludeLocations") or "").split("|") if l.strip()],
}
print(f"=== {CFG['name']} | ${CFG['budget']} | CPC ${CFG['cpc']} ===\n")

# ===== CONNECT =====
D = connect_selenium(f"127.0.0.1:{PORT}", browser_version="145")
print(f"Connected: {D.title}\n")

# ===== HELPERS =====
def log(msg): print(f"  {msg}", flush=True)
def jc(el): D.execute_script("arguments[0].click()", el)
def ac(el): ActionChains(D).move_to_element(el).pause(0.3).click().perform()
def ct(el, val):
    el.click(); time.sleep(0.3)
    el.send_keys(Keys.CONTROL, "a"); time.sleep(0.2)
    el.send_keys(str(val)); time.sleep(0.3)
def jst(el, val):
    D.execute_script("arguments[0].value=arguments[1];arguments[0].dispatchEvent(new Event('input',{bubbles:true}));arguments[0].dispatchEvent(new Event('change',{bubbles:true}));", el, val)
def ticked(cb): return "check_box_outline_blank" not in cb.text

def find_btn(text):
    for b in D.find_elements(By.XPATH, "//button | //material-button"):
        try:
            if b.is_displayed() and b.text.strip() == text: return b
        except: pass
    return None

def click_btn(text):
    b = find_btn(text)
    if b: ac(b); return True
    return False

def wait_page(timeout=15):
    """Doi trang load — sleep + check title thay doi."""
    time.sleep(timeout)

def get_2fa_secret(email):
    try:
        r = requests.get("http://localhost:3000/api/gmail", timeout=10)
        data = r.json()
        items = data.get("data", data) if isinstance(data, dict) else data
        for g in items:
            if g.get("email", "").lower() == email.lower():
                return g.get("twoFactorKey")
    except: pass
    return None

def handle_2fa():
    # Check dialog Confirm
    for dlg in D.find_elements(By.XPATH, "//material-dialog"):
        try:
            if not dlg.is_displayed() or "Confirm" not in dlg.text: continue
        except: continue
        log("[2FA] Popup Confirm...")
        # Click Confirm/Try again
        for b in dlg.find_elements(By.XPATH, ".//material-button | .//button"):
            try:
                if b.is_displayed() and b.text.strip() in ("Confirm", "Try again"):
                    ac(b); log(f"[2FA] {b.text.strip()}"); time.sleep(5); break
            except: pass
        # Try again lan 2
        for d2 in D.find_elements(By.XPATH, "//material-dialog"):
            try:
                if d2.is_displayed() and "Try again" in d2.text:
                    for b2 in d2.find_elements(By.XPATH, ".//material-button | .//button"):
                        if b2.is_displayed() and "Try again" in b2.text:
                            ac(b2); log("[2FA] Try again"); time.sleep(5); break
                    break
            except: pass
        # Tab 2FA
        time.sleep(2)
        if len(D.window_handles) > 1:
            for h in D.window_handles:
                D.switch_to.window(h)
                try:
                    if "Sign in" not in D.title: continue
                    tp = D.find_elements(By.CSS_SELECTOR, "input#totpPin")
                    if not tp or not tp[0].is_displayed(): continue
                    email = ""
                    for e in D.find_elements(By.XPATH, "//*[contains(text(),'@gmail.com')]"):
                        if e.is_displayed(): email = e.text.strip().lower(); break
                    secret = get_2fa_secret(email)
                    if secret:
                        code = pyotp.TOTP(secret).now()
                        log(f"[2FA] {email} -> {code}")
                        tp[0].click(); time.sleep(0.5); tp[0].send_keys(code); time.sleep(1)
                        ac(D.find_element(By.CSS_SELECTOR, "#totpNext button"))
                        log("[2FA] OK!"); time.sleep(5)
                    break
                except: pass
            for h in D.window_handles:
                D.switch_to.window(h)
                try:
                    if "Google Ads" in D.title: break
                except: pass
        return True
    return False

def handle_popups():
    for dlg in D.find_elements(By.XPATH, "//material-dialog"):
        try:
            if not dlg.is_displayed() or not dlg.text.strip(): continue
            if "Conversion goals" in dlg.text:
                for cb in dlg.find_elements(By.XPATH, ".//material-button[contains(@aria-label,'Close')]"):
                    if cb.is_displayed(): jc(cb); log("[POPUP] Dong Conversion goals"); time.sleep(2); break
            elif "Exit guide" in dlg.text:
                for b in dlg.find_elements(By.XPATH, ".//material-button | .//button"):
                    if b.is_displayed() and "Leave" in b.text: jc(b); log("[POPUP] Leave"); time.sleep(3); break
        except: pass

def handle_draft():
    for dlg in D.find_elements(By.XPATH, "//material-dialog"):
        try:
            if not dlg.is_displayed() or "draft" not in dlg.text.lower(): continue
            log("[DRAFT] Gap draft dialog")
            # Luon Start new vi day la camp moi
            for b in dlg.find_elements(By.XPATH, ".//material-button | .//button"):
                if b.is_displayed() and "Start new" in b.text:
                    jc(b); log("[DRAFT] Start new"); time.sleep(3); return True
        except: pass
    return False

def chk():
    handle_2fa(); handle_popups(); handle_draft()

def handle_login():
    """Xu ly Account Chooser / Sign in neu bi redirect."""
    if "selectaccount" in D.current_url:
        log("Gap selectaccount...")
        for item in D.find_elements(By.CSS_SELECTOR, "material-list-item"):
            if ACCOUNT_ID in item.text and "Setup in progress" not in item.text:
                item.click(); log(f"Chon TK {ACCOUNT_ID}"); time.sleep(10); break
    elif "accounts.google.com" in D.current_url:
        log("Gap Sign in...")
        for el in D.find_elements(By.XPATH, "//div[@data-identifier]"):
            if el.is_displayed():
                ac(el); log(f"Chon account {el.get_attribute('data-identifier')}"); time.sleep(5); break

# ===== MAIN FLOW =====
try:
    # Buoc 0: Dam bao dang o dung TK
    handle_login()
    chk()

    # Buoc 4-5: Create > Campaign
    print("[4-5] Create > Campaign")
    chk()
    # Thu nhieu cach tim nut
    clicked = False
    for xpath in [
        "//material-button[@aria-label='New campaign']",
        "//button[@aria-label='New campaign']",
        "//material-fab-menu//material-fab",
        "//uber-create//material-fab",
        "//material-fab",
    ]:
        try:
            el = D.find_element(By.XPATH, xpath)
            if el.is_displayed():
                ac(el)
                clicked = True
                log(f"Click {xpath}")
                time.sleep(3)
                # Neu la fab, can chon Campaign trong menu
                if "fab" in xpath:
                    for mi in D.find_elements(By.XPATH, "//material-select-item"):
                        if mi.is_displayed() and "Campaign" in mi.text:
                            jc(mi); time.sleep(3); break
                break
        except: pass
    if not clicked:
        # Navigate truc tiep
        D.get(f"https://ads.google.com/aw/campaigns/new?ocid={ACCOUNT_ID.replace('-','')}")
        time.sleep(8)
        handle_login()
    wait_page(5)
    chk()
    log(f"Title: {D.title}")

    # Buoc 6: Without guidance
    print("\n[6] Without guidance")
    chk()
    try:
        el = WebDriverWait(D, 10).until(EC.element_to_be_clickable((By.XPATH, "//*[@data-value='No objective'] | //span[contains(@class,'unified-goals-card-title') and contains(text(),'without guidance')]")))
        jc(el); time.sleep(3); log("OK")
    except: log("Skip — co the da chon")

    # Buoc 7: Search
    print("\n[7] Search")
    chk()
    try:
        el = WebDriverWait(D, 10).until(EC.element_to_be_clickable((By.XPATH, "//*[@data-value='SEARCH']")))
        jc(el); time.sleep(3); log("OK")
    except: log("Skip")

    # Buoc 8-11: Website visits + Campaign name
    # Continue co the phai an nhieu lan
    print("\n[8-11] Goals + Campaign name")
    chk(); time.sleep(3)

    for attempt in range(3):
        # Scan
        has_cb = any(c.is_displayed() and "Website visits" in c.text for c in D.find_elements(By.XPATH, "//mat-checkbox | //material-checkbox") if True)
        has_name = bool(D.find_elements(By.XPATH, "//input[@aria-label='Campaign name']"))
        if has_name:
            try:
                ni = D.find_element(By.XPATH, "//input[@aria-label='Campaign name']")
                if ni.is_displayed(): break
            except: pass
        log(f"  Attempt {attempt+1}: cb={has_cb} name={has_name} — an Continue")
        click_btn("Continue"); time.sleep(8); chk()

    # Tick Website visits
    for c in D.find_elements(By.XPATH, "//mat-checkbox | //material-checkbox"):
        try:
            if c.is_displayed() and "Website visits" in c.text and not ticked(c):
                jc(c); log("Tick Website visits"); time.sleep(1); break
        except: pass

    # Page view
    for el in D.find_elements(By.XPATH, "//*[contains(text(),'Page view')]"):
        try:
            if el.is_displayed(): jc(el); log("Page view"); time.sleep(1); break
        except: pass

    # Campaign name
    try:
        ni = WebDriverWait(D, 10).until(EC.element_to_be_clickable((By.XPATH, "//input[@aria-label='Campaign name']")))
        ct(ni, CFG["name"]); log(f"Campaign name: {CFG['name']}")
    except: log("LOI Campaign name")
    time.sleep(1)

    # Enhanced conversions
    for cb in D.find_elements(By.XPATH, "//enhanced-conversions-view//mat-checkbox"):
        try:
            if cb.is_displayed() and ticked(cb): jc(cb); log("Bo Enhanced conversions"); break
        except: pass

    # Buoc 13: Continue
    print("\n[13] Continue")
    chk(); click_btn("Continue"); time.sleep(8); chk()

    # Buoc 14: Bidding
    print("\n[14] Bidding")
    chk(); time.sleep(3)
    # Mo dropdown bang dropdown-button
    for db in D.find_elements(By.XPATH, "//material-dropdown-select//dropdown-button"):
        try:
            if db.is_displayed() and ("Conversions" in db.text or "Clicks" in db.text):
                ac(db); time.sleep(2); break
        except: pass
    # Chon Clicks
    for item in D.find_elements(By.XPATH, "//material-select-dropdown-item"):
        try:
            if item.is_displayed() and item.text.strip() == "Clicks":
                jc(item); log("Clicks"); time.sleep(2); break
        except: pass
    # Max CPC
    if CFG["cpc"]:
        for c in D.find_elements(By.XPATH, "//mat-checkbox | //material-checkbox"):
            try:
                if c.is_displayed() and "maximum cost per click" in c.text:
                    jc(c); time.sleep(1); break
            except: pass
        for s in D.find_elements(By.XPATH, "//div[contains(@class,'max-bid-container')] | //section[.//span[contains(text(),'Maximum CPC')]]"):
            try:
                if s.is_displayed():
                    for inp in s.find_elements(By.XPATH, ".//input"):
                        if inp.is_displayed(): ct(inp, CFG["cpc"]); log(f"CPC: {CFG['cpc']}"); break
                    break
            except: pass

    # Buoc 15: Next + Settings
    print("\n[15] Settings")
    chk(); click_btn("Next"); time.sleep(8); chk()
    # Bo tick (check bang icon text)
    for cls in ["search-checkbox", "display-checkbox"]:
        for c in D.find_elements(By.XPATH, f"//material-checkbox[contains(@class,'{cls}')]"):
            try:
                if c.is_displayed() and ticked(c): jc(c); time.sleep(0.5)
            except: pass
    log("Bo tick Search Partners + Display")

    # Buoc 16: Locations
    print("\n[16] Locations")
    chk()
    if CFG["target_locs"] or CFG["exclude_locs"]:
        try:
            WebDriverWait(D, 8).until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(),'Enter another location')]"))).click(); time.sleep(2)
            WebDriverWait(D, 8).until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(),'Advanced search')]"))).click(); time.sleep(3)
            bulk = D.find_element(By.XPATH, "//material-checkbox[contains(@class,'bulk-locations-checkbox')]")
            if bulk.get_attribute("aria-checked") != "true": jc(bulk); time.sleep(1)
            BTA = "//bulk-location-input//textarea[contains(@class,'textarea')]"
            SB = "//bulk-location-input//material-button[contains(@class,'search-button')]"
            TA = "//material-button[.//div[contains(text(),'Target all')] or .//span[contains(text(),'Target all')]]"
            EA = "//material-button[.//div[contains(text(),'Exclude all')] or .//span[contains(text(),'Exclude all')]]"

            def bulk_do(locs, btn_xp, label):
                ta = WebDriverWait(D, 10).until(EC.element_to_be_clickable((By.XPATH, BTA)))
                ta.click(); time.sleep(0.5)
                jst(ta, "\n".join(locs)); time.sleep(2)
                WebDriverWait(D, 15).until(lambda d: d.find_element(By.XPATH, SB).get_attribute("aria-disabled") != "true")
                jc(D.find_element(By.XPATH, SB)); time.sleep(8)
                WebDriverWait(D, 15).until(EC.element_to_be_clickable((By.XPATH, btn_xp)))
                jc(D.find_element(By.XPATH, btn_xp)); time.sleep(3)
                log(f"{label} {len(locs)} locations")

            if CFG["target_locs"]: bulk_do(CFG["target_locs"], TA, "Target")
            if CFG["exclude_locs"]:
                ta = D.find_element(By.XPATH, BTA); ta.click(); time.sleep(0.3)
                jst(ta, ""); time.sleep(1)
                bulk_do(CFG["exclude_locs"], EA, "Exclude")
            # Save
            time.sleep(2)
            for b in D.find_elements(By.XPATH, "//material-button | //button"):
                try:
                    if b.is_displayed() and b.text.strip() == "Save": jc(b); log("Save!"); time.sleep(5); break
                except: pass
        except Exception as e: log(f"LOI locations: {e}")

    # Buoc 17: Xoa English
    print("\n[17] Xoa English")
    for r in D.find_elements(By.XPATH, "//div[@aria-label='English remove']"):
        try:
            if r.is_displayed(): jc(r); log("OK"); time.sleep(1); break
        except: pass

    # Buoc 18-20: Next > Next > Skip
    for label, btn in [("[18] Next", "Next"), ("[19] AI Max", "Next"), ("[20] Skip keyword", "Skip")]:
        print(f"\n{label}")
        chk()
        if not click_btn(btn): click_btn("Next")
        time.sleep(8); chk()

    # Buoc 21: Keywords + Ads
    print("\n[21] Keywords + Ads")
    chk(); time.sleep(3)
    # Keywords
    try:
        kw = WebDriverWait(D, 15).until(EC.presence_of_element_located((By.XPATH, '//textarea[contains(@aria-label,"Enter or paste keywords")]')))
        kw.click(); time.sleep(0.5); kw.send_keys("\n".join(CFG["keywords"])); log(f"{len(CFG['keywords'])} keywords")
    except Exception as e: log(f"LOI keywords: {e}")
    time.sleep(1)
    # Final URL
    try:
        ui = WebDriverWait(D, 10).until(EC.element_to_be_clickable((By.XPATH, '//input[@aria-label="Final URL"]')))
        ct(ui, CFG["final_url"]); log("Final URL")
    except Exception as e: log(f"LOI URL: {e}")
    time.sleep(1)
    # Headlines
    try:
        WebDriverWait(D, 15).until(EC.presence_of_element_located((By.XPATH, '//section[contains(@class,"headline")]//input')))
        time.sleep(2)
        sec = D.find_element(By.XPATH, '//section[contains(@class,"headline")]')
        f = 0
        for hl in CFG["headlines"]:
            inps = [i for i in sec.find_elements(By.XPATH, ".//input") if i.is_displayed()]
            if f >= len(inps):
                try:
                    for ad in sec.find_elements(By.XPATH, ".//div[contains(@class,'add')]"):
                        if ad.is_displayed() and "Headline" in ad.text: jc(ad); time.sleep(1); break
                    inps = [i for i in sec.find_elements(By.XPATH, ".//input") if i.is_displayed()]
                except: break
            if f < len(inps): ct(inps[f], hl); f += 1; time.sleep(0.5)
        log(f"{f}/{len(CFG['headlines'])} headlines")
    except Exception as e: log(f"LOI headlines: {e}")
    # Descriptions
    try:
        vis = [d2 for d2 in D.find_elements(By.XPATH, '//textarea[@aria-label="Description"]') if d2.is_displayed()]
        f = 0
        for desc in CFG["descriptions"]:
            if f >= len(vis):
                try:
                    for ad in D.find_elements(By.XPATH, '//section[contains(@class,"description")]//div[contains(@class,"add")]'):
                        if ad.is_displayed() and "Description" in ad.text: jc(ad); time.sleep(1); break
                    vis = [d2 for d2 in D.find_elements(By.XPATH, '//textarea[@aria-label="Description"]') if d2.is_displayed()]
                except: break
            if f < len(vis): ct(vis[f], desc); f += 1; time.sleep(0.5)
        log(f"{f}/{len(CFG['descriptions'])} descriptions")
    except Exception as e: log(f"LOI desc: {e}")
    # Next
    chk(); click_btn("Next"); time.sleep(10); chk()

    # Buoc 22: Budget
    print("\n[22] Budget")
    chk(); time.sleep(3)
    # Set custom budget
    for r in D.find_elements(By.TAG_NAME, "material-radio"):
        try:
            if r.is_displayed() and "Set custom budget" in r.text:
                D.execute_script("arguments[0].scrollIntoView({block:'center'})", r)
                time.sleep(0.5); ac(r); time.sleep(2); break
        except: pass
    # Expand panel
    for p in reversed(D.find_elements(By.XPATH, "//proactive-budget-recommendation-picker//material-expansionpanel")):
        try:
            if p.is_displayed() and "Set custom" in p.text:
                hdr = p.find_element(By.XPATH, ".//div[contains(@class,'header')]")
                ac(hdr); time.sleep(3); break
        except: pass
    # Dien
    try:
        bi = WebDriverWait(D, 10).until(EC.element_to_be_clickable((By.XPATH, "//input[contains(@aria-label,'budget') or contains(@aria-label,'Budget')]")))
        ct(bi, CFG["budget"]); log(f"Budget: ${CFG['budget']}")
    except: log("LOI budget")
    # Next
    chk(); click_btn("Next"); time.sleep(15); chk()

    # Buoc 23: Publish
    print("\n[23] Publish")
    for w in range(6):
        chk()
        if find_btn("Publish campaign"): log("Tim thay Publish!"); break
        log(f"Doi... ({(w+1)*10}s)"); time.sleep(10)
    # Click
    for att in range(3):
        chk()
        pb = find_btn("Publish campaign")
        if pb:
            D.execute_script("arguments[0].scrollIntoView({block:'center'})", pb)
            time.sleep(1); ac(pb); log(f"Publish! (lan {att+1})"); time.sleep(10)
        chk()
        if "New campaign" not in D.title and "Search campaign" not in D.title: break
        log(f"Van Review (lan {att+1})"); time.sleep(5)

    # Dong Google Tag
    time.sleep(5)
    try:
        cb = D.find_element(By.XPATH, "//material-button[@aria-label='Close']")
        if cb.is_displayed(): ac(cb); log("Dong Google Tag"); time.sleep(3)
    except: pass

    print(f"\n{'='*50}")
    print(f"HOAN THANH! Title: {D.title}")
    print(f"{'='*50}")

except Exception as e:
    print(f"\n!!! LOI: {e}")
    import traceback; traceback.print_exc()
