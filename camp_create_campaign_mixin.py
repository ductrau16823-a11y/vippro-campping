"""
CreateCampaignMixin: Tao campaign moi (chon goal, type, settings).
Updated 2026-04: Google Ads dung unified-goals-card, can JS click qua parent card.
"""

import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from camp_selectors import (
    TIMEOUT_MEDIUM,
    TIMEOUT_LONG,
    DELAY_BETWEEN_STEPS,
    DELAY_PAGE_TRANSITION,
    ADS_NEW_CAMPAIGN_URL_TEMPLATE,
    SEL_NEW_CAMPAIGN_BTN,
    SEL_NEW_CAMPAIGN_PLUS,
    SEL_GOAL_SALES,
    SEL_GOAL_LEADS,
    SEL_GOAL_TRAFFIC,
    SEL_GOAL_WITHOUT,
    SEL_TYPE_SEARCH,
    SEL_TYPE_DISPLAY,
    SEL_TYPE_VIDEO,
    SEL_TYPE_SHOPPING,
    SEL_TYPE_APP,
    SEL_TYPE_PERFORMANCE_MAX,
    SEL_TYPE_DEMAND_GEN,
    SEL_CONTINUE_BTN,
    SEL_NEXT_BTN,
)
from selenium_helpers import click_element_safe, find_element_safe


# Map goal name -> selector
GOAL_MAP = {
    "sales": SEL_GOAL_SALES,
    "leads": SEL_GOAL_LEADS,
    "traffic": SEL_GOAL_TRAFFIC,
    "without_goal": SEL_GOAL_WITHOUT,
}

# Map campaign type -> selector
TYPE_MAP = {
    "search": SEL_TYPE_SEARCH,
    "display": SEL_TYPE_DISPLAY,
    "video": SEL_TYPE_VIDEO,
    "shopping": SEL_TYPE_SHOPPING,
    "app": SEL_TYPE_APP,
    "performance_max": SEL_TYPE_PERFORMANCE_MAX,
    "demand_gen": SEL_TYPE_DEMAND_GEN,
}


def _click_card(driver, selector, timeout=15):
    """Click vao Google Ads card (unified-goals-card).
    Span text bi che boi parent -> tim parent card roi JS click.
    """
    method, value = selector
    el = WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.XPATH if method == "xpath" else By.CSS_SELECTOR, value))
    )
    # Tim parent card
    try:
        parent = el.find_element(By.XPATH, './ancestor::div[contains(@class, "unified-goals-card-format")]')
        driver.execute_script("arguments[0].click()", parent)
    except Exception:
        # Fallback: JS click truc tiep
        driver.execute_script("arguments[0].click()", el)


def _click_button(driver, text, timeout=15):
    """Click button theo text (Continue, Next...)."""
    el = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.XPATH, f'//button[contains(text(), "{text}")]'))
    )
    driver.execute_script("arguments[0].click()", el)


class CreateCampaignMixin:
    """Tao campaign moi trong Google Ads."""

    def start_new_campaign(self, customer_id):
        """Click nut 'New campaign' tren trang hien tai.
        Neu khong tim thay nut, click link 'New campaign' trong menu + tren trang.
        KHONG navigate URL moi (de tranh bi redirect login).
        """
        self.tracker.set_current(step="Bat dau tao campaign moi")

        # Thu click nut "New campaign" / "+" / link
        btn = click_element_safe(self.driver, SEL_NEW_CAMPAIGN_BTN, timeout=5, required=False)
        if not btn:
            btn = click_element_safe(self.driver, SEL_NEW_CAMPAIGN_PLUS, timeout=5, required=False)
        if not btn:
            # Thu tim link/button co text "New campaign"
            try:
                els = self.driver.find_elements(By.XPATH, '//*[contains(text(), "New campaign") or contains(text(), "new campaign")]')
                for el in els:
                    if el.is_displayed():
                        self.driver.execute_script("arguments[0].click()", el)
                        btn = True
                        break
            except Exception:
                pass
        if not btn:
            # Cuoi cung: them /new vao URL hien tai (giu session)
            current = self.driver.current_url
            if "/aw/campaigns" in current and "/new" not in current:
                new_url = current.split("?")[0] + "/new?" + current.split("?")[1] if "?" in current else current + "/new"
                self.driver.get(new_url)
                time.sleep(DELAY_PAGE_TRANSITION)

        time.sleep(DELAY_BETWEEN_STEPS)
        self.tracker.log("Da vao trang tao campaign moi")

    def select_campaign_goal(self, goal="traffic"):
        """Chon muc tieu campaign."""
        self.tracker.set_current(step=f"Chon goal: {goal}")

        selector = GOAL_MAP.get(goal.lower(), SEL_GOAL_TRAFFIC)
        _click_card(self.driver, selector, timeout=TIMEOUT_MEDIUM)
        time.sleep(DELAY_BETWEEN_STEPS)

        _click_button(self.driver, "Continue", timeout=TIMEOUT_MEDIUM)
        time.sleep(DELAY_BETWEEN_STEPS)

        self.tracker.log(f"Da chon goal: {goal}", "success")

    def select_campaign_type(self, campaign_type="search"):
        """Chon loai campaign."""
        self.tracker.set_current(step=f"Chon type: {campaign_type}")

        selector = TYPE_MAP.get(campaign_type.lower(), SEL_TYPE_SEARCH)
        _click_card(self.driver, selector, timeout=TIMEOUT_MEDIUM)
        time.sleep(DELAY_BETWEEN_STEPS)

        _click_button(self.driver, "Continue", timeout=TIMEOUT_MEDIUM)
        time.sleep(DELAY_BETWEEN_STEPS)

        self.tracker.log(f"Da chon type: {campaign_type}", "success")

    def click_next(self):
        """Click nut Next de chuyen sang buoc tiep."""
        try:
            _click_button(self.driver, "Next", timeout=TIMEOUT_MEDIUM)
        except Exception:
            click_element_safe(self.driver, SEL_NEXT_BTN, timeout=TIMEOUT_MEDIUM)
        time.sleep(DELAY_BETWEEN_STEPS)
