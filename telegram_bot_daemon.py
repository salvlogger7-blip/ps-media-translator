import sys
if hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding='utf-8')
    except: pass
if hasattr(sys.stderr, 'reconfigure'):
    try: sys.stderr.reconfigure(encoding='utf-8')
    except: pass

import urllib.request
import json
import time
import os
import re
from datetime import datetime, timedelta

TG_BOT_TOKEN = "8928655174:AAGpYf-8kHhPCRRBcj21bvJ-sGXtxk5tlUE"
TG_ADMIN_CHAT_ID = "925539914"  # ONLY this chat ID can access the bot!
FIREBASE_URL = "https://ps-media-app-default-rtdb.firebaseio.com"
LOCAL_HISTORY_FILE = os.path.join(os.path.dirname(__file__), "purchase_history_90d.json")

print("=" * 65)
print("🚀 PS Media Telegram Admin Daemon V3.5 (BotFather Style Menu & Pricing)")
print(f"🔒 Security Lock: ONLY Admin Chat ID [{TG_ADMIN_CHAT_ID}] Allowed")
print("=" * 65)

# -------------------------------------------------------------
# 24/7 CLOUD HOSTING COMPATIBILITY (Render / Koyeb / VPS)
# -------------------------------------------------------------
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

class CloudHealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write("PS Media Telegram Admin Bot is Running 24/7 Online!".encode("utf-8"))

    def log_message(self, format, *args):
        pass  # Quiet logs

def start_cloud_health_server():
    port = int(os.environ.get("PORT", 8080))
    try:
        server = HTTPServer(("0.0.0.0", port), CloudHealthHandler)
        print(f"🌐 Cloud Health Server listening on port {port} (24/7 Active)")
        server.serve_forever()
    except Exception as e:
        pass

threading.Thread(target=start_cloud_health_server, daemon=True).start()

last_update_id = 0

PACKAGE_PRICES = {
    3: {"name": "សាកល្បង ៣ ថ្ងៃ (Trial)", "usd": "0.01", "khr": "50 ៛", "badge": "Trial"},
    7: {"name": "កញ្ចប់ ១ អាទិត្យ (7 Days)", "usd": "1.50", "khr": "6,000 ៛", "badge": "1 អាទិត្យ"},
    15: {"name": "កញ្ចប់ ១៥ ថ្ងៃ (15 Days)", "usd": "2.50", "khr": "10,000 ៛", "badge": "15 ថ្ងៃ"},
    30: {"name": "កញ្ចប់ ១ ខែ (30 Days)", "usd": "5.00", "khr": "20,000 ៛", "badge": "1 ខែ"},
    90: {"name": "កញ្ចប់ ៣ ខែ (90 Days)", "usd": "10.00", "khr": "40,000 ៛", "badge": "⭐ 3 ខែ"},
    365: {"name": "កញ្ចប់ ១ ឆ្នាំ (365 Days)", "usd": "30.00", "khr": "120,000 ៛", "badge": "👑 1 ឆ្នាំ"}
}

