"""
CreateCampaignMixin: Tao campaign moi (chon goal, type, settings).
"""

import time

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
    SEL_TYPE_PERFORMANCE_MAX,
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
    "performance_max": SEL_TYPE_PERFORMANCE_MAX,
}


class CreateCampaignMixin:
    """Tao campaign moi trong Google Ads."""

    def start_new_campaign(self, customer_id):
        """Click nut 'New campaign' hoac navigate truc tiep.

        Args:
            customer_id: Ads account ID (da clean, khong co dau '-')
        """
        self.tracker.set_current(step="Bat dau tao campaign moi")

        # Thu click nut "New campaign" truoc
        btn = click_element_safe(self.driver, SEL_NEW_CAMPAIGN_BTN, timeout=5, required=False)
        if not btn:
            btn = click_element_safe(self.driver, SEL_NEW_CAMPAIGN_PLUS, timeout=5, required=False)

        if not btn:
            # Fallback: navigate truc tiep
            clean_id = customer_id.replace("-", "")
            url = ADS_NEW_CAMPAIGN_URL_TEMPLATE.format(customer_id=clean_id)
            self.driver.get(url)
            time.sleep(DELAY_PAGE_TRANSITION)

        time.sleep(DELAY_BETWEEN_STEPS)
        self.tracker.log("Da vao trang tao campaign moi")

    def select_campaign_goal(self, goal="traffic"):
        """Chon muc tieu campaign.

        Args:
            goal: 'sales' | 'leads' | 'traffic' | 'without_goal'
        """
        self.tracker.set_current(step=f"Chon goal: {goal}")

        selector = GOAL_MAP.get(goal.lower(), SEL_GOAL_TRAFFIC)
        click_element_safe(self.driver, selector, timeout=TIMEOUT_MEDIUM)
        time.sleep(DELAY_BETWEEN_STEPS)

        # Click Continue
        click_element_safe(self.driver, SEL_CONTINUE_BTN, timeout=TIMEOUT_MEDIUM)
        time.sleep(DELAY_BETWEEN_STEPS)

        self.tracker.log(f"Da chon goal: {goal}", "success")

    def select_campaign_type(self, campaign_type="search"):
        """Chon loai campaign.

        Args:
            campaign_type: 'search' | 'display' | 'performance_max'
        """
        self.tracker.set_current(step=f"Chon type: {campaign_type}")

        selector = TYPE_MAP.get(campaign_type.lower(), SEL_TYPE_SEARCH)
        click_element_safe(self.driver, selector, timeout=TIMEOUT_MEDIUM)
        time.sleep(DELAY_BETWEEN_STEPS)

        # Click Continue
        click_element_safe(self.driver, SEL_CONTINUE_BTN, timeout=TIMEOUT_MEDIUM)
        time.sleep(DELAY_BETWEEN_STEPS)

        self.tracker.log(f"Da chon type: {campaign_type}", "success")

    def click_next(self):
        """Click nut Next de chuyen sang buoc tiep."""
        click_element_safe(self.driver, SEL_NEXT_BTN, timeout=TIMEOUT_MEDIUM)
        time.sleep(DELAY_BETWEEN_STEPS)
