#!/usr/bin/env python3
"""Chay tu buoc 21 den Publish tren profile 011 (port 65365)."""
import sys, time, pyotp, requests
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except: pass
from genlogin_api import connect_selenium
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

driver = connect_selenium("127.0.0.1:65365", browser_version="145")
def ac(el): ActionChains(driver).move_to_element(el).pause(0.3).click().perform()
def jc(el): driver.execute_script("arguments[0].click()", el)
def ct(el, val):
    el.click(); time.sleep(0.3); el.send_keys(Keys.CONTROL, "a"); time.sleep(0.2); el.send_keys(str(val)); time.sleep(0.3)
def click_btn(text):
    for b in driver.find_elements(By.XPATH, "//button | //material-button"):
        try:
            if b.is_displayed() and b.text.strip() == text: ac(b); return True
        except: pass
    return False

def handle_2fa():
    for dlg in driver.find_elements(By.XPATH, "//material-dialog"):
        try:
            if not dlg.is_displayed() or "Confirm" not in dlg.text: continue
        except: continue
        print("  [2FA] Popup...")
        for b in dlg.find_elements(By.XPATH, ".//material-button | .//button"):
            try:
                if b.is_displayed() and b.text.strip() in ("Confirm","Try again"): ac(b); time.sleep(5); break
            except: pass
        for d2 in driver.find_elements(By.XPATH, "//material-dialog"):
            try:
                if d2.is_displayed() and "Try again" in d2.text:
                    for b2 in d2.find_elements(By.XPATH, ".//material-button | .//button"):
                        if b2.is_displayed() and "Try again" in b2.text: ac(b2); time.sleep(5); break
                    break
            except: pass
        time.sleep(2)
        if len(driver.window_handles) > 1:
            for h in driver.window_handles:
                driver.switch_to.window(h)
                try:
                    if "Sign in" not in driver.title: continue
                    tp = driver.find_elements(By.CSS_SELECTOR, "input#totpPin")
                    if not tp or not tp[0].is_displayed(): continue
                    email = ""
                    for e in driver.find_elements(By.XPATH, "//*[contains(text(),'@gmail.com')]"):
                        if e.is_displayed(): email = e.text.strip().lower(); break
                    r = requests.get("http://localhost:3000/api/gmail", timeout=10)
                    items = r.json().get("data", r.json()) if isinstance(r.json(), dict) else r.json()
                    secret = None
                    for g in items:
                        if g.get("email","").lower() == email: secret = g.get("twoFactorKey"); break
                    if secret:
                        code = pyotp.TOTP(secret).now()
                        print(f"  [2FA] {email} -> {code}")
                        tp[0].click(); time.sleep(0.5); tp[0].send_keys(code); time.sleep(1)
                        ac(driver.find_element(By.CSS_SELECTOR, "#totpNext button"))
                        print("  [2FA] OK!"); time.sleep(5)
                    break
                except: pass
            for h in driver.window_handles:
                driver.switch_to.window(h)
                try:
                    if "Google Ads" in driver.title: break
                except: pass

def chk():
    handle_2fa()
    for dlg in driver.find_elements(By.XPATH, "//material-dialog"):
        try:
            if not dlg.is_displayed(): continue
            if "Fix errors" in dlg.text and "Discard" in dlg.text:
                for b in dlg.find_elements(By.XPATH, ".//material-button | .//button"):
                    if b.is_displayed() and b.text.strip() == "Fix errors": ac(b); time.sleep(5); break
        except: pass

# === [21] Keywords + Ads ===
print("[21] Keywords + Ads...")
chk(); time.sleep(3)
try:
    kw = WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.XPATH, '//textarea[contains(@aria-label,"Enter or paste keywords")]')))
    kw.click(); time.sleep(0.5); kw.send_keys("[comfiLife]"); print("Keywords")
except Exception as e: print(f"LOI kw: {e}")
time.sleep(1)
try:
    ui = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, '//input[@aria-label="Final URL"]')))
    ct(ui, "https://comfilife.com/?ref=xpcvgneb"); print("URL")
except Exception as e: print(f"LOI url: {e}")
time.sleep(1)

