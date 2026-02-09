# 📚 راهنمای نصب - Night Leech Bot

## پیش‌نیازها

| نیازمندی | حداقل | توصیه شده |
|----------|-------|-----------|
| CPU | 2 هسته | 4 هسته |
| RAM | 2 GB | 4+ GB |
| فضای دیسک | 20 GB | 50+ GB |
| OS | Ubuntu 20.04 | Ubuntu 22.04/24.04 |

---

## روش 1: نصب خودکار (توصیه شده)

```bash
# کلون پروژه
git clone https://github.com/nightclaw77/night-leech.git
cd night-leech

# اجرای اسکریپت نصب
chmod +x setup.sh
./setup.sh
```

---

## روش 2: نصب دستی

### مرحله 1: آپدیت سیستم
```bash
sudo apt update && sudo apt upgrade -y
```

### مرحله 2: نصب پیش‌نیازها
```bash
sudo apt install -y python3 python3-pip python3-venv git curl wget
```

### مرحله 3: نصب Docker (اختیاری اما توصیه شده)
```bash
sudo apt install -y docker.io docker-compose
sudo systemctl start docker
sudo systemctl enable docker
```

### مرحله 4: کلون پروژه
```bash
sudo mkdir -p /opt/night-leech
sudo chown $USER:$USER /opt/night-leech
git clone https://github.com/nightclaw77/night-leech.git /opt/night-leech
cd /opt/night-leech
```

### مرحله 5: ایجاد محیط مجازی پایتون
```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
deactivate
```

### مرحله 6: ایجاد دایرکتوری‌ها
```bash
mkdir -p downloads logs data
```

### مرحله 7: تنظیم کانفیگ
```bash
cp config/config.env.example config/config.env
nano config/config.env
```

---

## تنظیم API Keys

به [چک‌لیست API Keys](../config/api-keys-checklist.md) مراجعه کنید.

---

## اجرای ربات

### روش الف: بدون Docker
```bash
cd /opt/night-leech
source venv/bin/activate
python3 bot.py
```

### روش ب: با Docker
```bash
docker build . -t night-leech
docker run -d --name night-leech \
  -v $(pwd)/config/config.env:/app/config.env \
  -v $(pwd)/downloads:/app/downloads \
  night-leech
```

### روش ج: با systemd
```bash
sudo systemctl enable night-leech
sudo systemctl start night-leech
```

---

## بررسی وضعیت

```bash
# بررسی لاگ
journalctl -u night-leech -f

# بررسی وضعیت سرویس
systemctl status night-leech
```

---

## عیب‌یابی

به [راهنمای عیب‌یابی](./troubleshooting.md) مراجعه کنید.
