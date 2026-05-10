import os
import replicate
import uuid
import subprocess
import shutil
import uvicorn
import yt_dlp
import requests
from fastapi import FastAPI, Request, File, UploadFile, BackgroundTasks, Form
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates
from groq import Groq

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# ==========================================
# 🔑 منطقة المفاتيح السحابية
# ==========================================
GROQ_API_KEY = "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"
COOKIES_FILE = "cookies.txt"


YDL_OPTS = {
    'quiet': True, 'no_warnings': True, 'no_check_certificate': True,
    'format': 'bestvideo+bestaudio/best',
    'cookiefile': COOKIES_FILE if os.path.exists(COOKIES_FILE) else None,
    'http_headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
}

def cleanup_files(*files):
    for f in files:
        if f and os.path.exists(f):
            try: os.remove(f)
            except: pass

@app.get('/favicon.ico', include_in_schema=False)
async def favicon(): return JSONResponse(content={})

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

# ==========================================
# 🚀 المحرك الرئيسي (التحليل والتحميل)
# ==========================================
@app.post("/analyze")
async def analyze_video(data: dict):
    try:
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            info = ydl.extract_info(data.get("url"), download=False)
            formats = [{"id": f.get('format_id'), "res": f.get('height'), "label": f"{f.get('height')}p" if f.get('height') else "Audio", "size": f"{round(f['filesize']/1024/1024, 1)} MB" if f.get('filesize') else "HQ"} 
                       for f in reversed(info.get('formats', [])) if f.get('format_id')]
            seen = set()
            unique_formats = [x for x in formats if x['label'] not in seen and not seen.add(x['label'])][:6]
            return {"success": True, "title": info.get('title'), "thumbnail": info.get('thumbnail'), "formats": unique_formats}
    except Exception as e: return {"success": False, "error": str(e)}

@app.get("/download")
async def download(url: str, format_id: str, is_audio: str = "false", start_time: str = None, end_time: str = None, preview: str = "false"):
    is_audio_bool = is_audio.lower() == 'true'
    is_preview = preview.lower() == 'true'
    extension = "mp3" if is_audio_bool else "mp4"
    filename = f"U2_Pro_Media.{extension}"
    disposition = "inline" if is_preview else "attachment"
    
    def stream():
        format_spec = 'bestaudio/best' if is_audio_bool else f'{format_id}+bestaudio/best/best'
        cmd = ['yt-dlp', '--no-check-certificate', '-f', format_spec, '-o', '-']
        if start_time and end_time: cmd.extend(['--download-sections', f'*{start_time}-{end_time}'])
        if os.path.exists(COOKIES_FILE): cmd.extend(['--cookies', COOKIES_FILE])
        cmd.append(url)
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            while chunk := p.stdout.read(1024*1024): yield chunk
        finally: p.kill()
            
    return StreamingResponse(stream(), media_type="audio/mpeg" if is_audio_bool else "video/mp4", headers={"Content-Disposition": f'{disposition}; filename="{filename}"'})

