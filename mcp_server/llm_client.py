import os
import re
import json
import requests


LLM_API_KEY = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("LLM_API_KEY", "")
LLM_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
LLM_MODEL = os.environ.get("BI_MODEL", "deepseek-chat")


def is_available() -> bool:
    return bool(LLM_API_KEY)


def call_llm(
    prompt: str,
    system_msg: str = "You are a data analyst expert. Respond with valid JSON only.",
    max_tokens: int = 4096,
    temperature: float = 0.3,
    timeout: int = 60,
    strip_markdown: bool = True,
) -> str:
    if not LLM_API_KEY:
        raise ValueError(
            "LLM API key not configured. "
            "Set DEEPSEEK_API_KEY or LLM_API_KEY environment variable."
        )

    url = f"{LLM_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    response = requests.post(url, headers=headers, json=payload, timeout=timeout)
    if response.status_code != 200:
        raise Exception(f"LLM API error: {response.status_code} - {response.text[:500]}")

    result = response.json()
    content = result["choices"][0]["message"]["content"]
    finish_reason = result["choices"][0].get("finish_reason", "")

    if finish_reason == "length":
        print(f"[LLM] WARNING: output truncated (finish_reason=length)")

    if strip_markdown and content.startswith("```"):
        content = re.sub(r"^```(?:\w+)?\s*\n?", "", content)
        content = re.sub(r"\n?```\s*$", "", content)

    return content.strip()


def call_llm_json(
    prompt: str,
    system_msg: str = "You are a data analyst expert. Respond with valid JSON only, no markdown fences.",
    max_tokens: int = 4096,
    temperature: float = 0.3,
    timeout: int = 60,
) -> dict | list | None:
    raw = call_llm(
        prompt=prompt,
        system_msg=system_msg,
        max_tokens=max_tokens,
        temperature=temperature,
        timeout=timeout,
        strip_markdown=True,
    )
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    m = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    return None
