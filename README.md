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

## Serverda (systemd)

```bash
systemctl restart navbatchi     # qayta ishga tushirish
systemctl status navbatchi      # holat
journalctl -u navbatchi -f      # loglar
```

⚠️ **Muhim:** kodni o'zgartirgandan keyin `systemctl restart navbatchi` qilishni unutmang — aks holda eski kod ishlab turaveradi.

## Fayllar

- `navbatchi_bot.py` — asosiy kod
- `.env` — bot tokeni (GitHub'ga tushmaydi)
- `*.json` — ish paytida yaratiladigan data fayllar (GitHub'ga tushmaydi)

<!-- deploy test 18:48:11 -->
