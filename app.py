import os
import re
import asyncio
import uuid
import time
from flask import Flask, render_template, request, send_file, jsonify, url_for
import google.generativeai as genai
import edge_tts

app = Flask(__name__)

# --- ១. ការកំណត់សុវត្ថិភាព (Security Configuration) ---
# កូដនេះទាញយក Key ពី Render Environment
API_KEY = os.environ.get("GEMINI_API_KEY") 
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# បង្កើត Folder សម្រាប់ទុកឯកសារ
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static/uploads')
PROCESSED_FOLDER = os.path.join(BASE_DIR, 'static/processed')

for folder in [UPLOAD_FOLDER, PROCESSED_FOLDER]:
    os.makedirs(folder, exist_ok=True)

# កម្រិតការបុក API កុំឱ្យជាប់ Error 429
sem = asyncio.Semaphore(10)

# --- ២. Logic បកប្រែរឿង (Translation Engine) ---
async def translate_line(text):
    """បកប្រែអត្ថបទនីមួយៗឱ្យមានភាពរស់រវើក"""
    if not text.strip() or not re.search(r'[\u4e00-\u9fff]', text):
        return text

    async with sem:
        try:
            prompt = (
                f"You are an expert movie narrator. Translate this subtitle to natural Khmer "
                f"for a movie recap: {text}"
            )
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: model.generate_content(prompt))
            return response.text.strip()
        except Exception as e:
            print(f"Translation Error: {e}")
            return text

# --- ៣. Routes សម្រាប់ Interface ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
async def process_media():
    if 'file' not in request.files:
        return jsonify({"error": "រកមិនឃើញ File"}), 400
    
    file = request.files['file']
    file_id = str(uuid.uuid4())[:8]
    input_filename = f"{file_id}_{file.filename}"
    input_path = os.path.join(UPLOAD_FOLDER, input_filename)
    file.save(input_path)

    # អាន និងបកប្រែ
    with open(input_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    tasks = [translate_line(line) for line in lines]
    translated_content = await asyncio.gather(*tasks)
    
    output_filename = f"PS_PRO_{file_id}.srt"
    output_path = os.path.join(PROCESSED_FOLDER, output_filename)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("".join(translated_content))

    return jsonify({
        "success": True, 
        "download_url": url_for('static', filename=f'processed/{output_filename}'),
        "filename": output_filename
    })

@app.route('/generate_tts', methods=['POST'])
async def generate_tts():
    data = request.json
    text = data.get('text')
    
    # ចាប់យកតម្លៃពី Slider ក្នុង UI
    voice = data.get('voice', 'km-KH-PisethNeural')
    speed = data.get('speed', '+0%')   # ទាញពី Slider ល្បឿន
    pitch = data.get('pitch', '+0Hz')  # ទាញពី Slider Pitch

    if not text:
        return jsonify({"error": "គ្មានអត្ថបទ"}), 400

    audio_id = uuid.uuid4().hex[:8]
    audio_filename = f"PS_VOICE_{audio_id}.mp3"
    audio_path = os.path.join(PROCESSED_FOLDER, audio_filename)

    try:
        # បញ្ជូន Parameters ទៅកាន់ Edge TTS
        communicate = edge_tts.Communicate(text, voice, rate=speed, pitch=pitch)
        await communicate.save(audio_path)
        return jsonify({
            "success": True,
            "audio_url": url_for('static', filename=f'processed/{audio_filename}')
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- ៤. Deployment Setup (Render) ---
if __name__ == "__main__":
    # សំខាន់បំផុត៖ ប្រើ Port ពី Render Environment
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)