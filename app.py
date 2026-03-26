import os
import re
import asyncio
import time
import uuid
from flask import Flask, render_template, request, send_file, jsonify, url_for
import google.generativeai as genai
import edge_tts
from pydub import AudioSegment
from datetime import datetime

app = Flask(__name__)

# --- ១. ការកំណត់រចនាសម្ព័ន្ធ (Configuration) ---
API_KEY = "YOUR_GEMINI_API_KEY_HERE" 
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# បង្កើត Folder សម្រាប់ទុកឯកសារ
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static/uploads')
PROCESSED_FOLDER = os.path.join(BASE_DIR, 'static/processed')

for folder in [UPLOAD_FOLDER, PROCESSED_FOLDER]:
    os.makedirs(folder, exist_ok=True)

# ប្រើ Semaphore ដើម្បីការពារកុំឱ្យបុក API ខ្លាំងពេក (Concurrency Control)
sem = asyncio.Semaphore(3)

# --- ២. Logic សម្រាប់បកប្រែ (Advanced Translation) ---
async def translate_text_async(text, target_lang="Khmer"):
    async with sem:
        try:
            prompt = (
                f"You are an expert movie narrator. Translate this subtitle to {target_lang}. "
                "Use natural, engaging, and emotional language suitable for a movie recap. "
                f"Text: {text}"
            )
            # ដោយសារ Gemini SDK បច្ចុប្បន្នភាគច្រើនជា Synchronous យើងប្រើ run_in_executor
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: model.generate_content(prompt))
            return response.text.strip()
        except Exception as e:
            print(f"Translation Error: {e}")
            await asyncio.sleep(2) # បើ Error ឱ្យវាសម្រាកបន្តិច
            return text

def clean_srt_content(content):
    """បំបែក SRT យកតែអត្ថបទចិនមកបកប្រែ"""
    lines = content.split('\n')
    return lines

# --- ៣. Routes សម្រាប់ Interface ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
async def process_media():
    if 'file' not in request.files:
        return jsonify({"error": "រកមិនឃើញឯកសារ"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "មិនបានជ្រើសរើសឯកសារ"}), 400

    # រក្សាទុកឯកសារដើម
    file_id = str(uuid.uuid4())[:8]
    input_filename = f"{file_id}_{file.filename}"
    input_path = os.path.join(UPLOAD_FOLDER, input_filename)
    file.save(input_path)

    # អានខ្លឹមសារ SRT
    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = clean_srt_content(content)
    translated_tasks = []
    
    # ចាប់ផ្ដើមបកប្រែ (បកតែជួរណាដែលមានអក្សរចិន)
    for line in lines:
        if re.search(r'[\u4e00-\u9fff]', line):
            translated_tasks.append(translate_text_async(line))
        else:
            # បើជាលេខរៀង ឬម៉ោង រក្សាទុកដដែល
            future = asyncio.Future()
            future.set_result(line)
            translated_tasks.append(future)

    translated_lines = await asyncio.gather(*translated_tasks)
    
    # រក្សាទុកឯកសារដែលបកប្រែរួច
    output_filename = f"khmer_{input_filename}"
    output_path = os.path.join(PROCESSED_FOLDER, output_filename)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(translated_lines))

    return jsonify({
        "success": True, 
        "download_url": url_for('static', filename=f'processed/{output_filename}'),
        "message": "បកប្រែជោគជ័យ!"
    })

@app.route('/generate_tts', methods=['POST'])
async def generate_tts():
    data = request.json
    text = data.get('text')
    voice = data.get('voice', 'km-KH-PisethNeural')

    if not text:
        return jsonify({"error": "គ្មានអត្ថបទ"}), 400

    audio_filename = f"tts_{uuid.uuid4().hex[:8]}.mp3"
    audio_path = os.path.join(PROCESSED_FOLDER, audio_filename)

    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(audio_path)
        return jsonify({"audio_url": url_for('static', filename=f'processed/{audio_filename}')})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- ៤. បញ្ចប់ការកំណត់សម្រាប់ Deployment (Render) ---
if __name__ == "__main__":
    # ប្រើ Port ពី Render Environment
    port = int(os.environ.get("PORT", 5000))
    # បើកដំណើរការ Server
    app.run(host="0.0.0.0", port=port, debug=False)