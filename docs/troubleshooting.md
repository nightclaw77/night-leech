# 🔧 عیب‌یابی - Night Leech Bot

## مشکلات رایج

### ❌ ربات شروع نمی‌شود

**علائم:**
- لاگ خطا نشان داده می‌شود
- systemctl status خطا می‌دهد

**راه‌حل:**
```bash
# بررسی لاگ‌ها
journalctl -u night-leech -f

# بررسی فایل کانفیگ
cat /opt/night-leech/config/config.env

# بررسی خطاهای پایتون
cd /opt/night-leech
source venv/bin/activate
python3 bot.py
```

---

### ❌ خطای API تلگرام

**علائم:**
- `Error Code: 401` یا `Unauthorized`
- ربات به پیام‌ها جواب نمی‌دهد

**راه‌حل:**
1. توکن ربات را بررسی کنید
2. از @BotFather توکن جدید بگیرید
3. `BOT_TOKEN` را در کانفیگ آپدیت کنید

```bash
nano /opt/night-leech/config/config.env
# BOT_TOKEN = "new-token-here"

sudo systemctl restart night-leech
```

---

### ❌ خطای Google Drive

**علائم:**
- آپلود به GDrive انجام نمی‌شود
- خطای `GDRIVE_ID`

**راه‌حل:**
- اگر از تلگرام استفاده می‌کنید، `GDRIVE_ID` را خالی بگذارید
- اگر می‌خواهید از GDrive استفاده کنید، [راهنمای GDrive](./installation.md) را ببینید

---

### ❌ دانلود کند است

**علائم:**
- سرعت دانلود پایین
- تورنت سید نمی‌شود

**راه‌حل:**
1. از tracker خصوصی استفاده کنید
2. VPN روشن کنید
3. تنظیمات Aria2/qBittorrent را بررسی کنید

---

### ❌ فضای دیسک پر شده

**علائم:**
- خطای `No space left on device`
- دانلود متوقف می‌شود

**راه‌حل:**
```bash
# بررسی فضا
df -h

# پاک کردن فایل‌های موقت
rm -rf /opt/night-leech/downloads/*
rm -rf /opt/night-leech/logs/*
```

---

### ❌ خطای Docker

**علائم:**
- Docker بیلد یا اجرا نمی‌شود

**راه‌حل:**
```bash
# بررسی وضعیت Docker
sudo systemctl status docker

# ریستارت Docker
sudo systemctl restart docker

# بررسی لاگ
sudo journalctl -u docker -f
```

---

## لاگ‌گیری

### مشاهده لاگ‌ها
```bash
# لاگ زنده
journalctl -u night-leech -f

# لاگ دیروز
journalctl -u night-leech --since "1 day ago"

# لاگ خطاها
journalctl -u night-leech -p err
```

---

## ریستارت و بازیابی

### ریستارت کامل
```bash
sudo systemctl stop night-leech
sleep 5
sudo systemctl start night-leech
```

### پاک کردن کش
```bash
rm -rf /opt/night-leech/data/*
rm -rf /opt/night-leech/downloads/*
sudo systemctl restart night-leech
```

### بازیابی از بکاپ
```bash
cd /opt/night-leech
git pull
sudo systemctl restart night-leech
```
