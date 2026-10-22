# Evil2Ban

**Chủ động phát hiện & chặn brute-force / scan, dashboard localhost — real-IP Cloudflare an toàn.**

Evil2Ban đọc log nginx (`/www/wwwlogs/*.log`), journald SSH và fail2ban để phát
hiện quét lỗ hổng / brute-force, thống kê traffic + User-Agent, chặn/gỡ chặn IP,
theo dõi **realtime**, chặn ở cả **tầng tường lửa lẫn tầng web (Nginx)**, ngay trên
một WebUI nhẹ **không phụ thuộc CDN**, song ngữ **VI/EN**, giao diện **sáng/tối**.
Kèm TUI dòng lệnh và cảnh báo qua Telegram/Slack/Discord.

> Dashboard **chỉ bind `127.0.0.1`**. Ra Internet chỉ qua reverse proxy (Nginx + Cloudflare)
> hoặc SSH tunnel.

---

## Tính năng

- **Phát hiện scan/brute-force** theo bộ quy tắc mở rộng được (UA scanner, path
  nhạy cảm `/.env` `/.git` `wp-login`…, bùng nổ 404).
- **Real-IP Cloudflare an toàn** — *không bao giờ* chặn dải IP Cloudflare (tránh
  sập toàn bộ site); ưu tiên `CF-Connecting-IP` / `X-Forwarded-For` khi log có ghi.
  Request sau CDN không truy được client thật thì **bỏ qua** thay vì chặn nhầm.
- **WebUI** (v1.2) — sidebar chia nhóm (mở/đóng bằng +/−, thu gọn về dải icon,
  `Ctrl+B`): **Tổng quan · Giám sát · Chặn IP · Tên miền · Nhật ký · Cài đặt**.
  - **Realtime**: một kết nối SSE, server đẩy số liệu mỗi 5 giây (request/phút,
    SSH sai/phút, đang chặn, nghi vấn) kèm đồ thị nhỏ; tự chuyển sang hỏi lại 5 giây
    nếu SSE hỏng.
  - **Cảnh báo IP cào nhanh**: vượt ngưỡng request/phút (mặc định 120, chỉ tính IP
    thật) → thông báo góc màn có nút **Chặn ngay**, chuông, và gửi Telegram/Slack/Discord.
  - **Tên miền (DomainGate)**: số liệu theo từng site, mỗi site một cổng
    *Tắt / Chỉ giám sát / Tự chặn* với ngưỡng 404 riêng.
  - **Bản đồ** request theo quốc gia (SVG nhúng sẵn, Natural Earth, Equal Earth).
  - **Nhật ký audit**: đăng nhập (cả thất bại), chặn/gỡ, whitelist, đổi cài đặt,
    đổi mật khẩu, tạo lại token — kèm **IP người làm**, lọc, xuất CSV, giữ 90 ngày.
  - **Cài đặt** trên web: tài khoản, ngưỡng phát hiện, kênh cảnh báo (webhook,
    gửi thử), email, link công khai, giao diện; mỗi dòng tự lưu.
  - Song ngữ **VI/EN**, **sáng/tối/theo hệ thống**, câu lỗi có dấu kèm mã lỗi.
- **Chặn ở tầng web** (`evil2ban-setup --web-gate on`): IP bị chặn thấy **trang 403
  Evil2Ban** trên mọi site gắn cổng, kể cả khi đi qua Cloudflare (Nginx khôi phục IP
  thật rồi so danh sách `geo`, tự đồng bộ với fail2ban mỗi phút).
- **GeoIP tại chỗ** — DB-IP Lite Country (CC BY 4.0), nén ~2 MB, tự cập nhật mỗi tháng,
  không gọi dịch vụ ngoài khi tra.
- **TUI** (`evil2ban`) menu 1/2/3 + reset mật khẩu qua email.
- **fail2ban** để thực thi chặn; **notifier** Telegram/Slack/Discord dùng lại
  `/usr/local/bin/f2b-notify.sh`.
- **Auto-ban** tùy chọn (mặc định **TẮT** để tránh false-positive).
- **Một SQLite** quản lý toàn bộ: settings, whitelist, sessions, time-series, events.

