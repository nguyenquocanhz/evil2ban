# Evil2Ban

**Chủ động phát hiện & chặn brute-force / scan, dashboard localhost — real-IP Cloudflare an toàn.**

Evil2Ban đọc log nginx (`/www/wwwlogs/*.log`), journald SSH và fail2ban để phát
hiện quét lỗ hổng / brute-force, thống kê traffic + User-Agent, chặn/gỡ chặn IP,
và vẽ biểu đồ theo ngày/tháng (đường, nến OHLC, cột) ngay trên một WebUI nhẹ
**không phụ thuộc CDN** (vào qua SSH tunnel). Kèm TUI dòng lệnh và tích hợp
notifier Telegram/Slack/Discord có sẵn.

> Dashboard **chỉ bind `127.0.0.1`** — không phơi ra Internet. Truy cập qua SSH tunnel.

---

## Tính năng

- **Phát hiện scan/brute-force** theo bộ quy tắc mở rộng được (UA scanner, path
  nhạy cảm `/.env` `/.git` `wp-login`…, bùng nổ 404).
- **Real-IP Cloudflare an toàn** — *không bao giờ* chặn dải IP Cloudflare (tránh
  sập toàn bộ site); ưu tiên `CF-Connecting-IP` / `X-Forwarded-For` khi log có ghi.
  Request sau CDN không truy được client thật thì **bỏ qua** thay vì chặn nhầm.
- **WebUI** với sidebar trái: **Dashboard · Monitor · Blacklist**. Trang Blacklist
  có tìm kiếm, phân trang, chặn/gỡ chặn hàng loạt. Biểu đồ **đường / nến OHLC / cột**
  theo ngày/tháng, canvas thuần không CDN.
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
# -> ../evil2ban_1.0.0_all.deb
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
```

## Truy cập WebUI (SSH tunnel)

```bash
ssh -N -L 8793:127.0.0.1:8793 <user>@<server-ip>
# rồi mở: http://127.0.0.1:8793/?token=<token>
```

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

## Giấy phép

MIT — xem [LICENSE](LICENSE).
