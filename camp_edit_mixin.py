"""
EditCampaignMixin: Chinh sua demographics (age, gender) va devices sau khi Publish.

Flow:
  1. Dong trang Google Tag (X)
  2. Navigate vao Audiences -> chinh Age, Gender
  3. Navigate vao Devices (Insights > When and where ads showed) -> chinh Devices
  4. Tat ca dua tren DB config, khong co thi bo qua
"""

import time

from camp_selectors import (
    TIMEOUT_MEDIUM,
    TIMEOUT_LONG,
    SEL_CLOSE_GOOGLE_TAG,
    SEL_SIDEBAR_AUDIENCES,
    SEL_MODAL_CLOSE,
    SEL_DEMO_TAB_GENDER,
    SEL_DEMO_DATA_ROWS,
    SEL_DEMO_ROW_TEXT,
    SEL_DEMO_ROW_STATUS_ENABLED,
    SEL_DEMO_ROW_CHECKBOX,
    SEL_DEMO_EDIT_DROPDOWN,
    SEL_SIDEBAR_INSIGHTS,
    SEL_SIDEBAR_DEVICES,
    SEL_DEVICE_DATA_ROWS,
    SEL_DEVICE_ROW_TEXT,
    SEL_DEVICE_ROW_CHECKBOX,
    SEL_DEVICE_EDIT_DROPDOWN,
)
from selenium_helpers import (
    find_element_safe,
    click_element_safe,
    _by,
    _scroll_into_view_center,
    human_click,
)


# Mapping DB values -> UI text
AGE_DB_TO_UI = {
    "18-24": "18 - 24",
    "25-34": "25 - 34",
    "35-44": "35 - 44",
    "45-54": "45 - 54",
    "55-64": "55 - 64",
    "65+": "65+",
    "unknown": "Unknown",
}

GENDER_DB_TO_UI = {
    "male": "Male",
    "female": "Female",
    "unknown": "Unknown",
}

DEVICE_DB_TO_UI = {
    "computers": "Computers",
    "mobile": "Mobile phones",
    "tablets": "Tablets",
}


