from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import yt_dlp
import os
import uuid
import requests

app = FastAPI(title="Video Saver Pro API")

# Allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

class URLRequest(BaseModel):
    url: str

class DownloadRequest(BaseModel):
    url: str
    format_id: str

def resolve_url(url: str) -> str:
    if "/share/" in url or "/reel/" in url:
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Linux; Android 10)'}
            response = requests.head(url, allow_redirects=True, timeout=15, headers=headers)
            return response.url
        except:
            pass
    return url

@app.post("/api/extract")
async def extract_video(request: URLRequest):
    real_url = resolve_url(request.url)
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'user_agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36',
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(real_url, download=False)
            formats = []
            formats.append({
                "format_id": "best",
                "quality": "Best (Auto)",
                "size_mb": "Auto",
                "has_audio": True,
                "note": "Best available quality"
            })
            formats.append({
                "format_id": "best[height<=720]",
                "quality": "720p",
                "size_mb": "Auto",
                "has_audio": True,
                "note": "HD quality"
            })
            formats.append({
                "format_id": "best[height<=480]",
                "quality": "480p",
                "size_mb": "Auto",
                "has_audio": True,
                "note": "Good quality"
            })
            formats.append({
                "format_id": "worst",
                "quality": "360p",
                "size_mb": "Auto",
                "has_audio": True,
                "note": "Small file"
            })
            return {
                "success": True,
                "title": info.get('title', 'Unknown'),
                "duration": info.get('duration', 0),
                "thumbnail": info.get('thumbnail', ''),
                "uploader": info.get('uploader', 'Unknown'),
                "formats": formats
            }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/download")
async def download_video(request: DownloadRequest):
    """Download video and save to file"""
    real_url = resolve_url(request.url)
    video_id = str(uuid.uuid4())[:8]
    outtmpl = f"{DOWNLOAD_DIR}/{video_id}.%(ext)s"
    
    ydl_opts = {
        'format': request.format_id,
        'outtmpl': outtmpl,
        'merge_output_format': 'mp4',
        'user_agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36',
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(real_url, download=True)
            filename = ydl.prepare_filename(info)
            
            # Fix extension
            if not filename.endswith('.mp4'):
                filename = filename.rsplit('.', 1)[0] + '.mp4'
            
            # Check if file exists
            if not os.path.exists(filename):
                # Find actual file in downloads folder
                files = os.listdir(DOWNLOAD_DIR)
                for f in files:
                    if video_id in f:
                        filename = os.path.join(DOWNLOAD_DIR, f)
                        break
            
            if not os.path.exists(filename):
                return {"success": False, "error": "File not found after download"}
            
            file_size = os.path.getsize(filename)
            size_mb = round(file_size / (1024*1024), 1)
            
            return {
                "success": True,
                "video_id": video_id,
                "file_path": filename,
                "size_mb": size_mb,
                "download_url": f"/downloads/{os.path.basename(filename)}"
            }
            
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": "1.0.0"}

# Serve downloaded files
app.mount("/downloads", StaticFiles(directory="downloads"), name="downloads")

# Serve frontend HTML
@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    html_content = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Video Saver Pro</title>
<style>
body{font-family:sans-serif;background:#1a1a2e;color:#fff;padding:20px;max-width:500px;margin:0 auto}
.header{background:#e94560;padding:20px;text-align:center;border-radius:12px;margin-bottom:20px}
.input{width:100%;padding:15px;border-radius:10px;border:2px solid #e94560;background:#0f3460;color:#fff;margin:10px 0;font-size:14px}
.btn{width:100%;padding:15px;background:#e94560;border:none;border-radius:10px;color:#fff;font-size:16px;margin:10px 0;cursor:pointer}
.result{background:rgba(255,255,255,0.05);padding:15px;border-radius:12px;margin-top:20px;display:none}
.thumb{width:100%;border-radius:8px;margin-bottom:10px}
.quality{padding:10px;margin:5px 0;background:#0f3460;border-radius:8px;cursor:pointer;border:2px solid transparent}
.quality.selected{border-color:#e94560;background:rgba(233,69,96,0.2)}
.ad{height:50px;background:#0f3460;display:flex;align-items:center;justify-content:center;color:#888;font-size:11px;margin:10px 0;border-radius:8px}
.loading{text-align:center;padding:20px;display:none}
.spinner{width:30px;height:30px;border:3px solid #e94560;border-top-color:transparent;border-radius:50%;animation:spin 1s linear infinite;margin:0 auto 10px}
@keyframes spin{to{transform:rotate(360deg)}}
</style>
</head>
<body>
<div class="header">
<h1>Video Saver Pro</h1>
<p>Download Facebook Videos</p>
</div>
<div class="ad">AdMob Banner Ad (Top)</div>
<input type="text" class="input" id="url" placeholder="Paste Facebook URL here...">
<button class="btn" onclick="extract()">▶️ EXTRACT VIDEO</button>
<div class="loading" id="loading"><div class="spinner"></div><p>Extracting video...</p></div>
<div class="result" id="result">
<img class="thumb" id="thumb" src="">
<div id="title" style="font-weight:bold;margin-bottom:10px;"></div>
<div id="qualities"></div>
<button class="btn" onclick="download()" style="background:#00d26a">⬇️ DOWNLOAD</button>
</div>
<div class="ad">AdMob Banner Ad (Bottom)</div>
<script>
const API = '';
let videoData = null;
let selectedFormat = 'best';

async function extract(){
  const url = document.getElementById('url').value.trim();
  if(!url){alert('Paste URL first');return;}
  document.getElementById('loading').style.display='block';
  document.getElementById('result').style.display='none';
  try{
    const res = await fetch('/api/extract',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:url})});
    const data = await res.json();
    if(data.success){
      videoData = {...data, originalUrl:url};
      document.getElementById('thumb').src = data.thumbnail;
      document.getElementById('title').textContent = data.title;
      let html = '<p style="color:#e94560;font-weight:bold;">Select Quality:</p>';
      data.formats.forEach((f,i)=>{html += '<div class="quality '+(i==0?'selected':'')+'" onclick="select(this,\\''+f.format_id+'\\')"><b>'+f.quality+'</b> - '+f.note+'</div>';});
      document.getElementById('qualities').innerHTML = html;
      document.getElementById('result').style.display='block';
    } else {alert('Error: '+(data.error||'Unknown error'));}
  } catch(e){alert('Failed to connect. Is server running?');}
  finally{document.getElementById('loading').style.display='none';}
}
function select(el, fmt){document.querySelectorAll('.quality').forEach(q=>q.classList.remove('selected'));el.classList.add('selected');selectedFormat = fmt;}
async function download(){
  if(!videoData)return;
  try{
    const res = await fetch('/api/download',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:videoData.originalUrl,format_id:selectedFormat})});
    const data = await res.json();
    if(data.success){
      window.open('/downloads/'+data.video_id+'.mp4', '_blank');
      alert('Download started! Check your downloads folder.');
    } else {alert('Download failed: '+(data.error||'Unknown'));}
  } catch(e){alert('Download error');console.error(e);}
}
</script>
</body>
</html>"""
    return html_content
