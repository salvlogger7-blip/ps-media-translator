import os
import asyncio
import edge_tts
import uuid
import threading
import time
import datetime
import json
from flask import Flask, render_template, request, jsonify, send_from_directory
from pydub import AudioSegment
from static_ffmpeg import add_paths

# ១. បន្ថែម FFmpeg ទៅក្នុង System Path
add_paths()

app = Flask(__name__)

STATIC_DIR = 'static'
LICENSE_FILE = 'licenses.json'

if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)

progress_db = {}

# --- ⚙️ មុខងារគ្រប់គ្រង DATABASE LICENSE ---
def load_licenses():
    if os.path.exists(LICENSE_FILE):
        try:
            with open(LICENSE_FILE, 'r') as f:
                return json.load(f)
        except: return {}
    return {}

def save_licenses(data):
    with open(LICENSE_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# --- 🔐 API សម្រាប់បងបង្កើត LICENSE (ADMIN PANEL) ---
# របៀបប្រើ៖ ផ្ញើ POST ទៅ /api/admin/add_license ជាមួយ admin_pass
@app.route('/api/admin/add_license', methods=['POST'])
def admin_add_license():
    data = request.json
    # បងអាចប្តូរ Password "ps123" នេះតាមចិត្ត
    if data.get('admin_pass') != "ps123":
        return jsonify({"status": "Password ខុស! មិនអាចបង្កើតបានទេ"}), 403
    
    dev_id = data.get('device_id')
    expiry = data.get('expiry') # ទម្រង់ត្រូវតែ: YYYY-MM-DD (ឧ. 2026-12-31)
    
    if not dev_id or not expiry:
        return jsonify({"status": "សូមបំពេញ ID និង ថ្ងៃផុតកំណត់ឱ្យច្បាស់"}), 400

    licenses = load_licenses()
    licenses[dev_id] = expiry
    save_licenses(licenses)
    return jsonify({"status": f"ជោគជ័យ! ID: {dev_id} អាចប្រើបានដល់ {expiry}"})

# --- 🛡️ API សម្រាប់ឆែកមើល License (Client Side) ---
@app.route('/api/check_license', methods=['POST'])
def check_license():
    dev_id = request.json.get('device_id')
    licenses = load_licenses()
    
    # បន្ថែម Admin ID របស់បងទុកជាមុន (កុំឱ្យ Lock ខ្លួនឯង)
    if dev_id == "ADMIN-PS-PRO":
        return jsonify({"status": "Master Admin ✅", "authorized": True, "expiry": "2030-01-01"})

    if dev_id in licenses:
        exp_str = licenses[dev_id]
        exp_date = datetime.datetime.strptime(exp_str, "%Y-%m-%d")
        if datetime.datetime.now() < exp_date:
            return jsonify({"status": "Active ✅", "authorized": True, "expiry": exp_str})
    
    return jsonify({"status": "គ្មានអាជ្ញាប័ណ្ណ ❌", "authorized": False})

# --- មុខងារកែច្នៃសំឡេង (Effects) ---
def change_pitch(seg, pitch):
    if pitch == 0: return seg
    new_sample_rate = int(seg.frame_rate * (2.0 ** (pitch / 12.0)))
    return seg._spawn(seg.raw_data, overrides={'frame_rate': new_sample_rate}).set_frame_rate(44100)

def apply_preset(seg, preset):
    try:
        if preset == "bass":
            return seg.low_pass_filter(250).apply_gain(6).overlay(seg.high_pass_filter(250).apply_gain(-2))
        elif preset == "reverb":
            combined = seg
            for i in range(1, 3):
                combined = combined.overlay(seg - (i * 15), position=i * 30)
            return combined
        elif preset == "studio":
            mid = seg.high_pass_filter(300).low_pass_filter(3000).apply_gain(3)
            high = seg.high_pass_filter(3000).apply_gain(5)
            return seg.low_pass_filter(300).overlay(mid).overlay(high)
    except: pass
    return seg

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/manifest.json')
def serve_manifest():
    return send_from_directory('static', 'manifest.json')

# --- មុខងារ Preview ---
@app.route('/api/preview', methods=['POST'])
def preview_voice():
    try:
        data = request.json
        dev_id = data.get('device_id', 'unknown')
        
        # Security Check
        licenses = load_licenses()
        if dev_id != "ADMIN-PS-PRO" and dev_id not in licenses:
            return jsonify({"error": "No License"}), 403

        text = data.get('text', "សួស្តី")
        voice = data.get('voice', 'km-KH-SreymomNeural')
        speed = int(data.get('speed', 0))
        actual_speed = max(min(speed, 90), -15)
        rate = f"+{actual_speed}%" if actual_speed >= 0 else f"{actual_speed}%"
        
        pitch = int(data.get('pitch', 0))
        preset = data.get('preset', 'normal')

        task_id = f"prev_{dev_id}_" + str(uuid.uuid4())[:4]
        temp_path = os.path.join(STATIC_DIR, f"{task_id}.mp3")

        async def make_preview():
            communicate = edge_tts.Communicate(text, voice, rate=rate)
            await communicate.save(temp_path)
            if os.path.exists(temp_path):
                seg = AudioSegment.from_mp3(temp_path)
                if preset != 'normal': seg = apply_preset(seg, preset)
                if pitch != 0: seg = change_pitch(seg, pitch)
                seg.export(temp_path, format="mp3")

        asyncio.run(make_preview())
        return jsonify({"url": f"/static/{task_id}.mp3?v={time.time()}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- មុខងារផលិតហ្វាយពេញ ---
@app.route('/api/start', methods=['POST'])
def start_task():
    data = request.json
    dev_id = data.get('device_id', 'unknown')
    
    licenses = load_licenses()
    if dev_id != "ADMIN-PS-PRO" and dev_id not in licenses:
        return jsonify({"error": "No License"}), 403

    task_id = str(uuid.uuid4())[:8]
    progress_db[task_id] = 0
    threading.Thread(target=lambda: asyncio.run(run_conversion(task_id, data, dev_id))).start()
    return jsonify({"task_id": task_id})

async def run_conversion(task_id, data, dev_id):
    try:
        items = data['items']
        voice = data['voice']
        speed = int(data.get('speed', 0))
        actual_speed = max(min(speed, 90), -15)
        rate_str = f"+{actual_speed}%" if actual_speed >= 0 else f"{actual_speed}%"
        
        pitch = int(data.get('pitch', 0))
        preset = data.get('preset', 'normal')
        custom_name = data.get('filename', 'result').strip() or "result"
        
        full_audio = AudioSegment.silent(duration=items[-1]['end'] + 1000)
        
        for i, item in enumerate(items):
            temp_file = os.path.join(STATIC_DIR, f"temp_{task_id}_{i}.mp3")
            communicate = edge_tts.Communicate(item['text'], voice, rate=rate_str)
            await communicate.save(temp_file)
            
            if os.path.exists(temp_file):
                seg = AudioSegment.from_mp3(temp_file)
                if preset != 'normal': seg = apply_preset(seg, preset)
                if pitch != 0: seg = change_pitch(seg, pitch)
                full_audio = full_audio.overlay(seg, position=item['start'])
                os.remove(temp_file)
            
            progress_db[task_id] = int(((i + 1) / len(items)) * 100)
        
        output_name = f"user_{dev_id}_{custom_name}_{task_id}.mp3"
        output_file = os.path.join(STATIC_DIR, output_name)
        full_audio.export(output_file, format="mp3")
        progress_db[task_id] = "done"
    except Exception as e:
        progress_db[task_id] = "error"

@app.route('/api/progress/<task_id>')
def get_progress(task_id):
    return jsonify({"progress": progress_db.get(task_id, 0)})

@app.route('/api/files', methods=['POST'])
def list_files():
    dev_id = request.json.get('device_id', 'unknown')
    files = []
    if os.path.exists(STATIC_DIR):
        for f in os.listdir(STATIC_DIR):
            if f.startswith(f"user_{dev_id}_") and f.endswith('.mp3'):
                path = os.path.join(STATIC_DIR, f)
                files.append({
                    "name": f.replace(f"user_{dev_id}_", ""),
                    "real_name": f,
                    "url": f"/static/{f}",
                    "timestamp": os.path.getctime(path),
                    "size": f"{round(os.path.getsize(path) / (1024*1024), 2)} MB"
                })
    return jsonify(sorted(files, key=lambda x: x['timestamp'], reverse=True))

@app.route('/api/delete/<filename>', methods=['DELETE'])
def delete_file(filename):
    path = os.path.join(STATIC_DIR, filename)
    if os.path.exists(path):
        os.remove(path)
        return jsonify({"status":"ok"})
    return jsonify({"status":"error"}), 404

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)