## Kiến trúc (SOLID / OOP)

Mỗi tầng phụ thuộc vào **abstraction** (`core/interfaces.py`), không phụ thuộc
hiện thực cụ thể → dễ test/thay thế/mở rộng.

```
core/        models (dataclass) + interfaces (ABC) + exceptions
data/        Database (kết nối/schema) + repositories (Settings/Whitelist/Session/
             Event/Meta/Sample) — mỗi repo một trách nhiệm
detect/      cloudflare · realip (IpResolver) · parser (LogSource/LogParser) ·
             rules (mỗi 'case' phát hiện = 1 lớp) · detector (ScanDetector/Analyzer)
infra/       fail2ban (Firewall/SshReader) · notifier · mailer · geo  (adapters)
services/    ban_service · auth_service · analysis_service · stats_service
web/         container (DI composition root) + app (FastAPI routes mỏng) + static
cli/         wizard (installer/first-run) + tui
```

- **Open/Closed:** thêm kiểu phát hiện mới = thêm lớp trong `detect/rules.py` rồi
  đăng ký vào `DEFAULT_RULES`, **không sửa** detector.
- **Dependency Inversion:** `web/container.py` là composition root wire tất cả.

---

## Cài đặt

### A. Qua gói `.deb` + APT repo tự host

**1) Build gói (trên máy build):**

```bash
# cần python3-venv, dpkg-dev
bash packaging/build-deb.sh
# -> ../evil2ban_1.2.0_all.deb
```

**2) Dựng APT repo tự host:**

```bash
bash packaging/make-apt-repo.sh ./apt-repo
# (tùy chọn ký: GPG_KEY=<keyid> bash packaging/make-apt-repo.sh ./apt-repo)
# phục vụ qua web server bất kỳ, ví dụ:
#   rsync -a apt-repo/ user@host:/var/www/apt/evil2ban/
```

**3) Trên máy chủ cần bảo vệ:**

```bash
echo "deb [trusted=yes] https://apt.your-domain.com/evil2ban ./" \
  | sudo tee /etc/apt/sources.list.d/evil2ban.list
sudo apt update
sudo apt install evil2ban
```

> `postinst` tự tạo venv và kéo `fastapi/uvicorn/rich` từ PyPI (cần Internet lần
> đầu), seed SQLite + sinh tài khoản, in link WebUI, bật service.

Cài trực tiếp từ file `.deb` (không cần repo):

```bash
sudo apt install ./evil2ban_1.0.0_all.deb
```

### B. Build / chạy từ mã nguồn (dev)

```bash
python3 -m venv venv && . venv/bin/activate
pip install -e .
evil2ban-setup          # first-run: sinh tài khoản + hỏi cấu hình
evil2ban-server         # chạy backend (host/port lấy từ SQLite)
```

---

## First-run / Wizard

`evil2ban-setup` sẽ:

1. Sinh **username 5 ký tự** + **mật khẩu ≥12 ký tự** + **access token**, in ra
   link WebUI kèm token.
2. Hỏi (có xác nhận `y/n`): **Gmail App Password** (reset mật khẩu), **Telegram
   Bot TOKEN**, **ADMIN_ID**. Lưu vào SQLite (file quyền `600`) và đồng bộ Telegram
   sang `/etc/fail2ban/notify.conf` cho notifier có sẵn.
3. Cho nhập các **IP/CIDR của bạn** vào whitelist (không bao giờ bị chặn).

```bash
sudo evil2ban-setup --print    # in lại link WebUI + token
sudo evil2ban-setup --reset-creds   # sinh lại tài khoản
sudo evil2ban-setup --public-url https://e2b.ten-mien-cua-ban   # đặt link công khai
```

## Chặn ở tầng web + trang 403

Khách đi qua Cloudflare thì kết nối TCP tới máy chủ là IP Cloudflare, nên chặn bằng
tường lửa (fail2ban) theo IP thật **không có tác dụng** với web. Cổng web giải quyết:

```bash
sudo evil2ban-setup --web-gate on    # gắn vào mọi vhost aaPanel có thư mục extension
sudo evil2ban-setup --web-gate off   # gỡ
```

