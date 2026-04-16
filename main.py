import os
import uuid
import uvicorn
import yt_dlp
import subprocess
import random
import string
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# ==========================================
# 👑 إعدادات وحش البروكسي السكني (التركي) 👑
# ==========================================

BRD_USERNAME = "brd-customer-hl_4f511c19-zone-residential_proxy1"
BRD_PASSWORD = "3c7p3o63umdv"

# توليد Session ID ثابت لكل عملية تشغيل لمنع تغيير الـ IP في نص التحميل
session_id = ''.join(random.choices(string.ascii_letters + string.digits, k=10))

# الرابط السحري المخترق لليوتيوب (توجيه تركي + Session ثابت)
SUCCESS_PROXY = f"http://{BRD_USERNAME}-country-tr-session-{session_id}:{BRD_PASSWORD}@brd.superproxy.io:33335"

# إعدادات المحرك الفولاذية
YDL_OPTS_BASE = {
    'quiet': True,
    'no_warnings': True,
    'no_check_certificate': True,
    'proxy': SUCCESS_PROXY, 
    'extract_flat': False,
    'http_chunk_size': 1048576, # سحب البيانات بذكاء لمنع الـ 0 بايت
    'extractor_args': {
        'youtube': {
            'player_client': ['web', 'mweb'], # التخفي كمتصفح حقيقي
        }
    }
}

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.post("/analyze")
async def analyze_video(data: dict):
    url = data.get("url")
    try:
        ydl_opts = YDL_OPTS_BASE.copy()
        ydl_opts['format'] = 'all' # إجبار يوتيوب يفك الكيس ويورينا كل الجودات
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_formats = []
            added_res = set()
            
            formats = info.get('formats', [])
            for f in reversed(formats):
                height = f.get('height')
                vcodec = f.get('vcodec', 'none')
                acodec = f.get('acodec', 'none')
                
                if height and vcodec != 'none':
                    if height not in added_res:
                        added_res.add(height)
                        
                        if height >= 2160: tag = "4K ULTRA HD"
                        elif height >= 1440: tag = "2K QHD"
                        elif height >= 1080: tag = "FULL HD"
                        elif height >= 720: tag = "HD"
                        else: tag = "SD"
                        
                        size = f.get('filesize') or f.get('filesize_approx')
                        size_str = f"{round(size/1024/1024, 1)} MB" if size else "MAX"
                        
                        video_formats.append({
                            "id": f.get('format_id'),
                            "res_val": height,
                            "label": f"{height}P {tag}",
                            "type": "video",
                            "size": size_str,
                            "needs_merge": True if acodec == 'none' else False
                        })
            
            video_formats.sort(key=lambda x: x['res_val'], reverse=True)
            final_list = [{"id": "bestaudio", "label": "MP3 AUDIO - جودة خرافية", "type": "audio", "size": "HQ", "needs_merge": True}] + video_formats
            
            return {"success": True, "title": info.get('title', 'Video'), "thumbnail": info.get('thumbnail', ''), "formats": final_list}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/download")
async def download(url: str, format_id: str, is_audio: bool = False, needs_merge: str = "false"):
    nm = needs_merge.lower() == "true"
    
    def stream_data():
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        
        if not nm and not is_audio:
            # التحميل المباشر للتيك توك أو الجودات البسيطة
            command = ['yt-dlp', '--proxy', SUCCESS_PROXY, '--no-part', '-f', format_id, '-o', '-', url]
        else:
            # التحميل المعقد لليوتيوب (صوت + صورة) عبر البروكسي السكني
            with yt_dlp.YoutubeDL(YDL_OPTS_BASE) as ydl:
                info = ydl.extract_info(url, download=False)
                if is_audio:
                    audio_url = info['url'] if 'url' in info else info['formats'][-1]['url']
                    command = [
                        'ffmpeg', '-user_agent', ua, '-http_proxy', SUCCESS_PROXY, 
                        '-i', audio_url, '-c:a', 'libmp3lame', '-f', 'mp3', 'pipe:1'
                    ]
                else:
                    if 'requested_formats' in info:
                        v_url = info['requested_formats'][0]['url']
                        a_url = info['requested_formats'][1]['url']
                        command = [
                            'ffmpeg', 
                            '-user_agent', ua, '-http_proxy', SUCCESS_PROXY, '-i', v_url,
                            '-user_agent', ua, '-http_proxy', SUCCESS_PROXY, '-i', a_url,
                            '-c:v', 'copy', '-c:a', 'aac', '-f', 'mp4', 
                            '-movflags', 'frag_keyframe+empty_moov', 'pipe:1'
                        ]
                    else:
                        command = ['ffmpeg', '-user_agent', ua, '-http_proxy', SUCCESS_PROXY, '-i', info['url'], '-c', 'copy', '-f', 'mp4', '-movflags', 'frag_keyframe+empty_moov', 'pipe:1']
            
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        while True:
            chunk = process.stdout.read(1024 * 512)
            if not chunk: break
            yield chunk

    unique_id = uuid.uuid4().hex[:4]
    name = f"U2_{unique_id}.mp3" if is_audio else f"U2_{unique_id}.mp4"
    return StreamingResponse(stream_data(), media_type="application/octet-stream", headers={"Content-Disposition": f"attachment; filename={name}"})

if __name__ == "__main__":
    # الحصول على البورت من السيرفر السحابي، ولو ملقاش هيشتغل على 5000 محلياً
    port = int(os.environ.get("PORT", 5000))
    # 0.0.0.0 بتسمح للموقع إنه يتفتح من أي جهاز في العالم
    uvicorn.run("main:app", host="0.0.0.0", port=port)