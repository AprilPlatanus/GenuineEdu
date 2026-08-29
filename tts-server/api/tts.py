"""
Vercel serverless 版本的 Edge TTS 代理（与 server.py 等价的 Flask 实现）
- GET/POST /tts    合成音频（与原 server.py 完全兼容）
- GET  /health     健康检查
- GET  /           健康检查（兼容默认域名）
"""
import asyncio
import io
import os
from flask import Flask, request, Response
import edge_tts

app = Flask(__name__)

# 口音 × 音色 -> Edge 神经语音
VOICE_MAP = {
    'US': {'female': 'en-US-AriaNeural',    'male': 'en-US-AndrewNeural'},
    'GB': {'female': 'en-GB-SoniaNeural',   'male': 'en-GB-RyanNeural'},
    'AU': {'female': 'en-AU-NatashaNeural', 'male': 'en-AU-WilliamNeural'},
}

# 内存缓存（注意：Vercel serverless 函数是无状态的，每次冷启动会重建缓存，因此重复单词可仍会重合成；
# 但实际延迟通常 < 1s，体验可接受）
CACHE = {}
CACHE_MAX = 800

def rate_to_edge(r):
    try:
        r = float(r)
    except Exception:
        r = 1.0
    pct = int(round((r - 1.0) * 100))
    return ('+' if pct >= 0 else '') + str(pct) + '%'

async def synth_async(text, voice, rate):
    kwargs = {}
    if rate is not None:
        kwargs['rate'] = rate
    comm = edge_tts.Communicate(text, voice, **kwargs)
    buf = io.BytesIO()
    async for chunk in comm.stream():
        if chunk['type'] == 'audio':
            buf.write(chunk['data'])
    audio = buf.getvalue()
    if len(audio) < 200:
        raise RuntimeError('audio too short (%d bytes)' % len(audio))
    return audio

def synth(text, voice, rate=None, retries=3):
    last_err = None
    for attempt in range(retries):
        try:
            return asyncio.run(synth_async(text, voice, rate))
        except Exception as e:
            last_err = e
            if attempt < retries - 1:
                import time
                time.sleep(0.3 * (attempt + 1))
    raise last_err

def _resolve_args():
    # 兼容 GET（query string）与 POST（form / json）
    if request.method == 'POST':
        if request.is_json:
            data = request.get_json(silent=True) or {}
            return (
                data.get('text', ''),
                data.get('accent', 'US'),
                data.get('gender', 'female'),
                data.get('rate'),
            )
        return (
            request.form.get('text', ''),
            request.form.get('accent', 'US'),
            request.form.get('gender', 'female'),
            request.form.get('rate'),
        )
    return (
        request.args.get('text', ''),
        request.args.get('accent', 'US'),
        request.args.get('gender', 'female'),
        request.args.get('rate'),
    )

@app.route('/tts', methods=['GET', 'POST'])
def tts():
    text, accent, gender, rate = _resolve_args()
    if not text:
        return Response('missing text', mimetype='text/plain', status=400)
    voice = VOICE_MAP.get(accent, VOICE_MAP['US']).get(gender, 'en-US-AriaNeural')
    edge_rate = rate_to_edge(rate) if rate else None
    key = (text, voice, edge_rate)
    audio = CACHE.get(key)
    if audio is None:
        try:
            audio = synth(text, voice, edge_rate)
        except Exception as e:
            return Response('edge tts error: ' + str(e), mimetype='text/plain', status=500)
        if len(CACHE) >= CACHE_MAX:
            CACHE.clear()
        CACHE[key] = audio
    headers = {
        'Content-Type': 'audio/mpeg',
        'Content-Length': str(len(audio)),
        'Cache-Control': 'public, max-age=86400',
        'Access-Control-Allow-Origin': '*',
    }
    return Response(audio, headers=headers, status=200)

@app.route('/health', methods=['GET'])
def health():
    return Response('ok', mimetype='text/plain', status=200)

@app.route('/', methods=['GET'])
def root():
    return Response('ok', mimetype='text/plain', status=200)
