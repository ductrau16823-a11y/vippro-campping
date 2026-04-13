"""
BudgetMixin: Set budget va bidding strategy.
"""

import time

from camp_selectors import (
    TIMEOUT_MEDIUM,
    DELAY_BETWEEN_STEPS,
    SEL_BUDGET_INPUT,
    SEL_BIDDING_STRATEGY_DROPDOWN,
    SEL_BIDDING_MAXIMIZE_CLICKS,
    SEL_BIDDING_MAXIMIZE_CONVERSIONS,
    SEL_NEXT_BTN,
    SEL_PUBLISH_BTN,
)
from selenium_helpers import (
    click_element_safe,
    type_into_element,
    find_element_safe,
)


BIDDING_MAP = {
    "maximize_clicks": SEL_BIDDING_MAXIMIZE_CLICKS,
    "maximize_conversions": SEL_BIDDING_MAXIMIZE_CONVERSIONS,
}


class BudgetMixin:
    """Set budget va bidding strategy cho campaign."""

    def fill_budget(self, amount):
        """Dien budget hang ngay.

        Args:
            amount: So tien (vd: '50000' hoac 50000)
        """
        self.tracker.set_current(step=f"Set budget: {amount}")
        type_into_element(
            self.driver, SEL_BUDGET_INPUT, str(amount), timeout=TIMEOUT_MEDIUM
        )
        time.sleep(DELAY_BETWEEN_STEPS)
        self.tracker.log(f"Da set budget: {amount}")

    def select_bidding_strategy(self, strategy="maximize_clicks"):
        """Chon bidding strategy.

        Args:
            strategy: 'maximize_clicks' | 'maximize_conversions'
        """
        self.tracker.set_current(step=f"Chon bidding: {strategy}")

        # Click dropdown bidding
        click_element_safe(self.driver, SEL_BIDDING_STRATEGY_DROPDOWN, timeout=TIMEOUT_MEDIUM)
        time.sleep(1)

        # Chon strategy
        selector = BIDDING_MAP.get(strategy.lower(), SEL_BIDDING_MAXIMIZE_CLICKS)
        click_element_safe(self.driver, selector, timeout=TIMEOUT_MEDIUM)
        time.sleep(DELAY_BETWEEN_STEPS)

        self.tracker.log(f"Da chon bidding: {strategy}", "success")

    def click_next_budget(self):
        """Click Next sau khi xong budget."""
        click_element_safe(self.driver, SEL_NEXT_BTN, timeout=TIMEOUT_MEDIUM)
        time.sleep(DELAY_BETWEEN_STEPS)

    def publish_campaign(self):
        """Click Publish de dang campaign."""
        self.tracker.set_current(step="Publish campaign")
        click_element_safe(self.driver, SEL_PUBLISH_BTN, timeout=TIMEOUT_MEDIUM)
        time.sleep(DELAY_BETWEEN_STEPS)
        self.tracker.log("Da click Publish campaign!", "success")
