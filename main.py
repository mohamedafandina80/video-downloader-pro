import os
import uuid
import sqlite3
import hashlib
import requests
import uvicorn
import yt_dlp
import subprocess
import shutil
from fastapi import FastAPI, Request, File, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# 1. تفعيل مسار FFmpeg المحمل في Render
os.environ["PATH"] += os.pathsep + os.path.join(os.getcwd(), "ffmpeg")

# 2. ملف الكوكيز (تأكد من رفعه مع المشروع)
COOKIES_FILE = "cookies.txt"

# 3. مفتاح Groq من إعدادات البيئة
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# خيارات yt-dlp للتحليل
YDL_OPTS = {
    'quiet': True, 
    'no_warnings': True, 
    'no_check_certificate': True,
    'format': 'bestvideo+bestaudio/best',
    'cookiefile': COOKIES_FILE if os.path.exists(COOKIES_FILE) else None,
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
}

def init_db():
    conn = sqlite3.connect("u2_pro_database.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, avatar TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, title TEXT, type TEXT, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

init_db()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.post("/analyze")
async def analyze_video(data: dict):
    try:
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            info = ydl.extract_info(data.get("url"), download=False)
            formats = []
            for f in reversed(info.get('formats', [])):
                if f.get('height') and f.get('vcodec') != 'none':
                    formats.append({
                        "id": f.get('format_id'),
                        "res": f.get('height'),
                        "label": f"{f.get('height')}p",
                        "size": f"{round(f['filesize']/1024/1024, 1)} MB" if f.get('filesize') else "HQ"
                    })
            return {"success": True, "title": info.get('title'), "thumbnail": info.get('thumbnail'), "formats": formats[:6]}
    except:
        return {"success": False}

@app.get("/download")
async def download(url: str, format_id: str, is_audio: str = "false"):
    is_audio_bool = is_audio.lower() == 'true'
    
    def stream():
        # تعديل جوهري لضمان التحميل حتى لو الصيغة غير متوفرة
        if is_audio_bool:
            # طلب أفضل صوت
            cmd = ['yt-dlp', '--no-check-certificate', '-f', 'bestaudio/best', '-o', '-']
        else:
            # طلب المعرف المحدد، وإذا فشل يتم اختيار أفضل دمج متاح تلقائياً
            # f'{format_id}+bestaudio/best/best' هي السطر السحري لحل المشكلة
            cmd = ['yt-dlp', '--no-check-certificate', '-f', f'{format_id}+bestaudio/best/best', '-o', '-']
        
        if os.path.exists(COOKIES_FILE):
            cmd.extend(['--cookies', COOKIES_FILE])
        
        cmd.append(url)
        
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            while chunk := p.stdout.read(1024*1024):
                yield chunk
        finally:
            p.kill()

    return StreamingResponse(stream(), media_type="application/octet-stream")

# --- محرك الذكاء الاصطناعي ---
def process_to_json(transcription):
    segments = getattr(transcription, 'segments', []) if not isinstance(transcription, dict) else transcription.get('segments', [])
    return [{"start": round(s.get('start', 0), 2), "text": s.get('text', '').strip()} for s in segments]

@app.post("/tools/subs")
async def get_subs(data: dict):
    url = data.get("url")
    base = f"tmp_{uuid.uuid4().hex[:5]}"
    try:
        from groq import Groq
        opts = {'format':'bestaudio/best','outtmpl':f'{base}.%(ext)s','quiet':True}
        if os.path.exists(COOKIES_FILE): opts['cookiefile'] = COOKIES_FILE
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = f"{base}.{info['ext']}"
        client = Groq(api_key=GROQ_API_KEY)
        with open(file_path, "rb") as f:
            ts = client.audio.transcriptions.create(file=(file_path, f.read()), model="whisper-large-v3", response_format="verbose_json")
        if os.path.exists(file_path): os.remove(file_path)
        return {"success": True, "data": process_to_json(ts)}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/tools/subs/upload")
async def upload_subs(file: UploadFile = File(...)):
    path = f"up_{uuid.uuid4().hex[:5]}_{file.filename}"
    try:
        from groq import Groq
        with open(path, "wb") as b: shutil.copyfileobj(file.file, b)
        client = Groq(api_key=GROQ_API_KEY)
        with open(path, "rb") as f:
            ts = client.audio.transcriptions.create(file=(path, f.read()), model="whisper-large-v3", response_format="verbose_json")
        if os.path.exists(path): os.remove(path)
        return {"success": True, "data": process_to_json(ts)}
    except Exception as e: 
        if os.path.exists(path): os.remove(path)
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
