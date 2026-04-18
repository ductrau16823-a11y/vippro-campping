#!/usr/bin/env python3
"""
=== VIPPRO CAMPPING - V4 ===
Tao campaign Google Ads tu dong — TEXT-FIRST selectors.
Moi nut an/checkbox/radio/card/dropdown item tim theo TEXT hien thi tren UI.
Google hay doi class/aria-label/data-value, nhung text UI on dinh hon.

Ngoai le van dung selector id/aria-label:
- Login flow (email/password/TOTP input) — Google login page khong co text label visible
- Close button X — icon khong co text, dung aria-label='Close'
- Navigate URL truc tiep (ads_url)

Goi tu camp_runner.py sau khi da vao dung TK Ads.
"""

import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from api_helpers import upsert_campaign
from status_tracker import StatusTracker


class CampaignCreator:
    """Tao campaign tu dong cho 1 TK Ads — V4 text-based."""

    def __init__(self, driver, account_data, tracker):
        self.driver = driver
        self.account_data = account_data
        self.tracker = tracker
        self.customer_id = account_data.get("accountId", "")
        self.gmail = account_data.get("gmailEmail", "")

    def run_campaign_flow(self, campaign_config, skip_navigate=False, camp_index=1):
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.action_chains import ActionChains

        d = self.driver
        base_name = campaign_config.get("name", "Campaign")
        name = f"{base_name} {camp_index}" if camp_index > 1 else base_name
        self.tracker.log(f"=== [V4] Bat dau tao campaign: {name} (#{camp_index}) ===")

        def ads_url(path="/aw/campaigns"):
            cid = self.customer_id.replace("-", "")
            return f"https://ads.google.com{path}?__e={cid}"

        nav_state = {
            "entered_ads": False,
            "last_chooser_url": None,
            "chooser_clicks": 0,
            "last_select_url": None,
            "select_clicks": 0,
        }

        # ==================== CORE HELPERS ====================

        def js_click(el):
            d.execute_script("arguments[0].click()", el)

        def action_click(el):
            ActionChains(d).move_to_element(el).pause(0.3).click().perform()

        def safe_click(el):
            try:
                d.execute_script("arguments[0].scrollIntoView({block:'center'})", el)
                time.sleep(0.3)
            except Exception:
                pass
            for fn in (lambda: el.click(), lambda: action_click(el), lambda: js_click(el)):
                try:
                    fn()
                    return True
                except Exception:
                    pass
            return False

        def in_search_input(el):
            """True neu el la input/textarea hoac nam trong material-auto-suggest-input."""
            try:
                tag = (el.tag_name or "").lower()
                if tag in ("input", "textarea", "material-auto-suggest-input"):
                    return True
                anc = el.find_elements(By.XPATH, "ancestor::material-auto-suggest-input | ancestor::input | ancestor::textarea")
                return len(anc) > 0
            except Exception:
                return False

        def visible_els(xpath, allow_input=False):
            out = []
            try:
                for e in d.find_elements(By.XPATH, xpath):
                    try:
                        if not e.is_displayed():
                            continue
                        if not allow_input and in_search_input(e):
                            continue
                        out.append(e)
                    except Exception:
                        pass
            except Exception:
                pass
            return out

        def _esc(text):
            # XPath string literal — dung concat neu co ca " va '
            if '"' not in text:
                return f'"{text}"'
            if "'" not in text:
                return f"'{text}'"
            parts = text.split('"')
            return "concat(" + ", '\"', ".join(f'"{p}"' for p in parts) + ")"

        # ==================== TEXT-BASED CLICK HELPERS ====================

        def click_text(text, timeout=10, exact=True):
            """Click button/material-button/a co text (uu tien exact, fallback contains).
            Uu tien button enabled."""
            t = _esc(text)
            if exact:
                xp = (f"//button[normalize-space()={t}] | "
                      f"//material-button[normalize-space()={t}] | "
                      f"//a[normalize-space()={t}]")
            else:
                xp = (f"//button[contains(normalize-space(.), {t})] | "
                      f"//material-button[contains(normalize-space(.), {t})] | "
                      f"//a[contains(normalize-space(.), {t})]")
            deadline = time.time() + timeout
            while time.time() < deadline:
                enabled_match = None
                any_match = None
                for b in visible_els(xp):
                    try:
                        any_match = any_match or b
                        if (b.get_attribute("aria-disabled") or "").lower() != "true" and b.is_enabled():
                            enabled_match = b
                            break
                    except Exception:
                        pass
                target = enabled_match or any_match
                if target is not None:
                    return safe_click(target)
                time.sleep(0.5)
            return False

        def click_text_anywhere(text):
            """Click element bat ky chua text — chon element nho nhat (text khop sat).
            Skip input/textarea/searchbox de tranh click nham thanh search bar."""
            t = _esc(text)
            SKIP_TAGS = {"input", "textarea", "material-input", "search-box", "searchbox"}
            candidates = []
            for el in visible_els(f"//*[contains(normalize-space(.), {t})]"):
                try:
                    tag = (el.tag_name or "").lower()
                    if tag in SKIP_TAGS:
                        continue
                    role = (el.get_attribute("role") or "").lower()
                    if role in ("searchbox", "textbox"):
                        continue
                    # Skip neu element o trong thanh tim kiem top
                    cls = (el.get_attribute("class") or "").lower()
                    if "searchbox" in cls or "search-bar" in cls or "top-bar" in cls:
                        continue
                    own = (el.text or "").strip()
                    if text not in own:
                        continue
                    # Uu tien element co text gan bang text can tim
                    score = abs(len(own) - len(text))
                    candidates.append((score, el))
                except Exception:
                    pass
            candidates.sort(key=lambda x: x[0])
            for _, el in candidates:
                if safe_click(el):
                    return True
            return False

        def click_continue_or_agree():
            """Click 'Continue' hoac 'Agree and continue' — uu tien enabled."""
            for txt in ("Continue", "Agree and continue"):
                if click_text(txt, timeout=3):
                    self.tracker.log(f"Click '{txt}'")
                    return True
            return False

        # ==================== CHECKBOX / RADIO ====================

        def is_checked_by_icon(el):
            """Material checkbox check bang icon text."""
            try:
                tx = el.text or ""
                if "check_box_outline_blank" in tx:
                    return False
                if "check_box" in tx:
                    return True
                a = (el.get_attribute("aria-checked") or "").lower()
                return a == "true"
            except Exception:
                return False

        def find_checkbox_with_label(label_text):
            t = _esc(label_text)
            for xp in (
                f"//material-checkbox[contains(normalize-space(.), {t})]",
                f"//mat-checkbox[contains(normalize-space(.), {t})]",
                f"//*[@role='checkbox'][contains(normalize-space(.), {t})]",
            ):
                for el in visible_els(xp):
                    return el
            return None

        def tick(label_text):
            el = find_checkbox_with_label(label_text)
            if el is None:
                return False
            if not is_checked_by_icon(el):
                safe_click(el)
                time.sleep(0.5)
            return True

        def untick(label_text):
            el = find_checkbox_with_label(label_text)
            if el is None:
                return False
            if is_checked_by_icon(el):
                safe_click(el)
                time.sleep(0.5)
            return True

        def click_radio_with_text(text):
            """Click radio / card / item co text — uu tien EXACT match.
            Support Google Ads UI moi: <span class='unified-goals-card-title'>Search</span>."""
            t = _esc(text)
            # Uu tien 0: data-value (v1/v3 proven — SEARCH, DISPLAY, VIDEO...)
            t_upper = _esc(text.upper())
            for xp in (
                f"//*[@data-value={t_upper}]",
                f"//*[@data-value={t}]",
            ):
                for el in visible_els(xp):
                    try:
                        js_click(el)
                        time.sleep(0.5)
                        return True
                    except Exception:
                        if safe_click(el):
                            return True
            # Uu tien 0.5: js_click span unified-goals-card-title (v1 style)
            for xp in (
                f"//span[contains(@class,'unified-goals-card-title') and normalize-space(text())={t}]",
                f"//span[contains(@class,'unified-goals-card-title') and contains(text(), {t})]",
            ):
                for el in visible_els(xp):
                    try:
                        js_click(el)
                        time.sleep(0.5)
                        return True
                    except Exception:
                        pass
            # Uu tien 1: UI moi Google Ads 2026 — click <channel-selection-card-v2> / <selection-card>
            for xp in (
                f"//channel-selection-card-v2[.//span[contains(@class,'unified-goals-card-title') and normalize-space(text())={t}]]",
                f"//selection-card[.//span[contains(@class,'unified-goals-card-title') and normalize-space(text())={t}]]",
                f"//unified-goals-card[.//span[contains(@class,'unified-goals-card-title') and normalize-space(text())={t}]]",
            ):
                for el in visible_els(xp):
                    if safe_click(el):
                        return True
            # Uu tien 2: JS leo len tu span -> ancestor clickable
            js = """
            var spans = document.querySelectorAll('span.unified-goals-card-title');
            for (var i = 0; i < spans.length; i++) {
                if (spans[i].textContent.trim() !== arguments[0]) continue;
                if (!spans[i].offsetParent) continue;
                var el = spans[i];
                for (var j = 0; j < 10; j++) {
                    var tag = (el.tagName || '').toLowerCase();
                    var role = el.getAttribute && el.getAttribute('role');
                    if (tag === 'channel-selection-card-v2' ||
                        tag === 'selection-card' ||
                        tag === 'unified-goals-card' ||
                        tag === 'button' ||
                        role === 'button' || role === 'radio' || role === 'checkbox') {
                        el.click();
                        return tag + '#' + (el.id || '');
                    }
                    el = el.parentElement;
                    if (!el || el === document.body) break;
                }
                spans[i].click();
                return 'span';
            }
            return '';
            """
            try:
                result = d.execute_script(js, text)
                if result:
                    self.tracker.log(f"[JS-CLICK] {text} -> {result}")
                    return True
            except Exception:
                pass
            # Uu tien 3: element con co text CHINH XAC
            for xp in (
                f"//*[@role='radio'][.//*[normalize-space(text())={t}]]",
                f"//material-radio[.//*[normalize-space(text())={t}]]",
                f"//mat-radio-button[.//*[normalize-space(text())={t}]]",
                f"//conversion-goal-card[.//*[normalize-space(text())={t}]]",
                f"//*[contains(@class,'card')][.//*[normalize-space(text())={t}]]",
            ):
                for el in visible_els(xp):
                    if safe_click(el):
                        return True
            # Uu tien 4: contains (fallback)
            for xp in (
                f"//material-radio[contains(normalize-space(.), {t})]",
                f"//mat-radio-button[contains(normalize-space(.), {t})]",
                f"//*[@role='radio'][contains(normalize-space(.), {t})]",
                f"//conversion-goal-card[.//*[contains(normalize-space(.), {t})]]",
            ):
                for el in visible_els(xp):
                    if safe_click(el):
                        return True
            return click_text_anywhere(text)

        def tick_on_row(label_text):
            """Tim hang/card/row co text label_text, click o tick/radio ben phai cung hang.
            Dung cho conversion goal cards kieu 'Page view [✓]'."""
            t = _esc(label_text)
            # Cac container chua 1 hang/card co text
            container_xpaths = (
                f"//conversion-goal-card[.//*[normalize-space(text())={t}]]",
                f"//tr[.//*[normalize-space(text())={t}]]",
                f"//*[@role='row'][.//*[normalize-space(text())={t}]]",
                f"//li[.//*[normalize-space(text())={t}]]",
                f"//*[contains(@class,'row')][.//*[normalize-space(text())={t}]]",
                f"//*[contains(@class,'card')][.//*[normalize-space(text())={t}]]",
                f"//*[normalize-space(text())={t}]/ancestor::*[self::div or self::li or self::section][1]",
            )
            # O tick/radio ben trong container — thu nhieu loai
            tick_xpaths = (
                ".//*[@role='checkbox']",
                ".//*[@role='radio']",
                ".//material-checkbox",
                ".//mat-checkbox",
                ".//material-radio",
                ".//mat-radio-button",
                ".//button[@role='radio']",
                ".//button[@role='checkbox']",
                ".//input[@type='checkbox']",
                ".//input[@type='radio']",
            )
            for cxp in container_xpaths:
                for container in visible_els(cxp):
                    for txp in tick_xpaths:
                        for el in container.find_elements(By.XPATH, txp):
                            try:
                                if el.is_displayed():
                                    safe_click(el)
                                    return True
                            except Exception:
                                pass
            return False

        # ==================== VALIDATION / ERROR SCAN ====================

        def has_red_errors():
            """Scan trang tim loi validation (text do). Return list text loi."""
            errors = []
            seen = set()
            xpaths = (
                "//*[@role='alert']",
                "//*[contains(@class,'validation-error')]",
                "//*[contains(@class,'error-msg')]",
                "//*[contains(@class,'required-error')]",
                "//*[contains(@class,'field-error')]",
                "//material-input[contains(@class,'error')]//*[contains(@class,'message')]",
                "//*[contains(@class,'mat-error')]",
                "//error-message",
                "//validation-message",
            )
            for xp in xpaths:
                for el in visible_els(xp):
                    try:
                        text = (el.text or "").strip()
                        if text and 3 < len(text) < 250 and text not in seen:
                            seen.add(text)
                            errors.append(text)
                    except Exception:
                        pass
            return errors

        def continue_and_verify(page_marker_text, actions_fn, max_retries=3):
            """Chay actions -> rescan (actions lan 2) -> Continue -> verify trang doi.
            Neu chua doi, scan errors va retry actions.

            Args:
                page_marker_text: text dac trung trang hien tai (vd 'Choose your objective')
                actions_fn: function chay cac action (idempotent - click/tick OK khi da xong)
                max_retries: so lan retry neu van o trang cu sau Continue
            Return: True neu trang da doi, False neu het retry
            """
            for attempt in range(max_retries):
                # Lan 1: chay actions
                self.tracker.log(f"[ACTIONS #{attempt+1}] chay actions lan 1")
                actions_fn()
                time.sleep(1)
                # Lan 2: chay lai (idempotent) de verify khong sot
                self.tracker.log(f"[RESCAN #{attempt+1}] chay lai de verify khong sot")
                actions_fn()
                time.sleep(1)

                # Scan loi truoc Continue
                errs = has_red_errors()
                if errs:
                    self.tracker.log(f"[ERROR] Truoc Continue con loi: {errs[:3]}", "warn")

                # Continue
                self.tracker.log("[CONT] -> Continue")
                click_continue_or_agree()
                time.sleep(5)
                check_all()

                # Verify trang da doi — marker text bien mat
                deadline = time.time() + 8
                changed = False
                while time.time() < deadline:
                    if not on_page_with_text(page_marker_text):
                        changed = True
                        break
                    time.sleep(1)
                if changed:
                    self.tracker.log(f"[OK] Trang da doi sau Continue", "success")
                    return True

                # Van o trang cu — scan loi
                errs = has_red_errors()
                if errs:
                    self.tracker.log(f"[STUCK] Van o trang cu, loi: {errs[:3]}", "warn")
                else:
                    self.tracker.log(f"[STUCK] Van o trang cu, khong scan thay loi ro rang", "warn")
                time.sleep(2)
            return False

        # ==================== INPUT / TEXTAREA ====================

        def _fill_element(el, value, use_js=False):
            safe_click(el)
            time.sleep(0.2)
            try:
                el.send_keys(Keys.CONTROL, "a")
                time.sleep(0.15)
                el.send_keys(Keys.DELETE)
                time.sleep(0.15)
            except Exception:
                pass
            if use_js:
                d.execute_script(
                    "arguments[0].value=arguments[1];"
                    "arguments[0].dispatchEvent(new Event('input',{bubbles:true}));"
                    "arguments[0].dispatchEvent(new Event('change',{bubbles:true}));",
                    el, str(value),
                )
            else:
                try:
                    el.send_keys(str(value))
                except Exception:
                    d.execute_script(
                        "arguments[0].value=arguments[1];"
                        "arguments[0].dispatchEvent(new Event('input',{bubbles:true}));"
                        "arguments[0].dispatchEvent(new Event('change',{bubbles:true}));",
                        el, str(value),
                    )
            time.sleep(0.3)

        def fill_input_near(label_text, value):
            """Tim input gan label_text roi dien value."""
            t = _esc(label_text)
            for xp in (
                f"//label[contains(normalize-space(.), {t})]/following::input[not(@type='hidden')][1]",
                f"//*[normalize-space(text())={t}]/ancestor::*[self::div or self::section or self::material-input][1]//input[not(@type='hidden')]",
                f"//*[contains(normalize-space(text()), {t})]/following::input[not(@type='hidden')][1]",
                f"//input[@aria-label={t}]",
                f"//input[contains(@aria-label, {t})]",
                f"//input[@placeholder={t}]",
            ):
                for inp in visible_els(xp, allow_input=True):
                    _fill_element(inp, value)
                    return True
            return False

        def fill_textarea_near(label_text, value):
            t = _esc(label_text)
            for xp in (
                f"//label[contains(normalize-space(.), {t})]/following::textarea[1]",
                f"//*[contains(normalize-space(text()), {t})]/following::textarea[1]",
                f"//textarea[@aria-label={t}]",
                f"//textarea[contains(@aria-label, {t})]",
                f"//textarea[@placeholder={t}]",
                f"//textarea[contains(@placeholder, {t})]",
            ):
                for ta in visible_els(xp, allow_input=True):
                    _fill_element(ta, value, use_js=True)
                    return True
            return False

        # ==================== DROPDOWN ====================

        def pick_dropdown(current_text, new_text):
            """Mo dropdown dang hien current_text -> chon item new_text."""
            cur = _esc(current_text)
            new = _esc(new_text)
            dbs = visible_els(
                f"//dropdown-button[contains(normalize-space(.), {cur})] | "
                f"//material-dropdown-select[contains(normalize-space(.), {cur})]//dropdown-button | "
                f"//*[@role='combobox'][contains(normalize-space(.), {cur})]"
            )
            if not dbs:
                return False
            safe_click(dbs[0])
            time.sleep(1.5)
            for xp in (
                f"//material-select-dropdown-item[normalize-space()={new}]",
                f"//*[@role='option'][normalize-space()={new}]",
                f"//material-select-dropdown-item[contains(normalize-space(.), {new})]",
                f"//*[@role='option'][contains(normalize-space(.), {new})]",
            ):
                for item in visible_els(xp):
                    safe_click(item)
                    time.sleep(1)
                    return True
            return False

        # ==================== DIALOG CLOSE ====================

        def close_X_near_text(near_text):
            """Nut X (close) — icon khong co text, dung aria-label='Close'."""
            t = _esc(near_text)
            for xp in (
                f"//material-dialog[contains(normalize-space(.), {t})]//material-button[@aria-label='Close']",
                f"//material-dialog[contains(normalize-space(.), {t})]//button[@aria-label='Close']",
                f"//*[contains(normalize-space(.), {t})]/ancestor::material-dialog//material-button[@aria-label='Close']",
            ):
                for el in visible_els(xp):
                    safe_click(el)
                    return True
            return False

        def on_page_with_text(text):
            t = _esc(text)
            return len(visible_els(f"//*[contains(normalize-space(.), {t})]")) > 0

        # ==================== 2FA + POPUPS ====================

        def handle_2fa():
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

                # Click Confirm hoac Try again — tim theo TEXT
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
                                    self.tracker.log("[2FA] Click Try again (lan 2)")
                                    time.sleep(5)
                                    break
                            break
                    except Exception:
                        pass

                # Chuyen tab 2FA — input#totpPin la selector dac biet (Google login page, khong co text)
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
                            email = ""
                            for e in d.find_elements(By.XPATH, "//*[contains(text(), '@gmail.com')]"):
                                if e.is_displayed():
                                    email = e.text.strip().lower()
                                    break
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
            for dialog in d.find_elements(By.XPATH, "//material-dialog"):
                try:
                    if not dialog.is_displayed() or not dialog.text.strip():
                        continue
                    dlg_text = dialog.text
                    if "Conversion goals" in dlg_text:
                        for cb in dialog.find_elements(By.XPATH,
                                ".//material-button[@aria-label='Close'] | .//button[@aria-label='Close']"):
                            if cb.is_displayed():
                                js_click(cb)
                                self.tracker.log("[POPUP] Dong Conversion goals")
                                time.sleep(2)
                                break
                    elif "Exit guide" in dlg_text:
                        for b in dialog.find_elements(By.XPATH, ".//material-button | .//button"):
                            if b.is_displayed() and "Leave" in b.text:
                                js_click(b)
                                self.tracker.log("[POPUP] Leave")
                                time.sleep(3)
                                break
                    elif "Fix errors" in dlg_text and "Discard" in dlg_text:
                        for b in dialog.find_elements(By.XPATH, ".//material-button | .//button"):
                            if b.is_displayed() and b.text.strip() == "Fix errors":
                                action_click(b)
                                self.tracker.log("[POPUP] Fix errors")
                                time.sleep(5)
                                break
                except Exception:
                    pass

        def handle_draft():
            for dialog in d.find_elements(By.XPATH, "//material-dialog"):
                try:
                    if not dialog.is_displayed() or "draft" not in dialog.text.lower():
                        continue
                    self.tracker.log("[DRAFT] Gap dialog draft...")
                    for n in dialog.find_elements(By.XPATH,
                            ".//campaign-name-cell//div[contains(@class,'name')] | .//td//div[contains(@class,'name')]"):
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
            had_2fa = handle_2fa()
            handle_popups()
            handle_draft()
            if had_2fa:
                time.sleep(5)
                handle_popups()
                handle_draft()

        def check_login():
            cur_url = d.current_url.lower()
            cur_title = d.title.lower()
            on_login = "sign in" in cur_title or "accounts.google.com" in cur_url or "selectaccount" in cur_url
            if not on_login:
                return False
            if nav_state["entered_ads"]:
                self.tracker.log("[CHECK] Chooser/login sau khi da vao Ads — cho transient...", "warn")
                for _ in range(4):
                    time.sleep(2)
                    new_url = d.current_url.lower()
                    if "ads.google.com" in new_url and "selectaccount" not in new_url and "accounts.google.com" not in new_url:
                        return True
                self.tracker.log("[CHECK] Khong tu hoi phuc — abort", "error")
                return True
            self.tracker.log("[CHECK] Bi redirect ve login — do_navigate()", "warn")
            do_navigate()
            time.sleep(3)
            if "ads.google.com" not in d.current_url.lower() or "campaign" not in d.title.lower():
                d.get(ads_url("/aw/campaigns/new"))
                time.sleep(10)
                check_all()
            return True

        # ==================== NAVIGATE (login - giu selector id) ====================

        def do_navigate():
            """Login flow — giu selector id/aria-label vi Google login page khong co text label hien."""
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
                        if nav_state["last_chooser_url"] == cur_url:
                            nav_state["chooser_clicks"] += 1
                            if nav_state["chooser_clicks"] >= 2:
                                self.tracker.log(f"[NAV] LOOP Chooser — abort", "error")
                                return False
                        else:
                            nav_state["chooser_clicks"] = 0
                            nav_state["last_chooser_url"] = cur_url
                        try:
                            el = WebDriverWait(d, 8).until(
                                EC.element_to_be_clickable(
                                    (By.CSS_SELECTOR, f'div[data-identifier="{gmail_email.lower()}"]'))
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
                    # Email
                    try:
                        email_input = d.find_element(By.CSS_SELECTOR, "input[type='email']#identifierId")
                        if email_input.is_displayed():
                            email_input.clear()
                            email_input.send_keys(gmail_email)
                            time.sleep(0.5)
                            try:
                                d.find_element(By.CSS_SELECTOR, "#identifierNext button").click()
                                self.tracker.log(f"[NAV] Email: {gmail_email}")
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
                                    self.tracker.log("[NAV] Password", "success")
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
                                    self.tracker.log(f"[NAV] 2FA: {code}", "success")
                                    time.sleep(5)
                                except Exception:
                                    pass
                            continue
                    except Exception:
                        pass
                    # Fallback data-identifier
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
                    self.tracker.log("[NAV] Dang o Select Account — chon TK...")
                    cid = self.customer_id
                    for item in d.find_elements(By.CSS_SELECTOR, "material-list-item"):
                        if cid in item.text and "Setup in progress" not in item.text:
                            item.click()
                            self.tracker.log(f"[NAV] Chon TK {cid}")
                            time.sleep(10)
                            break
                    continue

                if any(kw in cur_url for kw in ["verification", "billing", "signup/tagging", "policy"]):
                    self.tracker.log("[NAV] Trang phu — navigate ve Campaigns")
                    d.get(ads_url("/aw/campaigns"))
                    time.sleep(10)
                    check_all()
                    continue

                if "ads.google.com" in cur_url:
                    nav_state["entered_ads"] = True
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
                nav_state["entered_ads"] = True
        else:
            do_navigate()

        if "ads.google.com" in d.current_url.lower() and "selectaccount" not in d.current_url.lower():
            nav_state["entered_ads"] = True

        # Check suspended
        self.tracker.log("[FLOW] Bat dau check suspended...")
        try:
            from camp_runner import check_account_status
            profile_name = self.account_data.get("profileName") or ""
            account_db_id = self.account_data.get("id")
            tk_status = check_account_status(d, profile_name, self.customer_id, account_db_id)
            self.tracker.log(f"[FLOW] check_account_status = {tk_status}")
            if tk_status == "suspended":
                self.tracker.log(f"TK {self.customer_id} BI SUSPENDED — skip!", "error")
                return False
        except Exception as e:
            self.tracker.log(f"[WARN] check_account_status loi: {e}", "warn")

        # === BUOC 3: Click New campaign ===
        self.tracker.log("[FLOW] -> Buoc 3")
        self.tracker.set_current(step="Buoc 3: New campaign")
        check_all()
        time.sleep(3)

        # Thu nhieu cach tim nut Create / New campaign (cascade tu v1)
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
            self.tracker.log("Khong tim thay nut Create — navigate truc tiep", "warn")
            d.get(ads_url("/aw/campaigns/new"))
            time.sleep(10)
            check_all()
            clicked = True

        if not clicked:
            self.tracker.log("Khong tim thay nut Create!", "error")
            return False

        time.sleep(5)
        try:
            WebDriverWait(d, 15).until(lambda drv: "campaign" in drv.title.lower())
        except Exception:
            pass
        time.sleep(3)
        check_all()

        # === BUOC 4-6: Objective + Type + Goals — PAGE-DRIVEN ===
        # Chi an Continue khi trang hien tai da hoan thanh (tranh skip truoc khi chon Search)
        self.tracker.set_current(step="Buoc 4-6: Setup campaign")
        time.sleep(3)

        camp_type = campaign_config.get("type", "Search")
        type_text = camp_type.capitalize() if camp_type else "Search"

        done_obj_page = False
        done_type_page = False
        done_goals_page = False

        for attempt in range(12):
            check_all()
            check_login()

            # Detect trang hien tai — moi trang co marker rieng
            on_obj = on_page_with_text("Choose your objective") or on_page_with_text("without a goal")
            on_type = (on_page_with_text("Shopping") and on_page_with_text("Video")
                       and on_page_with_text("Performance Max"))
            # on_goals: chi can "Campaign name" — khi draft da chon Page view sang, text "Page view" khong hien
            on_goals = on_page_with_text("Campaign name") or on_page_with_text("Website visits")

            self.tracker.log(
                f"[#{attempt+1}] obj_page={on_obj} type_page={on_type} goals_page={on_goals} "
                f"| done: obj={done_obj_page} type={done_type_page} goals={done_goals_page}"
            )

            # ========== TRANG OBJECTIVE ==========
            # UI moi: Objective + Type cung 1 trang. Phai click without guidance VA Search + Website visits
            if on_obj and not done_obj_page:
                def obj_actions():
                    # 1. Without guidance
                    try:
                        el = d.find_element(By.XPATH, "//*[@data-value='No objective']")
                        if el.is_displayed():
                            js_click(el)
                            self.tracker.log("[OBJ] Click [data-value='No objective']")
                            time.sleep(1)
                    except Exception:
                        (click_radio_with_text("Create a campaign without a goal's guidance")
                         or click_text_anywhere("without a goal")
                         or click_text_anywhere("without guidance"))
                        time.sleep(1)
                    # 2. Search card
                    if click_radio_with_text(type_text):
                        self.tracker.log(f"[OBJ] Click {type_text}")
                        time.sleep(1)
                    # 3. Website visits (neu hien ra)
                    if tick("Website visits"):
                        self.tracker.log("[OBJ] Tick Website visits")

                if continue_and_verify("Choose your objective", obj_actions):
                    done_obj_page = True
                    done_type_page = True  # UI moi gop Obj+Type
                else:
                    self.tracker.log("[OBJ] Continue khong qua duoc — scan lai", "warn")
                continue

            # ========== TRANG TYPE (UI cu — Search/Display/Shopping tren trang rieng) ==========
            if on_type and not done_type_page:
                def type_actions():
                    if click_radio_with_text(type_text):
                        self.tracker.log(f"[TYPE] Click {type_text}")
                        time.sleep(1)
                    if tick("Website visits"):
                        self.tracker.log("[TYPE] Tick Website visits")

                # Marker: "Performance Max" — trang Type co, trang Goals khong
                if continue_and_verify("Performance Max", type_actions):
                    done_type_page = True
                else:
                    self.tracker.log("[TYPE] Continue khong qua — retry", "warn")
                continue

            # ========== TRANG GOALS + NAME ==========
            if on_goals and not done_goals_page:
                def goals_actions():
                    # Bo tick Enhanced conversions
                    if untick("Turn on enhanced conversions") or untick("enhanced conversions"):
                        self.tracker.log("[GOALS] Untick Enhanced conversions")
                    # Campaign name
                    if fill_input_near("Campaign name", name):
                        self.tracker.log(f"[GOALS] Name: {name}")
                    # Page view — tick o ben phai cung hang
                    if tick_on_row("Page view"):
                        self.tracker.log("[GOALS] Tick Page view (row)")
                    elif click_radio_with_text("Page view"):
                        self.tracker.log("[GOALS] Click Page view (radio)")

                if continue_and_verify("Campaign name", goals_actions):
                    done_goals_page = True
                else:
                    self.tracker.log("[GOALS] Continue khong qua — retry", "warn")
                continue

            # ========== THOAT ==========
            if done_goals_page:
                self.tracker.log("Xong setup — sang Bidding")
                break

            # Khong detect duoc trang nao — co the dang load hoac chuyen trang
            # KHONG an Continue de tranh skip nham
            self.tracker.log("Khong detect duoc trang — cho...", "warn")
            time.sleep(3)

        check_all()
        check_login()

        # === BUOC 7: Bidding ===
        self.tracker.set_current(step="Buoc 7: Bidding")
        check_all()
        time.sleep(3)
        bidding = campaign_config.get("bidding", "maximize_clicks")
        cpc = campaign_config.get("cpc", "")

        if "click" in bidding.lower():
            if not pick_dropdown("Conversions", "Clicks"):
                if not pick_dropdown("Conversion value", "Clicks"):
                    pick_dropdown("Impression share", "Clicks")
            self.tracker.log("Da chon Clicks bidding", "success")

        if cpc:
            if tick("maximum cost per click"):
                time.sleep(1)
            if not fill_input_near("Maximum CPC", cpc):
                if not fill_input_near("Max. CPC", cpc):
                    fill_input_near("max CPC", cpc)
            self.tracker.log(f"Da dien CPC: {cpc}", "success")

        # === BUOC 8: Next + Campaign Settings ===
        self.tracker.set_current(step="Buoc 8: Campaign Settings")
        check_all()
        click_text("Next")
        time.sleep(5)
        check_all()

        # V1-proven: class-based selector
        for cls_name in ["search-checkbox", "display-checkbox"]:
            for c in d.find_elements(By.XPATH, f"//material-checkbox[contains(@class, '{cls_name}')]"):
                try:
                    if c.is_displayed() and is_checked_by_icon(c):
                        js_click(c)
                        time.sleep(0.5)
                except Exception:
                    pass
        # Fallback: text-based untick
        untick("Search Partners")
        untick("Display Network")
        self.tracker.log("Da bo tick Search Partners + Display Network", "success")

        # === Locations ===
        target_locs = campaign_config.get("target_locations", [])
        exclude_locs = campaign_config.get("exclude_locations", [])

        if target_locs or exclude_locs:
            try:
                # V1-proven: XPath contains text (khong can button/a tag)
                clicked_ea = False
                try:
                    WebDriverWait(d, 8).until(
                        EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Enter another location')]"))
                    ).click()
                    clicked_ea = True
                except Exception:
                    pass
                if not clicked_ea:
                    if not click_text("Enter another location", timeout=5):
                        click_text_anywhere("Enter another location")
                time.sleep(2)
                # Advanced search
                clicked_as = False
                try:
                    WebDriverWait(d, 8).until(
                        EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Advanced search')]"))
                    ).click()
                    clicked_as = True
                except Exception:
                    pass
                if not clicked_as:
                    if not click_text("Advanced search", timeout=5):
                        click_text_anywhere("Advanced search")
                time.sleep(3)

                # Bulk checkbox
                tick("Enter multiple locations")

                def bulk_search(locs, action_text, label):
                    loc_text = "\n".join(locs) if isinstance(locs, list) else str(locs).replace("|", "\n")
                    if not fill_textarea_near("Enter locations", loc_text):
                        # Fallback: textarea bat ky trong dialog
                        for ta in visible_els("//material-dialog//textarea"):
                            _fill_element(ta, loc_text, use_js=True)
                            break
                    time.sleep(2)
                    click_text("Search", timeout=15)
                    time.sleep(8)
                    click_text(action_text, timeout=15)
                    time.sleep(3)
                    count = len(locs) if isinstance(locs, list) else loc_text.count("\n") + 1
                    self.tracker.log(f"Da {label} {count} locations", "success")

                if target_locs:
                    bulk_search(target_locs, "Target all", "target")

                if exclude_locs:
                    # Clear textarea truoc
                    for ta in visible_els("//material-dialog//textarea"):
                        _fill_element(ta, "", use_js=True)
                        break
                    time.sleep(1)
                    bulk_search(exclude_locs, "Exclude all", "exclude")

                time.sleep(2)
                click_text("Save")
                self.tracker.log("Da save locations", "success")
                time.sleep(5)
            except Exception as e:
                self.tracker.log(f"Loi locations: {e}", "warn")
                click_text("Cancel")

        # === Xoa English ===
        self.tracker.set_current(step="Buoc 8: Languages")
        try:
            # Tim X ke text "English" — aria-label='English remove' hoac x-button canh chip English
            for xp in (
                "//div[@aria-label='English remove']",
                "//*[normalize-space(text())='English']/following-sibling::*[contains(@aria-label, 'remove')]",
                "//*[normalize-space(text())='English']/ancestor::*[self::material-chip or self::mat-chip or self::div][1]//*[contains(@aria-label, 'remove')]",
            ):
                for remove in visible_els(xp):
                    safe_click(remove)
                    self.tracker.log("Da xoa English -> All languages", "success")
                    time.sleep(1)
                    break
                else:
                    continue
                break
        except Exception:
            pass

        # EU political ads: chon No
        try:
            if on_page_with_text("political advertising") or on_page_with_text("political ads"):
                click_radio_with_text("No")
        except Exception:
            pass

        # === BUOC 9-10: Next + Skip AI Max + Skip keyword gen ===
        for step_name, btn_text in [
            ("Buoc 9: Next", "Next"),
            ("Buoc 9.5: Skip AI Max", "Next"),
            ("Buoc 9.6: Skip keyword gen", "Skip"),
        ]:
            self.tracker.set_current(step=step_name)
            check_all()
            if not click_text(btn_text, timeout=5):
                click_text("Next", timeout=5)
            time.sleep(8)
            check_all()

        # === BUOC 11: Keywords + Ads ===
        self.tracker.set_current(step="Buoc 11: Keywords + Ads")
        check_all()
        time.sleep(3)

        adgroup_name = campaign_config.get("adgroup_name") or campaign_config.get("adgroupName")
        if adgroup_name:
            if fill_input_near("Ad group name", adgroup_name):
                self.tracker.log(f"Dien Ad group name: {adgroup_name}", "success")

        # Keywords
        keywords = campaign_config.get("keywords", [])
        if keywords:
            kw_text = "\n".join(keywords) if isinstance(keywords, list) else str(keywords)
            ok = fill_textarea_near("Enter or paste keywords", kw_text) or \
                 fill_textarea_near("Keywords", kw_text)
            if ok:
                count = len(keywords) if isinstance(keywords, list) else 1
                self.tracker.log(f"Da dien {count} keywords", "success")
            else:
                self.tracker.log("Khong tim thay textarea keywords", "warn")
            time.sleep(1)

        # Final URL
        final_url = campaign_config.get("final_url", "")
        if final_url:
            if fill_input_near("Final URL", final_url):
                self.tracker.log("Da dien Final URL", "success")
            time.sleep(1)

        # Headlines — tim section co text "Headlines", dien input, click Add headline neu thieu
        headlines = campaign_config.get("headlines", [])
        if headlines:
            try:
                section_list = visible_els(
                    "//*[normalize-space(text())='Headlines']/ancestor::section[1] | "
                    "//section[.//*[normalize-space(text())='Headlines']]"
                )
                section = section_list[0] if section_list else None
                filled = 0
                for hl in headlines:
                    if section:
                        inps = [i for i in section.find_elements(By.XPATH, ".//input") if i.is_displayed()]
                    else:
                        inps = [i for i in d.find_elements(By.XPATH, "//input[@aria-label='Headline']") if i.is_displayed()]
                    if filled >= len(inps):
                        # Click "Add headline"
                        add_ok = False
                        if section:
                            for ad in section.find_elements(By.XPATH, ".//*[contains(normalize-space(.), 'Add headline')]"):
                                if ad.is_displayed():
                                    safe_click(ad)
                                    time.sleep(1)
                                    add_ok = True
                                    break
                        if not add_ok:
                            for ad in visible_els("//*[contains(normalize-space(.), 'Add headline')]"):
                                safe_click(ad)
                                time.sleep(1)
                                break
                        if section:
                            inps = [i for i in section.find_elements(By.XPATH, ".//input") if i.is_displayed()]
                    if filled < len(inps):
                        inp = inps[filled]
                        d.execute_script("arguments[0].scrollIntoView({block:'center'})", inp)
                        time.sleep(0.3)
                        try:
                            d.find_element(By.TAG_NAME, "body").click()
                            time.sleep(0.3)
                        except Exception:
                            pass
                        try:
                            _fill_element(inp, hl)
                        except Exception:
                            pass
                        # Dong popup Dynamic Keyword Insertion neu co '{'
                        if "{" in str(hl):
                            try:
                                inp.send_keys(Keys.ESCAPE)
                                time.sleep(0.3)
                            except Exception:
                                pass
                        filled += 1
                        time.sleep(0.5)
                self.tracker.log(f"Da dien {filled}/{len(headlines)} headlines", "success")
            except Exception as e:
                self.tracker.log(f"Loi headlines: {e}", "warn")

        # Descriptions
        descriptions = campaign_config.get("descriptions", [])
        if descriptions:
            try:
                filled = 0
                for desc in descriptions:
                    visible = [dd for dd in d.find_elements(By.XPATH, "//textarea[@aria-label='Description']") if dd.is_displayed()]
                    if filled >= len(visible):
                        for ad in visible_els("//*[contains(normalize-space(.), 'Add description')]"):
                            safe_click(ad)
                            time.sleep(1)
                            break
                        visible = [dd for dd in d.find_elements(By.XPATH, "//textarea[@aria-label='Description']") if dd.is_displayed()]
                    if filled < len(visible):
                        _fill_element(visible[filled], desc)
                        filled += 1
                        time.sleep(0.5)
                self.tracker.log(f"Da dien {filled}/{len(descriptions)} descriptions", "success")
            except Exception as e:
                self.tracker.log(f"Loi descriptions: {e}", "warn")

        # Next sang Budget — 2FA hay nhay ra
        check_all()
        click_text("Next")
        time.sleep(10)
        check_all()

        # Sau 2FA co the reset trang — retry
        for retry_after_11 in range(3):
            on_budget = on_page_with_text("Set custom budget")
            on_publish = False
            for b in visible_els("//button | //material-button"):
                try:
                    if "Publish campaign" in b.text:
                        on_publish = True
                        break
                except Exception:
                    pass
            on_keywords = on_page_with_text("Final URL") or on_page_with_text("Headlines")

            if on_budget:
                self.tracker.log("Dang o Budget", "warn")
                break
            elif on_publish:
                self.tracker.log("Da o Review — skip Budget")
                break
            elif on_keywords:
                self.tracker.log(f"Van o Keywords (2FA reset?) — Next lai ({retry_after_11+1})", "warn")
                click_text("Next")
                time.sleep(10)
                check_all()
                continue
            else:
                click_text("Next")
                time.sleep(8)
                check_all()
                break

        # === BUOC 12: Budget ===
        self.tracker.set_current(step="Buoc 12: Budget")
        check_all()
        time.sleep(3)
        budget = campaign_config.get("budget", "5")

        # Click radio "Set custom budget"
        click_radio_with_text("Set custom budget")
        time.sleep(2)

        # Dien budget — thu nhieu label phong khi Google doi
        ok = fill_input_near("Budget", budget) or \
             fill_input_near("budget amount", budget) or \
             fill_input_near("Enter amount", budget) or \
             fill_input_near("amount", budget)
        if not ok:
            self.tracker.log("Khong tim budget input bang text — fallback aria-label", "warn")
            for inp in visible_els(
                "//input[contains(@aria-label, 'budget') or contains(@aria-label, 'Budget') or contains(@aria-label, 'amount')]"
            ):
                _fill_element(inp, budget)
                ok = True
                break
        if ok:
            self.tracker.log(f"Da dien budget: ${budget}", "success")

        # Verify
        for verify_try in range(3):
            try:
                bi = None
                for inp in visible_els(
                    "//input[contains(@aria-label, 'budget') or contains(@aria-label, 'Budget') or contains(@aria-label, 'amount')]"
                ):
                    bi = inp
                    break
                if bi is None:
                    break
                val = (bi.get_attribute("value") or "").strip()
                if val == str(budget) or val.replace(",", "").replace(".00", "") == str(budget):
                    self.tracker.log(f"Budget verified: {val}", "success")
                    break
                self.tracker.log(f"Budget sai ({val} != {budget}) — dien lai ({verify_try+1})", "warn")
                _fill_element(bi, budget)
                time.sleep(1)
            except Exception:
                break

        check_all()
        click_text("Next")
        time.sleep(8)
        check_all()

        # === BUOC 13: Publish ===
        self.tracker.set_current(step="Buoc 13: Publish")

        for wait_round in range(12):
            check_all()
            check_login()

            found = False
            for b in visible_els("//button | //material-button"):
                try:
                    if "Publish campaign" in b.text:
                        if (b.get_attribute("aria-disabled") or "").lower() != "true" and b.is_enabled():
                            found = True
                            break
                except Exception:
                    pass
            if found:
                break

            # 2FA reset — dua ve trang truoc
            on_budget = on_page_with_text("Set custom budget")
            on_keywords = on_page_with_text("Final URL") or on_page_with_text("Headlines")
            on_settings = on_page_with_text("Search Partners") or on_page_with_text("Display Network")

            if on_budget:
                self.tracker.log("Dang o Budget — check + Next...")
                fill_input_near("Budget", budget)
                click_text("Next")
                time.sleep(8)
                check_all()
                continue
            elif on_keywords:
                self.tracker.log("Dang o Keywords/Ads — Next...")
                click_text("Next")
                time.sleep(10)
                check_all()
                continue
            elif on_settings:
                self.tracker.log("Dang o Settings — Next...")
                click_text("Next")
                time.sleep(10)
                check_all()
                continue

            self.tracker.log(f"Doi Publish... ({(wait_round+1)*5}s)")
            time.sleep(5)

        # Click Publish — retry xu ly Fix errors dialog
        for attempt in range(5):
            check_all()
            pub_clicked = False
            for b in visible_els("//button | //material-button"):
                try:
                    if "Publish campaign" not in b.text:
                        continue
                    if (b.get_attribute("aria-disabled") or "").lower() == "true" or not b.is_enabled():
                        self.tracker.log(f"Publish disabled — skip (lan {attempt+1})", "warn")
                        continue
                    d.execute_script("arguments[0].scrollIntoView({block:'center'})", b)
                    time.sleep(1)
                    action_click(b)
                    self.tracker.log(f"Da click Publish! (lan {attempt+1})", "success")
                    pub_clicked = True
                    time.sleep(10)
                    break
                except Exception:
                    pass
            if not pub_clicked:
                click_text("Next")
                time.sleep(10)
            check_all()
            if "New campaign" not in d.title and "Search campaign" not in d.title:
                break
            self.tracker.log(f"Van o Review (lan {attempt+1})", "warn")
            time.sleep(5)

        # === SAU PUBLISH: Policy Review + Google Tag ===
        time.sleep(5)
        check_all()

        # Policy Review: "Your campaign is published, but it can't run yet" -> Next
        for _ in range(3):
            if "policy" in d.current_url.lower() or on_page_with_text("can't run yet"):
                self.tracker.log("Trang Policy Review — an Next")
                click_text("Next")
                time.sleep(5)
                check_all()
            else:
                break

        # Google Tag — dong X (icon khong co text, dung aria-label='Close')
        time.sleep(3)
        if not close_X_near_text("Google tag"):
            if not close_X_near_text("Install Google tag"):
                # Fallback: bat ky nut Close nao dang hien
                for el in visible_els("//material-button[@aria-label='Close']"):
                    safe_click(el)
                    self.tracker.log("Da dong Google Tag (fallback)")
                    time.sleep(3)
                    break

        # Popup Campaign created
        try:
            for dlg in visible_els("//material-dialog"):
                dlg_text = dlg.text.lower()
                if "campaign created" in dlg_text or "what's next" in dlg_text or "congratulations" in dlg_text:
                    # Uu tien Done
                    done_clicked = False
                    for b in dlg.find_elements(By.XPATH, ".//button | .//material-button"):
                        try:
                            if b.is_displayed() and b.text.strip() == "Done":
                                safe_click(b)
                                self.tracker.log("Da dong popup Campaign created")
                                time.sleep(2)
                                done_clicked = True
                                break
                        except Exception:
                            pass
                    if not done_clicked:
                        close_X_near_text("Campaign created")
                    break
        except Exception:
            pass

        # ==================== VERIFY PUBLISH ====================
        time.sleep(3)
        cur_url = d.current_url.lower()
        cur_title = (d.title or "").lower()
        publish_ok = False

        if "/aw/campaigns" in cur_url and "/new" not in cur_url:
            publish_ok = True
        elif "published" in cur_title or "policy" in cur_url or "signup/tagging" in cur_url:
            publish_ok = True
        else:
            try:
                src = (d.page_source[:8000] or "").lower()
                if "campaign created" in src or "campaign is published" in src:
                    publish_ok = True
            except Exception:
                pass

        if publish_ok:
            upsert_campaign(self.customer_id, name, status="published")
            self.tracker.log(f"Campaign '{name}' da publish thanh cong!", "success")
            return True
        else:
            self.tracker.log(
                f"Publish KHONG xac nhan (URL: {d.current_url[:120]}, title: {d.title[:80]})",
                "error",
            )
            upsert_campaign(self.customer_id, name, status="failed",
                            notes="Publish clicked but success not verified")
            return False