headlines = ["{Keyword:ComfiLife}","ComfiLife OfficialStore","Comfort That You Deserve","Ergonomic Support Daily","Sit Better with ComfiLife","Pain Relief Made Simple","Upgrade Your Comfort Now","Work & Sit Without Pain","Better Posture Starts Here","ComfiLife - Feel the Comfort"]
try:
    WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.XPATH, '//section[contains(@class,"headline")]//input')))
    time.sleep(2)
    sec = driver.find_element(By.XPATH, '//section[contains(@class,"headline")]')
    f = 0
    for hl in headlines:
        inps = [i for i in sec.find_elements(By.XPATH, ".//input") if i.is_displayed()]
        if f >= len(inps):
            try:
                for ad in sec.find_elements(By.XPATH, ".//div[contains(@class,'add')]"):
                    if ad.is_displayed() and "Headline" in ad.text: jc(ad); time.sleep(1); break
                inps = [i for i in sec.find_elements(By.XPATH, ".//input") if i.is_displayed()]
            except: break
        if f < len(inps): ct(inps[f], hl); f += 1; time.sleep(0.5)
    print(f"{f}/{len(headlines)} headlines")
except Exception as e: print(f"LOI hl: {e}")

descs = ["Relieve back & tailbone pain with ComfiLife ergonomic cushions.","Premium memory foam support for daily comfort & posture.","Sit longer without pain - ideal for office, home & travel.","ComfiLife - comfort solutions for your everyday life."]
try:
    vis = [d2 for d2 in driver.find_elements(By.XPATH, '//textarea[@aria-label="Description"]') if d2.is_displayed()]
    f = 0
    for desc in descs:
        if f >= len(vis):
            try:
                for ad in driver.find_elements(By.XPATH, '//section[contains(@class,"description")]//div[contains(@class,"add")]'):
                    if ad.is_displayed() and "Description" in ad.text: jc(ad); time.sleep(1); break
                vis = [d2 for d2 in driver.find_elements(By.XPATH, '//textarea[@aria-label="Description"]') if d2.is_displayed()]
            except: break
        if f < len(vis): ct(vis[f], desc); f += 1; time.sleep(0.5)
    print(f"{f}/{len(descs)} descriptions")
except Exception as e: print(f"LOI desc: {e}")

chk(); click_btn("Next"); time.sleep(10); chk()

# === [22] Budget ===
print("\n[22] Budget...")
chk(); time.sleep(3)
for r in driver.find_elements(By.TAG_NAME, "material-radio"):
    try:
        if r.is_displayed() and "Set custom budget" in r.text:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'})", r)
            time.sleep(0.5); ac(r); time.sleep(2); break
    except: pass
for p in reversed(driver.find_elements(By.XPATH, "//proactive-budget-recommendation-picker//material-expansionpanel")):
    try:
        if p.is_displayed() and "Set custom" in p.text:
            hdr = p.find_element(By.XPATH, ".//div[contains(@class,'header')]")
            ac(hdr); time.sleep(3); break
    except: pass
try:
    bi = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//input[contains(@aria-label,'budget') or contains(@aria-label,'Budget')]")))
    ct(bi, "1"); print("Budget: $1")
except: print("LOI budget")
chk(); click_btn("Next"); time.sleep(15); chk()

# === [23] Publish ===
print("\n[23] Publish...")
for w in range(12):
    chk()
    found = False
    for b in driver.find_elements(By.XPATH, "//material-button | //button"):
        try:
            if b.is_displayed() and "Publish campaign" in b.text: found = True; break
        except: pass
    if found: print("Publish found!"); break
    has_budget = any(r.is_displayed() and "Set custom budget" in r.text for r in driver.find_elements(By.TAG_NAME, "material-radio"))
    if has_budget:
        print("Budget — Next..."); click_btn("Next"); time.sleep(15); chk(); continue
    print(f"Doi... ({(w+1)*5}s)"); time.sleep(5)

chk()
for b in driver.find_elements(By.XPATH, "//material-button | //button"):
    try:
        if b.is_displayed() and "Publish campaign" in b.text:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'})", b)
            time.sleep(1); ac(b); print("Publish!"); time.sleep(10); break
    except: pass

# Post-publish
chk(); time.sleep(5)
if "policy" in driver.current_url.lower():
    click_btn("Next"); print("Policy Next"); time.sleep(5)
time.sleep(3)
try:
    cb = driver.find_element(By.XPATH, "//material-button[@aria-label='Close']")
    if cb.is_displayed(): ac(cb); print("Dong Google Tag"); time.sleep(3)
except: pass

print(f"\n=== KET QUA: {driver.title} ===")
