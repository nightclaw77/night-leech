# 🚀 راهنمای راه‌اندازی Night Leech Bot

## مرحله 1: ورود به VPS

```bash
ssh night@2.59.133.224
```

---

## مرحله 2: اضافه کردن به گروه Docker

```bash
# اضافه کردن به گروه docker
sudo usermod -aG docker $USER

# فعال کردن تغییرات (یا logout/login)
newgrp docker
```

---

## مرحله 3: رفتن به پوشه پروژه

```bash
cd ~/night-leech/bot-code
ls -la
```

---

## مرحله 4: ساخت ایمیج Docker

```bash
docker build . -t night-leech-bot
```

---

## مرحله 5: اجرای ربات

```bash
# روش الف: اجرای ساده
docker run -d \
  --name night-leech \
  -v $(pwd)/config.py:/app/config.py \
  -v $(pwd)/downloads:/app/downloads \
  night-leech-bot

# روش ب: با لاگ زنده
docker run -it --rm \
  -v $(pwd)/config.py:/app/config.py \
  -v $(pwd)/downloads:/app/downloads \
  night-leech-bot
```

---

## مرحله 6: بررسی وضعیت

```bash
# بررسی لاگ‌ها
docker logs night-leech -f

# بررسی وضعیت
docker ps

# توقف ربات
docker stop night-leech

# حذف ربات
docker rm night-leech
```

---

## 📋 خلاصه دستورات

```
╔═══════════════════════════════════════════════════════════════╗
║  دستورات مهم Docker                                        ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  ساخت ایمیج:    docker build . -t night-leech-bot            ║
║  اجرا:          docker run -d --name night-leech ...          ║
║  لاگ:           docker logs night-leech -f                   ║
║  وضعیت:         docker ps                                    ║
║  توقف:          docker stop night-leech                      ║
║  حذف:           docker rm night-leech                        ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
```

---

## ❌ اگه خطای gcc دادی:

```bash
sudo apt-get update
sudo apt-get install -y build-essential python3-dev gcc g++
```

---

## ✅ بعد از اجرا:

1. به تلگرام برو
2. ربات `@night_leech_bot` رو پیدا کن
3. `/start` بزن
4. `/mirror <link>` بفرست

---

## 📞 اگه مشکلی بود:

```bash
# بررسی لاگ‌ها
docker logs night-leech
```

---

**موفق باشی!** 🌙