- Tạo `geo $e2b_blocked` ở tầng `http` + mỗi site một file trong
  `/www/server/panel/vhost/nginx/extension/<site>/evil2ban.conf`, bật khôi phục IP thật
  sau Cloudflare cho site chưa có (từ đó log và ứng dụng thấy **IP thật của khách**).
- Chỉ IP bị Evil2Ban chặn mới thấy trang 403 (`/usr/lib/evil2ban/www`, SSI chèn IP,
  mã tham chiếu, thời gian); trang 403 vốn có của site giữ nguyên.
- Mỗi lần ghi danh sách đều chạy `nginx -t`, lỗi thì tự trả file cũ.
- Vhost không có `include .../extension/<site>/*.conf` thì không gắn được (tự thêm
  dòng include đó vào vhost rồi chạy lại lệnh).

## Truy cập WebUI

`evil2ban-setup --print` in sẵn cả hai cách, kèm token và IP public của server
(đọc từ card mạng, không gọi dịch vụ ngoài):

1. **Link công khai** — khi đã dựng reverse proxy (Nginx + Cloudflare) trỏ vào
   `127.0.0.1:8793` và đặt link bằng `--public-url`:
   `https://e2b.ten-mien-cua-ban/?token=<token>`
2. **SSH tunnel** — không cần mở gì ra Internet:

```bash
ssh -N -L 8793:127.0.0.1:8793 <user>@<ip-server>
# rồi mở: http://127.0.0.1:8793/?token=<token>
```

> Link có `?token=` là đăng nhập thẳng, giữ kín như mật khẩu.

## TUI

```bash
sudo evil2ban
#  1) Dashboard   2) Monitor   3) Blacklist   4) Reset mật khẩu   5) Cấu hình
```

---

## Cấu hình (SQLite `settings`)

Xem/sửa qua TUI (mục 5) hoặc trực tiếp. Khóa chính:

| Key | Mặc định | Ý nghĩa |
|-----|----------|---------|
| `server.host` / `server.port` | `127.0.0.1` / `8793` | bind backend |
| `detect.jail` | `sshd` | jail fail2ban dùng để ban |
| `detect.log_dir` | `/www/wwwlogs` | thư mục nginx access log |
| `detect.autoban` | `0` | bật auto-ban (mặc định tắt) |
| `detect.autoban_404` | `40` | ngưỡng 404 để auto-ban |
| `mail.*` | Gmail SMTP | reset mật khẩu qua email |
| `notify.script` | `/usr/local/bin/f2b-notify.sh` | notifier Telegram/Slack/Discord |

Sau khi đổi cấu hình: `sudo systemctl restart evil2ban`.

Bật auto-ban:

```bash
sudo evil2ban        # mục 5 -> detect.autoban = 1
sudo systemctl restart evil2ban
```

## Vì sao real-IP Cloudflare quan trọng

Traffic qua Cloudflare khiến nginx ghi **IP edge Cloudflare** (104.x, 172.64/13,
162.158/15…). Nếu chặn theo IP đó, bạn sẽ chặn nguyên dải Cloudflare → **sập toàn
bộ site**. Evil2Ban:

1. Không bao giờ ban IP trong dải Cloudflare (whitelist seed sẵn + guard 2 lớp).
2. Khôi phục IP thật từ `CF-Connecting-IP` / `X-Forwarded-For` nếu log có ghi.
3. Không khôi phục được → bỏ qua request đó cho mục đích chặn.

## Gỡ cài đặt

```bash
sudo apt remove evil2ban     # giữ dữ liệu
sudo apt purge  evil2ban     # xóa luôn /var/lib/evil2ban, /etc/evil2ban
```

## Nguồn dữ liệu bên thứ ba

- Vị trí IP: **IP Geolocation by DB-IP** (db-ip.com), CC BY 4.0.
- Bản đồ: **Natural Earth** (qua `world-atlas`), phạm vi công cộng.
- Icon: **Lucide** (ISC). Thông báo: **SweetAlert2** (MIT), đóng gói sẵn, không CDN.

## Giấy phép

MIT — xem [LICENSE](LICENSE).
