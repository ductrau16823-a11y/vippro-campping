"""
NavigationMixin: Mo tab GenLogin, login Google, navigate vao dung TK Ads.
"""

import time

from camp_selectors import (
    ADS_HOME_URL,
    ADS_CAMPAIGNS_URL_TEMPLATE,
    TIMEOUT_LONG,
    TIMEOUT_PAGE_LOAD,
    DELAY_PAGE_TRANSITION,
    SEL_ACCOUNT_LIST_ITEM,
    SEL_ACCOUNT_ID,
)
from selenium_helpers import find_element_safe, click_element_safe


class NavigationMixin:
    """Navigate vao TK Ads can camp."""

    def navigate_to_ads_account(self, customer_id):
        """Navigate truc tiep vao TK Ads bang customer_id (XXX-XXX-XXXX).

        Args:
            customer_id: Ads account ID dang 'XXX-XXX-XXXX' hoac '1234567890'
        """
        # Xoa dau '-' neu co
        clean_id = customer_id.replace("-", "")
        url = ADS_CAMPAIGNS_URL_TEMPLATE.format(customer_id=clean_id)

        self.tracker.log(f"Navigate vao TK Ads: {customer_id}")
        self.tracker.set_current(account=customer_id, step="Navigate to Ads account")

        self.driver.get(url)
        time.sleep(DELAY_PAGE_TRANSITION)

        # Check 404
        if self._check_404():
            self.tracker.log(f"404 khi vao TK {customer_id}, thu reload...", "warn")
            self._handle_404_recovery(customer_id)

        self.tracker.log(f"Da vao TK Ads: {customer_id}", "success")

    def navigate_to_ads_home(self):
        """Navigate ve trang chu Google Ads."""
        self.driver.get(ADS_HOME_URL)
        time.sleep(DELAY_PAGE_TRANSITION)

    def _check_404(self):
        """Kiem tra trang hien tai co phai 404 khong."""
        try:
            page_source = self.driver.page_source[:2000].lower()
            if "404" in self.driver.title.lower() or "not found" in page_source:
                return True
        except Exception:
            pass
        return False

    def _handle_404_recovery(self, customer_id):
        """Xu ly 404: reload 2 lan truoc, navigate full neu van loi."""
        for attempt in range(2):
            self.tracker.log(f"Reload lan {attempt + 1}...")
            self.driver.refresh()
            time.sleep(DELAY_PAGE_TRANSITION)
            if not self._check_404():
                return

        # Reload khong duoc -> navigate full
        self.tracker.log("Reload khong duoc, navigate full...", "warn")
        clean_id = customer_id.replace("-", "")
        url = ADS_CAMPAIGNS_URL_TEMPLATE.format(customer_id=clean_id)
        self.driver.get(url)
        time.sleep(DELAY_PAGE_TRANSITION)
