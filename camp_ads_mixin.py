"""
AdsMixin: Tao responsive search ads (headlines, descriptions, final URL).
"""

import time

from camp_selectors import (
    TIMEOUT_MEDIUM,
    DELAY_BETWEEN_STEPS,
    SEL_FINAL_URL_INPUT,
    SEL_HEADLINE_INPUT,
    SEL_DESCRIPTION_INPUT,
    SEL_ADD_HEADLINE_BTN,
    SEL_ADD_DESCRIPTION_BTN,
    SEL_NEXT_BTN,
)
from selenium_helpers import (
    click_element_safe,
    type_into_element,
    find_element_safe,
)

from selenium.webdriver.common.by import By


class AdsMixin:
    """Tao responsive search ads."""

    def fill_final_url(self, url):
        """Dien Final URL.

        Args:
            url: URL trang dich (vd: 'https://example.com')
        """
        self.tracker.set_current(step="Dien Final URL")
        type_into_element(self.driver, SEL_FINAL_URL_INPUT, url, timeout=TIMEOUT_MEDIUM)
        time.sleep(DELAY_BETWEEN_STEPS)
        self.tracker.log(f"Da dien Final URL: {url}")

    def fill_headlines(self, headlines):
        """Dien cac headline cho responsive search ad.

        Args:
            headlines: list of str (toi thieu 3, toi da 15 headlines)
        """
        self.tracker.set_current(step="Dien headlines")

        # Tim tat ca headline inputs hien tai
        headline_inputs = self.driver.find_elements(By.XPATH, SEL_HEADLINE_INPUT[1])

        for i, headline in enumerate(headlines):
            if i < len(headline_inputs):
                # Dien vao input co san
                try:
                    headline_inputs[i].clear()
                    headline_inputs[i].send_keys(headline)
                    time.sleep(0.5)
                except Exception as e:
                    self.tracker.log(f"Loi dien headline {i+1}: {e}", "warn")
            else:
                # Can them headline input moi
                add_btn = click_element_safe(
                    self.driver, SEL_ADD_HEADLINE_BTN, timeout=5, required=False
                )
                if add_btn:
                    time.sleep(1)
                    # Tim lai inputs sau khi them
                    headline_inputs = self.driver.find_elements(By.XPATH, SEL_HEADLINE_INPUT[1])
                    if i < len(headline_inputs):
                        try:
                            headline_inputs[i].clear()
                            headline_inputs[i].send_keys(headline)
                            time.sleep(0.5)
                        except Exception:
                            pass

        self.tracker.log(f"Da dien {len(headlines)} headlines", "success")

    def fill_descriptions(self, descriptions):
        """Dien cac description cho responsive search ad.

        Args:
            descriptions: list of str (toi thieu 2, toi da 4 descriptions)
        """
        self.tracker.set_current(step="Dien descriptions")

        desc_inputs = self.driver.find_elements(By.XPATH, SEL_DESCRIPTION_INPUT[1])

        for i, desc in enumerate(descriptions):
            if i < len(desc_inputs):
                try:
                    desc_inputs[i].clear()
                    desc_inputs[i].send_keys(desc)
                    time.sleep(0.5)
                except Exception as e:
                    self.tracker.log(f"Loi dien description {i+1}: {e}", "warn")
            else:
                add_btn = click_element_safe(
                    self.driver, SEL_ADD_DESCRIPTION_BTN, timeout=5, required=False
                )
                if add_btn:
                    time.sleep(1)
                    desc_inputs = self.driver.find_elements(By.XPATH, SEL_DESCRIPTION_INPUT[1])
                    if i < len(desc_inputs):
                        try:
                            desc_inputs[i].clear()
                            desc_inputs[i].send_keys(desc)
                            time.sleep(0.5)
                        except Exception:
                            pass

        self.tracker.log(f"Da dien {len(descriptions)} descriptions", "success")

    def click_next_ads(self):
        """Click Next sau khi xong ads."""
        click_element_safe(self.driver, SEL_NEXT_BTN, timeout=TIMEOUT_MEDIUM)
        time.sleep(DELAY_BETWEEN_STEPS)
