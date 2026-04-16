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

# إعدادات مستقرة تناسب Railway وجهازك بدون حظر
YDL_OPTS = {
    'quiet': True,
    'no_warnings': True,
    'no_check_certificate': True,
    'extract_flat': False,
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
                video_formats.append({"id": "best", "res_val": 1080, "label": "أفضل جودة متاحة", "type": "video", "size": "MAX", "needs_merge": False})
            else:
                # 👑 المعالجة الخاصة للتيك توك (بدون دمج)
                if 'tiktok' in extractor:
                    tiktok_added = set()
                    for f in formats:
                        if f.get('vcodec') == 'none' or 'images' in f.get('format_id', ''): 
                            continue
                            
                        is_watermark = 'watermark' in f.get('format_id', '').lower() or 'watermark' in f.get('format_note', '').lower()
                        label = "بعلامة مائية (Watermarked)" if is_watermark else "بدون علامة مائية (No Watermark)"
                        
                        if label not in tiktok_added:
                            tiktok_added.add(label)
                            size = f.get('filesize') or f.get('filesize_approx')
                            size_str = f"{round(size/1024/1024, 1)} MB" if size else "MAX"
                            
                            video_formats.append({
                                "id": f.get('format_id'),
                                "res_val": 720 if is_watermark else 1080,
                                "label": label,
                                "type": "video",
                                "size": size_str,
                                "needs_merge": False # 👑 التيك توك لا يحتاج FFmpeg أبداً
                            })
                else:
                    # 👑 المعالجة الخاصة لليوتيوب (تحديد ما يحتاج دمج)
                    added_res = set()
                    for f in reversed(formats):
                        vcodec = f.get('vcodec')
                        acodec = f.get('acodec')
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
                                
                                # 👑 لو مفيش صوت، يبقى الجودة دي محتاجة دمج في التحميل
                                needs_merge = True if acodec == 'none' else False
                                
                                video_formats.append({
                                    "id": f.get('format_id'),
                                    "res_val": height,
                                    "label": f"{height}P {tag}",
                                    "type": "video",
                                    "size": size_str,
                                    "needs_merge": needs_merge
                                })
            
            video_formats.sort(key=lambda x: x['res_val'], reverse=True)
            final_list = [{"id": "bestaudio", "label": "MP3 AUDIO - جودة خرافية", "type": "audio", "size": "HQ", "needs_merge": True}] + video_formats
            
            title = info.get('title') or "U2_DOWNLOADER_MEDIA"
            thumbnail = info.get('thumbnail') or "https://via.placeholder.com/600x400/000000/ffd700?text=U2+DOWNLOADER"
            
            return {"success": True, "title": title, "thumbnail": thumbnail, "formats": final_list}
    except Exception as e:
        print(f"Error Extracting: {str(e)}")
        return {"success": False, "error": str(e)}

@app.get("/download")
async def download(url: str, format_id: str, is_audio: bool = False, needs_merge: str = "false"):
    needs_merge_bool = needs_merge.lower() == "true"
    
    def stream_data():
        # 👑 مسار التحميل المباشر للتيك توك (يمنع مشكلة الـ 0 بايت)
        if not needs_merge_bool and not is_audio:
            target_format = format_id if format_id != 'best' else 'best'
            command = [
                'yt-dlp',
                '-f', target_format,
                '--quiet', '--no-warnings',
                '-o', '-', # ضخ مباشر بدون FFmpeg
                url
            ]
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            while True:
                chunk = process.stdout.read(1024 * 512)
                if not chunk: break
                yield chunk

        # 👑 مسار التحميل المدمج لليوتيوب (يمنع مشكلة الفيديوهات الصامتة)
        else:
            target_format = 'bestaudio/best' if is_audio else f'{format_id}+bestaudio[ext=m4a]/bestaudio/best'
            if format_id == 'best' and not is_audio: target_format = 'bestvideo+bestaudio/best'
            
            with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                if 'http_headers' in info: ua = info['http_headers'].get('User-Agent', ua)
                
                if is_audio:
                    media_url = info['url']
                    command = [
                        'ffmpeg', '-user_agent', ua, '-reconnect', '1', '-reconnect_streamed', '1', '-reconnect_delay_max', '5',
                        '-i', media_url, '-c:a', 'libmp3lame', '-f', 'mp3', 'pipe:1'
                    ]
                else:
                    if 'requested_formats' in info:
                        v_url = info['requested_formats'][0]['url']
                        a_url = info['requested_formats'][1]['url']
                        a_codec = 'copy' if info['requested_formats'][1]['ext'] == 'm4a' else 'aac'
                        
                        command = [
                            'ffmpeg', '-user_agent', ua, '-reconnect', '1', '-reconnect_streamed', '1', '-reconnect_delay_max', '5', '-i', v_url,
                            '-user_agent', ua, '-reconnect', '1', '-reconnect_streamed', '1', '-reconnect_delay_max', '5', '-i', a_url,
                            '-c:v', 'copy', '-c:a', a_codec, '-f', 'mp4', '-movflags', 'frag_keyframe+empty_moov', 'pipe:1'
                        ]
                    else:
                        command = [
                            'ffmpeg', '-user_agent', ua, '-reconnect', '1', '-reconnect_streamed', '1', '-reconnect_delay_max', '5',
                            '-i', info['url'], '-c', 'copy', '-f', 'mp4', '-movflags', 'frag_keyframe+empty_moov', 'pipe:1'
                        ]
            
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            while True:
                chunk = process.stdout.read(1024 * 512)
                if not chunk: break
                yield chunk

    name = f"U2_DOWNLOADER_{uuid.uuid4().hex[:4]}"
    name += ".mp3" if is_audio else ".mp4"
    
    return StreamingResponse(stream_data(), media_type="application/octet-stream", headers={
        "Content-Disposition": f"attachment; filename={name}"
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
