# 🌙 Night Leech Bot

Telegram Mirror/Leech Bot - Backup Repository for Night Army

## 📋 Project Overview

این مخزن برای نگهداری تنظیمات، مستندات و بکاپ پروژه لیچر تلگرام استفاده می‌شود.

---

## 🚀 Quick Start

### پیش‌نیازها
- VPS با Ubuntu 20.04+
- Python 3.12+
- Git
- Docker (اختیاری، توصیه می‌شود)

### نصب سریع
```bash
git clone https://github.com/nightclaw77/night-leech.git
cd night-leech
chmod +x setup.sh
./setup.sh
```

---

## 📁 Project Structure

```
night-leech/
├── README.md                    # این فایل
├── config/
│   ├── config.env.example       # نمونه کانفیگ
│   └── api-keys-checklist.md   # چک‌لیست API Keyها
├── docs/
│   ├── installation.md         # راهنمای نصب
│   ├── usage.md                # راهنمای استفاده
│   └── troubleshooting.md       # عیب‌یابی
├── scripts/
│   ├── setup.sh                # اسکریپت نصب
│   ├── start.sh                # اسکریپت اجرا
│   └── backup.sh               # اسکریپت بکاپ
├── .env.example                # محیط توسعه
└── .gitignore                  # فایل‌های نادیده گرفته شده
```

---

## 🔧 Configuration

### تنظیمات تلگرام (ضروری)
| متغیر | توضیح | منبع |
|-------|-------|------|
| `BOT_TOKEN` | توکن ربات تلگرام | @BotFather |
| `OWNER_ID` | آی‌دی تلگرام شما | @userinfobot |
| `TELEGRAM_API` | API ID تلگرام | my.telegram.org |
| `TELEGRAM_HASH` | API Hash تلگرام | my.telegram.org |

### تنظیمات آپلود
| متغیر | مقدار پیش‌فرض | توضیح |
|-------|--------------|-------|
| `DEFAULT_UPLOAD` | `tg` | آپلود به تلگرام |
| `MAX_FILE_SIZE` | `2097152000` | حداکثر حجم فایل |

---

## 📚 Documentation

- [راهنمای نصب](./docs/installation.md)
- [راهنمای استفاده](./docs/usage.md)
- [عیب‌یابی](./docs/troubleshooting.md)
- [چک‌لیست API Keyها](./config/api-keys-checklist.md)

---

## ⚠️ نکات مهم

1. **هیچ‌گاه** فایل `config.env` را در گیت آپلود نکنید
2. از `.env.example` به عنوان الگو استفاده کنید
3. API Keyها را در مکان امن نگهداری کنید
4. به صورت منظم از تنظیمات بکاپ بگیرید

---

## 🔒 امنیت

- این مخزن **خصوصی** (Private) تنظیم شده است
- فایل‌های حساس در `.gitignore` لیست شده‌اند
- تنظیمات در فایل جداگانه نگهداری می‌شوند

---

## 📞 ارتباط

- **مدیر:** Night (@Night_walker77)
- **وضعیت:** 🚧 در حال توسعه

---

## 📝 License

MIT License - استفاده شخصی
