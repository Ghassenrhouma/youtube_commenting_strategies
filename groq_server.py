"""
Minimal Groq proxy server — runs on the Windows host.
Containers call http://host.docker.internal:7860/generate
and this server forwards the request to Groq using the real host IP.
"""
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
_MODEL = "qwen/qwen3-32b"

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # suppress per-request logs

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        try:
            response = _client.chat.completions.create(
                model=_MODEL,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant. Reply directly without any thinking, reasoning, or preamble. Output only the final answer."},
                    {"role": "user", "content": body["prompt"]},
                ],
                temperature=0.9,
                max_tokens=800,
            )
            text = response.choices[0].message.content or ""
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"text": text}).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

if __name__ == "__main__":
    port = int(os.getenv("GROQ_SERVER_PORT", "7860"))
    print(f"[GROQ-SERVER] Listening on 0.0.0.0:{port}")
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()
