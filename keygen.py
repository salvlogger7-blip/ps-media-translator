import hashlib
import time
from datetime import datetime, timedelta

# --- កំណត់សម្ងាត់ (ត្រូវតែដូចគ្នាជាមួយក្នុង app.py) ---
SECRET_SALT = "PS_MEDIA_PRO_2026"

def generate_key(client_id, days):
    """បង្កើត License Key ដោយប្រើសញ្ញា | ដើម្បីកុំឱ្យច្រឡំជាមួយសញ្ញា - ក្នុង ID"""
    # ១. កំណត់ថ្ងៃផុតកំណត់
    expiry_date = (datetime.now() + timedelta(days=days)).strftime("%Y%m%d")
    
    # ២. បង្កើត Hash សម្រាប់សុវត្ថិភាព (ប្រើសញ្ញា _ ក្នុង raw_str)
    raw_str = f"{client_id}_{expiry_date}_{SECRET_SALT}"
    signature = hashlib.md5(raw_str.encode()).hexdigest().upper()[:6]
    
    # ៣. រួមបញ្ចូលគ្នាជា License Key (ទ្រង់ទ្រាយ៖ PS|ID|DATE|HASH)
    return f"PS|{client_id}|{expiry_date}|{signature}"

def main():
    print("========================================")
    print("   PS MEDIA PRO - KEY GENERATOR (V2)   ")
    print("========================================")
    
    # ទទួលយក ID ពីអ្នកប្រើប្រាស់
    client_id = input("👉 បញ្ចូល Device ID (ឧទាហរណ៍៖ 03000200-0): ").strip()
    
    if not client_id:
        print("❌ កំហុស: សូមបញ្ចូល ID ឱ្យបានត្រឹមត្រូវ!")
        return

    try:
        days = int(input("👉 បញ្ចូលចំនួនថ្ងៃដែលត្រូវឱ្យប្រើ (ឧទាហរណ៍ 30): "))
    except ValueError:
        print("❌ កំហុស: សូមបញ្ចូលចំនួនថ្ងៃជាលេខ!")
        return

    # បង្កើត Key
    key = generate_key(client_id, days)
    
    print("\n" + "✨" * 20)
    print(f"✅ បង្កើតជោគជ័យសម្រាប់ ID: {client_id}")
    print(f"📅 ផុតកំណត់នៅថ្ងៃទី: {(datetime.now() + timedelta(days=days)).strftime('%d-%m-%Y')}")
    print(f"🔑 LICENSE KEY: {key}")
    print("✨" * 20)
    
    print("\n💡 ណែនាំ: Copy Key ខាងលើ រួចយកទៅដាក់ក្នុងប្រអប់ Activate ក្នុង Browser។")
    input("\nចុច Enter ដើម្បីបិទកម្មវិធី...")

if __name__ == "__main__":
    main()