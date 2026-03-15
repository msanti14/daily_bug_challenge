import os
import json
import random
import urllib.request
import urllib.error
from datetime import date

# ── Config ────────────────────────────────────────────────────────────────────
GITHUB_TOKEN      = os.environ["GITHUB_TOKEN"]   # para crear issues
GH_PAT            = os.environ["GH_PAT"]          # para llamar a GitHub Models
SENDGRID_API_KEY  = os.environ["SENDGRID_API_KEY"]
EMAIL_RECEIVER    = os.environ["EMAIL_RECEIVER"]
EMAIL_SENDER      = os.environ["EMAIL_SENDER"]

REPO_OWNER = "msanti14"
REPO_NAME  = "daily_bug_challenge"
ASSIGNEE   = "msanti14"

BUG_CATEGORIES = ["Python puro", "FastAPI / backend", "tests con errores"]
TODAY          = date.today().isoformat()
CATEGORY       = random.choice(BUG_CATEGORIES)

# ── Prompts ───────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """Eres un generador de desafíos de debugging para un desarrollador Python junior.
Debes responder SOLO con un JSON válido, sin backticks ni texto adicional.
El JSON debe tener exactamente estas claves:
{
  "title": "string corto descriptivo del bug",
  "category": "string con la categoría",
  "difficulty": "Fácil | Media | Difícil",
  "description": "string explicando el contexto del bug en español",
  "buggy_code": "string con el código Python que contiene el bug",
  "hints": ["hint 1", "hint 2"],
  "solution": "string con la explicación de la solución (NO el código corregido)"
}"""

USER_PROMPT = f"""Genera un desafío de debugging de categoría: {CATEGORY}.
Fecha: {TODAY}.
El código debe tener exactamente UN bug sutil pero educativo.
Dificultad aleatoria entre Fácil, Media o Difícil."""


def call_github_models(system: str, user: str) -> dict:
    url = "https://models.inference.ai.azure.com/chat/completions"
    payload = json.dumps({
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        "temperature": 0.9,
        "max_tokens": 1200,
    }).encode()

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {GH_PAT}",  # PAT para GitHub Models
        },
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())

    raw = data["choices"][0]["message"]["content"].strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(raw)


def build_issue_body(bug: dict) -> str:
    hints = "\n".join(f"- {h}" for h in bug["hints"])
    return f"""## 🐛 Daily Bug Challenge — {TODAY}

**Categoría:** {bug['category']}
**Dificultad:** {bug['difficulty']}

---

### 📋 Descripción

{bug['description']}

---

### 🔴 Código con el bug

```python
{bug['buggy_code']}
```

---

### 💡 Hints

{hints}

---

<details>
<summary>✅ Ver solución (spoiler)</summary>

{bug['solution']}

</details>

---
*Generado automáticamente por [daily-bug-challenge](https://github.com/{REPO_OWNER}/{REPO_NAME})*
"""


def github_request(method: str, endpoint: str, payload: dict | None = None):
    url = f"https://api.github.com{endpoint}"
    data = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def create_issue(bug: dict) -> dict:
    return github_request(
        "POST",
        f"/repos/{REPO_OWNER}/{REPO_NAME}/issues",
        {
            "title": f"[Bug {TODAY}] {bug['title']}",
            "body": build_issue_body(bug),
            "assignees": [ASSIGNEE],
            "labels": ["daily-bug",],
        },
    )


def send_email_sendgrid(bug: dict, issue_url: str):
    subject = f"🐛 Bug del día ({TODAY}) — {bug['difficulty']} — {bug['category']}"
    body_text = (
        f"Hola Santi,\n\n"
        f"Tu desafío de hoy es de categoría '{bug['category']}' "
        f"y dificultad '{bug['difficulty']}'.\n\n"
        f"📌 Issue: {issue_url}\n\n"
        f"Descripción:\n{bug['description']}\n\n"
        f"Hints:\n" + "\n".join(f"- {h}" for h in bug["hints"]) + "\n\n"
        f"¡Buena suerte!\n"
    )

    payload = json.dumps({
        "personalizations": [{"to": [{"email": EMAIL_RECEIVER}]}],
        "from": {"email": EMAIL_SENDER, "name": "Daily Bug Challenge"},
        "subject": subject,
        "content": [{"type": "text/plain", "value": body_text}],
    }).encode()

    req = urllib.request.Request(
        "https://api.sendgrid.com/v3/mail/send",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {SENDGRID_API_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            print(f"Email enviado. Status: {resp.status}")
    except urllib.error.HTTPError as e:
        print(f"Error enviando email: {e.code} — {e.read().decode()}")


def ensure_labels():
    labels = [
        ("daily-bug",           "B60205", "Bug diario generado por IA"),
        ("facil",               "0E8A16", "Dificultad facil"),
        ("media",               "E4E669", "Dificultad media"),
        ("dificil",             "D93F0B", "Dificultad dificil"),
        ("python puro",         "3572A5", "Categoria Python puro"),
        ("fastapi / backend",   "009688", "Categoria FastAPI / backend"),
        ("tests con errores",   "FF9800", "Categoria tests con errores"),
    ]
    for name, color, desc in labels:
        try:
            github_request("POST", f"/repos/{REPO_OWNER}/{REPO_NAME}/labels",
                           {"name": name, "color": color, "description": desc})
            print(f"Label creado: {name}")
        except urllib.error.HTTPError as e:
            if e.code == 422:
                pass  # ya existe, ignorar
            else:
                print(f"Error creando label '{name}': {e.code}")


def main():
    print(f"Categoría de hoy: {CATEGORY}")

    ensure_labels()

    print("Llamando a GitHub Models...")
    bug = call_github_models(SYSTEM_PROMPT, USER_PROMPT)
    print(f"Bug generado: {bug['title']} | {bug['difficulty']}")

    issue = create_issue(bug)
    print(f"Issue creado: {issue['html_url']}")

    send_email_sendgrid(bug, issue["html_url"])
    print("¡Todo listo!")


if __name__ == "__main__":
    main()
