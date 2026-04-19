import os
import uuid
import uvicorn
import yt_dlp
import subprocess
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# إعدادات yt-dlp الأساسية
YDL_OPTS = {
    'quiet': True,
    'no_warnings': True,
    'no_check_certificate': True,
    'extract_flat': False,
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
}

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.post("/analyze")
async def analyze_video(data: dict):
    url = data.get("url")
    try:
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            info = ydl.extract_info(url, download=False)
            video_formats = []
            
            # جلب التنسيقات المتاحة
            formats = info.get('formats', [])
            for f in formats:
                # تصفية الصيغ اللي فيها فيديو وصوت مدمجين أو فيديو عالي الجودة
                if f.get('vcodec') != 'none':
                    res = f.get('height')
                    if res and res not in [res.get('res_val') for res in video_formats]:
                        video_formats.append({
                            "id": f.get('format_id'),
                            "res_val": res,
                            "label": f"{res}p - عالي الجودة",
                            "type": "video",
                            "size": "Variable"
                        })
            
            # إضافة خيار صوت فقط
            video_formats.append({
                "id": "bestaudio",
                "label": "صوت فقط (MP3)",
                "type": "audio",
                "size": "Small"
            })

            return {
                "title": info.get('title', 'Video'),
                "formats": sorted(video_formats, key=lambda x: x.get('res_val', 0), reverse=True)
            }
    except Exception as e:
        return {"error": str(e)}

@app.get("/download")
async def download(url: str, format_id: str, is_audio: str):
    is_audio_bool = is_audio.lower() == 'true'
    
    def stream_data():
        # استخدام yt-dlp لجلب روابط البث المباشرة
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if is_audio_bool:
                # أمر FFmpeg لتحويل الصوت لـ MP3 مباشرة
                audio_url = info['url'] if 'url' in info else ydl.extract_info(url, download=False)['formats'][0]['url']
                command = [
                    'ffmpeg', '-i', audio_url,
                    '-vn', '-ar', '44100', '-ac', '2', '-b:a', '192k',
                    '-f', 'mp3', 'pipe:1'
                ]
            else:
                # دمج أفضل فيديو مع أفضل صوت متاح
                # ملاحظة: yt-dlp بيعطينا روابط منفصلة للفيديو والصوت في الجودات العالية
                command = [
                    'ffmpeg',
                    '-i', 'artifacts_url_video', # yt-dlp هيعوض هنا تلقائياً لو استخدمنا الخيار المدمج
                    '-i', 'artifacts_url_audio',
                    '-c:v', 'copy', '-c:a', 'aac', '-strict', 'experimental',
                    '-f', 'mp4', '-movflags', 'frag_keyframe+empty_moov',
                    'pipe:1'
                ]
                
                # لتسهيل الأمر في السيرفر، سنستخدم yt-dlp كـ "ممر" للبيانات لـ FFmpeg
                ydl_command = [
                    'yt-dlp',
                    '-f', f'{format_id}+bestaudio/best',
                    '--ffmpeg-location', '/usr/bin/ffmpeg',
                    '-o', '-', # إخراج لـ stdout
                    url
                ]
                process = subprocess.Popen(ydl_command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                while True:
                    chunk = process.stdout.read(1024 * 256)
                    if not chunk: break
                    yield chunk
                return

        # تنفيذ أمر FFmpeg المباشر للصوت أو الحالات البسيطة
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        while True:
            chunk = process.stdout.read(1024 * 256)
            if not chunk: break
            yield chunk

    filename = f"U2_{uuid.uuid4().hex[:4]}.{'mp3' if is_audio_bool else 'mp4'}"
    return StreamingResponse(stream_data(), media_type="application/octet-stream", headers={
        "Content-Disposition": f"attachment; filename={filename}"
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