class EditCampaignMixin:
    """Chinh sua demographics cho campaign da publish."""

    def edit_campaign_demographics(self, campaign_config):
        """Dieu phoi chinh sua demographics + devices sau khi publish.

        Args:
            campaign_config: dict chua 'ageRanges', 'genders', 'devices' (optional)

        Return: True neu thanh cong hoac khong can chinh, False neu loi
        """
        age_ranges = campaign_config.get("ageRanges", [])
        genders = campaign_config.get("genders", [])
        devices = campaign_config.get("devices", [])

        if not age_ranges and not genders and not devices:
            self.tracker.log("Khong co config demographics/devices trong DB, bo qua")
            return True

        self.tracker.log("=== Bat dau chinh sua campaign sau publish ===")

        try:
            # 1. Dong trang Google Tag
            self._close_google_tag_page()

            # 2. Chinh Demographics (Age, Gender)
            if age_ranges or genders:
                self._navigate_to_audiences()
                self._close_audience_modal()

                if age_ranges:
                    self.tracker.log(f"Chinh Age: giu {age_ranges}")
                    self._edit_demographic_tab("age", age_ranges, AGE_DB_TO_UI)
                else:
                    self.tracker.log("Khong co ageRanges trong DB, bo qua Age")

                if genders:
                    self.tracker.log(f"Chinh Gender: giu {genders}")
                    self._click_gender_tab()
                    time.sleep(DELAY_BETWEEN_STEPS)
                    self._edit_demographic_tab("gender", genders, GENDER_DB_TO_UI)
                else:
                    self.tracker.log("Khong co genders trong DB, bo qua Gender")

            # 3. Chinh Devices
            if devices:
                self.tracker.log(f"Chinh Devices: giu {devices}")
                self._navigate_to_devices()
                self._edit_devices(devices)
            else:
                self.tracker.log("Khong co devices trong DB, bo qua Devices")

            self.tracker.log("=== Chinh sua campaign sau publish hoan tat ===", "success")
            return True

        except Exception as e:
            self.tracker.log(f"Loi chinh sua campaign: {e}", "error")
            return False

    def _close_google_tag_page(self):
        """Dong trang 'Set up with a Google Tag' bang nut X."""
        self.tracker.set_current(step="Dong trang Google Tag")
        try:
            close_btn = find_element_safe(
                self.driver, SEL_CLOSE_GOOGLE_TAG, timeout=TIMEOUT_MEDIUM, required=False
            )
            if close_btn:
                _scroll_into_view_center(self.driver, close_btn)
                time.sleep(0.5)
                if not human_click(self.driver, close_btn):
                    close_btn.click()
                time.sleep(5)  # Cho trang load lai sau khi dong Google Tag
                self.tracker.log("Da dong trang Google Tag")
            else:
                self.tracker.log("Khong thay trang Google Tag, bo qua")
        except Exception:
            self.tracker.log("Khong dong duoc trang Google Tag, bo qua", "warn")

    def _navigate_to_audiences(self):
        """Click vao Audiences trong sidebar."""
        self.tracker.set_current(step="Navigate to Audiences")
        click_element_safe(self.driver, SEL_SIDEBAR_AUDIENCES, timeout=TIMEOUT_LONG)
        time.sleep(5)  # Cho trang Audiences load day du
        self.tracker.log("Da vao trang Audiences")

    def _close_audience_modal(self):
        """Dong modal 'Unified audience reporting' neu xuat hien."""
        try:
            modal_close = find_element_safe(
                self.driver, SEL_MODAL_CLOSE, timeout=TIMEOUT_MEDIUM, required=False
            )
            if modal_close:
                _scroll_into_view_center(self.driver, modal_close)
                time.sleep(0.5)
                if not human_click(self.driver, modal_close):
                    modal_close.click()
                time.sleep(3)  # Cho modal dong va trang load lai
                self.tracker.log("Da dong modal Unified audience reporting")
        except Exception:
            pass

    def _click_gender_tab(self):
        """Click tab Gender trong Demographics section."""
        self.tracker.set_current(step="Click tab Gender")
        click_element_safe(self.driver, SEL_DEMO_TAB_GENDER, timeout=TIMEOUT_MEDIUM)
        time.sleep(5)  # Cho tab Gender load data
        self.tracker.log("Da chuyen sang tab Gender")

    def _edit_demographic_tab(self, tab_name, db_values, db_to_ui_map):
        """Chinh sua 1 tab demographics (Age hoac Gender).

        Logic:
          - Doc tung row trong bang
          - Row nao KHONG CO trong DB va dang Enabled -> tick checkbox de exclude
          - Sau khi tick het -> click Edit dropdown -> Exclude from ad group

        Args:
            tab_name: "age" hoac "gender" (de log)
            db_values: list values tu DB (vd: ["18-24", "25-34"])
            db_to_ui_map: dict mapping DB value -> UI text
        """
        self.tracker.set_current(step=f"Edit {tab_name} demographics")

        # Convert DB values sang UI text
        ui_keep_values = set()
        for val in db_values:
            ui_text = db_to_ui_map.get(val.lower().strip())
            if ui_text:
                ui_keep_values.add(ui_text)
            else:
                self.tracker.log(f"Khong map duoc DB value '{val}' sang UI text", "warn")

        self.tracker.log(f"Giu lai tren UI: {ui_keep_values}")

        # Tim tat ca data rows trong bang
        try:
            rows = self.driver.find_elements(
                _by(SEL_DEMO_DATA_ROWS[0]), SEL_DEMO_DATA_ROWS[1]
            )
        except Exception:
            self.tracker.log(f"Khong tim thay rows trong bang {tab_name}", "error")
            return

        self.tracker.log(f"Tim thay {len(rows)} rows trong tab {tab_name}")

        # Tim rows can exclude
        rows_to_exclude = []
        for row in rows:
            try:
                # Lay text (age range / gender)
                text_el = row.find_element(_by(SEL_DEMO_ROW_TEXT[0]), SEL_DEMO_ROW_TEXT[1])
                row_text = text_el.text.strip()

                if not row_text:
                    continue

                # Check status hien tai
                is_enabled = False
                try:
                    status_el = row.find_element(
                        _by(SEL_DEMO_ROW_STATUS_ENABLED[0]),
                        SEL_DEMO_ROW_STATUS_ENABLED[1],
                    )
                    if status_el:
                        is_enabled = True
                except Exception:
                    is_enabled = False

                # Neu KHONG co trong DB va dang Enabled -> can exclude
                if row_text not in ui_keep_values and is_enabled:
                    rows_to_exclude.append((row, row_text))
                    self.tracker.log(f"  -> Can exclude: {row_text}")
                else:
                    if row_text in ui_keep_values:
                        self.tracker.log(f"  -> Giu: {row_text}")
                    else:
                        self.tracker.log(f"  -> Da excluded: {row_text}")

            except Exception as e:
                self.tracker.log(f"Loi doc row: {e}", "warn")
                continue

        if not rows_to_exclude:
            self.tracker.log(f"Khong co row nao can exclude trong tab {tab_name}")
            return

        # Tick checkbox cac rows can exclude
        self.tracker.log(f"Tick checkbox {len(rows_to_exclude)} rows...")
        for row, row_text in rows_to_exclude:
            try:
                checkbox = row.find_element(
                    _by(SEL_DEMO_ROW_CHECKBOX[0]), SEL_DEMO_ROW_CHECKBOX[1]
                )
                _scroll_into_view_center(self.driver, checkbox)
                time.sleep(0.5)
                if not human_click(self.driver, checkbox):
                    checkbox.click()
                time.sleep(1)  # Cho UI cap nhat sau moi tick
                self.tracker.log(f"  Ticked: {row_text}")
            except Exception as e:
                self.tracker.log(f"  Loi tick checkbox '{row_text}': {e}", "error")

        time.sleep(5)  # Cho toolbar hien day du sau khi tick xong

        # Click Edit dropdown
        self.tracker.log("Click Edit dropdown...")
        try:
            edit_btn = find_element_safe(
                self.driver, SEL_DEMO_EDIT_DROPDOWN, timeout=TIMEOUT_MEDIUM
            )
            _scroll_into_view_center(self.driver, edit_btn)
            time.sleep(0.5)
            if not human_click(self.driver, edit_btn):
                edit_btn.click()
            time.sleep(5)  # Cho menu dropdown mo ra
        except Exception as e:
            self.tracker.log(f"Loi click Edit dropdown: {e}", "error")
            return

        # Click "Exclude from ad group" trong menu
        self.tracker.log("Chon 'Exclude from ad group'...")
        try:
            exclude_option = ("xpath",
                "//material-select-item[contains(., 'Exclude from ad group')]"
                " | //div[contains(@class, 'menu-item')][contains(., 'Exclude from ad group')]"
                " | //material-select-dropdown-item[contains(., 'Exclude')]"
            )
            click_element_safe(self.driver, exclude_option, timeout=TIMEOUT_MEDIUM)
            time.sleep(5)  # Cho exclude ap dung xong
            self.tracker.log(
                f"Da exclude {len(rows_to_exclude)} rows trong tab {tab_name}",
                "success",
            )
        except Exception as e:
            self.tracker.log(f"Loi chon Exclude: {e}", "error")

    def _navigate_to_devices(self):
        """Navigate vao Insights and reports > When and where ads showed (Devices)."""
        self.tracker.set_current(step="Navigate to Devices")

        # Mo "Insights and reports" truoc (neu chua mo)
        try:
            insights_panel = find_element_safe(
                self.driver, SEL_SIDEBAR_INSIGHTS, timeout=TIMEOUT_MEDIUM, required=False
            )
            if insights_panel:
                _scroll_into_view_center(self.driver, insights_panel)
                time.sleep(0.5)
                if not human_click(self.driver, insights_panel):
                    insights_panel.click()
                time.sleep(5)  # Cho sub-menu Insights mo ra
        except Exception:
            pass

        # Click "When and where ads showed"
        click_element_safe(self.driver, SEL_SIDEBAR_DEVICES, timeout=TIMEOUT_LONG)
        time.sleep(5)  # Cho trang Devices load day du
        self.tracker.log("Da vao trang Devices")

    def _edit_devices(self, db_devices):
        """Chinh sua devices: exclude nhung device khong co trong DB.

        Args:
            db_devices: list tu DB (vd: ["computers", "mobile"])
        """
        self.tracker.set_current(step="Edit devices")

        # Convert DB values sang UI text
        ui_keep_values = set()
        for val in db_devices:
            ui_text = DEVICE_DB_TO_UI.get(val.lower().strip())
            if ui_text:
                ui_keep_values.add(ui_text)
            else:
                self.tracker.log(f"Khong map duoc device '{val}' sang UI text", "warn")

        self.tracker.log(f"Devices giu lai: {ui_keep_values}")

        # Tim tat ca device rows
        try:
            rows = self.driver.find_elements(
                _by(SEL_DEVICE_DATA_ROWS[0]), SEL_DEVICE_DATA_ROWS[1]
            )
        except Exception:
            self.tracker.log("Khong tim thay rows trong bang Devices", "error")
            return

        self.tracker.log(f"Tim thay {len(rows)} device rows")

        # Tim rows can exclude
        rows_to_exclude = []
        for row in rows:
            try:
                text_el = row.find_element(
                    _by(SEL_DEVICE_ROW_TEXT[0]), SEL_DEVICE_ROW_TEXT[1]
                )
                row_text = text_el.text.strip()

                if not row_text:
                    continue

                if row_text not in ui_keep_values:
                    rows_to_exclude.append((row, row_text))
                    self.tracker.log(f"  -> Can exclude: {row_text}")
                else:
                    self.tracker.log(f"  -> Giu: {row_text}")

            except Exception as e:
                self.tracker.log(f"Loi doc device row: {e}", "warn")
                continue

        if not rows_to_exclude:
            self.tracker.log("Khong co device nao can exclude")
            return

        # Tick checkbox cac rows can exclude
        self.tracker.log(f"Tick checkbox {len(rows_to_exclude)} devices...")
        for row, row_text in rows_to_exclude:
            try:
                checkbox = row.find_element(
                    _by(SEL_DEVICE_ROW_CHECKBOX[0]), SEL_DEVICE_ROW_CHECKBOX[1]
                )
                _scroll_into_view_center(self.driver, checkbox)
                time.sleep(0.5)
                if not human_click(self.driver, checkbox):
                    checkbox.click()
                time.sleep(1)  # Cho UI cap nhat sau moi tick
                self.tracker.log(f"  Ticked: {row_text}")
            except Exception as e:
                self.tracker.log(f"  Loi tick checkbox '{row_text}': {e}", "error")

        time.sleep(5)  # Cho toolbar hien day du sau khi tick xong

        # Click Edit dropdown
        self.tracker.log("Click Edit dropdown (Devices)...")
        try:
            edit_btn = find_element_safe(
                self.driver, SEL_DEVICE_EDIT_DROPDOWN, timeout=TIMEOUT_MEDIUM
            )
            _scroll_into_view_center(self.driver, edit_btn)
            time.sleep(0.5)
            if not human_click(self.driver, edit_btn):
                edit_btn.click()
            time.sleep(5)  # Cho menu dropdown mo ra
        except Exception as e:
            self.tracker.log(f"Loi click Edit dropdown: {e}", "error")
            return

        # Click "Exclude" option
        self.tracker.log("Chon 'Exclude' cho devices...")
        try:
            exclude_option = ("xpath",
                "//material-select-item[contains(., 'Exclude')]"
                " | //div[contains(@class, 'menu-item')][contains(., 'Exclude')]"
                " | //material-select-dropdown-item[contains(., 'Exclude')]"
            )
            click_element_safe(self.driver, exclude_option, timeout=TIMEOUT_MEDIUM)
            time.sleep(5)  # Cho exclude ap dung xong
            self.tracker.log(
                f"Da exclude {len(rows_to_exclude)} devices",
                "success",
            )
        except Exception as e:
            self.tracker.log(f"Loi chon Exclude devices: {e}", "error")