# ==========================================
# 3-MONTH PURCHASE MEMORY FUNCTIONS
# ==========================================
def load_local_history():
    if os.path.exists(LOCAL_HISTORY_FILE):
        try:
            with open(LOCAL_HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_local_history(data):
    try:
        with open(LOCAL_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("Save local history error:", e)

def record_purchase_event(bill_no, customer_name, hwid, pc_name, plan, amount):
    now = datetime.now()
    event = {
        "bill_no": bill_no,
        "customer_name": customer_name,
        "hwid": hwid,
        "pc_name": pc_name,
        "plan": plan,
        "amount": amount,
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%I:%M:%S %p"),
        "timestamp": now.isoformat()
    }
    
    # 1. Save to Local JSON
    history = load_local_history()
    history[bill_no] = event
    
    # 2. Prune records older than 90 days (3 months)
    cutoff = now - timedelta(days=90)
    pruned_history = {}
    for b, rec in history.items():
        try:
            rec_dt = datetime.fromisoformat(rec.get("timestamp", ""))
            if rec_dt >= cutoff:
                pruned_history[b] = rec
        except Exception:
            pruned_history[b] = rec
            
    save_local_history(pruned_history)

    # 3. Save to Firebase /purchase_history
    try:
        url = f"{FIREBASE_URL}/purchase_history/{bill_no}.json"
        p_bytes = json.dumps(event).encode('utf-8')
        req = urllib.request.Request(url, data=p_bytes, headers={'Content-Type': 'application/json'}, method='PUT')
        urllib.request.urlopen(req, timeout=4)
    except Exception as e:
        print("Firebase purchase_history error:", e)

def prune_firebase_history_90d():
    """Auto cleans any Firebase records older than 90 days (3 months)"""
    try:
        url = f"{FIREBASE_URL}/purchase_history.json"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if not data: return
            
            cutoff = datetime.now() - timedelta(days=90)
            for b_no, rec in list(data.items()):
                try:
                    ts = rec.get("timestamp")
                    if ts and datetime.fromisoformat(ts) < cutoff:
                        del_url = f"{FIREBASE_URL}/purchase_history/{b_no}.json"
                        urllib.request.urlopen(urllib.request.Request(del_url, method='DELETE'), timeout=3)
                except Exception:
                    pass
    except Exception:
        pass

# ==========================================
# TELEGRAM API HELPERS
# ==========================================
def setup_bot_commands():
    try:
        url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/setMyCommands"
        commands = [
            {"command": "start", "description": "🏠 បើកផ្ទាំង Menu ដើម (BotFather Style)"},
            {"command": "playlist", "description": "📋 បញ្ជីភ្ញៀវទាំងអស់ (Playlist)"},
            {"command": "online", "description": "🟢 ភ្ញៀវកំពុង Online"},
            {"command": "today", "description": "📅 ការទិញថ្ងៃនេះ (Today)"},
            {"command": "memory", "description": "📜 អង្គចងចាំ ៣ ខែ (Archive)"},
            {"command": "add", "description": "➕ បន្ថែមថ្ងៃ និងតម្លៃ (Add Days)"},
            {"command": "stats", "description": "📊 ស្ថិតិប្រព័ន្ធសរុប"}
        ]
        payload = json.dumps({"commands": commands}).encode('utf-8')
        req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(req, timeout=5)
        print("Telegram setMyCommands configured successfully!")
    except Exception as e:
        print("setMyCommands error:", e)

def send_msg(chat_id, text, reply_markup=None):
    try:
        url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        p_bytes = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=p_bytes, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data.get("result", {}).get("message_id")
    except Exception as e:
        print("Send msg error:", e)
        return None

def edit_msg(chat_id, message_id, text, reply_markup=None):
    # 1. Try editMessageText (for text messages)
    try:
        url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/editMessageText"
        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "HTML"
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        p_bytes = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=p_bytes, headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(req, timeout=5)
        return
    except Exception:
        pass

    # 2. If it failed (e.g. photo message with caption), call editMessageCaption
    try:
        url_cap = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/editMessageCaption"
        payload_cap = {
            "chat_id": chat_id,
            "message_id": message_id,
            "caption": text,
            "parse_mode": "HTML"
        }
        if reply_markup is not None:
            payload_cap["reply_markup"] = reply_markup
        p_bytes = json.dumps(payload_cap).encode('utf-8')
        req = urllib.request.Request(url_cap, data=p_bytes, headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        print("Edit msg/caption error:", e)

def delete_msg(chat_id, message_id):
    try:
        url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/deleteMessage"
        payload = {"chat_id": chat_id, "message_id": message_id}
        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(req, timeout=4)
    except Exception:
        pass

def answer_callback(cq_id, text=None, show_alert=False):
    try:
        url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/answerCallbackQuery"
        payload = {"callback_query_id": cq_id}
        if text:
            payload["text"] = text
            payload["show_alert"] = show_alert
        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(req, timeout=4)
    except Exception:
        pass

def get_admin_keyboard():
    return {
        "keyboard": [
            [{"text": "📋 បញ្ជីភ្ញៀវ (Playlist)"}, {"text": "🟢 ភ្ញៀវ Online"}],
            [{"text": "📅 ការទិញថ្ងៃនេះ (Today)"}, {"text": "📜 អង្គចងចាំ ៣ ខែ"}],
            [{"text": "➕ បន្ថែមថ្ងៃ (Add Days)"}, {"text": "📊 ស្ថិតិសរុប (Stats)"}]
        ],
        "resize_keyboard": True,
        "is_persistent": True
    }

def get_admin_inline_menu():
    return {
        "inline_keyboard": [
            [
                {"text": "📋 បញ្ជីភ្ញៀវ (Playlist)", "callback_data": "menu_playlist"},
                {"text": "🟢 ភ្ញៀវ Online", "callback_data": "menu_online"}
            ],
            [
                {"text": "📅 ការទិញថ្ងៃនេះ (Today)", "callback_data": "menu_today"},
                {"text": "📜 អង្គចងចាំ ៣ ខែ", "callback_data": "menu_memory"}
            ],
            [
                {"text": "➕ បន្ថែមថ្ងៃ (Add Days)", "callback_data": "menu_add_days"},
                {"text": "📊 ស្ថិតិសរុប (Stats)", "callback_data": "menu_stats"}
            ]
        ]
    }

def build_main_menu_content():
    now_str = datetime.now().strftime('%d/%m/%Y %I:%M %p')
    text = (
        "👑 <b>ផ្ទាំងគ្រប់គ្រង PS MEDIA App Admin 24/7</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "👋 <b>សួស្តី Admin SAN PISAL!</b>\n\n"
        "👉 <i>សូមចុចជ្រើសរើសមុខងារខាងក្រោមដើម្បីពិនិត្យមើល៖</i>\n"
        "• <b>📋 បញ្ជីភ្ញៀវ</b> : មើលឈ្មោះ, HWID & ថ្ងៃសល់ (លាក់ទុកតាមស្តង់ដារ)\n"
        "• <b>🟢 ភ្ញៀវ Online</b> : ពិនិត្យអ្នកកំពុងបើកប្រើជាក់ស្តែង\n"
        "• <b>📅 ការទិញថ្ងៃនេះ</b> : បង្ហាញការទិញថ្ងៃនេះ (Reset រៀងរាល់ថ្ងៃថ្មី)\n"
        "• <b>📜 អង្គចងចាំ ៣ ខែ</b> : ប្រវត្តិទិញ 90 ថ្ងៃពេញលេញ\n"
        "• <b>➕ បន្ថែមថ្ងៃ</b> : ជ្រើសរើសកញ្ចប់ថ្ងៃ និងតម្លៃលុយជាក់ស្តែង\n"
        "• <b>📊 ស្ថិតិសរុប</b> : ទិន្នន័យម៉ាស៊ីន និងការប្រើប្រាស់\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"⏰ <i>{now_str}</i>"
    )
    return text, get_admin_inline_menu()

# ==========================================
# USER & STATUS HELPERS
# ==========================================
def get_firebase_users():
    try:
        url = f"{FIREBASE_URL}/users.json"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data or {}
    except Exception as e:
        print("Fetch users error:", e)
        return {}

def get_remaining_seconds(user_data):
    exp_str = user_data.get("expiry", "")
    if exp_str:
        try:
            exp_dt = datetime.fromisoformat(exp_str.replace("Z", "+00:00")).replace(tzinfo=None)
            return (exp_dt - datetime.now()).total_seconds()
        except Exception:
            return -999999
    return -999999

def parse_user_status(user_data):
    # Online/Offline check
    last_seen_str = user_data.get("last_seen", "")
    is_online = False
    status_text = "⚪ OFFLINE"

    if last_seen_str:
        try:
            ls_dt = datetime.fromisoformat(last_seen_str.replace("Z", "+00:00")).replace(tzinfo=None)
            diff = datetime.now() - ls_dt
            diff_secs = diff.total_seconds()
            if diff_secs <= 180:
                is_online = True
                status_text = "🟢 Online"
            else:
                m = int(diff_secs // 60)
                if m < 60:
                    status_text = f"⚪ Offline ({m}m មុន)"
                elif m < 1440:
                    status_text = f"⚪ Offline ({m // 60}h មុន)"
                else:
                    status_text = f"⚪ Offline ({m // 1440}d មុន)"
        except Exception:
            status_text = "⚪ Offline"

    # Expiry remaining days
    rem_secs = get_remaining_seconds(user_data)
    if rem_secs > 0:
        days = int(rem_secs // 86400)
        hours = int((rem_secs % 86400) // 3600)
        mins = int((rem_secs % 3600) // 60)
        if days > 3000:
            rem_badge = "👑 LIFETIME VIP"
            days_str = "LIFETIME"
        else:
            rem_badge = f"⏳ សល់ {days} ថ្ងៃ {hours:02d}h {mins:02d}m"
            days_str = f"{days} ថ្ងៃ"
    else:
        rem_badge = "🚫 ផុតកំណត់"
        days_str = "0 ថ្ងៃ"

    return is_online, status_text, rem_badge, days_str

# ==========================================
# PLAYLIST BUILDER (SINGLE MESSAGE)
# ==========================================
def build_playlist_content(only_online=False):
    users = get_firebase_users()
    if not users:
        markup = {"inline_keyboard": [[{"text": "🔙 ត្រឡប់ទៅ Menu ដើម", "callback_data": "menu_home"}]]}
        return "ℹ️ មិនទាន់មានទិន្នន័យអតិថិជនក្នុងប្រព័ន្ធនៅឡើយទេ។", markup

    # SORT BY REMAINING DAYS DESCENDING (So 70+ days clients show first!)
    sorted_users = sorted(users.items(), key=lambda item: get_remaining_seconds(item[1]), reverse=True)

    if only_online:
        sorted_users = [u for u in sorted_users if parse_user_status(u[1])[0]]
        if not sorted_users:
            markup = {"inline_keyboard": [
                [{"text": "🔄 Refresh", "callback_data": "refresh_online"}],
                [{"text": "🔙 ត្រឡប់ទៅ Menu ដើម", "callback_data": "menu_home"}]
            ]}
            return "⚪ <b>បច្ចុប្បន្នគ្មានភ្ញៀវណាកំពុង Online ឡើយ។</b>", markup

    lines = []
    header_title = "🟢 <b>បញ្ជីភ្ញៀវកំពុង ONLINE</b>" if only_online else "📋 <b>បញ្ជីឈ្មោះអតិថិជន PS MEDIA (Playlist)</b>"
    lines.append(header_title)
    lines.append("━━━━━━━━━━━━━━━━━━━━")

    online_count = 0
    offline_count = 0

    select_buttons = []
    row = []

    for idx, (hwid, u_info) in enumerate(sorted_users[:25], 1):
        c_name = u_info.get("customer_name") or "Customer"
        pc_name = u_info.get("pc_name") or "PC"
        is_on, status_str, rem_badge, days_str = parse_user_status(u_info)
        
        if is_on: online_count += 1
        else: offline_count += 1

        icon = "🟢" if is_on else "⚪"
        lines.append(f"<b>{idx}.</b> {icon} <b>{c_name}</b> • {rem_badge}")
        lines.append(f"    💻 <code>{hwid[-8:]}</code> | PC: <code>{pc_name}</code> ({status_str})")
        lines.append("────────────────────")

        btn_label = f"{idx}. {c_name[:10]} ({days_str})"
        row.append({"text": btn_label, "callback_data": f"ext_u:{hwid}"})
        if len(row) == 2:
            select_buttons.append(row)
            row = []

    if row:
        select_buttons.append(row)

    lines.append(f"📊 <b>សរុប៖ {len(sorted_users)} នាក់</b> | 🟢 Online: <b>{online_count}</b> | ⚪ Offline: <b>{offline_count}</b>")

    control_row = [
        {"text": "🔄 Refresh", "callback_data": "refresh_online" if only_online else "refresh_playlist"},
        {"text": "🔙 ត្រឡប់ទៅ Menu ដើម", "callback_data": "menu_home"}
    ]
    select_buttons.insert(0, control_row)

    reply_markup = {"inline_keyboard": select_buttons[:14]}
    return "\n".join(lines), reply_markup

# ==========================================
# CLIENT PICKER FOR ADD DAYS
# ==========================================
def build_add_days_client_picker():
    users = get_firebase_users()
    if not users:
        text = "ℹ️ មិនទាន់មានទិន្នន័យអតិថិជនក្នុងប្រព័ន្ធនៅឡើយទេ។"
        markup = {"inline_keyboard": [[{"text": "🔙 ត្រឡប់ទៅ Menu ដើម", "callback_data": "menu_home"}]]}
        return text, markup

    sorted_users = sorted(users.items(), key=lambda item: get_remaining_seconds(item[1]), reverse=True)
    
    text = (
        "➕ <b>ជ្រើសរើសអតិថិជនដើម្បីបន្ថែមថ្ងៃ និងតម្លៃ៖</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "👉 <i>សូមចុចលើឈ្មោះអតិថិជនខាងក្រោមដើម្បីជ្រើសរើសកញ្ចប់ថ្ងៃ៖</i>"
    )
    
    buttons = []
    row = []
    for idx, (hwid, u_info) in enumerate(sorted_users[:20], 1):
        c_name = u_info.get("customer_name") or "Customer"
        _, _, _, days_str = parse_user_status(u_info)
        btn_label = f"{idx}. {c_name[:10]} ({days_str})"
        row.append({"text": btn_label, "callback_data": f"ext_u:{hwid}"})
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
        
    buttons.append([{"text": "🔙 ត្រឡប់ទៅ Menu ដើម", "callback_data": "menu_home"}])
    return text, {"inline_keyboard": buttons}

def get_day_options_keyboard(hwid, c_name):
    buttons = [
        [
            {"text": "➕ 3 ថ្ងៃ ($0.01 / 50 ៛)", "callback_data": f"add_d:{hwid}:3"},
            {"text": "➕ 7 ថ្ងៃ ($1.50 / 6,000 ៛)", "callback_data": f"add_d:{hwid}:7"}
        ],
        [
            {"text": "➕ 15 ថ្ងៃ ($2.50 / 10,000 ៛)", "callback_data": f"add_d:{hwid}:15"},
            {"text": "➕ 30 ថ្ងៃ ($5.00 / 20,000 ៛)", "callback_data": f"add_d:{hwid}:30"}
        ],
        [
            {"text": "➕ 90 ថ្ងៃ ($10.00 / 40,000 ៛) ⭐ 3ខែ", "callback_data": f"add_d:{hwid}:90"}
        ],
        [
            {"text": "➕ 365 ថ្ងៃ ($30.00 / 120,000 ៛) 👑 1ឆ្នាំ", "callback_data": f"add_d:{hwid}:365"}
        ],
        [
            {"text": "🔙 ត្រឡប់ទៅបញ្ជីភ្ញៀវ", "callback_data": "menu_playlist"},
            {"text": "🏠 ទៅកាន់ Menu ដើម", "callback_data": "menu_home"}
        ]
    ]
    return {"inline_keyboard": buttons}

# ==========================================
# TODAY'S SALES BUILDER
# ==========================================
def build_today_sales_content():
    today_str = datetime.now().strftime("%Y-%m-%d")
    history = load_local_history()

    # Filter for today's purchases
    today_purchases = [rec for rec in history.values() if rec.get("date") == today_str]

    # Also query Firebase /payments for any approved payments today
    try:
        url = f"{FIREBASE_URL}/payments.json"
        with urllib.request.urlopen(urllib.request.Request(url), timeout=5) as resp:
            payments = json.loads(resp.read().decode('utf-8')) or {}
            for b_no, p in payments.items():
                if p.get("status") in ["paid", "confirmed"] and b_no not in [t.get("bill_no") for t in today_purchases]:
                    created = p.get("created_at", "")
                    if created and created.startswith(today_str):
                        today_purchases.append({
                            "bill_no": b_no,
                            "customer_name": p.get("customer_name", "Customer"),
                            "plan": p.get("plan", "Plan"),
                            "amount": str(p.get("amount", "0")),
                            "date": today_str,
                            "time": p.get("approved_at", created)[11:19] if "T" in created else "Today"
                        })
    except Exception:
        pass

    if not today_purchases:
        text = (
            f"📅 <b>ការទិញប្រចាំថ្ងៃ ({today_str})</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "✨ <b>ថ្ងៃនេះមិនទាន់មានការទិញថ្មីនៅឡើយទេ។</b>\n\n"
            "💡 <i>ប្រព័ន្ធនឹង Reset សម្អាតដោយស្វ័យប្រវត្តិកាលណាដល់ថ្ងៃថ្មី (Midnight 00:00)។</i>"
        )
        markup = {
            "inline_keyboard": [
                [{"text": "🔄 Refresh", "callback_data": "refresh_today"}],
                [{"text": "🔙 ត្រឡប់ទៅ Menu ដើម", "callback_data": "menu_home"}]
            ]
        }
        return text, markup

    total_usd = sum(float(p.get("amount", 0)) for p in today_purchases)
    lines = [
        f"📅 <b>ការទិញប្រចាំថ្ងៃ ({today_str})</b>",
        "━━━━━━━━━━━━━━━━━━━━"
    ]
    for i, p in enumerate(today_purchases, 1):
        c_name = p.get("customer_name", "Customer")
        plan_name = p.get("plan", "Plan")
        amt = p.get("amount", "0")
        t_str = p.get("time", "")
        b_no = p.get("bill_no", "")
        lines.append(f"<b>{i}. 👤 {c_name}</b> — <code>${amt}</code>")
        lines.append(f"   📦 {plan_name} | ⏰ {t_str} | ID: <code>{b_no}</code>")
        lines.append("────────────────────")

    lines.append(f"💰 <b>ចំណូលសរុបថ្ងៃនេះ៖</b> <code>${total_usd:.2f}</code> (<b>{len(today_purchases)} នាក់</b>)")
    lines.append("\n💡 <i>ប្រព័ន្ធ Reset ស្អាតរាល់ពេលចូលថ្ងៃថ្មី។</i>")

    markup = {
        "inline_keyboard": [
            [{"text": "🔄 Refresh", "callback_data": "refresh_today"}],
            [{"text": "🔙 ត្រឡប់ទៅ Menu ដើម", "callback_data": "menu_home"}]
        ]
    }
    return "\n".join(lines), markup

# ==========================================
# 3-MONTH ARCHIVE BUILDER
# ==========================================
def build_3month_memory_content():
    history = load_local_history()
    now = datetime.now()
    cutoff_90d = now - timedelta(days=90)

    # Sort descending by timestamp
    valid_records = []
    for b_no, rec in history.items():
        try:
            ts = rec.get("timestamp")
            if ts and datetime.fromisoformat(ts) >= cutoff_90d:
                valid_records.append(rec)
            elif not ts:
                valid_records.append(rec)
        except Exception:
            valid_records.append(rec)

    valid_records.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    total_orders = len(valid_records)
    total_rev = sum(float(r.get("amount", 0)) for r in valid_records)

    lines = [
        "📜 <b>អង្គចងចាំប្រវត្តិទិញ ៣ ខែ (3-Month Archive)</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"🗓️ រយៈពេលរក្សាទុក៖ <b>90 ថ្ងៃ</b> (សម្អាតស្វ័យប្រវត្តិកាលណាលើស 3 ខែ)",
        f"📦 ចំនួនការទិញសរុប៖ <b>{total_orders} ដង</b>",
        f"💰 ប្រាក់ចំណូលសរុប៖ <code>${total_rev:.2f}</code>",
        "━━━━━━━━━━━━━━━━━━━━",
        "👇 <b>បញ្ជីទិញចុងក្រោយបំផុត (Recent Purchases)៖</b>"
    ]

    if not valid_records:
        lines.append("<i>មិនទាន់មានទិន្នន័យប្រវត្តិទិញនៅឡើយទេ។</i>")
    else:
        for i, r in enumerate(valid_records[:15], 1):
            c_name = r.get("customer_name", "Customer")
            amt = r.get("amount", "0")
            plan_n = r.get("plan", "")
            d_str = r.get("date", "")
            t_str = r.get("time", "")
            lines.append(f"{i}. <b>{c_name}</b>: <code>${amt}</code> ({plan_n})")
            lines.append(f"   📅 {d_str} {t_str} | ID: <code>{r.get('bill_no', '')}</code>")
            lines.append("────────────────────")

    markup = {
        "inline_keyboard": [
            [{"text": "🔄 Refresh អង្គចងចាំ", "callback_data": "refresh_memory"}],
            [{"text": "🧹 សម្អាតទិន្នន័យលើស 90 ថ្ងៃឥឡូវនេះ", "callback_data": "prune_now"}],
            [{"text": "🔙 ត្រឡប់ទៅ Menu ដើម", "callback_data": "menu_home"}]
        ]
    }
    return "\n".join(lines), markup

# ==========================================
# MAIN POLLING LOOP
# ==========================================
def run_daemon():
    global last_update_id
    last_prune_check = time.time()

    # Configure Telegram native Menu commands
    setup_bot_commands()

    while True:
        try:
            # Periodic 90-day pruning every 6 hours
            if time.time() - last_prune_check > 21600:
                prune_firebase_history_90d()
                last_prune_check = time.time()

            url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/getUpdates?offset={last_update_id + 1}&timeout=10"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                for u in data.get("result", []):
                    last_update_id = u["update_id"]

                    # ----------------------------------------------------
                    # 1. HANDLE MESSAGES
                    # ----------------------------------------------------
                    if "message" in u:
                        msg = u["message"]
                        chat_id = msg.get("chat", {}).get("id")
                        text = msg.get("text", "").strip()
                        reply = msg.get("reply_to_message")

                        # 🔒 STRICT SECURITY CHECK: Only Admin
                        if str(chat_id) != str(TG_ADMIN_CHAT_ID):
                            send_msg(chat_id, "⛔ <b>សុំទោស!</b> លោកអ្នកគ្មានសិទ្ធិប្រើប្រាស់ Bot នេះឡើយ។\nនេះជា Private Admin Bot សម្រាប់តែ Admin PS MEDIA តែប៉ុណ្ណោះ!")
                            continue

                        reply_content = (reply.get("text") or reply.get("caption") or "") if reply else ""
                        if reply and reply_content and ("Order ID" in reply_content or "PS" in reply_content):
                            match = re.search(r"PS[A-Za-z0-9_]+", reply_content)
                            if match and text and not text.startswith("/"):
                                bill_no = match.group(0)
                                parts = text.split(maxsplit=1)
                                custom_days = None
                                if len(parts) == 2 and parts[0].isdigit():
                                    custom_days = int(parts[0])
                                    new_name = parts[1]
                                else:
                                    new_name = text

                                print(f"[{datetime.now().strftime('%H:%M:%S')}] Admin Named '{new_name}' (Days: {custom_days or 'default'}) and Approved: {bill_no}")

                                # Update Firebase Payment
                                p_info = {}
                                try:
                                    f_url = f"{FIREBASE_URL}/payments/{bill_no}.json"
                                    with urllib.request.urlopen(urllib.request.Request(f_url), timeout=4) as f_resp:
                                        p_info = json.loads(f_resp.read().decode('utf-8')) or {}
                                    
                                    patch_data = {
                                        "status": "paid",
                                        "customer_name": new_name,
                                        "approved_by": "Telegram Admin (Manual Reply)",
                                        "approved_at": datetime.now().isoformat()
                                    }
                                    if custom_days:
                                        patch_data["days"] = custom_days
                                        patch_data["plan"] = f"កញ្ចប់ {custom_days} ថ្ងៃ"

                                    patch_p = json.dumps(patch_data).encode('utf-8')
                                    urllib.request.urlopen(urllib.request.Request(f_url, data=patch_p, headers={'Content-Type': 'application/json'}, method='PATCH'), timeout=5)
                                except Exception as e:
                                    print("Firebase patch error on reply:", e)

                                final_plan = patch_data.get("plan", p_info.get("plan", "License"))
                                final_amt = str(p_info.get("amount", "0"))

                                # Record to 90-day memory
                                record_purchase_event(
                                    bill_no=bill_no,
                                    customer_name=new_name,
                                    hwid=p_info.get("hwid", ""),
                                    pc_name=p_info.get("pc_name", "PC"),
                                    plan=final_plan,
                                    amount=final_amt
                                )

                                if reply.get("message_id"):
                                    orig_t = reply.get("text") or reply.get("caption") or ""
                                    upd_t = orig_t + f"\n\n━━━━━━━━━━━━━━━━━━━━\n✅ <b>ស្ថានភាព៖ បានកំណត់ឈ្មោះ និងយល់ព្រម (APPROVED)</b>\n👤 ឈ្មោះ៖ <b>{new_name}</b>\n📦 កញ្ចប់៖ <b>{final_plan}</b>\n⏰ {datetime.now().strftime('%I:%M:%S %p')}\n📜 បានកត់ត្រាចូលអង្គចងចាំ ៣ ខែ"
                                    edit_msg(chat_id, reply.get("message_id"), upd_t)

                                send_msg(chat_id, f"✅ បានកំណត់ឈ្មោះ «<b>{new_name}</b>» ({final_plan}) និងបើកសោរ Order <code>{bill_no}</code> ជោគជ័យ!\n📜 បានកត់ត្រាចូលអង្គចងចាំ ៣ ខែរួចរាល់។")
                                continue

                        # Command: /start or /menu -> BotFather Style Menu (Hides clients by default!)
                        if text in ["/start", "/menu", "🏠 Menu ដើម"]:
                            content, markup = build_main_menu_content()
                            send_msg(chat_id, content, reply_markup=markup)

                        # Button: 📋 បញ្ជីភ្ញៀវ (Playlist)
                        elif text in ["📋 បញ្ជីភ្ញៀវ (Playlist)", "👥 បញ្ជីភ្ញៀវទាំងអស់", "/users", "/playlist"]:
                            content, markup = build_playlist_content(only_online=False)
                            send_msg(chat_id, content, reply_markup=markup)

                        # Button: 🟢 ភ្ញៀវ Online
                        elif text in ["🟢 ភ្ញៀវ Online", "🟢 ភ្ញៀវកំពុង Online", "/online"]:
                            content, markup = build_playlist_content(only_online=True)
                            send_msg(chat_id, content, reply_markup=markup)

                        # Button: 📅 ការទិញថ្ងៃនេះ (Today)
                        elif text in ["📅 ការទិញថ្ងៃនេះ (Today)", "/today"]:
                            content, markup = build_today_sales_content()
                            send_msg(chat_id, content, reply_markup=markup)

                        # Button: 📜 អង្គចងចាំ ៣ ខែ
                        elif text in ["📜 អង្គចងចាំ ៣ ខែ", "/memory", "/history"]:
                            content, markup = build_3month_memory_content()
                            send_msg(chat_id, content, reply_markup=markup)

                        # Button: ➕ បន្ថែមថ្ងៃ (Add Days)
                        elif text in ["➕ បន្ថែមថ្ងៃ (Add Days)", "/add"]:
                            content, markup = build_add_days_client_picker()
                            send_msg(chat_id, content, reply_markup=markup)

                        # Command: /add <days> <hwid>
                        elif text.startswith("/add "):
                            parts = text.split()
                            if len(parts) >= 3:
                                try:
                                    d_val = int(parts[1])
                                    target_hwid_prefix = parts[2].strip().upper()
                                    users = get_firebase_users()
                                    matched_hwid = None
                                    matched_name = None
                                    for h, u in users.items():
                                        if target_hwid_prefix in h.upper():
                                            matched_hwid = h
                                            matched_name = u.get("customer_name", "Unknown")
                                            break

                                    if matched_hwid:
                                        p_url = f"{FIREBASE_URL}/users/{matched_hwid}.json"
                                        patch_p = json.dumps({
                                            "admin_add_days": d_val,
                                            "admin_extended_at": datetime.now().isoformat()
                                        }).encode('utf-8')
                                        urllib.request.urlopen(urllib.request.Request(p_url, data=patch_p, headers={'Content-Type': 'application/json'}, method='PATCH'), timeout=5)

                                        pkg_info = PACKAGE_PRICES.get(d_val, {"name": f"បន្ថែម {d_val} ថ្ងៃ", "usd": "0.00"})
                                        record_purchase_event(
                                            bill_no=f"ADD_{int(time.time())}",
                                            customer_name=matched_name,
                                            hwid=matched_hwid,
                                            pc_name="PC",
                                            plan=pkg_info["name"],
                                            amount=pkg_info["usd"]
                                        )

                                        send_msg(chat_id, f"✅ <b>ជោគជ័យ!</b> បានបន្ថែម <b>{d_val} ថ្ងៃ</b> (${pkg_info['usd']}) ជូន «<b>{matched_name}</b>» (HWID: <code>{matched_hwid}</code>)!\n⚡ ម៉ាស៊ីនរបស់គាត់នឹងឡើងថ្ងៃអូតូភ្លាមៗ។")
                                    else:
                                        send_msg(chat_id, f"❌ រកមិនឃើញ HWID ដែលដូច <code>{target_hwid_prefix}</code> ឡើយ។")
                                except Exception as ex:
                                    send_msg(chat_id, f"❌ ទម្រង់មិនត្រឹមត្រូវ: {ex}")
                            else:
                                send_msg(chat_id, "⚠️ សូមវាយតាមទម្រង់៖ <code>/add 7 <HWID></code>")

                        # Button: 📊 ស្ថិតិសរុប (Stats)
                        elif text in ["📊 ស្ថិតិសរុប (Stats)", "/stats"]:
                            users = get_firebase_users()
                            total_users = len(users)
                            online_count = sum(1 for _, u in users.items() if parse_user_status(u)[0])
                            active_count = sum(1 for _, u in users.items() if get_remaining_seconds(u) > 0)
                            history = load_local_history()

                            stats_msg = (
                                "📊 <b>ស្ថិតិប្រព័ន្ធ PS MEDIA៖</b>\n"
                                "━━━━━━━━━━━━━━━━━━━━\n"
                                f"👥 ម៉ាស៊ីនអតិថិជនសរុប: <b>{total_users} នាក់</b>\n"
                                f"🟢 កំពុងបើកប្រើ (Online): <b>{online_count} នាក់</b>\n"
                                f"💎 គណនីមានសុពលភាព: <b>{active_count} នាក់</b>\n"
                                f"🚫 ផុតកំណត់ប្រើប្រាស់: <b>{total_users - active_count} នាក់</b>\n"
                                f"📜 ចំនួនកត់ត្រាក្នុង 3 ខែ: <b>{len(history)} ប្រតិបត្តិការ</b>\n"
                                "━━━━━━━━━━━━━━━━━━━━\n"
                                f"⏰ គិតត្រឹមម៉ោង: {datetime.now().strftime('%I:%M:%S %p')}"
                            )
                            markup = {"inline_keyboard": [[{"text": "🔙 ត្រឡប់ទៅ Menu ដើម", "callback_data": "menu_home"}]]}
                            send_msg(chat_id, stats_msg, reply_markup=markup)

                    # ----------------------------------------------------
                    # 2. HANDLE INLINE BUTTON CALLBACKS (BotFather Style In-Place Navigation)
                    # ----------------------------------------------------
                    elif "callback_query" in u:
                        cq = u["callback_query"]
                        cq_id = cq.get("id")
                        c_data = cq.get("data", "")
                        cq_msg = cq.get("message", {})
                        chat_id = cq_msg.get("chat", {}).get("id")
                        msg_id = cq_msg.get("message_id")
                        orig_text = cq_msg.get("text") or cq_msg.get("caption") or ""

                        # 🔒 Security Check
                        if str(chat_id) != str(TG_ADMIN_CHAT_ID):
                            answer_callback(cq_id, "⛔ គ្មានសិទ្ធិ!", show_alert=True)
                            continue

                        # Menu Home (Return to clean main menu)
                        if c_data == "menu_home":
                            content, markup = build_main_menu_content()
                            edit_msg(chat_id, msg_id, content, reply_markup=markup)
                            answer_callback(cq_id)

                        # Menu: Playlist
                        elif c_data == "menu_playlist" or c_data == "refresh_playlist":
                            content, markup = build_playlist_content(only_online=False)
                            edit_msg(chat_id, msg_id, content, reply_markup=markup)
                            answer_callback(cq_id, "📋 បញ្ជីភ្ញៀវ Playlist")

                        # Menu: Online
                        elif c_data == "menu_online" or c_data == "refresh_online":
                            content, markup = build_playlist_content(only_online=True)
                            edit_msg(chat_id, msg_id, content, reply_markup=markup)
                            answer_callback(cq_id, "🟢 ភ្ញៀវ Online")

                        # Menu: Today
                        elif c_data == "menu_today" or c_data == "refresh_today":
                            content, markup = build_today_sales_content()
                            edit_msg(chat_id, msg_id, content, reply_markup=markup)
                            answer_callback(cq_id, "📅 ការទិញថ្ងៃនេះ")

                        # Menu: Memory (90 Days)
                        elif c_data == "menu_memory" or c_data == "refresh_memory":
                            content, markup = build_3month_memory_content()
                            edit_msg(chat_id, msg_id, content, reply_markup=markup)
                            answer_callback(cq_id, "📜 អង្គចងចាំ ៣ ខែ")

                        # Menu: Add Days (Client picker)
                        elif c_data == "menu_add_days":
                            content, markup = build_add_days_client_picker()
                            edit_msg(chat_id, msg_id, content, reply_markup=markup)
                            answer_callback(cq_id)

                        # Menu: Stats
                        elif c_data == "menu_stats":
                            users = get_firebase_users()
                            total_users = len(users)
                            online_count = sum(1 for _, u in users.items() if parse_user_status(u)[0])
                            active_count = sum(1 for _, u in users.items() if get_remaining_seconds(u) > 0)
                            history = load_local_history()

                            stats_msg = (
                                "📊 <b>ស្ថិតិប្រព័ន្ធ PS MEDIA៖</b>\n"
                                "━━━━━━━━━━━━━━━━━━━━\n"
                                f"👥 ម៉ាស៊ីនអតិថិជនសរុប: <b>{total_users} នាក់</b>\n"
                                f"🟢 កំពុងបើកប្រើ (Online): <b>{online_count} នាក់</b>\n"
                                f"💎 គណនីមានសុពលភាព: <b>{active_count} នាក់</b>\n"
                                f"🚫 ផុតកំណត់ប្រើប្រាស់: <b>{total_users - active_count} នាក់</b>\n"
                                f"📜 ចំនួនកត់ត្រាក្នុង 3 ខែ: <b>{len(history)} ប្រតិបត្តិការ</b>\n"
                                "━━━━━━━━━━━━━━━━━━━━\n"
                                f"⏰ គិតត្រឹមម៉ោង: {datetime.now().strftime('%I:%M:%S %p')}"
                            )
                            markup = {"inline_keyboard": [[{"text": "🔙 ត្រឡប់ទៅ Menu ដើម", "callback_data": "menu_home"}]]}
                            edit_msg(chat_id, msg_id, stats_msg, reply_markup=markup)
                            answer_callback(cq_id)

                        # Prune 90 days
                        elif c_data == "prune_now":
                            prune_firebase_history_90d()
                            content, markup = build_3month_memory_content()
                            edit_msg(chat_id, msg_id, content, reply_markup=markup)
                            answer_callback(cq_id, "🧹 បានសម្អាតទិន្នន័យដែលលើស 90 ថ្ងៃរួចរាល់!", show_alert=True)

                        # ext_u:{hwid} -> show days options WITH EXACT PRICES for that user
                        elif c_data.startswith("ext_u:"):
                            hwid = c_data.split(":")[1]
                            user_info = get_firebase_users().get(hwid, {})
                            c_name = user_info.get("customer_name", "អតិថិជន")

                            menu_text = (
                                f"➕ <b>ជ្រើសរើសកញ្ចប់ថ្ងៃ និងតម្លៃដើម្បីបន្ថែមជូន៖</b>\n"
                                f"👤 ឈ្មោះ៖ <b>{c_name}</b>\n"
                                f"💻 HWID: <code>{hwid}</code>\n"
                                "━━━━━━━━━━━━━━━━━━━━\n"
                                "👉 <i>សូមចុចលើកញ្ចប់ខាងក្រោម (មានតម្លៃ និងថ្ងៃច្បាស់លាស់)៖</i>"
                            )
                            day_btns = get_day_options_keyboard(hwid, c_name)
                            edit_msg(chat_id, msg_id, menu_text, reply_markup=day_btns)
                            answer_callback(cq_id)

                        # add_d:{hwid}:{days} -> execute extension
                        elif c_data.startswith("add_d:"):
                            parts = c_data.split(":")
                            hwid = parts[1]
                            days_add = int(parts[2])
                            user_info = get_firebase_users().get(hwid, {})
                            c_name = user_info.get("customer_name", "អតិថិជន")
                            pc_name = user_info.get("pc_name", "PC")

                            pkg = PACKAGE_PRICES.get(days_add, {"name": f"បន្ថែម {days_add} ថ្ងៃ", "usd": "0.00", "khr": "0 ៛"})

                            try:
                                p_url = f"{FIREBASE_URL}/users/{hwid}.json"
                                patch_p = json.dumps({
                                    "admin_add_days": days_add,
                                    "admin_extended_at": datetime.now().isoformat()
                                }).encode('utf-8')
                                urllib.request.urlopen(urllib.request.Request(p_url, data=patch_p, headers={'Content-Type': 'application/json'}, method='PATCH'), timeout=5)
                            except Exception as e:
                                print("Firebase patch add_d error:", e)

                            # Record in 90-day archive with exact price
                            record_purchase_event(
                                bill_no=f"EXT_{int(time.time())}",
                                customer_name=c_name,
                                hwid=hwid,
                                pc_name=pc_name,
                                plan=pkg["name"],
                                amount=pkg["usd"]
                            )

                            answer_callback(cq_id, f"✅ បានបន្ថែម {days_add} ថ្ងៃ (${pkg['usd']}) ជោគជ័យ!", show_alert=True)
                            succ_text = (
                                f"🎉 <b>ជោគជ័យ!</b> បានបន្ថែម <b>{days_add} ថ្ងៃ</b> (តម្លៃ <code>${pkg['usd']} / {pkg['khr']}</code>) ជូន «<b>{c_name}</b>» (HWID: <code>{hwid}</code>) រួចរាល់។\n\n"
                                "⚡ កុំព្យូទ័ររបស់គាត់នឹងឡើងថ្ងៃដោយស្វ័យប្រវត្តិភ្លាមៗ!\n"
                                "📜 បានកត់ត្រាចូលអង្គចងចាំ ៣ ខែរួចរាល់។"
                            )
                            succ_markup = {
                                "inline_keyboard": [
                                    [{"text": "➕ បន្ថែមភ្ញៀវផ្សេងទៀត", "callback_data": "menu_add_days"}],
                                    [{"text": "📋 ទៅកាន់ Playlist", "callback_data": "menu_playlist"}],
                                    [{"text": "🏠 ទៅ Menu ដើម", "callback_data": "menu_home"}]
                                ]
                            }
                            edit_msg(chat_id, msg_id, succ_text, reply_markup=succ_markup)

                        # Approve Order with Bank Name
                        # 1-Click Approve Order
                        elif c_data.startswith("approve:") or c_data.startswith("appr_bank:"):
                            bill_no = c_data.split(":")[1]
                            o_data = {}
                            try:
                                f_url = f"{FIREBASE_URL}/payments/{bill_no}.json"
                                with urllib.request.urlopen(urllib.request.Request(f_url), timeout=4) as o_resp:
                                    o_data = json.loads(o_resp.read().decode('utf-8')) or {}
                            except Exception: pass

                            b_name = o_data.get("customer_name") or o_data.get("pc_name") or "Customer"
                            plan_name = o_data.get("plan", "License")
                            amt_val = str(o_data.get("amount", "0"))
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] Admin 1-Click Approved: {bill_no} ({plan_name})")

                            try:
                                p_url = f"{FIREBASE_URL}/payments/{bill_no}.json"
                                patch_p = json.dumps({"status": "paid", "customer_name": b_name, "approved_by": "Telegram Admin (1-Click)", "approved_at": datetime.now().isoformat()}).encode('utf-8')
                                urllib.request.urlopen(urllib.request.Request(p_url, data=patch_p, headers={'Content-Type': 'application/json'}, method='PATCH'), timeout=5)
                            except Exception as e:
                                print("Firebase patch error:", e)

                            # Record in 90-day memory
                            record_purchase_event(
                                bill_no=bill_no,
                                customer_name=b_name,
                                hwid=o_data.get("hwid", ""),
                                pc_name=o_data.get("pc_name", "PC"),
                                plan=plan_name,
                                amount=amt_val
                            )

                            answer_callback(cq_id, f"✅ បានយល់ព្រម 1-Click បើកសោរ {plan_name} ជូន {b_name} ជោគជ័យ!", show_alert=True)

                            new_text = orig_text + f"\n\n━━━━━━━━━━━━━━━━━━━━\n✅ <b>ស្ថានភាព៖ បានយល់ព្រម (1-CLICK APPROVED)</b>\n📦 កញ្ចប់៖ <b>{plan_name}</b> (<code>${amt_val}</code>)\n👤 ឈ្មោះ៖ <b>{b_name}</b>\n⏰ {datetime.now().strftime('%I:%M:%S %p')}\n📜 បានកត់ត្រាចូលអង្គចងចាំ ៣ ខែ"
                            edit_msg(chat_id, msg_id, new_text)

                        # Rename Callback
                        elif c_data.startswith("rename:"):
                            bill_no = c_data.split(":")[1]
                            answer_callback(cq_id, "👉 សូម Swipe Reply លើសារនេះ រួចវាយឈ្មោះដែលចង់កំណត់ (ឧ. VIP DARA)!", show_alert=True)

                        # Adjusted Day Approval (When customer transfers less or different amount)
                        elif c_data.startswith("appr_c:"):
                            parts = c_data.split(":")
                            bill_no = parts[1]
                            adj_days = int(parts[2])
                            adj_amt = parts[3]

                            o_data = {}
                            try:
                                f_url = f"{FIREBASE_URL}/payments/{bill_no}.json"
                                with urllib.request.urlopen(urllib.request.Request(f_url), timeout=4) as o_resp:
                                    o_data = json.loads(o_resp.read().decode('utf-8')) or {}
                            except Exception: pass

                            b_name = o_data.get("customer_name") or o_data.get("pc_name") or "Customer"
                            plan_name = f"កញ្ចប់ {adj_days} ថ្ងៃ (${adj_amt})"
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] Admin Adjusted and Approved {adj_days}d (${adj_amt}): {bill_no}")

                            try:
                                p_url = f"{FIREBASE_URL}/payments/{bill_no}.json"
                                patch_p = json.dumps({
                                    "status": "paid",
                                    "days": adj_days,
                                    "plan": plan_name,
                                    "amount": adj_amt,
                                    "approved_by": f"Telegram Admin (Adjusted ${adj_amt})",
                                    "approved_at": datetime.now().isoformat()
                                }).encode('utf-8')
                                urllib.request.urlopen(urllib.request.Request(p_url, data=patch_p, headers={'Content-Type': 'application/json'}, method='PATCH'), timeout=5)
                            except Exception as e:
                                print("Firebase patch error:", e)

                            # Record in 90-day memory
                            record_purchase_event(
                                bill_no=bill_no,
                                customer_name=b_name,
                                hwid=o_data.get("hwid", ""),
                                pc_name=o_data.get("pc_name", "PC"),
                                plan=plan_name,
                                amount=adj_amt
                            )

                            answer_callback(cq_id, f"✅ បានកែសម្រួលបើកសោរ {adj_days} ថ្ងៃ (${adj_amt}) ជូន {b_name} ជោគជ័យ!", show_alert=True)

                            new_text = orig_text + f"\n\n━━━━━━━━━━━━━━━━━━━━\n✅ <b>ស្ថានភាព៖ បានកែសម្រួលបើកសោរតាមលុយជាក់ស្តែង</b>\n📦 កញ្ចប់៖ <b>{plan_name}</b> (<code>${adj_amt}</code>)\n👤 ឈ្មោះ៖ <b>{b_name}</b>\n⏰ {datetime.now().strftime('%I:%M:%S %p')}\n📜 បានកត់ត្រាចូលអង្គចងចាំ ៣ ខែ"
                            edit_msg(chat_id, msg_id, new_text)

                        # Approve Order with PC Name
                        elif c_data.startswith("appr_pc:"):
                            bill_no = c_data.split(":")[1]
                            o_data = {}
                            try:
                                f_url = f"{FIREBASE_URL}/payments/{bill_no}.json"
                                with urllib.request.urlopen(urllib.request.Request(f_url), timeout=4) as o_resp:
                                    o_data = json.loads(o_resp.read().decode('utf-8')) or {}
                            except Exception: pass

                            p_name = o_data.get("pc_name") or "PC-User"
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] Admin Approved with PC Name '{p_name}': {bill_no}")

                            try:
                                p_url = f"{FIREBASE_URL}/payments/{bill_no}.json"
                                patch_p = json.dumps({"status": "paid", "customer_name": p_name, "approved_by": "Telegram Admin (PC Name)", "approved_at": datetime.now().isoformat()}).encode('utf-8')
                                urllib.request.urlopen(urllib.request.Request(p_url, data=patch_p, headers={'Content-Type': 'application/json'}, method='PATCH'), timeout=5)
                            except Exception as e:
                                print("Firebase patch error:", e)

                            record_purchase_event(
                                bill_no=bill_no,
                                customer_name=p_name,
                                hwid=o_data.get("hwid", ""),
                                pc_name=p_name,
                                plan=o_data.get("plan", "License"),
                                amount=str(o_data.get("amount", "0"))
                            )

                            answer_callback(cq_id, f"✅ បានយល់ព្រមយកឈ្មោះកុំព្យូទ័រ «{p_name}» និងបើកសោរ {bill_no}!", show_alert=True)

                            new_text = orig_text + f"\n\n━━━━━━━━━━━━━━━━━━━━\n✅ <b>ស្ថានភាព៖ បានយល់ព្រម (APPROVED)</b>\n👤 ឈ្មោះ៖ <b>{p_name}</b> (តាមកុំព្យូទ័រ)\n⏰ {datetime.now().strftime('%I:%M:%S %p')}\n📜 បានកត់ត្រាចូលអង្គចងចាំ ៣ ខែ"
                            edit_msg(chat_id, msg_id, new_text)

                        # Reject Order
                        elif c_data.startswith("reject:"):
                            bill_no = c_data.split(":")[1]
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] Admin Rejected: {bill_no}")

                            try:
                                p_url = f"{FIREBASE_URL}/payments/{bill_no}.json"
                                patch_p = json.dumps({"status": "rejected", "rejected_at": datetime.now().isoformat()}).encode('utf-8')
                                urllib.request.urlopen(urllib.request.Request(p_url, data=patch_p, headers={'Content-Type': 'application/json'}, method='PATCH'), timeout=5)
                            except Exception: pass

                            answer_callback(cq_id, f"❌ បានបដិសេធ {bill_no}!", show_alert=True)
                            new_text = orig_text + f"\n\n━━━━━━━━━━━━━━━━━━━━\n❌ <b>ស្ថានភាព៖ ត្រូវបានបដិសេធ (REJECTED)</b>"
                            edit_msg(chat_id, msg_id, new_text)
        except Exception as e:
            time.sleep(3)

if __name__ == "__main__":
    run_daemon()
