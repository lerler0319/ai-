"""Upload Prompt Lab to GitHub - no extra tools needed."""
import subprocess
import sys
import json
import base64
import urllib.request

GITHUB_USER = "lerler0319"
REPO_NAME = "ai提示词评分"
REPO_DESC = "AI 提示词 A/B 测试平台 — 用数据驱动的方式找到最优 prompt"

def api_request(token, method, url, data=None):
    req = urllib.request.Request(url, method=method)
    auth = base64.b64encode(f"{GITHUB_USER}:{token}".encode()).decode()
    req.add_header("Authorization", f"Basic {auth}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "PromptLab")
    if data:
        req.add_header("Content-Type", "application/json")
        req.data = json.dumps(data).encode()
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())

def push_with_token(token):
    """Push using token as password in git URL."""
    # Use token in URL: https://token:x-oauth-basic@github.com/user/repo.git
    encoded_repo = urllib.parse.quote(REPO_NAME)
    url = f"https://{GITHUB_USER}:{token}@github.com/{GITHUB_USER}/{encoded_repo}.git"

    # Set remote with token
    subprocess.run(["git", "remote", "remove", "origin"], capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", url], capture_output=True)

    proc = subprocess.run(
        ["git", "push", "-u", "origin", "master"],
        capture_output=True, text=True,
    )
    if proc.returncode == 0:
        # Remove token from URL after push (security)
        clean_url = f"https://github.com/{GITHUB_USER}/{encoded_repo}.git"
        subprocess.run(["git", "remote", "set-url", "origin", clean_url], capture_output=True)
        return True, proc.stdout
    return False, proc.stderr

if __name__ == "__main__":
    import urllib.parse

    if len(sys.argv) < 2:
        token = input("GitHub Token: ").strip()
    else:
        token = sys.argv[1]

    if not token:
        print("❌ Token 不能为空")
        sys.exit(1)

    # 1. Create repo via API
    print("创建仓库...")
    status, result = api_request(token, "POST", "https://api.github.com/user/repos", {
        "name": REPO_NAME,
        "description": REPO_DESC,
        "private": False,
    })

    if status == 201:
        print(f"✓ 仓库已创建: {result['html_url']}")
    elif status == 422 and "already exists" in str(result.get("errors", "")):
        print("✓ 仓库已存在，直接推送")
    else:
        print(f"❌ 创建失败 ({status}): {result}")
        sys.exit(1)

    # 2. Push code
    print("推送代码...")
    ok, msg = push_with_token(token)
    if ok:
        encoded_repo = urllib.parse.quote(REPO_NAME)
        print(f"✓ 上传成功！")
        print(f"  https://github.com/{GITHUB_USER}/{encoded_repo}")
    else:
        print(f"❌ 推送失败:\n{msg}")
