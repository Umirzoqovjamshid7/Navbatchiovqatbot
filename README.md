# Navbatchi Bot

Telegram bot — ikki vazifani bajaradi:
1. **Navbatchi** — har kuni 12:30 da navbatchilarni guruhda e'lon qiladi.
2. **Ovqat so'rovnoma** — har kuni 18:00 da tushlik so'rovi, 06:00 da yopiladi, shanba 06:05 da haftalik hisobot.

## O'rnatish

```bash
# 1. Kutubxonalar
pip install python-telegram-bot python-dotenv

# 2. Maxfiy sozlama
cp .env.example .env
# .env ni ochib BOT_TOKEN qiymatini yozing

# 3. Ishga tushirish
python3 navbatchi_bot.py
```

## Ish tartibi (avto-deploy)

Kodni GitHub'da o'zgartirib push qiling — server har 2 daqiqada o'zi tekshiradi,
yangi kod bo'lsa avtomatik yuklab oladi va botni qayta ishga tushiradi.
Serverga qo'lda kirish shart emas.

## Serverdagi avtomatlashtirish (systemd)

```bash
systemctl status navbatchi          # bot holati
journalctl -u navbatchi -f          # bot loglari
systemctl list-timers 'navbatchi-*' # avto-deploy va backup timerlar
```

- `navbatchi.service` — botning o'zi (24/7)
- `navbatchi-deploy.timer` — GitHub'dan avtomatik yangilash (har 2 daqiqa)
- `navbatchi-backup.timer` — data JSON'larni GitHub'ga avto-backup (kuniga 07:00)

## Fayllar

- `navbatchi_bot.py` — asosiy kod
- `.env` — bot tokeni (GitHub'ga tushmaydi, faqat serverda)
- `*.json` — data fayllar (backup uchun GitHub'da saqlanadi)
- `auto_deploy.sh`, `data_backup.sh` — avtomatlashtirish skriptlari
