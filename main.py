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

# 👑 التعديل الأول: حقن الكوكيز في إعدادات الفحص الأساسية
YDL_OPTS = {
    'quiet': True,
    'no_warnings': True,
    'no_check_certificate': True,
    'extract_flat': False,
    'cookiefile': 'cookies.txt', # 👑 السطر السحري اللي هيضحك على يوتيوب
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
            added_res = set()
            
            formats = info.get('formats', [])
            
            if not formats:
                video_formats.append({
                    "id": "best",
                    "res_val": 1080,
                    "label": "أفضل جودة متاحة (Live)",
                    "type": "video",
                    "size": "MAX"
                })
            else:
                for f in reversed(formats):
                    ext = f.get('ext', '')
                    protocol = f.get('protocol', '')
                    vcodec = f.get('vcodec', '')
                    
                    if vcodec != 'none' or 'm3u8' in protocol or ext in ['mp4', 'mkv', 'flv']:
                        res = f.get('height') or 0
                        
                        if res not in added_res or res == 0:
                            if res >= 2160: tag = "4K ULTRA HD"
                            elif res >= 1440: tag = "2K QHD"
                            elif res >= 1080: tag = "FULL HD"
                            elif res >= 720: tag = "HD"
                            elif res > 0: tag = "SD"
                            else: tag = "جودة سينمائية مخصصة"
                            
                            label = f"{res}P {tag}" if res > 0 else f"{tag} ({ext.upper()})"
                            
                            video_formats.append({
                                "id": f.get('format_id', 'best'),
                                "res_val": res,
                                "label": label,
                                "type": "video",
                                "size": f"{round(f['filesize']/1024/1024, 1)} MB" if f.get('filesize') else "MAX"
                            })
                            if res > 0:
                                added_res.add(res)
            
            video_formats.sort(key=lambda x: x['res_val'], reverse=True)
            final_list = [{"id": "bestaudio", "label": "MP3 AUDIO - جودة خرافية", "type": "audio", "size": "HQ"}] + video_formats
            
            title = info.get('title') or "U2_DOWNLOADER_MEDIA"
            thumbnail = info.get('thumbnail') or "https://via.placeholder.com/600x400/000000/ffd700?text=U2+DOWNLOADER"
            
            return {"success": True, "title": title, "thumbnail": thumbnail, "formats": final_list}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/download")
async def download(url: str, format_id: str, is_audio: bool = False, res: int = 0):
    def stream_data():
        if is_audio:
            target_format = 'bestaudio/best'
        elif format_id == 'best':
            target_format = 'bestvideo+bestaudio[ext=m4a]/bestvideo+bestaudio/best'
        else:
            target_format = f'{format_id}+bestaudio[ext=m4a]/bestaudio/best'

        # 👑 التعديل الثاني: حقن الكوكيز في إعدادات التحميل والدمج
        ydl_opts = {
            'quiet': True, 
            'no_warnings': True, 
            'no_check_certificate': True, 
            'format': target_format,
            'cookiefile': 'cookies.txt' # 👑 لازم يكون هنا كمان عشان التحميل ميقطعش
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            if 'http_headers' in info:
                ua = info['http_headers'].get('User-Agent', ua)
            
            if is_audio:
                media_url = info['url']
                command = [
                    'ffmpeg', 
                    '-user_agent', ua,
                    '-reconnect', '1', '-reconnect_streamed', '1', '-reconnect_delay_max', '5',
                    '-i', media_url, '-c:a', 'libmp3lame', '-f', 'mp3', 'pipe:1'
                ]
                
            elif 'requested_formats' in info:
                video_url = info['requested_formats'][0]['url']
                audio_url = info['requested_formats'][1]['url']
                audio_ext = info['requested_formats'][1]['ext']
                
                a_codec = 'copy' if audio_ext == 'm4a' else 'aac'
                
                command = [
                    'ffmpeg',
                    '-user_agent', ua, 
                    '-reconnect', '1', '-reconnect_streamed', '1', '-reconnect_delay_max', '5',
                    '-thread_queue_size', '10000',
                    '-i', video_url,
                    '-user_agent', ua, 
                    '-reconnect', '1', '-reconnect_streamed', '1', '-reconnect_delay_max', '5',
                    '-thread_queue_size', '10000',
                    '-i', audio_url,
                    '-c:v', 'copy',
                    '-c:a', a_codec,
                    '-f', 'mp4',
                    '-movflags', 'frag_keyframe+empty_moov',
                    '-threads', '0',
                    'pipe:1'
                ]
            else:
                media_url = info['url']
                command = [
                    'ffmpeg',
                    '-user_agent', ua,
                    '-reconnect', '1', '-reconnect_streamed', '1', '-reconnect_delay_max', '5',
                    '-i', media_url,
                    '-c', 'copy',
                    '-f', 'mp4',
                    '-movflags', 'frag_keyframe+empty_moov',
                    '-threads', '0',
                    'pipe:1'
                ]

        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        
        while True:
            chunk = process.stdout.read(1024 * 256)
            if not chunk:
                break
            yield chunk

    name = f"U2_DOWNLOADER_{uuid.uuid4().hex[:4]}"
    name += ".mp3" if is_audio else ".mp4"
    
    return StreamingResponse(stream_data(), media_type="application/octet-stream", headers={
        "Content-Disposition": f"attachment; filename={name}"
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)