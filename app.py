import os
import asyncio
import edge_tts
import uuid
import threading
import time
import datetime
import hashlib
from flask import Flask, render_template, request, jsonify
from pydub import AudioSegment
from static_ffmpeg import add_paths

# ១. បន្ថែម FFmpeg ទៅក្នុង System Path (ដោះស្រាយបញ្ហា error% លើ Render និង Local)
add_paths()

app = Flask(__name__)

# កំណត់ Folder សម្រាប់រក្សាទុកហ្វាយ
STATIC_DIR = 'static'
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)

progress_db = {}

# --- [ផ្នែកឡាយសិន] មុខងារត្រួតពិនិត្យសុពលភាព ---
SECRET_SALT = "PS_MEDIA_PRO_2026"

@app.route('/api/license_info')
def get_license():
    # កំណត់ថ្ងៃផុតកំណត់៖ ២៦ មេសា ២០២៦
    expiry_date = datetime.datetime(2026, 4, 26, 23, 59, 59) 
    now = datetime.datetime.now()
    remaining = int((expiry_date - now).total_seconds())
    return jsonify({
        "id": "PS-PRO-03000200",
        "status": "Active ✅" if remaining > 0 else "Expired ❌",
        "remaining_seconds": max(0, remaining)
    })

# --- មុខងារជំនួយសម្រាប់សំឡេង ---
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

@app.route('/api/preview', methods=['POST'])
def preview_voice():
    try:
        data = request.json
        text = "សួស្តីបង! នេះគឺជាសំឡេងសាកល្បងពី ភី អេស មីឌៀ ប្រូ។"
        voice = data['voice']
        speed_base = int(data.get('speed', 0))
        rate = f"+{speed_base}%" if speed_base >= 0 else f"{speed_base}%"
        pitch = int(data.get('pitch', 0))
        preset = data.get('preset', 'normal')
        
        task_id = "preview_" + str(uuid.uuid4())[:8]
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

@app.route('/api/start', methods=['POST'])
def start_task():
    data = request.json
    task_id = str(uuid.uuid4())[:8]
    progress_db[task_id] = 0
    threading.Thread(target=lambda: asyncio.run(run_conversion(task_id, data))).start()
    return jsonify({"task_id": task_id})

async def run_conversion(task_id, data):
    try:
        items = data['items']
        voice = data['voice']
        speed_base = int(data['speed'])
        pitch = int(data['pitch'])
        preset = data['preset']
        custom_name = data.get('filename', 'result').strip() or "result"
        
        # រៀបចំ Audio ប្លង់ទទេ
        max_duration = items[-1]['end'] + 3000
        full_audio = AudioSegment.silent(duration=max_duration)
        rate_str = f"+{speed_base}%" if speed_base >= 0 else f"{speed_base}%"
        
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
        
        output_file = os.path.join(STATIC_DIR, f"{custom_name}_{task_id}.mp3")
        full_audio.export(output_file, format="mp3")
        progress_db[task_id] = "done"
    except Exception as e:
        print(f"Error: {e}")
        progress_db[task_id] = "error"

@app.route('/api/progress/<task_id>')
def get_progress(task_id):
    return jsonify({"progress": progress_db.get(task_id, 0)})

@app.route('/api/files')
def list_files():
    files = []
    if os.path.exists(STATIC_DIR):
        for f in os.listdir(STATIC_DIR):
            if f.endswith('.mp3') and not (f.startswith('temp_') or f.startswith('preview_')):
                path = os.path.join(STATIC_DIR, f)
                files.append({
                    "name": f, "url": f"/static/{f}",
                    "time": time.ctime(os.path.getctime(path)),
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
    # កំណត់ Port ឱ្យត្រូវតាម Render (Default 5000)
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)