# Edge TTS 代理（云端部署版）

这是「听英文测试」网页的 **Edge 神经语音服务端代理**。网页通过它把单词转发给微软 Edge TTS（与 Azure 同款录音棚级音色），返回 MP3。

**为什么需要它**：微软已限制外部网站用浏览器直连 Edge 语音接口，所以 Edge 音质必须经过这个服务端代理转发。

## 部署到 Render（免费、永久地址，推荐）

1. 打开 https://render.com 用 GitHub 账号注册（免费，无需信用卡）。
2. 登录后点 **New → Blueprint**（或 **New → Web Service**），选择 GitHub 仓库 `AprilPlatanus/GenuineEdu`。
3. 配置：
   - **Root Directory**：`tts-server`
   - **Runtime**：`Python 3`
   - **Build Command**：`pip install -r requirements.txt`
   - **Start Command**：`python server.py`
   - **Instance Type**：Free（免费）
4. 点 **Create/Deploy**，等待 1~3 分钟部署完成。
5. 部署完成后会得到一个地址，形如 `https://edge-tts-proxy-xxxx.onrender.com`。

## 生成带 Edge 音质的分享链接

把代理地址做 URL 编码后拼进分享链接：

- 原始分享链接：`https://AprilPlatanus.github.io/GenuineEdu/听英文测试/`
- 代理地址示例：`https://edge-tts-proxy-xxxx.onrender.com`
- URL 编码：`https%3A%2F%2Fedge-tts-proxy-xxxx.onrender.com`
- **最终分享链接**：`https://AprilPlatanus.github.io/GenuineEdu/听英文测试/?tts=https%3A%2F%2Fedge-tts-proxy-xxxx.onrender.com`

把最终链接发给学生即可，打开后自动使用 Edge 音质、不需要任何设置。

## 注意事项

- **免费版闲置约 15 分钟会休眠**，学生首次打开可能等 30~60 秒冷启动（之后就快了）。可以在 https://uptimerobot.com 添加一个免费监控（每 5 分钟访问一次），保持服务常醒。
- 本代理只做语音合成转发，不存储任何数据；合成结果带内存缓存，重复单词秒回。
- 若需永久不休眠，可升级 Render 付费实例（约 7 美元/月）。
