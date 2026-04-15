"""
=== CAMP SELECTORS ===
Tat ca XPath/CSS selectors va constants cho campaign automation.
Tach rieng de de bao tri khi Google thay doi UI.
"""

# ============================================================
# TIMEOUT CONSTANTS (giay)
# ============================================================
TIMEOUT_SHORT = 5
TIMEOUT_MEDIUM = 15
TIMEOUT_LONG = 30
TIMEOUT_PAGE_LOAD = 60

# Cho nguoi thao tac tay khi bot khong tim thay element
MANUAL_FALLBACK_TIMEOUT = 30

# ============================================================
# DELAY CONSTANTS (giay) - gia hanh vi nguoi that
# ============================================================
DELAY_AFTER_CLICK = 0.8
DELAY_AFTER_TYPE = 0.5
DELAY_BETWEEN_STEPS = 2.0
DELAY_PAGE_TRANSITION = 3.0

# Human-like mouse movement
HUMAN_MOVE_STEPS_MIN = 15
HUMAN_MOVE_STEPS_MAX = 30
HUMAN_MOVE_STEP_DELAY_MIN = 0.005
HUMAN_MOVE_STEP_DELAY_MAX = 0.015
HUMAN_PAUSE_BEFORE_CLICK_MIN = 0.1
HUMAN_PAUSE_BEFORE_CLICK_MAX = 0.4
HUMAN_HOVER_BEFORE_CLICK_MIN = 0.05
HUMAN_HOVER_BEFORE_CLICK_MAX = 0.2

# Human-like typing
HUMAN_TYPE_DELAY_MIN = 0.03
HUMAN_TYPE_DELAY_MAX = 0.12
HUMAN_TYPE_HESITATE_PROB = 0.05
HUMAN_TYPE_HESITATE_MIN = 0.2
HUMAN_TYPE_HESITATE_MAX = 0.6

# ============================================================
# FILE PATHS
# ============================================================
STATUS_FILE = "status.json"

# ============================================================
# GOOGLE ADS URLS
# ============================================================
ADS_HOME_URL = "https://ads.google.com/"
ADS_CAMPAIGNS_URL_TEMPLATE = "https://ads.google.com/aw/campaigns?ocid={customer_id}"
ADS_NEW_CAMPAIGN_URL_TEMPLATE = "https://ads.google.com/aw/campaigns/new"

# ============================================================
# NAVIGATION SELECTORS
# ============================================================

# Select Account page - chon tai khoan Ads
SEL_ACCOUNT_LIST_ITEM = ("xpath", "//material-list-item[contains(@class, 'account-item')]")
SEL_ACCOUNT_NAME = ("xpath", ".//span[contains(@class, 'account-name')]")
SEL_ACCOUNT_ID = ("xpath", ".//span[contains(@class, 'account-id')]")

# ============================================================
# CAMPAIGN CREATION SELECTORS
# ============================================================

# Button "New campaign" / "+" tren trang campaigns
SEL_NEW_CAMPAIGN_BTN = ("xpath", "//material-button[contains(@aria-label, 'New campaign') or contains(@aria-label, 'campaign')]")
SEL_NEW_CAMPAIGN_PLUS = ("xpath", "//material-fab[contains(@class, 'new-entity')]")

# Campaign goal selection (Google Ads 2026 — class: unified-goals-card)
SEL_GOAL_SALES = ("xpath", "//span[contains(@class, 'unified-goals-card-title') and contains(text(), 'Sales')]")
SEL_GOAL_LEADS = ("xpath", "//span[contains(@class, 'unified-goals-card-title') and contains(text(), 'Leads')]")
SEL_GOAL_TRAFFIC = ("xpath", "//span[contains(@class, 'unified-goals-card-title') and contains(text(), 'Website traffic')]")
SEL_GOAL_AWARENESS = ("xpath", "//span[contains(@class, 'unified-goals-card-title') and contains(text(), 'Awareness')]")
SEL_GOAL_WITHOUT = ("xpath", "//span[contains(@class, 'unified-goals-card-title') and contains(text(), 'without guidance')]")

# Campaign type selection (Google Ads 2026 — same class as goals)
SEL_TYPE_SEARCH = ("xpath", "//span[contains(@class, 'unified-goals-card-title') and text()='Search']")
SEL_TYPE_DISPLAY = ("xpath", "//span[contains(@class, 'unified-goals-card-title') and text()='Display']")
SEL_TYPE_VIDEO = ("xpath", "//span[contains(@class, 'unified-goals-card-title') and text()='Video']")
SEL_TYPE_SHOPPING = ("xpath", "//span[contains(@class, 'unified-goals-card-title') and text()='Shopping']")
SEL_TYPE_APP = ("xpath", "//span[contains(@class, 'unified-goals-card-title') and contains(text(), 'App promotion')]")
SEL_TYPE_PERFORMANCE_MAX = ("xpath", "//span[contains(@class, 'unified-goals-card-title') and text()='Performance Max']")
SEL_TYPE_DEMAND_GEN = ("xpath", "//span[contains(@class, 'unified-goals-card-title') and text()='Demand Gen']")

# Continue / Next buttons (Google Ads 2026)
SEL_CONTINUE_BTN = ("xpath", "//button[contains(text(), 'Continue')]")
SEL_NEXT_BTN = ("xpath", "//button[contains(text(), 'Next')] | //material-button[.//span[contains(text(), 'Next')]]")

