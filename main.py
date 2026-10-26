import os
import json
import requests
from datetime import datetime

# Local .env fayli bo'lsa uni o'qish (ixtiyoriy)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Konfiguratsiya va sozlamalar
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
NOTIFY_ON_SUCCESS = os.getenv("NOTIFY_ON_SUCCESS", "false").lower() in ("true", "1", "yes")

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "last_seen_runs.json")

def get_headers():
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }

def send_telegram(text: str):
    """Telegramga xabar yuborish."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[OGOHLANTIRISH] Telegram token yoki Chat ID belgilanmagan!")
        return
        
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try:
        res = requests.post(url, json=payload, timeout=15)
        if res.status_code != 200:
            print(f"Telegram yuborishda xato ({res.status_code}): {res.text}")
    except Exception as e:
        print(f"Telegram tarmoq xatosi: {e}")

def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_state(state: dict):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"Holatni saqlashda xato: {e}")

def get_failed_step_details(repo_full_name: str, run_id: int) -> str:
    """Xato bergan aniq job va qadam (step) nomini aniqlash."""
    headers = get_headers()
    jobs_url = f"https://api.github.com/repos/{repo_full_name}/actions/runs/{run_id}/jobs"
    try:
        res = requests.get(jobs_url, headers=headers, timeout=15)
        if res.status_code == 200:
            data = res.json()
            for job in data.get("jobs", []):
                if job.get("conclusion") == "failure":
                    job_name = job.get("name", "Job")
                    # Failed stepni topish
                    for step in job.get("steps", []):
                        if step.get("conclusion") == "failure":
                            return f"Job: `{job_name}`, Step: `{step.get('name')}`"
                    return f"Job: `{job_name}`"
    except Exception:
        pass
    return "Noma'lum qadam"

def ask_gemini_for_tip(repo_name: str, workflow_name: str, failed_step: str, commit_msg: str) -> str:
    """Gemini orqali xatolikni bartaraf qilish uchun 1-2 jumla maslahat olish."""
    if not GEMINI_API_KEY:
        return ""
    
    prompt = (
        f"Loyiham: '{repo_name}'\n"
        f"Workflow: '{workflow_name}'\n"
        f"Xato bergan bosqich: '{failed_step}'\n"
        f"Oxirgi commit: '{commit_msg}'\n"
        f"Vazifa: Dasturchiga o'zbek tilida ushbu GitHub Actions xatosini qanday tuzatish bo'yicha "
        f"aniq, londa 1 yoki 2 jumlada maslahat ber. Ortiqcha so'z yozma."
    )
    
    # 1. google-genai SDK orqali
    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        if response and response.text:
            return response.text.strip()
    except Exception:
        pass

    # 2. To'g'ridan-to'g'ri REST API orqali (fallback)
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        r = requests.post(url, json=payload, timeout=15)
        if r.status_code == 200:
            return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception:
        pass

    return ""

def escape_markdown(text: str) -> str:
    """Maxsus belgilarni Telegram Markdown formatiga moslash."""
    if not text:
        return ""
    return text.replace("`", "'")

def run_agent():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Workflowlarni tekshirish boshlandi...")
    
    if not GITHUB_TOKEN:
        print("[XATO] GITHUB_TOKEN mavjud emas! .env faylini to'ldiring.")
        return

    state = load_state()
    headers = get_headers()

    # Foydalanuvchining barcha repolarini olish (shaxsiy + a'zo bo'lgan)
    repos_url = "https://api.github.com/user/repos?per_page=100&sort=updated"
    try:
        repos_res = requests.get(repos_url, headers=headers, timeout=20)
    except Exception as e:
        print(f"GitHub API bilan bog'lanishda xato: {e}")
        return

    if repos_res.status_code != 200:
        print(f"GitHub API xatosi ({repos_res.status_code}): {repos_res.text}")
        return

    repos = repos_res.json()
    print(f"Jami {len(repos)} ta repository topildi.")

    new_runs_count = 0

    for repo in repos:
        repo_full_name = repo["full_name"]
        
        # Ushbu repo uchun oxirgi 3 ta run ni olish
        runs_url = f"https://api.github.com/repos/{repo_full_name}/actions/runs?per_page=3"
        try:
            runs_res = requests.get(runs_url, headers=headers, timeout=15)
            if runs_res.status_code != 200:
                continue
            runs_data = runs_res.json().get("workflow_runs", [])
        except Exception:
            continue

        if not runs_data:
            continue

        latest_run = runs_data[0]
        run_id = latest_run["id"]
        status = latest_run.get("status")          # completed, queued, in_progress
        conclusion = latest_run.get("conclusion")  # success, failure, cancelled, timed_out

        last_known = state.get(repo_full_name, {})
        # Oldingi saqlangan run_id va conclusion bilan solishtiramiz
        if isinstance(last_known, int):
            last_known_id = last_known
            last_known_conclusion = None
        else:
            last_known_id = last_known.get("id")
            last_known_conclusion = last_known.get("conclusion")

        # Faqat run tugagan bo'lsa (completed) yoki yangi bo'lsa tekshiramiz
        is_new_run = (last_known_id != run_id)
        status_changed = (last_known_id == run_id and last_known_conclusion != conclusion and status == "completed")

        if is_new_run or status_changed:
            new_runs_count += 1
            wf_name = escape_markdown(latest_run.get("name", "Workflow"))
            branch = latest_run.get("head_branch", "main")
            commit_msg = escape_markdown(latest_run.get("head_commit", {}).get("message", "Commit xabari yo'q").split("\n")[0])
            actor = latest_run.get("actor", {}).get("login", "Noma'lum")
            html_url = latest_run.get("html_url")
            created_at = latest_run.get("created_at", "").replace("Z", "").replace("T", " ")

            if conclusion == "failure":
                failed_step = get_failed_step_details(repo_full_name, run_id)
                ai_tip = ask_gemini_for_tip(repo_full_name, wf_name, failed_step, commit_msg)
                
                tip_section = f"\n💡 *AI Tavsiyasi:*\n_{ai_tip}_\n" if ai_tip else ""

                msg = (
                    f"🚨 *GitHub Actions Xatoligi!*\n\n"
                    f"📁 *Repo:* `{repo_full_name}`\n"
                    f"⚙️ *Workflow:* `{wf_name}`\n"
                    f"🌿 *Branch:* `{branch}`\n"
                    f"👤 *Muallif:* @{actor}\n"
                    f"💬 *Commit:* _{commit_msg}_\n"
                    f"❌ *Xato qismi:* {failed_step}\n"
                    f"🕒 *Vaqt:* `{created_at}`\n"
                    f"{tip_section}\n"
                    f"🔗 [Xatolik loglarini ochish]({html_url})"
                )
                print(f"Xatolik topildi: {repo_full_name} -> {wf_name}")
                send_telegram(msg)

            elif conclusion == "success" and NOTIFY_ON_SUCCESS:
                msg = (
                    f"✅ *Workflow muvaffaqiyatli yakunlandi*\n\n"
                    f"📁 *Repo:* `{repo_full_name}`\n"
                    f"⚙️ *Workflow:* `{wf_name}`\n"
                    f"🌿 *Branch:* `{branch}`\n"
                    f"👤 *Muallif:* @{actor}\n"
                    f"💬 *Commit:* _{commit_msg}_\n"
                    f"🕒 *Vaqt:* `{created_at}`\n\n"
                    f"🔗 [Ish jarayonini ko'rish]({html_url})"
                )
                print(f"Muvaffaqiyatli run: {repo_full_name} -> {wf_name}")
                send_telegram(msg)

            # Yangi holatni eslab qolamiz
            state[repo_full_name] = {
                "id": run_id,
                "status": status,
                "conclusion": conclusion
            }

    save_state(state)
    print(f"Tekshirish tugadi. Yangilangan workflowlar soni: {new_runs_count}")

if __name__ == "__main__":
    run_agent()
