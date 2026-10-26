# 🤖 GitHub Actions Workflow Monitor Agent

Ushbu agent sizning GitHub hisobingizdagi barcha repolarni (shaxsiy va ommaviy) tekshirib boradi. Agar qaysidir loyihangizda CI/CD workflow xato bersa (Failure) yoki muvaffaqiyatli yakunlansa, darhol Telegram botingizga batafsil ma'lumot (muallif, commit xabari, xato bergan qadam) va Gemini AI orqali yechim bo'yicha maslahat yuboradi.

---

## 📁 Loyiha tarkibi
- `main.py` — Agentning asosiy kodi (GitHub API, Gemini AI va Telegram bilan ishlaydi).
- `.env.example` — Kalitlar va konfiguratsiyalar namunasi.
- `requirements.txt` — Kerakli kutubxonalar (`requests`, `google-genai`, `python-dotenv`).
- `.github/workflows/monitor.yml` — Loyihani 24/7 bepul GitHub Actions orqali yurgazish ssenariysi.

---

## 🔑 Kerakli Tokenlarni olish

### 1. Telegram Bot Token va Chat ID
1. Telegramda [@BotFather](https://t.me/botfather) ga kiring va `/newbot` buyrug'ini yuboring.
2. Botga nom va username bering (masalan: `my_gh_monitor_bot`).
3. BotFather sizga **API Token** beradi (masalan: `782348234:AAHq_...`). Uni saqlab oling (`TELEGRAM_BOT_TOKEN`).
4. Yangi ochilgan botingizga kiring va **/start** tugmasini bosing! (Bu juda muhim, aks holda bot sizga xabar yubora olmaydi).
5. O'zingizning Telegram **Chat ID** raqamingizni bilish uchun [@userinfobot](https://t.me/userinfobot) ga kiring va `/start` bosing. U sizga `Id: 123456789` raqamingizni ko'rsatadi (`TELEGRAM_CHAT_ID`).

### 2. GitHub Personal Access Token (PAT)
1. GitHub-ga kiring: [github.com/settings/tokens](https://github.com/settings/tokens).
2. **Generate new token** $\rightarrow$ **Generate new token (classic)** tugmasini bosing.
3. *Note* qismiga ixtiyoriy nom bering (masalan: `Workflow Monitor`).
4. Quyidagi katakchalarga (scopes) **belgi qo'ying**:
   - `repo` (Barcha repolar va statuslarni o'qish uchun to'liq ruxsat).
   - `workflow` (Workflow run holatlarini o'qish uchun).
5. Pastdagi yashil **Generate token** tugmasini bosing va hosil bo'lgan tokenni nusxalab oling (`GITHUB_TOKEN`). *(Eslatma: bu tokenni keyin qayta ko'rib bo'lmaydi).*

### 3. Google Gemini API Key (Ixtiyoriy - Xatolarni tahlil qilish uchun)
1. [Google AI Studio (aistudio.google.com)](https://aistudio.google.com/) saytiga kiring.
2. **Get API Key** tugmasini bosing va yangi bepul kalit oling (`GEMINI_API_KEY`).

---

## 💻 1-Usul: O'z kompyuteringizda (Lokal) ishlatish

1. Loyiha papkasida `.env.example` faylidan nusxa olib, nomini `.env` deb o'zgartiring.
2. `.env` faylini ochib, o'zingizning tokenlaringizni yozing:
   ```ini
   GITHUB_TOKEN=ghp_sizning_tokeningiz
   TELEGRAM_BOT_TOKEN=123456789:ABC...
   TELEGRAM_CHAT_ID=123456789
   GEMINI_API_KEY=AIzaSy...
   NOTIFY_ON_SUCCESS=false
   ```
3. Kutubxonalarni o'rnating:
   ```bash
   pip install -r requirements.txt
   ```
4. Agentni ishga tushiring:
   ```bash
   python main.py
   ```

---

## ☁️ 2-Usul: Kompyuterni yoqmasdan, 24/7 Bepul ishlatish (GitHub Actions orqali)

Agar ushbu agent 24/7 davomida avtomatik ishlab turishini xohlasangiz:

1. GitHub-da yangi shaxsiy repo oching (masalan, `github-monitor-agent`, Private rejimida).
2. Ushbu papkadagi barcha fayllarni shu yangi repoga `git push` qiling.
3. Repongizning **Settings** $\rightarrow$ **Secrets and variables** $\rightarrow$ **Actions** bo'limiga kiring:
4. **New repository secret** tugmasini bosib, quyidagi 4 ta sirli kalitni kiriting:
   - `MY_GITHUB_TOKEN` — siz olgan GitHub PAT token.
   - `TELEGRAM_BOT_TOKEN` — Telegram bot tokeni.
   - `TELEGRAM_CHAT_ID` — Telegram Chat ID raqamingiz.
   - `GEMINI_API_KEY` — Google Gemini API kaliti (agar kerak bo'lsa).
5. Bo'ldi! `.github/workflows/monitor.yml` har 15 daqiqada avtomatik ishlab, Telegramingizga yangi xato yoki natijalar haqida xabar berib turadi.
