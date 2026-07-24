#!/bin/bash
# Navbatchi bot data (JSON) fayllarini avtomatik GitHub'ga saqlaydi.
# navbatchi-backup.timer orqali kuniga bir marta ishlaydi.
cd /root/navbatchi || exit 1

git add -- *.json 2>/dev/null

# O'zgarish bo'lmasa — hech narsa qilmaydi
if git diff --cached --quiet; then
    echo "$(date '+%F %T') | O'zgarish yo'q, backup shart emas."
    exit 0
fi

git commit -q -m "Avto data-backup: $(date '+%F %H:%M')"
if git push -q 2>/dev/null; then
    echo "$(date '+%F %T') | ✅ Data GitHub'ga saqlandi."
else
    echo "$(date '+%F %T') | ⚠️ Push bo'lmadi (internet/token?)."
    exit 1
fi