# ==========================================
# ✂️ مقص الإمبراطور (Auto Silence Remover)
# ==========================================
@app.post("/tools/silence/local")
async def remove_silence_local(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    ext = file.filename.split('.')[-1]
    in_file = f"in_sil_{uuid.uuid4().hex[:5]}.{ext}"
    out_file = f"out_sil_{uuid.uuid4().hex[:5]}.mp4"
    try:
        with open(in_file, "wb") as f: shutil.copyfileobj(file.file, f)
        cmd = f'python -m auto_editor {in_file} --margin 0.2sec --video-codec libx264 --audio-codec aac -o {out_file}'
        subprocess.run(cmd, shell=True, check=True)
        background_tasks.add_task(cleanup_files, in_file, out_file)
        return FileResponse(out_file, media_type="video/mp4", filename=f"U2_NoSilence_{file.filename}.mp4")
    except Exception as e:
        cleanup_files(in_file, out_file)
        return JSONResponse({"success": False, "error": "فشل القص التلقائي"})

@app.post("/tools/silence/url")
async def remove_silence_url(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    base = f"tmp_sil_{uuid.uuid4().hex[:5]}"
    in_file = None; out_file = f"out_{base}.mp4"
    try:
        opts = {
            'format': 'bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'merge_output_format': 'mp4',
            'outtmpl': f'{base}.%(ext)s', 
            'quiet': True
        }
        if os.path.exists(COOKIES_FILE): opts['cookiefile'] = COOKIES_FILE
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(data.get("url"), download=True)
            in_file = f"{base}.mp4"
            title = info.get('title', 'Video')[:15].replace('/', '_')
            
        cmd = f'python -m auto_editor {in_file} --margin 0.2sec --video-codec libx264 --audio-codec aac -o {out_file}'
        subprocess.run(cmd, shell=True, check=True)
        
        background_tasks.add_task(cleanup_files, in_file, out_file)
        return FileResponse(out_file, media_type="video/mp4", filename=f"U2_NoSilence_{title}.mp4")
    except Exception as e:
        if in_file: cleanup_files(in_file, out_file)
        return JSONResponse({"success": False, "error": "فشل القص"})

# ==========================================
# ⚡ المحرك العالمي للتفريغ الصوتي (Whisper-Large-V3)
# ==========================================
def transcribe_with_ai(file_path):
    """
    هنا التعديل السحري: استخراج الصوت فقط وضغطه لحجم صغير جداً
    لمنع الـ Timeout وتسريع الرفع للذكاء الاصطناعي أضعاف مضاعفة!
    """
    compressed_audio = f"tmp_audio_ai_{uuid.uuid4().hex[:5]}.mp3"
    try:
        # استخراج الصوت بضغط 64k (يقلل حجم الـ 100 ميجا لـ 1 ميجا فقط!)
        subprocess.run(['ffmpeg', '-y', '-i', file_path, '-vn', '-c:a', 'libmp3lame', '-b:a', '64k', compressed_audio], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        
        client = Groq(api_key=GROQ_API_KEY)
        with open(compressed_audio, "rb") as f:
            ts = client.audio.transcriptions.create(
                file=("audio.mp3", f.read()), # نخدع API ونقوله ده ملف صوتي صغير
                model="whisper-large-v3", 
                response_format="verbose_json"
            )
        cleanup_files(compressed_audio)
        return ts
    except Exception as e:
        cleanup_files(compressed_audio)
        print(f"Transcription Error: {e}")
        raise e

# ==========================================
# 🌐 محرك الترجمة والدمج التلقائي
# ==========================================
def format_time(seconds):
    h, m, s = int(seconds // 3600), int((seconds % 3600) // 60), int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def translate_and_build_srt(transcription, target_lang):
    segments = getattr(transcription, 'segments', []) if not isinstance(transcription, dict) else transcription.get('segments', [])
    def get_val(seg, key, default=0): return seg.get(key, default) if isinstance(seg, dict) else getattr(seg, key, default)
    
    if target_lang == "Original":
        srt_content = ""
        for i, s in enumerate(segments, start=1):
            srt_content += f"{i}\n{format_time(get_val(s, 'start'))} --> {format_time(get_val(s, 'end'))}\n{get_val(s, 'text', '').strip()}\n\n"
        return srt_content

    lines_to_translate = "\n".join([f"{i}|{get_val(s, 'text', '').strip()}" for i, s in enumerate(segments)])
    try:
        client = Groq(api_key=GROQ_API_KEY)
        prompt = f"You are a strict professional translator. Translate to {target_lang}. Keep the exact format 'ID|Text'. DO NOT add any intro, notes, or outro. Translate everything accurately:\n\n{lines_to_translate}"
        chat = client.chat.completions.create(messages=[{"role": "user", "content": prompt}], model="llama-3.1-8b-instant")
        trans_dict = {}
        for line in chat.choices[0].message.content.split('\n'):
            if '|' in line:
                parts = line.split('|', 1)
                try: trans_dict[int(parts[0].strip())] = parts[1].strip()
                except: pass
                
        srt_content = ""
        for i, s in enumerate(segments, start=1):
            text = trans_dict.get(i, get_val(s, 'text', ''))
            srt_content += f"{i}\n{format_time(get_val(s, 'start'))} --> {format_time(get_val(s, 'end'))}\n{text}\n\n"
        return srt_content
    except Exception as e:
        return "1\n00:00:00,000 --> 00:00:05,000\n[خطأ في الترجمة]\n\n"

async def process_auto_sub(in_file, target_lang, action, background_tasks, out_name_base):
    srt_file = f"sub_{uuid.uuid4().hex[:5]}.srt"; out_video = f"final_{uuid.uuid4().hex[:5]}.mp4"
    try:
        ts = transcribe_with_ai(in_file)
            
        srt_content = translate_and_build_srt(ts, target_lang)
        if action == "srt":
            background_tasks.add_task(cleanup_files, in_file)
            return StreamingResponse(iter([srt_content.encode("utf-8")]), media_type="text/plain", headers={"Content-Disposition": f'attachment; filename="U2_{target_lang}_Subs.srt"'})
        else:
            with open(srt_file, "w", encoding="utf-8") as f: f.write(srt_content)
            subprocess.run(['ffmpeg', '-y', '-i', in_file, '-f', 'srt', '-i', srt_file, '-c:v', 'copy', '-c:a', 'copy', '-c:s', 'mov_text', out_video], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            background_tasks.add_task(cleanup_files, in_file, srt_file, out_video)
            return FileResponse(out_video, media_type="video/mp4", filename=f"U2_Subbed_{out_name_base}.mp4")
    except Exception as e:
        cleanup_files(in_file, srt_file, out_video)
        return JSONResponse({"success": False, "error": str(e)})

@app.post("/tools/autosub/url")
async def autosub_url(request: Request, background_tasks: BackgroundTasks):
    data = await request.json(); base = f"tmp_{uuid.uuid4().hex[:5]}"; in_file = None
    try:
        opts = {'format': 'bestvideo[height<=720]+bestaudio/best', 'outtmpl': f'{base}.%(ext)s', 'quiet': True}
        if os.path.exists(COOKIES_FILE): opts['cookiefile'] = COOKIES_FILE
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(data.get("url"), download=True)
            in_file = f"{base}.{info.get('ext', 'mp4')}"
            title = info.get('title', 'Video').replace('/', '_').replace('\\', '_')[:15]
        return await process_auto_sub(in_file, data.get("lang"), data.get("action"), background_tasks, title)
    except Exception as e: 
        if in_file: cleanup_files(in_file)
        return JSONResponse({"success": False, "error": str(e)})

@app.post("/tools/autosub/local")
async def autosub_local(background_tasks: BackgroundTasks, file: UploadFile = File(...), lang: str = Form(...), action: str = Form(...)):
    ext = file.filename.split('.')[-1]; in_file = f"in_vid_{uuid.uuid4().hex[:5]}.{ext}"
    try:
        with open(in_file, "wb") as f: shutil.copyfileobj(file.file, f)
        return await process_auto_sub(in_file, lang, action, background_tasks, "LocalFile")
    except Exception as e: return JSONResponse({"success": False, "error": str(e)})

# ==========================================
# 🧠 استوديو التفريغ النصي الدقيق
# ==========================================
def process_to_json(transcription):
    segments = getattr(transcription, 'segments', []) if not isinstance(transcription, dict) else transcription.get('segments', [])
    text_content = ""
    for s in segments: text_content += f"[{round(s.get('start', 0), 2)}s] {s.get('text', '').strip()}\n"
    return text_content

@app.post("/tools/subs")
async def get_subs(data: dict):
    url = data.get("url"); base = f"tmp_{uuid.uuid4().hex[:5]}"; file_path = None
    try:
        opts = {'format':'bestaudio/best','outtmpl':f'{base}.%(ext)s','quiet':True}
        if os.path.exists(COOKIES_FILE): opts['cookiefile'] = COOKIES_FILE
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True); file_path = f"{base}.{info['ext']}"
        
        ts = transcribe_with_ai(file_path)
        cleanup_files(file_path)
        return {"success": True, "text": process_to_json(ts)}
    except Exception as e:
        if file_path: cleanup_files(file_path)
        return {"success": False, "error": str(e)}

@app.post("/tools/subs/upload")
async def upload_subs(file: UploadFile = File(...)):
    path = f"up_{uuid.uuid4().hex[:5]}_{file.filename}"
    try:
        with open(path, "wb") as b: shutil.copyfileobj(file.file, b)
        
        ts = transcribe_with_ai(path)
        cleanup_files(path)
        return {"success": True, "text": process_to_json(ts)}
    except Exception as e: 
        cleanup_files(path)
        return {"success": False, "error": str(e)}

# ==========================================
# 🎧 مُنقي الصوت AI
# ==========================================
AUDIO_FILTER = "afftdn=nf=-25,highpass=f=150,loudnorm"

@app.post("/tools/denoise/local")
async def denoise_local(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    ext = file.filename.split('.')[-1]; in_file = f"in_{uuid.uuid4().hex[:5]}.{ext}"; out_file = f"clean_{uuid.uuid4().hex[:5]}.{ext}"
    try:
        with open(in_file, "wb") as f: shutil.copyfileobj(file.file, f)
        subprocess.run(['ffmpeg', '-y', '-i', in_file, '-af', AUDIO_FILTER, '-c:v', 'copy', out_file], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        background_tasks.add_task(cleanup_files, in_file, out_file)
        return FileResponse(out_file, media_type="application/octet-stream", filename=f"U2_Clean_{file.filename}")
    except: cleanup_files(in_file, out_file); return JSONResponse({"success": False, "error": "فشل التنقية"})

@app.post("/tools/denoise/url")
async def denoise_url(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    url = data.get("url")
    base = f"tmp_denoise_{uuid.uuid4().hex[:5]}"
    in_file = None
    out_file = f"clean_{base}.mp4"

    try:
        # 1. تحميل الفيديو
        opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': f'{base}.%(ext)s',
            'quiet': True
        }
        if os.path.exists(COOKIES_FILE):
            opts['cookiefile'] = COOKIES_FILE
            
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            in_file = f"{base}.{info.get('ext', 'mp4')}"
            title = info.get('title', 'Video')[:15].replace('/', '_')

        # 2. تنقية الصوت بالـ FFmpeg
        subprocess.run(['ffmpeg', '-y', '-i', in_file, '-af', AUDIO_FILTER, '-c:v', 'copy', out_file], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        # 3. إرجاع الملف النهائي ومسح المؤقت
        background_tasks.add_task(cleanup_files, in_file, out_file)
        return FileResponse(out_file, media_type="video/mp4", filename=f"U2_Clean_{title}.mp4")

    except Exception as e:
        if in_file:
            cleanup_files(in_file, out_file)
        return JSONResponse({"success": False, "error": f"فشل التنقية: {str(e)}"})

# ==========================================
# 📱 صانع الشورتس والريلز
# ==========================================
SHORTS_FILTER = "crop=ih*(9/16):ih,scale=1080:1920"

@app.post("/tools/shorts/local")
async def make_shorts_local(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    ext = file.filename.split('.')[-1]
    in_file = f"in_shorts_{uuid.uuid4().hex[:5]}.{ext}"
    out_file = f"shorts_{uuid.uuid4().hex[:5]}.mp4"
    try:
        with open(in_file, "wb") as f: shutil.copyfileobj(file.file, f)
        subprocess.run(['ffmpeg', '-y', '-i', in_file, '-vf', SHORTS_FILTER, '-c:a', 'copy', out_file], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        background_tasks.add_task(cleanup_files, in_file, out_file)
        return FileResponse(out_file, media_type="video/mp4", filename=f"U2_Shorts_{file.filename}")
    except Exception as e:
        cleanup_files(in_file, out_file)
        return JSONResponse({"success": False, "error": "فشل التحويل"})

@app.post("/tools/shorts/url")
async def make_shorts_url(request: Request, background_tasks: BackgroundTasks):
    data = await request.json(); base = f"tmp_s_{uuid.uuid4().hex[:5]}"; in_file = None
    try:
        opts = {'format': 'bestvideo[height<=720]+bestaudio/best', 'outtmpl': f'{base}.%(ext)s', 'quiet': True}
        if os.path.exists(COOKIES_FILE): opts['cookiefile'] = COOKIES_FILE
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(data.get("url"), download=True); in_file = f"{base}.{info['ext']}"; out_file = f"s_{base}.mp4"
        subprocess.run(['ffmpeg', '-y', '-i', in_file, '-vf', SHORTS_FILTER, '-c:a', 'copy', out_file], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        background_tasks.add_task(cleanup_files, in_file, out_file)
        return FileResponse(out_file, media_type="video/mp4", filename="U2_Shorts.mp4")
    except: 
        if in_file: cleanup_files(in_file)
        return JSONResponse({"success": False, "error": "فشل التحويل"})

# ==========================================
# 🖼️ صائد الأغلفة 4K
# ==========================================
@app.post("/tools/thumbnail")
async def get_thumbnail(data: dict):
    try:
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(data.get("url"), download=False); return {"success": True, "url": info.get('thumbnail')}
    except: return {"success": False, "error": "فشل جلب الصورة"}

@app.get("/tools/download_thumb_proxy")
async def download_thumb_proxy(img_url: str):
    req = requests.get(img_url, stream=True)
    return StreamingResponse(req.iter_content(chunk_size=1024), media_type="image/jpeg", headers={"Content-Disposition": 'attachment; filename="U2_Cover.jpg"'})

# ==========================================
# 🎙️ محرك الدبلجة الإمبراطوري (النسخة المستقرة)
# ==========================================
import edge_tts

# ==========================================
# 🎙️ محرك الدبلجة السينمائي (ضبط السرعة + جودة HQ)
# ==========================================
@app.post("/tools/dub/url")
async def ai_dubber(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    url = data.get("url")
    voice_name = data.get("voice_name", "ar-EG-ShakirNeural")
    base = f"dub_{uuid.uuid4().hex[:5]}"
    in_vid = f"{base}_in.mp4"
    ai_voice = f"{base}_voice.mp3"
    final_vid = f"U2_Dubbed_{uuid.uuid4().hex[:5]}.mp4"

    try:
        # 1. تحميل الفيديو
        # 1. تحميل الفيديو (تعديل الأوامر لضمان عدم الفشل)
        opts = {
            'format': 'bestvideo+bestaudio/best', # هات أحسن جودة فيديو وصوت متاحين وادمجهم
            'outtmpl': in_vid,
            'quiet': True,
            'no_warnings': True,
            # إضافة معالج للأخطاء عشان لو الجودة مش موجودة ميفصلش
            'format_sort': ['res:480', 'ext:mp4:m4a'], 
        }
        
        # التأكد من وجود ملف الكوكيز لو متاح عشان ميتعملش بلوك
        if os.path.exists(COOKIES_FILE): 
            opts['cookiefile'] = COOKIES_FILE
            
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])

        # 2. التفريغ
        ts = transcribe_with_ai(in_vid)
        raw_text = " ".join([s.get('text', '') if isinstance(s, dict) else getattr(s, 'text', '') for s in getattr(ts, 'segments', [])])

        # 3. الترجمة الصارمة (Strict Translation)
        target_lang_name = "Arabic" if "ar-" in voice_name else "English"
        client = Groq(api_key=GROQ_API_KEY)
        
        # عدلنا الـ Prompt هنا عشان نجبره ميكتبش أي حرف زيادة
        trans_prompt = f"Translate the following text to natural {target_lang_name}. Return ONLY the translated text. Do not include 'Here is the translation' or any English characters if translating to Arabic:\n\n{raw_text}"
        
        chat = client.chat.completions.create(messages=[{"role": "user", "content": trans_prompt}], model="llama-3.1-8b-instant")
        translated_text = chat.choices[0].message.content.strip()

        # 🛡️ فلتر أمان إضافي: إزالة أي حروف إنجليزية لو الدبلجة عربي
        if "ar-" in voice_name:
            import re
            translated_text = re.sub(r'[a-zA-Z]', '', translated_text)

        # 4. توليد الصوت
        communicate = edge_tts.Communicate(translated_text, voice_name, rate='-10%')
        await communicate.save(ai_voice)

        # 5. الدمج
        cmd = [
            'ffmpeg', '-y', '-i', in_vid, '-i', ai_voice,
            '-filter_complex', "[0:a]volume=0.15[bg]; [1:a]volume=1.8[voice]; [bg][voice]amix=inputs=2:duration=first[a]",
            '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', final_vid
        ]
        subprocess.run(cmd, check=True)

        background_tasks.add_task(cleanup_files, in_vid, ai_voice, final_vid)
        return FileResponse(final_vid, media_type="video/mp4", filename=f"U2_Cinema_Dub.mp4")

    except Exception as e:
        print(f"❌ Error in Dubbing: {e}")
        cleanup_files(in_vid, ai_voice, final_vid)
        return JSONResponse({"success": False, "error": str(e)})
    
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 1000))
    uvicorn.run(app, host="0.0.0.0", port=port)
