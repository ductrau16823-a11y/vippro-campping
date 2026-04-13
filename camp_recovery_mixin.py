"""
RecoveryMixin: Xu ly loi 404, butterbar error, retry logic.
"""

import time

from camp_selectors import (
    DELAY_PAGE_TRANSITION,
    TIMEOUT_SHORT,
    ADS_HOME_URL,
    ADS_CAMPAIGNS_URL_TEMPLATE,
    SEL_BUTTERBAR_ERROR,
    SEL_BUTTERBAR_TEXT,
    SEL_LOADING_SPINNER,
)
from selenium_helpers import find_element_safe


class RecoveryMixin:
    """Xu ly loi va recovery cho campaign automation."""

    def check_and_handle_error(self):
        """Kiem tra co loi butterbar khong, return error text hoac None."""
        error_bar = find_element_safe(
            self.driver, SEL_BUTTERBAR_ERROR, timeout=2, required=False
        )
        if error_bar:
            try:
                text_el = find_element_safe(
                    self.driver, SEL_BUTTERBAR_TEXT, timeout=2, required=False
                )
                error_text = text_el.text if text_el else "Unknown error"
            except Exception:
                error_text = "Unknown butterbar error"
            self.tracker.log(f"Butterbar error: {error_text}", "error")
            return error_text
        return None

    def wait_loading_done(self, timeout=30):
        """Cho loading spinner bien mat."""
        start = time.time()
        while time.time() - start < timeout:
            spinner = find_element_safe(
                self.driver, SEL_LOADING_SPINNER, timeout=1, required=False
            )
            if not spinner:
                return True
            time.sleep(1)
        self.tracker.log("Loading qua lau, tiep tuc...", "warn")
        return False

    def recover_404(self, customer_id):
        """Xu ly 404: reload 2 lan truoc, navigate full neu van loi.

        Args:
            customer_id: Ads account ID
        """
        # Reload 2 lan truoc
        for attempt in range(2):
            self.tracker.log(f"404 recovery: reload lan {attempt + 1}")
            self.driver.refresh()
            time.sleep(DELAY_PAGE_TRANSITION)

            if not self._is_404():
                self.tracker.log("Recovery thanh cong sau reload!", "success")
                return True

        # Navigate full
        self.tracker.log("Reload khong duoc, navigate full...", "warn")
        clean_id = customer_id.replace("-", "")
        url = ADS_CAMPAIGNS_URL_TEMPLATE.format(customer_id=clean_id)
        self.driver.get(url)
        time.sleep(DELAY_PAGE_TRANSITION)

        if self._is_404():
            self.tracker.log(f"Van 404 sau navigate full! TK {customer_id} co van de.", "error")
            return False

        self.tracker.log("Recovery thanh cong sau navigate full!", "success")
        return True

    def _is_404(self):
        """Check trang hien tai co phai 404 khong."""
        try:
            title = self.driver.title.lower()
            source = self.driver.page_source[:2000].lower()
            return "404" in title or "not found" in source
        except Exception:
            return False
