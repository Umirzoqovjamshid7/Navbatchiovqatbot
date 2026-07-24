#!/bin/bash
# GitHub'dan yangi kod kelsa avtomatik yuklaydi va botni qayta ishga tushiradi.
# navbatchi-deploy.timer orqali har 2 daqiqada tekshiradi.
cd /root/navbatchi || exit 1

git fetch origin main -q 2>/dev/null || exit 0

LOCAL=$(git rev-parse @ 2>/dev/null)
REMOTE=$(git rev-parse origin/main 2>/dev/null)

# GitHub'da yangilik yo'q bo'lsa — hech narsa qilmaydi
if [ "$LOCAL" = "$REMOTE" ]; then
    exit 0
fi

# Yangi kod bor — birlashtiramiz (data faqat serverda, kod faqat GitHub'da o'zgargani uchun to'qnashuv bo'lmaydi)
if git merge --no-edit origin/main -q 2>/dev/null; then
    systemctl restart navbatchi
    echo "$(date '+%F %T') | ✅ GitHub'dan yangilandi, bot restart qilindi."
else
    git merge --abort 2>/dev/null
    echo "$(date '+%F %T') | ⚠️ Avtomatik birlashtirib bo'lmadi — qo'lda tekshirish kerak."
    exit 1
fi
