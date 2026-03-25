from flask import Flask, render_template, request, jsonify
import os, asyncio, edge_tts, uuid, threading, time
from pydub import AudioSegment

# --- ១. កំណត់ផ្លូវ FFmpeg ឱ្យចំគោលដៅ ១០០% ---
ffmpeg_path = r"C:\Users\KOLDER\Downloads\ffmpeg-2026-03-22-git-9c63742425-full_build\ffmpeg\bin\ffmpeg.exe"
ffprobe_path = r"C:\Users\KOLDER\Downloads\ffmpeg-2026-03-22-git-9c63742425-full_build\ffmpeg\bin\ffprobe.exe"

AudioSegment.converter = ffmpeg_path
AudioSegment.ffprobe = ffprobe_path

app = Flask(__name__)
STATIC_DIR = 'static'
if not os.path.exists(STATIC_DIR): os.makedirs(STATIC_DIR)

progress_db = {}

# មុខងារប្ដូរ Pitch (ស្រួច/គ្រលរ)
def change_pitch(seg, pitch):
    if pitch == 0: return seg
    # ប្ដូរ Sample Rate ដើម្បីបង្កើតសម្លេងប្លែក
    new_sample_rate = int(seg.frame_rate * (2.0 ** (pitch / 12.0)))
    return seg._spawn(seg.raw_data, overrides={'frame_rate': new_sample_rate}).set_frame_rate(44100)

# មុខងារជំនួយសម្រាប់ EQ
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
        text = "សួស្តីបង! នេះគឺជាសំឡេងសាកល្បងពី ភី អេស មីឌៀ។"
        voice = data['voice']
        
        # Speed Guard Fix
        speed_val = int(data.get('speed', 0))
        rate = f"+{speed_val}%" if speed_val >= 0 else f"{speed_val}%"
        
        pitch = int(data.get('pitch', 0))
        preset = data.get('preset', 'normal')
        
        task_id = "preview_" + str(uuid.uuid4())[:8]
        temp_path = os.path.join(STATIC_DIR, f"{task_id}.mp3")
        
        async def make_preview():
            await edge_tts.Communicate(text, voice, rate=rate).save(temp_path)
            if os.path.exists(temp_path):
                seg = AudioSegment.from_mp3(temp_path)
                if preset != 'normal': seg = apply_preset(seg, preset)
                if pitch != 0: seg = change_pitch(seg, pitch) # បើកដំណើរការ Pitch
                seg.export(temp_path, format="mp3")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(make_preview())
        loop.close()
        return jsonify({"url": f"/static/{task_id}.mp3?v={time.time()}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/start', methods=['POST'])
def start_task():
    data = request.json
    task_id = str(uuid.uuid4())
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
        
        # បង្កើត Timeline
        max_duration = items[-1]['end'] + 3000
        full_audio = AudioSegment.silent(duration=max_duration)
        
        for i, item in enumerate(items):
            rate_str = f"+{speed_base}%" if speed_base >= 0 else f"{speed_base}%"
            temp_file = os.path.join(STATIC_DIR, f"temp_{task_id}_{i}.mp3")
            
            await edge_tts.Communicate(item['text'], voice, rate=rate_str).save(temp_file)
            
            if os.path.exists(temp_file):
                seg = AudioSegment.from_mp3(temp_file)
                if preset != 'normal': seg = apply_preset(seg, preset)
                if pitch != 0: seg = change_pitch(seg, pitch) # បើកដំណើរការ Pitch ពេលផលិតពេញ
                
                full_audio = full_audio.overlay(seg, position=item['start'])
                os.remove(temp_file)
            
            progress_db[task_id] = int(((i + 1) / len(items)) * 100)
        
        output_file = os.path.join(STATIC_DIR, f"result_{task_id}.mp3")
        full_audio.export(output_file, format="mp3")
        progress_db[task_id] = "done"
    except Exception as e:
        progress_db[task_id] = "error"

@app.route('/api/progress/<task_id>')
def get_progress(task_id):
    return jsonify({"progress": progress_db.get(task_id, 0)})

@app.route('/api/files')
def list_files():
    files = []
    if os.path.exists(STATIC_DIR):
        for f in os.listdir(STATIC_DIR):
            if f.startswith('result_'):
                path = os.path.join(STATIC_DIR, f)
                files.append({
                    "name": f,
                    "url": f"/static/{f}",
                    "time": time.ctime(os.path.getctime(path)),
                    "size": f"{round(os.path.getsize(path) / (1024*1024), 2)} MB"
                })
    return jsonify(sorted(files, key=lambda x: x['time'], reverse=True))

@app.route('/api/delete/<filename>', methods=['DELETE'])
def delete_file(filename):
    path = os.path.join(STATIC_DIR, filename)
    if os.path.exists(path):
        os.remove(path)
        return jsonify({"status":"ok"})
    return jsonify({"status":"error"}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)