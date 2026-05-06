import os, requests

key = os.environ.get("DEEPSEEK_API_KEY", "")
print("API Key:", key[:8] + "..." + key[-4:] if len(key) > 12 else "Key too short")

url = "https://api.deepseek.com/chat/completions"
headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
payload = {
    "model": "deepseek-chat",
    "messages": [{"role": "user", "content": "Say hello in JSON format"}],
    "max_tokens": 50,
    "temperature": 0.1,
}

try:
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    print("Status:", resp.status_code)
    if resp.status_code == 200:
        print("Response:", resp.json()["choices"][0]["message"]["content"])
    else:
        print("Error:", resp.text[:200])
except Exception as e:
    print("Connection failed:", e)
