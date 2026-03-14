from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl
import asyncio
import base64
from typing import Optional, Dict, Any

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    pass # Wait until it's fully installed

router = APIRouter(prefix="/api", tags=["sandbox"])

class SandboxRequest(BaseModel):
    url: HttpUrl

class SandboxResponse(BaseModel):
    url: str
    status_code: int
    title: str
    screenshot_base64: Optional[str]
    suspicious_elements: Dict[str, Any]
    risk_score: int

@router.post("/sandbox", response_model=SandboxResponse)
def analyze_in_sandbox(req: SandboxRequest):
    """
    Safely open a URL in a headless Chromium browser instance.
    Collect network responses, evaluate DOM heuristics, and capture a screenshot.
    """
    target_url = str(req.url)
    screenshot_b64 = None
    title = "Unknown"
    status_code = 0
    forms_count = 0
    iframes_count = 0
    has_pwd = False
    scripts_count = 0
    
    score = 0
    
    try:
        import asyncio
        import sys
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                ignore_https_errors=True,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            # Set a timeout for navigation so it doesn't hang forever
            try:
                response = page.goto(target_url, timeout=15000, wait_until="networkidle")
                if response:
                    status_code = response.status
            except Exception as e:
                # Page load might partially succeed or timeout, we still proceed to grab what we can
                pass
            
            # Wait a tiny bit more for obfuscated JS rendering
            page.wait_for_timeout(2000)

            try:
                title = page.title()
            except Exception:
                title = "Unknown (Context Destroyed/Navigating)"
            
            # Evaluate DOM context heuristics safely inside the sandbox
            try:
                heuristics = page.evaluate('''() => {
                    return {
                        forms: document.querySelectorAll("form").length,
                        iframes: document.querySelectorAll("iframe").length,
                        passwords: document.querySelectorAll('input[type="password"]').length,
                        scripts: document.querySelectorAll("script[src]").length
                    }
                }''')

                forms_count = heuristics.get('forms', 0)
                iframes_count = heuristics.get('iframes', 0)
                has_pwd = heuristics.get('passwords', 0) > 0
                scripts_count = heuristics.get('scripts', 0)
            except Exception:
                # If page is stuck in infinite redirect loop or context destroyed
                pass

            # Take screenshot as JPEG
            try:
                screenshot_bytes = page.screenshot(type='jpeg', quality=60, full_page=False)
                screenshot_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')
            except Exception:
                pass

            browser.close()
            
            # Simple heuristic risk scoring
            if has_pwd:
                score += 40
            if iframes_count > 0:
                score += 10 * iframes_count
            if forms_count > 0:
                score += 15
            if scripts_count > 10:
                score += 10
                
            # Cap at 100
            score = min(score, 100)

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {str(e)}")

    return SandboxResponse(
        url=target_url,
        status_code=status_code,
        title=title,
        screenshot_base64=screenshot_b64,
        suspicious_elements={
            "forms": forms_count,
            "iframes": iframes_count,
            "has_password_field": has_pwd,
            "external_scripts": scripts_count
        },
        risk_score=score
    )
