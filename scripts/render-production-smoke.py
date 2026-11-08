#!/usr/bin/env python3
"""Read-only production checks for the ChapelFlow Render deployment.

Does not authenticate as a real user, create attendance sessions, or mutate data.
Run from GitHub Actions or a machine with internet access.
"""
import json
import re
import sys
import time
from urllib import error, parse, request

WEB = "https://chapelflow-web.onrender.com"
API = "https://chapelflow-api-71wq.onrender.com"
checks = []

def fetch(url, method="GET", headers=None, body=None):
    for attempt in range(3):
        req = request.Request(url, data=body, method=method, headers=headers or {})
        try:
            with request.urlopen(req, timeout=65) as resp:
                return resp.status, dict(resp.headers.items()), resp.read(4_000_000)
        except error.HTTPError as exc:
            if exc.code not in (429, 502, 503, 504) or attempt == 2:
                return exc.code, dict(exc.headers.items()), exc.read(2000)
            print(f"  Render waking up: HTTP {exc.code}; retry {attempt + 1}", flush=True)
        except (TimeoutError, OSError) as exc:
            if attempt == 2:
                raise RuntimeError(str(exc)) from exc
            print(f"  Network retry {attempt + 1}: {type(exc).__name__}", flush=True)
        time.sleep(10)

def header(headers, name):
    return next((str(v) for k, v in headers.items() if k.lower() == name.lower()), "")

def check(name, fn):
    try:
        detail = fn()
        checks.append((name, True, detail))
        print(f"PASS {name}: {detail}", flush=True)
    except Exception as exc:
        checks.append((name, False, str(exc)))
        print(f"FAIL {name}: {exc}", flush=True)

def expect(condition, message):
    if not condition:
        raise AssertionError(message)

def check_frontend():
    status, headers, body = fetch(WEB + "/")
    expect(status == 200, f"frontend / returned HTTP {status}: {body[:160]!r}")
    html = body.decode("utf-8", "replace")
    expect("<html" in html.lower(), "frontend root did not return HTML")
    assets = re.findall(r'(?:src|href)=["\x27]([^"\x27]+\.js)(?:["\x27])', html)
    expect(assets, "frontend entry JS asset missing from HTML")
    scripts = []
    for path in assets[:8]:
        url = parse.urljoin(WEB + "/", path)
        code, _, payload = fetch(url)
        expect(code == 200, f"JS asset {url} returned HTTP {code}")
        scripts.append(payload.decode("utf-8", "replace"))
    bundle = "\n".join(scripts)
    expect(API in bundle,
           f"frontend JS does not contain the intended Render API origin {API}; "
           "set VITE_API_BASE_URL=https://chapelflow-api-71wq.onrender.com/api/v1 "
           "on the Render static service and redeploy")
    return f"HTTP 200, HTML and JS load; configured API origin: {API}"

def check_spa(path):
    status, _, body = fetch(WEB + path)
    expect(status == 200 and b"<html" in body.lower(),
           f"SPA route {path} returned HTTP {status}; configure Render static rewrite /* -> /index.html")
    return f"{path} -> HTML (HTTP 200)"

def check_health(path):
    status, _, body = fetch(API + path)
    expect(status == 200, f"GET {path} returned HTTP {status}: {body[:250]!r}")
    return f"{path} returned HTTP 200"

def check_csrf():
    status, headers, body = fetch(API + "/api/v1/auth/csrf/", headers={"Origin": WEB, "Accept": "application/json"})
    expect(status == 200, f"CSRF endpoint HTTP {status}: {body[:300]!r}")
    expect(header(headers, "Access-Control-Allow-Origin") == WEB,
           f"missing CORS allow origin for frontend; got {header(headers, 'Access-Control-Allow-Origin')!r}")
    expect(header(headers, "Access-Control-Allow-Credentials").lower() == "true",
           "CORS does not permit credentialed requests")
    cookies = header(headers, "Set-Cookie")
    expect("chapelflow_csrf" in cookies, "CSRF bootstrap cookie not issued")
    expect("samesite=none" in cookies.lower() and "secure" in cookies.lower(),
           "cross-site CSRF cookie must be Secure; SameSite=None")
    value = json.loads(body.decode())
    expect(isinstance(value.get("data", {}).get("csrf_token"), str),
           "CSRF token missing from response JSON")
    return "HTTP 200, frontend CORS and credential headers correct, Secure SameSite=None CSRF issued"

def check_preflight():
    status, headers, body = fetch(API + "/api/v1/attendance/sessions/", method="OPTIONS", headers={
        "Origin": WEB,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type,x-chapelflow-csrf,x-requested-with",
    })
    expect(status in (200, 204), f"attendance preflight HTTP {status}: {body[:120]!r}")
    expect(header(headers, "Access-Control-Allow-Origin") == WEB,
           "attendance preflight CORS origin missing")
    expect(header(headers, "Access-Control-Allow-Credentials").lower() == "true",
           "attendance preflight credentials not allowed")
    allow_headers = header(headers, "Access-Control-Allow-Headers").lower()
    expect(all(x in allow_headers for x in ("x-chapelflow-csrf", "x-requested-with", "content-type")),
           f"required request headers missing from CORS: {allow_headers}")
    return "attendance POST preflight permitted from ChapelFlow static frontend"

def check_unauth(path, method="GET"):
    status, _, body = fetch(API + path, method=method,
                            headers={"Origin": WEB, "Accept": "application/json",
                                     "Content-Type": "application/json"},
                            body=b"{}" if method == "POST" else None)
    expect(status in (401, 403), f"unauthenticated {method} {path} returned HTTP {status}: {body[:250]!r}")
    return f"unauthenticated {method} {path}: HTTP {status} (properly denied)"

check("Render frontend root and bundled API URL", check_frontend)
check("SPA Super Admin route", lambda: check_spa("/app"))
check("SPA login route", lambda: check_spa("/login"))
check("Django liveness", lambda: check_health("/health/"))
check("Django database readiness", lambda: check_health("/readiness/"))
check("CSRF bootstrap and cookie/CORS", check_csrf)
check("Attendance POST CORS preflight", check_preflight)
check("Attendance listing requires authentication", lambda: check_unauth("/api/v1/attendance/sessions/"))
check("Attendance creation requires authentication", lambda: check_unauth("/api/v1/attendance/sessions/", "POST"))
check("Auth/me requires authentication", lambda: check_unauth("/api/v1/auth/me/"))

passed = sum(1 for _, ok, _ in checks if ok)
print(f"\nRESULT: {passed}/{len(checks)} production checks passed", flush=True)
if passed != len(checks):
    print("Only authenticated Super Admin end-to-end start/stop remains outside this read-only probe.", flush=True)
sys.exit(0 if passed == len(checks) else 1)
