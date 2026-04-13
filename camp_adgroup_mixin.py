"""
AdGroupMixin: Tao ad group + them keywords.
"""

import time

from camp_selectors import (
    TIMEOUT_MEDIUM,
    DELAY_BETWEEN_STEPS,
    SEL_ADGROUP_NAME_INPUT,
    SEL_KEYWORD_INPUT,
    SEL_ADD_KEYWORDS_BTN,
    SEL_NEXT_BTN,
)
from selenium_helpers import (
    click_element_safe,
    type_into_element,
    find_element_safe,
)


class AdGroupMixin:
    """Tao ad group va them keywords."""

    def fill_adgroup_name(self, name):
        """Dien ten ad group.

        Args:
            name: Ten ad group (vd: 'Ad Group 1')
        """
        self.tracker.set_current(step=f"Dien ten ad group: {name}")
        type_into_element(self.driver, SEL_ADGROUP_NAME_INPUT, name, timeout=TIMEOUT_MEDIUM)
        time.sleep(DELAY_BETWEEN_STEPS)
        self.tracker.log(f"Da dien ten ad group: {name}")

    def fill_keywords(self, keywords):
        """Them keywords vao ad group.

        Args:
            keywords: list of str (vd: ['mua hang online', 'giam gia'])
                      hoac str (moi keyword 1 dong)
        """
        self.tracker.set_current(step="Them keywords")

        if isinstance(keywords, list):
            keyword_text = "\n".join(keywords)
        else:
            keyword_text = str(keywords)

        type_into_element(self.driver, SEL_KEYWORD_INPUT, keyword_text, timeout=TIMEOUT_MEDIUM)
        time.sleep(DELAY_BETWEEN_STEPS)

        # Click "Add keywords" neu co
        add_btn = click_element_safe(self.driver, SEL_ADD_KEYWORDS_BTN, timeout=5, required=False)

        self.tracker.log(f"Da them {len(keywords) if isinstance(keywords, list) else '?'} keywords", "success")

    def click_next_adgroup(self):
        """Click Next sau khi xong ad group."""
        click_element_safe(self.driver, SEL_NEXT_BTN, timeout=TIMEOUT_MEDIUM)
        time.sleep(DELAY_BETWEEN_STEPS)
