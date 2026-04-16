import os
import uuid
import glob
import uvicorn
import yt_dlp
import requests
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# إعدادات متقدمة للـ yt-dlp لضمان أقصى سرعة
YDL_COMMON_OPTS = {
    'quiet': True,
    'no_warnings': True,
    'no_check_certificate': True,
    'concurrent_fragment_downloads': 10,
    'buffer_size': '256K'
}

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    # استخدام الصيغة الصحيحة لتجنب أخطاء الإصدارات الجديدة
    return templates.TemplateResponse(request=request, name="index.html")

@app.post("/analyze")
async def analyze_video(data: dict):
    url = data.get("url")
    try:
        with yt_dlp.YoutubeDL(YDL_COMMON_OPTS) as ydl:
            info = ydl.extract_info(url, download=False)
            video_formats = []
            added_res = set()
            
            for f in info.get('formats', []):
                res = f.get('height')
                # اختيار الجودات التي تدعم الصوت والفيديو معاً للتحميل المباشر
                if res and res not in added_res and res >= 360 and f.get('acodec') != 'none':
                    tag = "FULL HD" if res >= 1080 else ("HD" if res >= 720 else "SD")
                    size = f"{round(f['filesize']/1024/1024, 1)} MB" if f.get('filesize') else "Live"
                    video_formats.append({
                        "id": f['format_id'], 
                        "label": f"{res}P {tag}", 
                        "type": "video", 
                        "height": res,
                        "size": size
                    })
                    added_res.add(res)
            
            video_formats.sort(key=lambda x: x['height'], reverse=True)
            final_list = [{"id": "bestaudio", "label": "MP3 AUDIO - High Quality", "type": "audio", "size": "HQ"}] + video_formats
            
            return {"success": True, "title": info.get('title'), "thumbnail": info.get('thumbnail'), "formats": final_list}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/download")
async def download(url: str, format_id: str, is_audio: bool = False):
    def get_stream():
        ydl_opts = {
            'format': 'bestaudio/best' if is_audio else f'{format_id}',
            'quiet': True,
            'no_check_certificate': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            stream_url = info['url']
            # جلب البيانات وبثها فوراً للمستخدم (Streaming)
            r = requests.get(stream_url, stream=True, timeout=30)
            for chunk in r.iter_content(chunk_size=1024*1024): # 1MB chunks للسرعة
                if chunk:
                    yield chunk

    filename = f"U2_Download_{uuid.uuid4().hex[:4]}.mp4"
    if is_audio: filename = filename.replace(".mp4", ".mp3")
    
    return StreamingResponse(get_stream(), media_type="application/octet-stream", headers={
        "Content-Disposition": f"attachment; filename={filename}"
    })

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=5000)