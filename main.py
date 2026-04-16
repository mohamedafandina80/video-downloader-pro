import os
import uuid
import uvicorn
import yt_dlp
import subprocess
import requests 
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# 👑 تم إزالة السطر المسبب للمشكلة في الويندوز واستخدام بديل آمن 100%
YDL_OPTS = {
    'quiet': True,
    'no_warnings': True,
    'no_check_certificate': True,
    'extract_flat': False,
    'force_ipv4': True, # هذا الخيار آمن على جهازك وعلى سيرفر Railway
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
            
            formats = info.get('formats', [])
            extractor = info.get('extractor', '').lower()
            
            if not formats:
                video_formats.append({"id": "best", "res_val": 1080, "label": "أفضل جودة متاحة", "type": "video", "size": "MAX"})
            else:
                if 'tiktok' in extractor:
                    tiktok_added = set()
                    for f in formats:
                        vcodec = f.get('vcodec')
                        if vcodec == 'none' or 'images' in f.get('format_id', ''): 
                            continue
                            
                        is_watermark = 'watermark' in f.get('format_id', '').lower() or 'watermark' in f.get('format_note', '').lower()
                        label = "بعلامة مائية (Watermarked)" if is_watermark else "بدون علامة مائية (No Watermark)"
                        
                        if label not in tiktok_added:
                            tiktok_added.add(label)
                            
                            # تأمين حساب الحجم حتى لو كان مخفياً
                            size = f.get('filesize') or f.get('filesize_approx')
                            size_str = f"{round(size/1024/1024, 1)} MB" if size else "MAX"
                            
                            video_formats.append({
                                "id": f.get('format_id'),
                                "res_val": 720 if is_watermark else 1080,
                                "label": label,
                                "type": "video",
                                "size": size_str
                            })
                else:
                    added_res = set()
                    for f in reversed(formats):
                        vcodec = f.get('vcodec')
                        height = f.get('height')
                        
                        if vcodec != 'none' and height and height >= 144:
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
                                    "size": size_str
                                })
            
            video_formats.sort(key=lambda x: x['res_val'], reverse=True)
            final_list = [{"id": "bestaudio", "label": "MP3 AUDIO - جودة خرافية", "type": "audio", "size": "HQ"}] + video_formats
            
            title = info.get('title') or "U2_DOWNLOADER_MEDIA"
            thumbnail = info.get('thumbnail') or "https://via.placeholder.com/600x400/000000/ffd700?text=U2+DOWNLOADER"
            
            return {"success": True, "title": title, "thumbnail": thumbnail, "formats": final_list}
    except Exception as e:
        # طباعة الخطأ في السيرفر لتسهيل اكتشافه لو حصل مرة تانية
        print(f"Error extracting info: {str(e)}")
        return {"success": False, "error": str(e)}

@app.get("/download")
async def download(url: str, format_id: str, is_audio: bool = False, res: int = 0):
    def stream_data():
        with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True, 'force_ipv4': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            extractor = info.get('extractor', '').lower()
            
            if 'youtube' in extractor and not is_audio:
                target_format = 'bestvideo+bestaudio[ext=m4a]/bestvideo+bestaudio/best' if format_id == 'best' else f'{format_id}+bestaudio[ext=m4a]/bestaudio/best'
                info = ydl.extract_info(url, download=False)
                ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                
                if 'requested_formats' in info:
                    v_url = info['requested_formats'][0]['url']
                    a_url = info['requested_formats'][1]['url']
                    a_codec = 'copy' if info['requested_formats'][1]['ext'] == 'm4a' else 'aac'
                    
                    command = [
                        'ffmpeg', '-user_agent', ua, '-reconnect', '1', '-reconnect_streamed', '1', '-reconnect_delay_max', '5', '-thread_queue_size', '10000', '-i', v_url,
                        '-user_agent', ua, '-reconnect', '1', '-reconnect_streamed', '1', '-reconnect_delay_max', '5', '-thread_queue_size', '10000', '-i', a_url,
                        '-c:v', 'copy', '-c:a', a_codec, '-f', 'mp4', '-movflags', 'frag_keyframe+empty_moov', '-threads', '0', 'pipe:1'
                    ]
                else:
                    command = ['ffmpeg', '-user_agent', ua, '-reconnect', '1', '-reconnect_streamed', '1', '-reconnect_delay_max', '5', '-i', info['url'], '-c', 'copy', '-f', 'mp4', '-movflags', 'frag_keyframe+empty_moov', '-threads', '0', 'pipe:1']
                
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                while True:
                    chunk = process.stdout.read(1024 * 256)
                    if not chunk: break
                    yield chunk

            else:
                # محرك التيك توك الخالي من الـ 0 بايت
                headers = info.get('http_headers', {})
                media_url = info['url']
                
                if format_id != 'best' and not is_audio:
                    for f in info.get('formats', []):
                        if f.get('format_id') == format_id:
                            media_url = f.get('url')
                            break

                r = requests.get(media_url, headers=headers, stream=True)
                for chunk in r.iter_content(chunk_size=1024 * 256):
                    if chunk: 
                        yield chunk

    name = f"U2_DOWNLOADER_{uuid.uuid4().hex[:4]}"
    name += ".mp3" if is_audio else ".mp4"
    
    return StreamingResponse(stream_data(), media_type="application/octet-stream", headers={
        "Content-Disposition": f"attachment; filename={name}"
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
