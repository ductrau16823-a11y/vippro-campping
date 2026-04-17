#!/usr/bin/env python3
"""
=== VIPPRO CAMPPING ===
Tao campaign Google Ads tu dong — scan trang truoc moi buoc, linh hoat xu ly.
Goi tu camp_runner.py sau khi da vao dung TK Ads.

Bai hoc thuc te (2026-04-15):
- Continue co the phai an 2 lan de hien checkbox + Campaign name
- Checkbox check bang icon text (check_box / check_box_outline_blank), KHONG dung class
- Bidding dropdown: click dropdown-button truoc, roi moi chon material-select-dropdown-item
- Budget: click radio Set custom budget + expand panel truoc khi dien
- 2FA: popup Confirm -> Try again -> tab moi Sign in -> nhap TOTP -> tab tu dong
- Popup: Conversion goals -> X, Exit guide -> Leave, Draft -> click ten hoac Start new
"""

import sys
import time
import traceback

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from api_helpers import upsert_campaign
from status_tracker import StatusTracker


class CampaignCreator:
    """Tao campaign tu dong cho 1 TK Ads."""

    def __init__(self, driver, account_data, tracker):
        self.driver = driver
        self.account_data = account_data
        self.tracker = tracker
        self.customer_id = account_data.get("accountId", "")
        self.gmail = account_data.get("gmailEmail", "")

    def run_campaign_flow(self, campaign_config, skip_navigate=False, camp_index=1):
        """Chay toan bo flow tao 1 campaign.

        Args:
            campaign_config: dict tu DB project
            skip_navigate: True neu camp_runner da vao san TK Ads
            camp_index: so thu tu camp tren TK nay (de danh so ten: viltrox 1, viltrox 2)
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.action_chains import ActionChains

        d = self.driver
        base_name = campaign_config.get("name", "Campaign")
        name = f"{base_name} {camp_index}" if camp_index > 1 else base_name
        self.tracker.log(f"=== Bat dau tao campaign: {name} (#{camp_index}) ===")

        # ==================== HELPERS ====================

        def js_click(el):
            d.execute_script("arguments[0].click()", el)

        def action_click(el):
            ActionChains(d).move_to_element(el).pause(0.3).click().perform()

        def clear_and_type(el, value):
            """Click vao input, Ctrl+A roi type de — fix Material input."""
            el.click()
            time.sleep(0.3)
            el.send_keys(Keys.CONTROL, "a")
            time.sleep(0.2)
            el.send_keys(str(value))
            time.sleep(0.3)

        def js_set_textarea(el, value):
            """Dung JS set value cho textarea — fix send_keys nuot ky tu."""
            d.execute_script(
                "arguments[0].value = arguments[1];"
                "arguments[0].dispatchEvent(new Event('input', {bubbles: true}));"
                "arguments[0].dispatchEvent(new Event('change', {bubbles: true}));",
                el, value,
            )

        def click_button(text, timeout=10):
            """Tim va click button theo text chinh xac."""
            for _ in range(3):
                for b in d.find_elements(By.XPATH, "//button | //material-button"):
                    try:
                        if b.is_displayed() and b.text.strip() == text:
                            action_click(b)
                            return True
                    except Exception:
                        pass
                time.sleep(1)
            return False

        def click_by_text(text, exact=False):
            """Tim element bat ky chua text roi click — linh hoat cho card/radio/checkbox."""
            text_lc = text.lower()
            xpaths = [
                f"//*[normalize-space(text())='{text}']",
                f"//*[@role='radio' or @role='checkbox' or @role='button'][contains(., \"{text}\")]",
                f"//conversion-goal-card[.//*[contains(., \"{text}\")]]//button[@role='radio']",
                f"//conversion-goal-card[.//*[contains(., \"{text}\")]]",
                f"//mat-checkbox[contains(., \"{text}\")] | //material-checkbox[contains(., \"{text}\")]",
                f"//*[contains(normalize-space(.), \"{text}\")]",
            ]
            for xp in xpaths:
                try:
                    for el in d.find_elements(By.XPATH, xp):
                        try:
                            if not el.is_displayed():
                                continue
                            el_text = (el.text or "").strip()
                            if exact and el_text.lower() != text_lc:
                                continue
                            d.execute_script("arguments[0].scrollIntoView({block:'center'})", el)
                            time.sleep(0.3)
                            try:
                                el.click()
                            except Exception:
                                js_click(el)
                            return True
                        except Exception:
                            continue
                except Exception:
                    continue
            return False

        def is_checkbox_ticked(cb_element):
            """Check checkbox dang tick hay chua — bang icon text."""
            return "check_box_outline_blank" not in cb_element.text

        def on_page(xpath):
            """Check xem trang co element match xpath + displayed hay khong."""
            try:
                return any(el.is_displayed() for el in d.find_elements(By.XPATH, xpath))
            except Exception:
                return False

        # ==================== 2FA + POPUPS ====================

        def handle_2fa():
            """Xu ly popup Confirm + 2FA day du."""
            import pyotp
            import requests

            TWO_FA_KEYWORDS = ["Confirm your identity", "Verify it's you", "2-Step Verification",
                               "confirm your identity", "verify it", "identity verification"]
            for dialog in d.find_elements(By.XPATH, "//material-dialog"):
                try:
                    if not dialog.is_displayed():
                        continue
                    dlg_text = dialog.text
                    is_2fa = any(kw in dlg_text for kw in TWO_FA_KEYWORDS)
                    if not is_2fa and "Confirm" in dlg_text and ("identity" in dlg_text.lower() or "verif" in dlg_text.lower()):
                        is_2fa = True
                    if not is_2fa:
                        continue
                except Exception:
                    continue

                self.tracker.log("[2FA] Gap popup xac thuc...", "warn")

                # Click Confirm hoac Try again
                for b in dialog.find_elements(By.XPATH, ".//material-button | .//button"):
                    try:
                        if b.is_displayed() and b.text.strip() in ("Confirm", "Try again"):
                            action_click(b)
                            self.tracker.log(f"[2FA] Click {b.text.strip()}")
                            time.sleep(5)
                            break
                    except Exception:
                        pass

                # Try again lan 2
                for d2 in d.find_elements(By.XPATH, "//material-dialog"):
                    try:
                        if d2.is_displayed() and "Try again" in d2.text:
                            for b2 in d2.find_elements(By.XPATH, ".//material-button | .//button"):
                                if b2.is_displayed() and "Try again" in b2.text:
                                    action_click(b2)
                                    self.tracker.log("[2FA] Click Try again")
                                    time.sleep(5)
                                    break
                            break
                    except Exception:
                        pass

                # Check tab 2FA moi
                time.sleep(2)
                handles = d.window_handles
                if len(handles) > 1:
                    for h in handles:
                        d.switch_to.window(h)
                        try:
                            if "Sign in" not in d.title:
                                continue
                            totp_els = d.find_elements(By.CSS_SELECTOR, "input#totpPin")
                            if not totp_els or not totp_els[0].is_displayed():
                                continue

                            # Lay email tren trang
                            email = ""
                            for e in d.find_elements(By.XPATH, "//*[contains(text(), '@gmail.com')]"):
                                if e.is_displayed():
                                    email = e.text.strip().lower()
                                    break

                            # Lay 2FA key tu dashboard API
                            secret = None
                            try:
                                r = requests.get("http://localhost:3000/api/gmail", timeout=10)
                                data = r.json()
                                items = data.get("data", data) if isinstance(data, dict) else data
                                for g in items:
                                    if g.get("email", "").lower() == email:
                                        secret = g.get("twoFactorKey")
                                        break
                            except Exception:
                                pass

                            if secret:
                                code = pyotp.TOTP(secret).now()
                                self.tracker.log(f"[2FA] {email} -> {code}")
                                totp_els[0].click()
                                time.sleep(0.5)
                                totp_els[0].send_keys(code)
                                time.sleep(1)
                                next_btn = d.find_element(By.CSS_SELECTOR, "#totpNext button")
                                action_click(next_btn)
                                self.tracker.log("[2FA] OK!")
                                time.sleep(5)
                            break
                        except Exception:
                            pass

                    # Quay ve tab Ads
                    for h in d.window_handles:
                        d.switch_to.window(h)
                        try:
                            if "Google Ads" in d.title:
                                break
                        except Exception:
                            pass
                return True
            return False

        def handle_popups():
            """Dong popup Conversion goals / Exit guide."""
            for dialog in d.find_elements(By.XPATH, "//material-dialog"):
                try:
                    if not dialog.is_displayed() or not dialog.text.strip():
                        continue
                    if "Conversion goals" in dialog.text:
                        for cb in dialog.find_elements(By.XPATH, ".//material-button[contains(@aria-label, 'Close')]"):
                            if cb.is_displayed():
                                js_click(cb)
                                self.tracker.log("[POPUP] Dong Conversion goals")
                                time.sleep(2)
                                break
                    elif "Exit guide" in dialog.text:
                        for b in dialog.find_elements(By.XPATH, ".//material-button | .//button"):
                            if b.is_displayed() and "Leave" in b.text:
                                js_click(b)
                                self.tracker.log("[POPUP] Leave")
                                time.sleep(3)
                                break
                    elif "Fix errors" in dialog.text and "Discard" in dialog.text:
                        for b in dialog.find_elements(By.XPATH, ".//material-button | .//button"):
                            if b.is_displayed() and b.text.strip() == "Fix errors":
                                action_click(b)
                                self.tracker.log("[POPUP] Fix errors — quay lai sua loi")
                                time.sleep(5)
                                break
                except Exception:
                    pass

        def handle_draft():
            """Xu ly dialog draft — click ten neu trung, Start new neu khac."""
            for dialog in d.find_elements(By.XPATH, "//material-dialog"):
                try:
                    if not dialog.is_displayed() or "draft" not in dialog.text.lower():
                        continue
                    self.tracker.log("[DRAFT] Gap dialog draft...")
                    for n in dialog.find_elements(By.XPATH, ".//campaign-name-cell//div[contains(@class, 'name')]"):
                        if n.is_displayed():
                            draft_name = n.text.strip()
                            if draft_name == base_name:
                                js_click(n)
                                self.tracker.log(f"[DRAFT] Click '{draft_name}'")
                                time.sleep(5)
                            else:
                                for b in dialog.find_elements(By.XPATH, ".//material-button | .//button"):
                                    if b.is_displayed() and "Start new" in b.text:
                                        js_click(b)
                                        self.tracker.log("[DRAFT] Start new")
                                        time.sleep(3)
                                        break
                            return True
                except Exception:
                    pass
            return False

        def check_all():
            """Check 2FA + popup + draft truoc moi buoc.
            Sau 2FA, Google co the reset ve trang truoc — can xu ly."""
            had_2fa = handle_2fa()
            handle_popups()
            handle_draft()
            if had_2fa:
                # 2FA co the reset trang — doi them va check lai
                time.sleep(5)
                handle_popups()
                handle_draft()

        def check_login():
            """Check bi redirect ve login — neu co thi do_navigate()."""
            cur_url = d.current_url.lower()
            cur_title = d.title.lower()
            if "sign in" in cur_title or "accounts.google.com" in cur_url or "selectaccount" in cur_url:
                self.tracker.log("[CHECK] Bi redirect ve login — do_navigate()...", "warn")
                do_navigate()
                time.sleep(3)
                if "ads.google.com" not in d.current_url.lower() or "campaign" not in d.title.lower():
                    cid = self.customer_id.replace("-", "")
                    d.get(f"https://ads.google.com/aw/campaigns/new?ocid={cid}")
                    time.sleep(10)
                    check_all()
                return True
            return False

        def do_navigate():
            """Xu ly full login: Account Chooser, email, password, 2FA, Select Account."""
            from camp_runner import get_gmail_password, get_2fa_key, generate_totp
            profile_id = self.account_data.get("profileId", "")
            gmail_email = self.gmail

            for nav_try in range(5):
                cur_url = d.current_url.lower()
                cur_title = d.title.lower()
                self.tracker.log(f"[NAV] Trang: {d.title} (lan {nav_try + 1})")

                # Account Chooser
                try:
                    heading = d.find_element(By.CSS_SELECTOR, "h1#headingText span")
                    if "Choose an account" in heading.text or "Chọn tài khoản" in heading.text:
                        self.tracker.log("[NAV] Account Chooser...")
                        try:
                            el = WebDriverWait(d, 8).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, f'div[data-identifier="{gmail_email.lower()}"]'))
                            )
                            action_click(el)
                            self.tracker.log(f"[NAV] Click {gmail_email}")
                            time.sleep(5)
                        except Exception:
                            for el in d.find_elements(By.XPATH, "//div[@data-identifier]"):
                                if el.is_displayed():
                                    action_click(el)
                                    time.sleep(5)
                                    break
                        continue
                except Exception:
                    pass

                if "sign in" in cur_title or "accounts.google.com" in cur_url:
                    # Email input
                    try:
                        email_input = d.find_element(By.CSS_SELECTOR, "input[type='email']#identifierId")
                        if email_input.is_displayed():
                            email_input.clear()
                            email_input.send_keys(gmail_email)
                            time.sleep(0.5)
                            try:
                                d.find_element(By.CSS_SELECTOR, "#identifierNext button").click()
                                self.tracker.log(f"[NAV] Nhap email: {gmail_email}")
                                time.sleep(4)
                            except Exception:
                                pass
                            continue
                    except Exception:
                        pass
                    # Password
                    try:
                        pw_input = d.find_element(By.CSS_SELECTOR, "input[type='password'][name='Passwd']")
                        if pw_input.is_displayed():
                            password = get_gmail_password(profile_id) if profile_id else None
                            if password:
                                pw_input.clear()
                                pw_input.send_keys(password)
                                time.sleep(0.5)
                                try:
                                    d.find_element(By.CSS_SELECTOR, "#passwordNext button").click()
                                    self.tracker.log("[NAV] Nhap password", "success")
                                    time.sleep(5)
                                except Exception:
                                    pass
                            continue
                    except Exception:
                        pass
                    # 2FA
                    try:
                        totp_input = d.find_element(By.CSS_SELECTOR, "input#totpPin")
                        if totp_input.is_displayed():
                            secret = get_2fa_key(profile_id) if profile_id else None
                            if secret:
                                code = generate_totp(secret)
                                totp_input.click()
                                time.sleep(0.3)
                                totp_input.send_keys(code)
                                time.sleep(1)
                                try:
                                    d.find_element(By.CSS_SELECTOR, "#totpNext button").click()
                                    self.tracker.log(f"[NAV] Nhap 2FA: {code}", "success")
                                    time.sleep(5)
                                except Exception:
                                    pass
                            continue
                    except Exception:
                        pass
                    # Fallback: click data-identifier
                    try:
                        for el in d.find_elements(By.XPATH, "//div[@data-identifier]"):
                            if el.is_displayed():
                                action_click(el)
                                self.tracker.log(f"[NAV] Click {el.get_attribute('data-identifier')}")
                                time.sleep(8)
                                break
                    except Exception:
                        pass
                    time.sleep(3)
                    continue

                if "selectaccount" in cur_url:
                    self.tracker.log("[NAV] Select Account...")
                    for item in d.find_elements(By.CSS_SELECTOR, "material-list-item"):
                        if self.customer_id in item.text and "Setup in progress" not in item.text:
                            item.click()
                            self.tracker.log(f"[NAV] Chon TK {self.customer_id}")
                            time.sleep(10)
                            break
                    continue

                if any(kw in cur_url for kw in ["verification", "billing", "signup/tagging", "policy"]):
                    self.tracker.log("[NAV] Trang phu — navigate ve Campaigns")
                    cid = self.customer_id.replace("-", "")
                    d.get(f"https://ads.google.com/aw/campaigns?ocid={cid}")
                    time.sleep(10)
                    check_all()
                    continue

                self.tracker.log("[NAV] San sang!", "success")
                return True
            return True

        # ==================== MAIN FLOW ====================

        # === BUOC 0: Navigate ===
        self.tracker.set_current(step="Buoc 0: Navigate")
        self.tracker.log(f"Trang hien tai: {d.title}")

        if skip_navigate:
            cur_url = d.current_url.lower()
            cur_title = d.title.lower()
            if "sign in" in cur_title or "accounts.google.com" in cur_url or "selectaccount" in cur_url:
                self.tracker.log("[NAV] skip_navigate=True nhung dang o login — do_navigate()", "warn")
                do_navigate()
            else:
                self.tracker.log("[NAV] Da o trang Ads", "success")
        else:
            do_navigate()

        # === BUOC 4-5: Click Create > Campaign ===
        self.tracker.set_current(step="Buoc 4-5: Create > Campaign")
        check_all()
        time.sleep(3)

        # Thu nhieu cach tim nut Create / New campaign
        clicked = False
        for xpath in [
            "//material-button[@aria-label='New campaign']",
            "//button[@aria-label='New campaign']",
            "//material-fab-menu//material-fab",
            "//uber-create//material-fab",
            "//material-fab",
        ]:
            try:
                el = d.find_element(By.XPATH, xpath)
                if el.is_displayed():
                    action_click(el)
                    clicked = True
                    self.tracker.log(f"Click {xpath}")
                    time.sleep(3)
                    # Neu la fab, can chon Campaign trong menu
                    if "fab" in xpath:
                        for mi in d.find_elements(By.XPATH, "//material-select-item"):
                            if mi.is_displayed() and "Campaign" in mi.text:
                                js_click(mi)
                                time.sleep(3)
                                break
                    break
            except Exception:
                pass

        if not clicked:
            self.tracker.log("Khong tim thay nut Create — thu navigate truc tiep", "warn")
            cid = self.customer_id.replace("-", "")
            d.get(f"https://ads.google.com/aw/campaigns/new?ocid={cid}")
            time.sleep(10)
            check_all()
            clicked = True

        if not clicked:
            self.tracker.log("Khong tim thay nut Create!", "error")
            return False

        time.sleep(5)
        self.tracker.log("Da click Create > Campaign", "success")

        # Doi trang New campaign load
        try:
            WebDriverWait(d, 15).until(lambda drv: "campaign" in drv.title.lower())
        except Exception:
            pass
        time.sleep(3)
        check_all()

        # === BUOC 6-13: Setup campaign — thu tung action truc tiep, khong scan ===
        self.tracker.set_current(step="Buoc 6-13: Setup campaign")
        time.sleep(3)

        camp_type = campaign_config.get("type", "search").upper()
        done_objective = False
        done_type = False
        done_visits = False
        done_pv = False
        done_name = False

        PV_XPATHS = [
            "//conversion-goal-card[.//material-icon[@id='PAGE_VIEW']]//button[@role='radio']",
            "//button[@role='radio'][.//material-icon[@id='PAGE_VIEW']]",
            "//button[@role='radio'][.//div[contains(@class, 'title') and contains(text(), 'Page view')]]",
            "//conversion-goal-card[.//div[contains(@class, 'title') and contains(text(), 'Page view')]]//button",
            "//conversion-goal-card[.//div[contains(text(), 'Page view')]]//button",
            "//conversion-goal-card[.//div[contains(text(), 'Page view')]]",
        ]

        for attempt in range(8):
            check_all()
            check_login()
            self.tracker.log(f"[#{attempt+1}] obj={done_objective} type={done_type} visits={done_visits} pv={done_pv} name={done_name}")

            # --- Without guidance ---
            if not done_objective:
                try:
                    el = d.find_element(By.XPATH, "//*[@data-value='No objective']")
                    if el.is_displayed():
                        js_click(el)
                        done_objective = True
                        self.tracker.log("Chon without guidance", "success")
                        time.sleep(2)
                except Exception:
                    pass

            # --- Campaign type (Search) ---
            if not done_type:
                try:
                    el = d.find_element(By.XPATH, f"//*[@data-value='{camp_type}']")
                    if el.is_displayed():
                        js_click(el)
                        done_type = True
                        self.tracker.log(f"Chon {camp_type}", "success")
                        time.sleep(2)
                except Exception:
                    pass

            # --- Enhanced conversions: bo tick ---
            for cb in d.find_elements(By.XPATH,
                    "//enhanced-conversions-view//mat-checkbox | //material-checkbox | //mat-checkbox"):
                try:
                    if cb.is_displayed() and "enhanced conversions" in cb.text.lower() and is_checkbox_ticked(cb):
                        js_click(cb)
                        self.tracker.log("Bo tick Enhanced conversions", "success")
                        time.sleep(1)
                        break
                except Exception:
                    pass

            # --- Website visits: tick ---
            if not done_visits:
                for c in d.find_elements(By.XPATH, "//mat-checkbox | //material-checkbox"):
                    try:
                        if c.is_displayed() and "Website visits" in c.text:
                            if not is_checkbox_ticked(c):
                                js_click(c)
                                self.tracker.log("Tick Website visits", "success")
                                time.sleep(2)
                            done_visits = True
                            break
                    except Exception:
                        pass

            # --- Campaign name ---
            if not done_name:
                try:
                    name_input = d.find_element(By.XPATH, "//input[@aria-label='Campaign name']")
                    if name_input.is_displayed():
                        clear_and_type(name_input, name)
                        self.tracker.log(f"Dien Campaign name: {name}", "success")
                        done_name = True
                        time.sleep(1)
                except Exception:
                    pass

            # --- Page view ---
            if not done_pv:
                if click_by_text("Page view"):
                    done_pv = True
                    self.tracker.log("Click Page view", "success")
                    time.sleep(1)
                else:
                    for xp in PV_XPATHS:
                        if done_pv:
                            break
                        for el in d.find_elements(By.XPATH, xp):
                            try:
                                if not el.is_displayed():
                                    continue
                                d.execute_script("arguments[0].scrollIntoView({block: 'center'})", el)
                                time.sleep(0.3)
                                js_click(el)
                                done_pv = True
                                self.tracker.log("Click Page view (xpath)", "success")
                                time.sleep(1)
                                break
                            except Exception:
                                pass

            # --- Xong? ---
            if done_name and (done_pv or attempt >= 4):
                self.tracker.log(f"Xong! obj={done_objective} type={done_type} visits={done_visits} pv={done_pv} name={done_name}")
                if not click_button("Continue"):
                    click_button("Agree and continue")
                time.sleep(5)
                check_all()
                check_login()
                break

            # Chua xong → Continue de chuyen trang / hien form tiep
            self.tracker.log("Continue...")
            if not click_button("Continue"):
                click_button("Agree and continue")
            time.sleep(5)
            check_all()
            check_login()

        # === BUOC 14: Bidding ===
        self.tracker.set_current(step="Buoc 14: Bidding")
        check_all()
        time.sleep(3)
        bidding = campaign_config.get("bidding", "maximize_clicks")
        cpc = campaign_config.get("cpc", "")

        if "click" in bidding.lower():
            # Mo dropdown bang dropdown-button (KHONG click text Conversions truc tiep)
            try:
                dbs = d.find_elements(By.XPATH, "//material-dropdown-select//dropdown-button")
                for db in dbs:
                    if db.is_displayed() and ("Conversions" in db.text or "Clicks" in db.text):
                        action_click(db)
                        time.sleep(2)
                        break
                # Chon Clicks
                for item in d.find_elements(By.XPATH, "//material-select-dropdown-item"):
                    if item.is_displayed() and item.text.strip() == "Clicks":
                        js_click(item)
                        self.tracker.log("Da chon Clicks bidding", "success")
                        time.sleep(2)
                        break
            except Exception:
                self.tracker.log("Khong doi duoc bidding", "warn")

        if cpc:
            try:
                # Tick checkbox max CPC
                for c in d.find_elements(By.XPATH, "//mat-checkbox | //material-checkbox"):
                    if c.is_displayed() and "maximum cost per click" in c.text:
                        js_click(c)
                        time.sleep(1)
                        break
                # Dien CPC trong max-bid-container
                for s in d.find_elements(By.XPATH, "//div[contains(@class, 'max-bid-container')] | //section[.//span[contains(text(), 'Maximum CPC')]]"):
                    if s.is_displayed():
                        for inp in s.find_elements(By.XPATH, ".//input"):
                            if inp.is_displayed():
                                clear_and_type(inp, cpc)
                                self.tracker.log(f"Da dien CPC: {cpc}", "success")
                                break
                        break
            except Exception:
                self.tracker.log("Khong dien duoc CPC", "warn")

        # === BUOC 15: Next + Campaign Settings ===
        self.tracker.set_current(step="Buoc 15: Campaign Settings")
        check_all()
        click_button("Next")
        time.sleep(5)
        check_all()

        # Bo tick Search Partners + Display Network (check bang icon text)
        for cls_name in ["search-checkbox", "display-checkbox"]:
            for c in d.find_elements(By.XPATH, f"//material-checkbox[contains(@class, '{cls_name}')]"):
                try:
                    if c.is_displayed() and is_checkbox_ticked(c):
                        js_click(c)
                        time.sleep(0.5)
                except Exception:
                    pass
        self.tracker.log("Da bo tick Search Partners + Display Network", "success")

        # === BUOC 16: Locations ===
        self.tracker.set_current(step="Buoc 16: Locations")
        check_all()
        target_locs = campaign_config.get("target_locations", [])
        exclude_locs = campaign_config.get("exclude_locations", [])

        if target_locs or exclude_locs:
            try:
                WebDriverWait(d, 8).until(
                    EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Enter another location')]"))
                ).click()
                time.sleep(2)
                WebDriverWait(d, 8).until(
                    EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Advanced search')]"))
                ).click()
                time.sleep(3)

                # Tick bulk
                bulk_cb = d.find_element(By.XPATH, "//material-checkbox[contains(@class, 'bulk-locations-checkbox')]")
                if bulk_cb.get_attribute("aria-checked") != "true":
                    js_click(bulk_cb)
                    time.sleep(1)

                BULK_TA = "//bulk-location-input//textarea[contains(@class, 'textarea')]"
                SEARCH_BTN = "//bulk-location-input//material-button[contains(@class, 'search-button')]"
                TARGET_ALL = "//material-button[.//div[contains(text(), 'Target all')] or .//span[contains(text(), 'Target all')]]"
                EXCLUDE_ALL = "//material-button[.//div[contains(text(), 'Exclude all')] or .//span[contains(text(), 'Exclude all')]]"

                def bulk_search(locs, action_xpath, label):
                    ta = WebDriverWait(d, 10).until(EC.element_to_be_clickable((By.XPATH, BULK_TA)))
                    ta.click()
                    time.sleep(0.5)
                    loc_text = "\n".join(locs) if isinstance(locs, list) else str(locs).replace("|", "\n")
                    js_set_textarea(ta, loc_text)
                    time.sleep(2)
                    WebDriverWait(d, 15).until(
                        lambda drv: drv.find_element(By.XPATH, SEARCH_BTN).get_attribute("aria-disabled") != "true"
                    )
                    js_click(d.find_element(By.XPATH, SEARCH_BTN))
                    time.sleep(8)
                    WebDriverWait(d, 15).until(EC.element_to_be_clickable((By.XPATH, action_xpath)))
                    js_click(d.find_element(By.XPATH, action_xpath))
                    time.sleep(3)
                    count = len(locs) if isinstance(locs, list) else locs.count("|") + 1
                    self.tracker.log(f"Da {label} {count} locations", "success")

                if target_locs:
                    bulk_search(target_locs, TARGET_ALL, "target")

                if exclude_locs:
                    # Clear textarea cu
                    try:
                        ta = d.find_element(By.XPATH, BULK_TA)
                        ta.click()
                        time.sleep(0.3)
                        js_set_textarea(ta, "")
                        time.sleep(1)
                    except Exception:
                        pass
                    bulk_search(exclude_locs, EXCLUDE_ALL, "exclude")

                # Save — tim nut Save (khong phai btn-yes vi selector co the sai)
                time.sleep(2)
                for b in d.find_elements(By.XPATH, "//material-button | //button"):
                    try:
                        if b.is_displayed() and b.text.strip() == "Save":
                            js_click(b)
                            self.tracker.log("Da save locations", "success")
                            time.sleep(5)
                            break
                    except Exception:
                        pass
            except Exception as e:
                self.tracker.log(f"Loi locations: {e}", "warn")
                try:
                    for c in d.find_elements(By.XPATH, "//material-button | //button"):
                        if c.is_displayed() and c.text.strip() == "Cancel":
                            js_click(c)
                            break
                except Exception:
                    pass

        # === BUOC 17: Xoa English ===
        self.tracker.set_current(step="Buoc 17: Languages")
        try:
            for r in d.find_elements(By.XPATH, "//div[@aria-label='English remove']"):
                if r.is_displayed():
                    js_click(r)
                    self.tracker.log("Da xoa English -> All languages", "success")
                    time.sleep(1)
                    break
        except Exception:
            pass

        # === BUOC 18-20: Next > Next > Skip ===
        for step_name, btn_text in [("Buoc 18: Next", "Next"), ("Buoc 19: Skip AI Max", "Next"), ("Buoc 20: Skip keyword gen", "Skip")]:
            self.tracker.set_current(step=step_name)
            check_all()
            if not click_button(btn_text):
                click_button("Next")
            time.sleep(8)
            check_all()

        # === BUOC 21: Keywords + Ads ===
        self.tracker.set_current(step="Buoc 21: Keywords + Ads")
        check_all()
        time.sleep(3)

        # Keywords
        keywords = campaign_config.get("keywords", [])
        if keywords:
            try:
                kw_ta = WebDriverWait(d, 15).until(
                    EC.presence_of_element_located((By.XPATH, '//textarea[contains(@aria-label, "Enter or paste keywords")]'))
                )
                kw_ta.click()
                time.sleep(0.5)
                kw_text = "\n".join(keywords) if isinstance(keywords, list) else str(keywords)
                kw_ta.send_keys(kw_text)
                self.tracker.log(f"Da dien {len(keywords)} keywords", "success")
            except Exception as e:
                self.tracker.log(f"Loi keywords: {e}", "warn")
            time.sleep(1)

        # Final URL
        final_url = campaign_config.get("final_url", "")
        if final_url:
            try:
                url_input = WebDriverWait(d, 10).until(
                    EC.element_to_be_clickable((By.XPATH, '//input[@aria-label="Final URL"]'))
                )
                clear_and_type(url_input, final_url)
                self.tracker.log(f"Da dien Final URL", "success")
            except Exception as e:
                self.tracker.log(f"Loi Final URL: {e}", "warn")
            time.sleep(1)

        # Headlines — dien het toi da, click Add neu thieu o
        headlines = campaign_config.get("headlines", [])
        if headlines:
            try:
                HL_XPATH = '//section[contains(@class, "headline")]//input'
                WebDriverWait(d, 15).until(EC.presence_of_element_located((By.XPATH, HL_XPATH)))
                time.sleep(2)
                section = d.find_element(By.XPATH, '//section[contains(@class, "headline")]')
                filled = 0
                for hl in headlines:
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
                        inp = inps[filled]
                        d.execute_script("arguments[0].scrollIntoView({block: 'center'})", inp)
                        time.sleep(0.5)
                        try:
                            d.find_element(By.TAG_NAME, "body").click()
                            time.sleep(0.3)
                        except Exception:
                            pass
                        try:
                            clear_and_type(inp, hl)
                        except Exception:
                            js_click(inp)
                            time.sleep(0.3)
                            inp.send_keys(Keys.CONTROL, "a")
                            time.sleep(0.2)
                            inp.send_keys(str(hl))
                        filled += 1
                        time.sleep(0.5)
                self.tracker.log(f"Da dien {filled}/{len(headlines)} headlines", "success")
            except Exception as e:
                self.tracker.log(f"Loi headlines: {e}", "warn")

        # Descriptions — dien het toi da
        descriptions = campaign_config.get("descriptions", [])
        if descriptions:
            try:
                visible = [dd for dd in d.find_elements(By.XPATH, '//textarea[@aria-label="Description"]') if dd.is_displayed()]
                filled = 0
                for desc in descriptions:
                    if filled >= len(visible):
                        try:
                            for ad in d.find_elements(By.XPATH, '//section[contains(@class, "description")]//div[contains(@class, "add")]'):
                                if ad.is_displayed() and "Description" in ad.text:
                                    js_click(ad)
                                    time.sleep(1)
                                    break
                            visible = [dd for dd in d.find_elements(By.XPATH, '//textarea[@aria-label="Description"]') if dd.is_displayed()]
                        except Exception:
                            break
                    if filled < len(visible):
                        clear_and_type(visible[filled], desc)
                        filled += 1
                        time.sleep(0.5)
                self.tracker.log(f"Da dien {filled}/{len(descriptions)} descriptions", "success")
            except Exception as e:
                self.tracker.log(f"Loi descriptions: {e}", "warn")

        # Next — check 2FA truoc vi hay nhay ra o buoc 21
        check_all()
        click_button("Next")
        time.sleep(10)
        check_all()

        # Sau 2FA co the bi reset — check trang hien tai truc tiep
        for retry_after_21 in range(3):
            on_budget = on_page(
                "//material-radio[contains(., 'Set custom budget')] | "
                "//input[contains(@aria-label, 'budget') or contains(@aria-label, 'Budget')]"
            )
            on_publish = False
            for b in d.find_elements(By.XPATH, "//material-button | //button"):
                try:
                    if b.is_displayed() and "Publish campaign" in b.text:
                        on_publish = True
                        break
                except Exception:
                    pass
            on_keywords = on_page(
                "//textarea[contains(@aria-label, 'keyword')] | "
                "//input[@aria-label='Final URL']"
            )

            if on_budget:
                self.tracker.log("Dang o trang Budget", "warn")
                break
            elif on_publish:
                self.tracker.log("Da o trang Review — skip Budget")
                break
            elif on_keywords:
                self.tracker.log(f"Van o Keywords (2FA reset?) — Next lai ({retry_after_21 + 1})", "warn")
                click_button("Next")
                time.sleep(10)
                check_all()
                continue
            else:
                click_button("Next")
                time.sleep(8)
                check_all()
                break

        # === BUOC 22: Budget ===
        self.tracker.set_current(step="Buoc 22: Budget")
        check_all()
        time.sleep(3)
        budget = campaign_config.get("budget", "5")

        # Click radio Set custom budget bang ActionChains
        for r in d.find_elements(By.TAG_NAME, "material-radio"):
            try:
                if r.is_displayed() and "Set custom budget" in r.text:
                    d.execute_script("arguments[0].scrollIntoView({block: 'center'})", r)
                    time.sleep(0.5)
                    action_click(r)
                    time.sleep(2)
                    break
            except Exception:
                pass

        # Expand panel
        panels = d.find_elements(By.XPATH, "//proactive-budget-recommendation-picker//material-expansionpanel")
        for p in reversed(panels):
            try:
                if p.is_displayed() and "Set custom" in p.text:
                    header = p.find_element(By.XPATH, ".//div[contains(@class, 'header')]")
                    action_click(header)
                    time.sleep(3)
                    break
            except Exception:
                pass

        # Dien budget — nhieu selector fallback
        budget_filled = False
        for xp in [
            "//input[contains(@aria-label, 'budget') or contains(@aria-label, 'Budget')]",
            "//input[contains(@aria-label, 'amount') or contains(@aria-label, 'Amount')]",
            "//proactive-budget-recommendation-picker//input[@type='text']",
            "//material-expansionpanel[.//span[contains(text(), 'Set custom')]]//input",
            "//div[contains(@class, 'budget')]//input",
        ]:
            if budget_filled:
                break
            try:
                for el in d.find_elements(By.XPATH, xp):
                    if el.is_displayed():
                        d.execute_script("arguments[0].scrollIntoView({block: 'center'})", el)
                        time.sleep(0.5)
                        clear_and_type(el, budget)
                        self.tracker.log(f"Da dien budget: ${budget}", "success")
                        budget_filled = True
                        break
            except Exception:
                pass
        if not budget_filled:
            time.sleep(5)
            try:
                bi = WebDriverWait(d, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//input[contains(@aria-label, 'budget') or contains(@aria-label, 'Budget')]"))
                )
                clear_and_type(bi, budget)
                self.tracker.log(f"Da dien budget (retry): ${budget}", "success")
            except Exception:
                self.tracker.log("Khong tim thay budget input", "warn")

        # Next -> Review
        check_all()
        click_button("Next")
        time.sleep(8)
        check_all()

        # === BUOC 23: Publish ===
        self.tracker.set_current(step="Buoc 23: Publish")

        # Doi nut Publish — neu 2FA reset hoac Fix errors, scan lai va xu ly
        budget = campaign_config.get("budget", "5")
        for wait_round in range(12):
            check_all()
            check_login()

            # Tim nut Publish
            found = False
            for b in d.find_elements(By.XPATH, "//material-button | //button"):
                try:
                    if b.is_displayed() and "Publish campaign" in b.text:
                        found = True
                        break
                except Exception:
                    pass
            if found:
                break

            # Chua thay Publish — check trang hien tai truc tiep
            on_budget = on_page(
                "//material-radio[contains(., 'Set custom budget')] | "
                "//input[contains(@aria-label, 'budget') or contains(@aria-label, 'Budget')]"
            )
            on_keywords = on_page(
                "//textarea[contains(@aria-label, 'keyword')] | "
                "//input[@aria-label='Final URL'] | "
                "//section[contains(@class, 'headline')]//input"
            )
            on_settings = on_page(
                "//material-checkbox[contains(@class, 'search-checkbox')] | "
                "//material-checkbox[contains(@class, 'display-checkbox')]"
            )

            if on_budget:
                self.tracker.log("Dang o Budget — check + Next...")
                try:
                    bi = d.find_element(By.XPATH, "//input[contains(@aria-label, 'budget') or contains(@aria-label, 'Budget')]")
                    if bi.is_displayed():
                        val = bi.get_attribute("value") or ""
                        if not val or val == "0":
                            clear_and_type(bi, budget)
                            self.tracker.log(f"Dien lai budget: ${budget}")
                except Exception:
                    pass
                click_button("Next")
                time.sleep(8)
                check_all()
                continue

            elif on_keywords:
                self.tracker.log("Dang o Keywords/Ads — Next...")
                click_button("Next")
                time.sleep(10)
                check_all()
                continue

            elif on_settings:
                self.tracker.log("Dang o Settings — Next...")
                click_button("Next")
                time.sleep(10)
                check_all()
                continue

            self.tracker.log(f"Doi Publish... ({(wait_round + 1) * 5}s)")
            time.sleep(5)

        # Click Publish (retry 5 lan — xu ly Fix errors dialog neu co)
        for attempt in range(5):
            # QUAN TRONG: check dialog Fix errors TRUOC khi click Publish
            # Dialog de len Publish button nen phai dong dialog truoc
            check_all()

            # Tim va click Publish
            pub_clicked = False
            for b in d.find_elements(By.XPATH, "//material-button | //button"):
                try:
                    if b.is_displayed() and "Publish campaign" in b.text:
                        d.execute_script("arguments[0].scrollIntoView({block: 'center'})", b)
                        time.sleep(1)
                        action_click(b)
                        self.tracker.log(f"Da click Publish! (lan {attempt + 1})", "success")
                        pub_clicked = True
                        time.sleep(10)
                        break
                except Exception:
                    pass

            if not pub_clicked:
                # Khong tim thay Publish — co the dialog che, thu Next
                click_button("Next")
                time.sleep(10)

            check_all()
            if "New campaign" not in d.title and "Search campaign" not in d.title:
                break
            self.tracker.log(f"Van o trang Review (lan {attempt + 1})", "warn")
            time.sleep(5)

        # === SAU PUBLISH: Policy Review + Google Tag ===
        time.sleep(5)
        check_all()

        # Policy Review: "Your campaign is published, but it can't run yet" -> Next
        for _ in range(3):
            if "policy" in d.current_url.lower() or "can't run" in (d.page_source[:5000] if d.page_source else ""):
                self.tracker.log("Trang Policy Review — an Next")
                click_button("Next")
                time.sleep(5)
                check_all()
            else:
                break

        # Google Tag: /aw/signup/tagging -> Close (X)
        time.sleep(3)
        try:
            close_btn = d.find_element(By.XPATH, "//material-button[@aria-label='Close']")
            if close_btn.is_displayed():
                action_click(close_btn)
                self.tracker.log("Da dong Google Tag")
                time.sleep(3)
        except Exception:
            pass

        # Luu vao DB
        upsert_campaign(self.customer_id, name, status="published")
        self.tracker.log(f"Campaign '{name}' da duoc publish thanh cong!", "success")
        return True
