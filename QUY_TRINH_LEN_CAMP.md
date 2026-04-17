# QUY TRÌNH LÊN CAMP — TK CHƯA CÓ CAMP NÀO

> Anh ghi lại từng bước thao tác trên Google Ads UI ở đây.
> Em sẽ đọc file này để code bot làm đúng theo.

---

## Bước 1: Lấy dữ liệu từ DB
- Trên dashboard chọn dự án (vd: viltrox, ComfiLife...)
- Tick các TK Ads muốn chạy (mỗi TK thuộc 1 profile GenLogin)
- Ấn "Chạy camp" → API gửi config dự án + danh sách TK cho camp_runner.py
- Dữ liệu gồm: tên camp, keywords, headlines, descriptions, budget, bidding, CPC, locations, devices, age, gender...


## Bước 2: Mở profile GenLogin + vào TK Ads
- Start profile GenLogin bằng genloginId → lấy debugger address → connect Selenium
- Navigate tới: https://ads.google.com/aw/campaigns?ocid={accountId bỏ dấu -}
- Xử lý trang Sign in: click chọn email đúng trong Account Chooser
- Xử lý trang Select Account: click chọn TK Ads đúng theo ID
- Xử lý billing/setup: reload nếu gặp trang billing setup
- Kết quả: đang ở trang Campaigns/Overview của TK Ads đúng


## Bước 3: Click tạo Campaign mới (2 cách)
- **Cách 1 (ưu tiên):** Tìm nút "New campaign" → click thẳng → vào luôn trang tạo
- **Cách 2:** Chỉ có nút "+" (material-fab aria-label="Create") → click → hiện dropdown → chọn "Campaign"
- Ưu tiên cách 1 trước, không có thì dùng cách 2
- Đợi trang "New campaign" load xong


## Bước 4: Chọn objective — "without guidance"
- Trang hiện "Choose your objective" với các card: Sales, Leads, Website traffic...
- Click chọn "Create a campaign without a goal's guidance"
- Selector: data-value='No objective' hoặc text chứa "without guidance"


## Bước 5: Chọn loại campaign — Search + tick Website visits
- Trang hiện các card: Search, Display, Video, Shopping, App, Performance Max, Demand Gen
- Click chọn "Search" (data-value='SEARCH')
- KHÔNG ấn Continue vội — đợi phần checkbox hiện ra bên dưới
- Tích checkbox "Website visits"
- Rồi mới ấn Continue


## Bước 6: Choose goals (Page view) + Campaign name + bỏ Enhanced conversions
- Trang hiện "Choose goals you would like to focus on" với conversion-goal-picker
- **6a.** Tích vào "Page view" — element là conversion-goal-card chứa button, icon id="PAGE_VIEW"
- **6b.** Điền Campaign name — input bên dưới:
  + Camp đầu tiên: "viltrox"
  + Camp thứ 2 trở đi: "viltrox 2", "viltrox 3"... (đếm từ DB)
- **6c.** Bỏ tích "Turn on enhanced conversions" — material-checkbox mặc định đang checked, click để untick
- Xong hết 3 việc → ấn Continue


## Bước 7: Bidding — chọn chiến lược đấu giá
- Trang có left-stepper-menu: Bidding → Campaign settings → Keywords and ads → Budget → Review
- Làm lần lượt, KHÔNG skip bước nào
- **Bidding:**
  + Mở dropdown (dropdown-button có text "Conversions" hoặc "Clicks") → click
  + Chọn "Clicks" trong material-select-dropdown-item
  + Nếu có CPC: tích checkbox "maximum cost per click" → điền giá CPC vào input
- Ấn Next để sang bước tiếp


## Bước 8: Campaign settings — Networks + Locations + Languages
- **8a.** Bỏ tick "Search Partners" (material-checkbox class search-checkbox)
- **8b.** Bỏ tick "Display Network" (material-checkbox class display-checkbox)
- **8c.** Locations:
  + Click "Enter another location" → "Advanced search"
  + Tick bulk locations checkbox
  + Paste danh sách target locations vào textarea → Search → "Target all"
  + Clear textarea → paste exclude locations → Search → "Exclude all"
  + Click Save
- **8d.** Xóa English (click div aria-label="English remove") → tự chuyển All languages
- **8e.** Nếu thấy EU political ads (eu-political-ads-plugin) → chọn "No"
- Ấn Next để sang bước tiếp


## Bước 8.5: AI Max for Search campaigns — Skip
- Trang hiện "AI Max for Search campaigns"
- Không làm gì — ấn Next để skip

## Bước 8.6: Keyword and asset generation — Skip
- Trang hiện "Keyword and asset generation"
- Ấn Skip để bỏ qua

## Bước 9: Keywords and ads
- **9a.** Điền keywords vào textarea (aria-label chứa "Enter or paste keywords")
- **9b.** Điền Final URL vào input (aria-label="Final URL")
- **9c.** Điền headlines — tối đa 15 ô, click "Add headline" nếu thiếu ô
- **9d.** Điền descriptions — tối đa 4 ô, click "Add description" nếu thiếu ô
- Ấn Next để sang bước tiếp


## XỬ LÝ 2FA (có thể nhảy ra BẤT KỲ LÚC NÀO — check trước mỗi bước)
- Thấy material-dialog "Confirm it's you" → click nút xanh **Confirm** (dùng ActionChains)
- Nếu hiện lại với nút **"Try again"** → click Try again (cũng ActionChains)
- Google mở tab mới "Sign in" với input TOTP
- Đọc email trên trang → gọi GET /api/gmail → tìm twoFactorKey
- Tạo TOTP bằng pyotp → điền vào input#totpPin → click #totpNext button
- Tab tự đóng → quay lại tab Google Ads
- SAU 2FA: vẫn ở đúng trang cũ nhưng trang có thể bị reload/reset
- → **Đọc thanh stepper bên trái** (left-stepper-menu) để xác định đang ở bước nào
- → Tiếp tục đúng bước đó, KHÔNG chạy lại từ đầu

## Bước 10: Budget
- Click radio "Set custom budget" → expand panel nếu cần
- Điền số tiền budget vào input
- ⚠️ Popup 2FA hay nhảy ra ở bước này — xử lý xong rồi mới tiếp
- Ấn Next → sang Review


---

## Bước 11: Review + Publish
- Trang Review hiện tóm tắt toàn bộ campaign
- ⚠️ 2FA có thể nhảy ra ở đây — xử lý xong → đọc stepper xác định vị trí → tiếp tục
- Nếu có dialog "Fix errors" → click Fix errors → sửa lỗi → Next lại
- Click nút "Publish campaign"
- Sau publish:
  + Trang Policy Review ("can't run yet") → ấn Next
  + Trang Google Tag → ấn Close (X)
- Lưu campaign vào DB → XONG

## Ghi chú thêm
- 2FA có thể nhảy ra ở BẤT KỲ bước nào (hay nhất ở Budget và Review)
- Sau 2FA luôn đọc stepper để biết đang ở đâu
- Popup draft có thể hiện: trùng tên → click tên, khác tên → Start new
- Popup "Exit guide" → click Leave
- Popup "Conversion goals" → click Close (X)