# ============================================================
# BUDGET & BIDDING SELECTORS
# ============================================================
SEL_BUDGET_INPUT = ("xpath", "//input[contains(@aria-label, 'budget') or contains(@aria-label, 'Budget')]")
SEL_BIDDING_STRATEGY_DROPDOWN = ("xpath", "//div[contains(@class, 'bidding')]//material-dropdown-select")
SEL_BIDDING_MAXIMIZE_CLICKS = ("xpath", "//material-select-item[.//span[contains(text(), 'Maximize clicks')]]")
SEL_BIDDING_MAXIMIZE_CONVERSIONS = ("xpath", "//material-select-item[.//span[contains(text(), 'Maximize conversions')]]")

# ============================================================
# AD GROUP SELECTORS
# ============================================================
SEL_ADGROUP_NAME_INPUT = ("xpath", "//input[contains(@aria-label, 'Ad group name')]")
SEL_KEYWORD_INPUT = ("xpath", "//textarea[contains(@aria-label, 'keyword') or contains(@aria-label, 'Keyword')]")
SEL_ADD_KEYWORDS_BTN = ("xpath", "//material-button[.//span[contains(text(), 'Add keyword')]]")

# ============================================================
# AD CREATION SELECTORS (Responsive Search Ad)
# ============================================================
SEL_FINAL_URL_INPUT = ("xpath", "//input[contains(@aria-label, 'Final URL')]")
SEL_HEADLINE_INPUT = ("xpath", "//input[contains(@aria-label, 'Headline')]")
SEL_DESCRIPTION_INPUT = ("xpath", "//textarea[contains(@aria-label, 'Description')]")
SEL_ADD_HEADLINE_BTN = ("xpath", "//material-button[.//span[contains(text(), 'Add headline')]]")
SEL_ADD_DESCRIPTION_BTN = ("xpath", "//material-button[.//span[contains(text(), 'Add description')]]")

# ============================================================
# REVIEW & PUBLISH
# ============================================================
SEL_PUBLISH_BTN = ("xpath", "//material-button[.//span[contains(text(), 'Publish') or contains(text(), 'publish')]]")
SEL_REVIEW_SUMMARY = ("xpath", "//div[contains(@class, 'review-summary')]")

# ============================================================
# POST-PUBLISH: CLOSE GOOGLE TAG PAGE
# ============================================================
SEL_CLOSE_GOOGLE_TAG = ("xpath", "//material-button[contains(@aria-label, 'Close')]")

# ============================================================
# SIDEBAR NAVIGATION (sau khi publish)
# ============================================================
SEL_SIDEBAR_AUDIENCES = ("xpath", "//sidebar-panel[@id='navigation.campaigns.audiences.audiences']//a")

# ============================================================
# MODAL: Unified audience reporting
# ============================================================
SEL_MODAL_CLOSE = ("xpath", "//material-dialog//material-button[contains(@aria-label, 'Close')]")

# ============================================================
# DEMOGRAPHICS SECTION
# ============================================================
# Tab buttons
SEL_DEMO_TAB_AGE = ("xpath", "//tab-button[@aria-label='Age']")
SEL_DEMO_TAB_GENDER = ("xpath", "//tab-button[@aria-label='Gender']")

# Table rows (chi lay data rows, bo qua summary rows)
SEL_DEMO_DATA_ROWS = ("xpath", "//div[contains(@class,'demographics-section')]//div[contains(@class,'particle-table-row') and not(contains(@class,'summary-row'))]")

# Trong 1 row: lay text demographic (age range / gender)
SEL_DEMO_ROW_TEXT = ("xpath", ".//demographics-cell//span")

# Trong 1 row: check status enabled
SEL_DEMO_ROW_STATUS_ENABLED = ("xpath", ".//aw-status//div[contains(@class,'enabled')]")

# Trong 1 row: checkbox
SEL_DEMO_ROW_CHECKBOX = ("xpath", ".//mat-checkbox")

# Edit dropdown (secondary toolbar) - "Bulk edit" button
SEL_DEMO_EDIT_DROPDOWN = ("xpath", "//material-button[contains(@aria-label, 'Bulk edit')]")

# ============================================================
# DEVICES PAGE (Insights and reports -> When and where ads showed)
# ============================================================
# Sidebar: mo "Insights and reports" (neu chua mo)
SEL_SIDEBAR_INSIGHTS = ("xpath", "//sidebar-panel[@id='navigation.campaigns.insightsAndReports']//a")
# Sidebar: click "When and where ads showed"
SEL_SIDEBAR_DEVICES = ("xpath", "//sidebar-panel[@id='navigation.campaigns.insightsAndReports.whenAndWhereAdsShowed']//a")

# Device table rows (chi data rows, bo summary)
SEL_DEVICE_DATA_ROWS = ("xpath", "//div[contains(@class,'particle-table-row') and not(contains(@class,'summary-row'))]")

# Trong 1 row: lay device name
SEL_DEVICE_ROW_TEXT = ("xpath", ".//device-criterion-cell//div[@class='device']")

# Trong 1 row: checkbox
SEL_DEVICE_ROW_CHECKBOX = ("xpath", ".//mat-checkbox")

# Device Edit dropdown (Bulk edit)
SEL_DEVICE_EDIT_DROPDOWN = ("xpath", "//material-button[contains(@aria-label, 'Bulk edit')]")

# ============================================================
# COMMON / SHARED
# ============================================================
SEL_LOADING_SPINNER = ("xpath", "//material-spinner | //mat-spinner")
SEL_BUTTERBAR_ERROR = ("xpath", "//div[contains(@class, 'butterbar') and contains(@class, 'error')]")
SEL_BUTTERBAR_TEXT = ("xpath", "//div[contains(@class, 'butterbar')]//span")
