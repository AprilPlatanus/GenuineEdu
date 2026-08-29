# -*- coding: utf-8 -*-
"""
单词速答网页的本地服务器 + Edge 免费神经语音代理
- 静态托管当前目录的 index.html
- /tts 端点：把文本转发到微软 Edge 免费神经语音（与 Azure 同款音色），返回 MP3
  用法：/tts?text=hello&accent=US&gender=female
"""
import http.server
import socketserver
import urllib.parse
import asyncio
import io
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
# 云平台（如 Render）会注入 PORT 环境变量；本地默认 8899
PORT = int(os.environ.get('PORT', '8899'))

# 口音 × 音色 -> Edge 神经语音（与 Azure 同款，免费）
VOICE_MAP = {
    'US': {'female': 'en-US-AriaNeural',    'male': 'en-US-AndrewNeural'},
    'GB': {'female': 'en-GB-SoniaNeural',   'male': 'en-GB-RyanNeural'},
    'AU': {'female': 'en-AU-NatashaNeural', 'male': 'en-AU-WilliamNeural'},
}

import edge_tts

# 合成结果缓存：同一单词+发音人+语速只连一次微软，之后秒回
CACHE = {}
CACHE_MAX = 800

async def synth(text, voice, rate=None, retries=4):
    kwargs = {}
    if rate is not None:
        kwargs['rate'] = rate
    last_err = None
    for attempt in range(retries):
        try:
            comm = edge_tts.Communicate(text, voice, **kwargs)
            buf = io.BytesIO()
            async for chunk in comm.stream():
                if chunk['type'] == 'audio':
                    buf.write(chunk['data'])
            audio = buf.getvalue()
            # 校验：过短的音频视为合成失败（微软偶发返回空/半截），强制重试，根治“截断/无音频”
            if len(audio) < 200:
                raise RuntimeError('audio too short (%d bytes)' % len(audio))
            return audio
        except Exception as e:
            last_err = e
            if attempt < retries - 1:
                await asyncio.sleep(0.4 * (attempt + 1))  # 退避重试，扛微软接口抖动
    raise last_err

def rate_to_edge(r):
    # r: 0.5~1.3(倍速) -> 百分比字符串，相对 1.0
    try:
        r = float(r)
    except Exception:
        r = 1.0
    pct = int(round((r - 1.0) * 100))
    return ('+' if pct >= 0 else '') + str(pct) + '%'

class Handler(http.server.SimpleHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'   # 配合 Content-Length，浏览器可准确获知音频总字节，避免半截截断

    def _edge(self, text, accent, gender, rate=None):
        voice = VOICE_MAP.get(accent, VOICE_MAP['US']).get(gender, 'en-US-AriaNeural')
        edge_rate = rate_to_edge(rate) if rate is not None else None
        key = (text, voice, edge_rate)
        audio = CACHE.get(key)
        if audio is None:
            audio = asyncio.run(synth(text, voice, edge_rate))
            if len(audio) > 0:
                if len(CACHE) >= CACHE_MAX:
                    CACHE.clear()
                CACHE[key] = audio
        self.send_response(200)
        self.send_header('Content-Type', 'audio/mpeg')
        self.send_header('Content-Length', str(len(audio)))
        self.send_header('Cache-Control', 'public, max-age=86400')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Connection', 'close')  # 明确关闭连接，确保整段音频写完再断开
        self.end_headers()
        try:
            self.wfile.write(audio)
            self.wfile.flush()                     # 强制刷出全部字节，杜绝只写到一半
        except Exception:
            pass

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path == '/tts':
            p = urllib.parse.parse_qs(u.query)
            text = p.get('text', [''])[0]
            accent = p.get('accent', ['US'])[0]
            gender = p.get('gender', ['female'])[0]
            rate = p.get('rate', [None])[0]
            if not text:
                self.send_response(400)
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write('missing text'.encode('utf-8'))
                return
            try:
                self._edge(text, accent, gender, rate)
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write(('edge tts error: ' + str(e)).encode('utf-8'))
            return
        # 其余走静态文件
        super().do_GET()

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        if u.path == '/tts':
            length = int(self.headers.get('Content-Length', 0))
            body = urllib.parse.parse_qs(self.rfile.read(length).decode('utf-8'))
            text = body.get('text', [''])[0]
            accent = body.get('accent', ['US'])[0]
            gender = body.get('gender', ['female'])[0]
            rate = body.get('rate', [None])[0]
            if not text:
                self.send_response(400); self.end_headers(); return
            try:
                self._edge(text, accent, gender, rate)
            except Exception as e:
                self.send_response(500); self.send_header('Content-Type','text/plain; charset=utf-8'); self.end_headers(); self.wfile.write(('edge tts error: '+str(e)).encode('utf-8'))
            return
        self.send_response(404); self.end_headers()

    def log_message(self, fmt, *args):
        # 静默静态请求日志，只保留 /tts 错误
        if args and '/tts' in str(args[0]):
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True

if __name__ == '__main__':
    os.chdir(ROOT)
    with Server(('0.0.0.0', PORT), Handler) as httpd:
        print(f'本地服务器+Edge TTS 代理已启动: http://localhost:{PORT}')
        httpd.serve_forever()
