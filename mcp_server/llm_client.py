import os
import re
import json
import uuid
import requests

LLM_API_KEY = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("LLM_API_KEY", "")
LLM_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
LLM_MODEL = os.environ.get("BI_MODEL", "deepseek-chat")

_pending_tasks: dict[str, dict] = {}


class LlmDelegationNeeded(Exception):
    def __init__(self, task_id: str, prompt: str, system_msg: str, max_tokens: int = 4096):
        self.task_id = task_id
        self.prompt = prompt
        self.system_msg = system_msg
        self.max_tokens = max_tokens
        super().__init__(f"LLM delegation needed: task_id={task_id}")


def is_available() -> bool:
    return bool(LLM_API_KEY)


def has_api_key() -> bool:
    return bool(LLM_API_KEY)


def mode() -> str:
    if LLM_API_KEY:
        return "direct"
    return "agent"


def delegate_llm(
    prompt: str,
    system_msg: str = "You are a data analyst expert. Respond with valid JSON only.",
    max_tokens: int = 4096,
    temperature: float = 0.3,
    timeout: int = 60,
    strip_markdown: bool = True,
) -> str:
    if LLM_API_KEY:
        return _call_direct(prompt, system_msg, max_tokens, temperature, timeout, strip_markdown)

    task_id = uuid.uuid4().hex[:12]
    _pending_tasks[task_id] = {
        "prompt": prompt,
        "system_msg": system_msg,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "strip_markdown": strip_markdown,
    }
    raise LlmDelegationNeeded(task_id, prompt, system_msg, max_tokens)


def submit_result(task_id: str, result: str) -> bool:
    task = _pending_tasks.pop(task_id, None)
    if not task:
        return False
    task["result"] = result
    task["completed"] = True
    return True


def get_pending_tasks() -> list[dict]:
    return [
        {"task_id": tid, "prompt_preview": t["prompt"][:200], "system_msg": t["system_msg"][:100]}
        for tid, t in _pending_tasks.items()
        if "result" not in t
    ]


def call_llm(
    prompt: str,
    system_msg: str = "You are a data analyst expert. Respond with valid JSON only.",
    max_tokens: int = 4096,
    temperature: float = 0.3,
    timeout: int = 60,
    strip_markdown: bool = True,
) -> str:
    if LLM_API_KEY:
        return _call_direct(prompt, system_msg, max_tokens, temperature, timeout, strip_markdown)

    raise LlmDelegationNeeded(
        task_id=uuid.uuid4().hex[:12],
        prompt=prompt,
        system_msg=system_msg,
        max_tokens=max_tokens,
    )


def _call_direct(
    prompt: str,
    system_msg: str,
    max_tokens: int,
    temperature: float,
    timeout: int,
    strip_markdown: bool,
) -> str:
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
    return _parse_json(raw)


def _parse_json(raw: str) -> dict | list | None:
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
