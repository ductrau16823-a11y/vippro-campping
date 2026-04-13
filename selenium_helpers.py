"""
Selenium helpers: Tim, click, type element an toan voi timeout va manual fallback.
Human-like: di chuot theo duong cong, hover, go tung ky tu voi delay ngau nhien.
"""

import time
import random

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from camp_selectors import (
    TIMEOUT_MEDIUM,
    DELAY_AFTER_CLICK,
    DELAY_AFTER_TYPE,
    MANUAL_FALLBACK_TIMEOUT,
    HUMAN_MOVE_STEPS_MIN,
    HUMAN_MOVE_STEPS_MAX,
    HUMAN_MOVE_STEP_DELAY_MIN,
    HUMAN_MOVE_STEP_DELAY_MAX,
    HUMAN_PAUSE_BEFORE_CLICK_MIN,
    HUMAN_PAUSE_BEFORE_CLICK_MAX,
    HUMAN_HOVER_BEFORE_CLICK_MIN,
    HUMAN_HOVER_BEFORE_CLICK_MAX,
    HUMAN_TYPE_DELAY_MIN,
    HUMAN_TYPE_DELAY_MAX,
    HUMAN_TYPE_HESITATE_PROB,
    HUMAN_TYPE_HESITATE_MIN,
    HUMAN_TYPE_HESITATE_MAX,
)


def _by(strategy):
    mapping = {
        "xpath": By.XPATH,
        "css": By.CSS_SELECTOR,
        "id": By.ID,
        "name": By.NAME,
        "class": By.CLASS_NAME,
        "link_text": By.LINK_TEXT,
    }
    return mapping.get(strategy.lower(), By.XPATH)


def _rand(a, b):
    return random.uniform(a, b)


def _scroll_into_view_center(driver, element):
    try:
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center', inline: 'center', behavior: 'instant'});",
            element,
        )
    except Exception:
        try:
            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", element
            )
        except Exception:
            driver.execute_script("arguments[0].scrollIntoView(true);", element)


def human_mouse_move_to(driver, element):
    try:
        rect = driver.execute_script(
            "var r = arguments[0].getBoundingClientRect();"
            "return {x: r.left, y: r.top, w: r.width, h: r.height};",
            element,
        )
        if not rect or rect["w"] == 0 or rect["h"] == 0:
            return False

        target_x_offset = rect["w"] * _rand(0.3, 0.7)
        target_y_offset = rect["h"] * _rand(0.3, 0.7)

        actions = ActionChains(driver)
        cx = rect["w"] / 2
        cy = rect["h"] / 2

        wobble_points = random.randint(
            max(2, HUMAN_MOVE_STEPS_MIN // 8),
            max(3, HUMAN_MOVE_STEPS_MAX // 8),
        )
        for _ in range(wobble_points):
            ox = cx + _rand(-rect["w"] * 0.6, rect["w"] * 0.6)
            oy = cy + _rand(-rect["h"] * 0.6, rect["h"] * 0.6)
            actions.move_to_element_with_offset(element, ox - cx, oy - cy)
            actions.pause(_rand(HUMAN_MOVE_STEP_DELAY_MIN, HUMAN_MOVE_STEP_DELAY_MAX))

        final_ox = target_x_offset - cx
        final_oy = target_y_offset - cy
        actions.move_to_element_with_offset(element, final_ox, final_oy)
        actions.pause(_rand(HUMAN_HOVER_BEFORE_CLICK_MIN, HUMAN_HOVER_BEFORE_CLICK_MAX))

        actions.perform()
        return True
    except Exception:
        return False


def human_click(driver, element):
    time.sleep(_rand(HUMAN_PAUSE_BEFORE_CLICK_MIN, HUMAN_PAUSE_BEFORE_CLICK_MAX))
    moved = human_mouse_move_to(driver, element)
    if not moved:
        return False
    try:
        ActionChains(driver).click().perform()
        return True
    except Exception:
        return False


def human_type(element, text):
    for ch in text:
        element.send_keys(ch)
        time.sleep(_rand(HUMAN_TYPE_DELAY_MIN, HUMAN_TYPE_DELAY_MAX))
        if random.random() < HUMAN_TYPE_HESITATE_PROB:
            time.sleep(_rand(HUMAN_TYPE_HESITATE_MIN, HUMAN_TYPE_HESITATE_MAX))


def find_element_safe(driver, selector_tuple, timeout=TIMEOUT_MEDIUM, required=True):
    strategy, value = selector_tuple
    by = _by(strategy)

    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )
        return element
    except Exception:
        if not required:
            return None

        print(f"\n  [!] Khong tim thay element: {value[:80]}")
        print(f"  [!] Cho {MANUAL_FALLBACK_TIMEOUT} giay de anh tu thao tac...")

        try:
            element = WebDriverWait(driver, MANUAL_FALLBACK_TIMEOUT).until(
                EC.presence_of_element_located((by, value))
            )
            return element
        except Exception:
            raise Exception(
                f"Khong tim thay element sau {timeout + MANUAL_FALLBACK_TIMEOUT}s: "
                f"({strategy}) {value[:80]}"
            )


def click_element_safe(driver, selector_tuple, timeout=TIMEOUT_MEDIUM, required=True):
    element = find_element_safe(driver, selector_tuple, timeout, required)
    if element:
        try:
            _scroll_into_view_center(driver, element)
            time.sleep(_rand(0.2, 0.5))
        except Exception:
            pass

        clicked = False
        try:
            clicked = human_click(driver, element)
        except Exception:
            clicked = False

        if not clicked:
            try:
                element.click()
                clicked = True
            except Exception:
                clicked = False

        if not clicked:
            try:
                driver.execute_script("arguments[0].click();", element)
            except Exception as e:
                if required:
                    raise

        time.sleep(DELAY_AFTER_CLICK)
    return element


def type_into_element(driver, selector_tuple, text, timeout=TIMEOUT_MEDIUM, clear=True):
    element = find_element_safe(driver, selector_tuple, timeout)
    if element and text:
        try:
            _scroll_into_view_center(driver, element)
            time.sleep(_rand(0.2, 0.4))

            focused = False
            try:
                focused = human_click(driver, element)
            except Exception:
                focused = False
            if not focused:
                try:
                    element.click()
                except Exception:
                    pass

            time.sleep(_rand(0.1, 0.25))

            if clear:
                try:
                    element.clear()
                except Exception:
                    pass
                time.sleep(0.15)
                element.send_keys(Keys.CONTROL, "a")
                time.sleep(0.1)
                element.send_keys(Keys.DELETE)
                time.sleep(0.1)

            human_type(element, text)
            time.sleep(DELAY_AFTER_TYPE)
        except Exception as e:
            raise Exception(f"Loi go text vao element: {e}")
    return element
