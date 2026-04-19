import os
import uvicorn
import requests
import yt_dlp
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

app = FastAPI()
base_dir = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(base_dir, "templates"))

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.post("/analyze")
async def analyze_video(data: dict):
    url = data.get("url")
    if not url: 
        return {"success": False, "error": "الرابط فارغ"}
    
    # استخدام yt-dlp لفحص الجودات الحقيقية المتاحة (المدمجة فقط لتجنب ffmpeg)
    ydl_opts = {'quiet': True, 'extract_flat': False}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = []
            added_res = set()

            for f in info.get('formats', []):
                height = f.get('height')
                vcodec = f.get('vcodec')
                acodec = f.get('acodec')
                
                # نفلتر الجودات اللي فيها صوت وصورة مع بعض
                if height and vcodec != 'none' and acodec != 'none':
                    if height not in added_res:
                        added_res.add(height)
                        size = f.get('filesize') or f.get('filesize_approx', 0)
                        size_mb = f"{round(size/1024/1024, 1)} MB" if size else "جودة أصلية"
                        formats.append({
                            "id": f.get('format_id'),
                            "res_val": height,
                            "label": f"فيديو {height}p",
                            "size": size_mb,
                            "type": "video"
                        })
            
            formats.sort(key=lambda x: x['res_val'], reverse=True)
            
            formats.append({
                "id": "audio",
                "label": "ملف صوتي M4A",
                "size": "صوت نقي",
                "type": "audio"
            })

            return {"success": True, "title": info.get('title'), "thumbnail": info.get('thumbnail'), "formats": formats}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/get_link")
async def get_link(url: str, format_id: str):
    # 👑 استخراج الرابط المباشر من سيرفرات جوجل (بدون الاعتماد على أي موقع خارجي)
    ydl_opts = {'quiet': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if format_id == "audio":
                for f in info['formats'][::-1]:
                    if f.get('vcodec') == 'none' and f.get('acodec') != 'none':
                        return {"success": True, "download_url": f['url']}
            else:
                for f in info['formats']:
                    if str(f.get('format_id')) == format_id:
                        return {"success": True, "download_url": f['url']}
                        
            return {"success": True, "download_url": info['url']}
    except Exception as e:
        return {"success": False, "error": f"فشل استخراج الرابط: {str(e)}"}

@app.get("/stream")
async def stream_video(url: str):
    headers_dict = {}
    
    # تخفي كامل للسيرفر عشان جوجل ميعملوش بلوك
    req_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        head_res = requests.head(url, headers=req_headers, timeout=5)
        if 'Content-Length' in head_res.headers:
            headers_dict['Content-Length'] = head_res.headers['Content-Length']
    except: pass
    
    headers_dict["Content-Disposition"] = "attachment; filename=U2_Empire_Media.mp4"
    
    def iter_file():
        # شلال البيانات: نقل الفيديو من جوجل للمستخدم مباشرة عبر السيرفر بتاعك
        with requests.get(url, headers=req_headers, stream=True) as r:
            for chunk in r.iter_content(chunk_size=1024*512):
                if chunk: yield chunk
                
    return StreamingResponse(iter_file(), media_type="application/octet-stream", headers=headers_dict)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    uvicorn.run(app, host="0.0.0.0", port=port)