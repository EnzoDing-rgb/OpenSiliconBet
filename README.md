# OpenSiliconBet

需要已安装 Git、Python 3、Node.js。

```bash
git clone https://github.com/EnzoDing-rgb/OpenSiliconBet.git
cd OpenSiliconBet
cp .env.example .env
```

打开 `.env`，把 `API_KEY=` 换成你的 DeepSeek 密钥。对话走 DeepSeek，语音仍用文件里另一把阿里云密钥。

```bash
chmod +x dev.sh
./dev.sh
```

`./dev.sh` 在 macOS、Linux，以及 Windows 的 Git Bash 里都能用。缺的 Python 依赖和前端依赖会自己安装。

浏览器打开 http://127.0.0.1:5173

停掉：回到这个终端，按 `Ctrl+C`。
