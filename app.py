from flask import Flask, render_template, request, jsonify
import os, asyncio, edge_tts, uuid, threading, time, datetime
from pydub import AudioSegment

# --- កំណត់ផ្លូវ FFmpeg ---
ffmpeg_path = r"C:\Users\KOLDER\Downloads\ffmpeg-2026-03-22-git-9c63742425-full_build\ffmpeg\bin\ffmpeg.exe"
ffprobe_path = r"C:\Users\KOLDER\Downloads\ffmpeg-2026-03-22-git-9c63742425-full_build\ffmpeg\bin\ffprobe.exe"

AudioSegment.converter = ffmpeg_path
AudioSegment.ffprobe = ffprobe_path

app = Flask(__name__)
STATIC_DIR = 'static'
if not os.path.exists(STATIC_DIR): os.makedirs(STATIC_DIR)

progress_db = {}

# --- [បន្ថែមថ្មី] មុខងារគណនាថ្ងៃផុតកំណត់ ---
@app.route('/api/license_info')
def get_license():
    # កំណត់ថ្ងៃផុតកំណត់នៅទីនេះ
    expiry_date = datetime.datetime(2026, 4, 26, 23, 59, 59) 
    now = datetime.datetime.now()
    remaining = int((expiry_date - now).total_seconds())
    return jsonify({
        "id": "03000200-0",
        "status": "Active ✅" if remaining > 0 else "Expired ❌",
        "remaining_seconds": max(0, remaining)
    })

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
        min_g = int(data.get('min_speed', -15))
        max_g = int(data.get('max_speed', 90))
        final_speed = max(min_g, min(max_g, speed_base))
        rate = f"+{final_speed}%" if final_speed >= 0 else f"{final_speed}%"
        pitch = int(data.get('pitch', 0))
        preset = data.get('preset', 'normal')
        task_id = "preview_" + str(uuid.uuid4())[:8]
        temp_path = os.path.join(STATIC_DIR, f"{task_id}.mp3")
        
        async def make_preview():
            await edge_tts.Communicate(text, voice, rate=rate).save(temp_path)
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
    task_id = str(uuid.uuid4())[:8] # ប្រើ ID ខ្លីងាយស្រួលមើល
    progress_db[task_id] = 0
    threading.Thread(target=lambda: asyncio.run(run_conversion(task_id, data))).start()
    return jsonify({"task_id": task_id})

async def run_conversion(task_id, data):
    try:
        items = data['items']
        voice = data['voice']
        speed_base = int(data['speed'])
        min_g = int(data.get('min_speed', -15))
        max_g = int(data.get('max_speed', 90))
        final_speed = max(min_g, min(max_g, speed_base))
        pitch = int(data['pitch'])
        preset = data['preset']
        # [បន្ថែមថ្មី] ទទួលឈ្មោះហ្វាយពី Client
        custom_name = data.get('filename', 'result').strip() or "result"
        
        max_duration = items[-1]['end'] + 3000
        full_audio = AudioSegment.silent(duration=max_duration)
        rate_str = f"+{final_speed}%" if final_speed >= 0 else f"{final_speed}%"
        
        for i, item in enumerate(items):
            temp_file = os.path.join(STATIC_DIR, f"temp_{task_id}_{i}.mp3")
            await edge_tts.Communicate(item['text'], voice, rate=rate_str).save(temp_file)
            if os.path.exists(temp_file):
                seg = AudioSegment.from_mp3(temp_file)
                if preset != 'normal': seg = apply_preset(seg, preset)
                if pitch != 0: seg = change_pitch(seg, pitch)
                full_audio = full_audio.overlay(seg, position=item['start'])
                os.remove(temp_file)
            progress_db[task_id] = int(((i + 1) / len(items)) * 100)
        
        # រក្សាទុកតាមឈ្មោះដែលបងចង់បាន
        output_file = os.path.join(STATIC_DIR, f"{custom_name}_{task_id}.mp3")
        full_audio.export(output_file, format="mp3")
        progress_db[task_id] = "done"
    except:
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
    app.run(host='0.0.0.0', port=5000, debug=True)