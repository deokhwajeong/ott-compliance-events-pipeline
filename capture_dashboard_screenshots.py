"""
Capture actual dashboard screenshots from running application
"""

import asyncio
import subprocess
import time
import sys
from pathlib import Path
from playwright.async_api import async_playwright


async def capture_screenshots():
    """Capture actual dashboard screenshots"""
    
    images_dir = Path("docs/images")
    images_dir.mkdir(parents=True, exist_ok=True)
    
    print("Starting FastAPI application...")
    app_process = subprocess.Popen(
        ["python", "-m", "uvicorn", "src.app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait for app to start
    await asyncio.sleep(8)
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(viewport={"width": 1400, "height": 900})
            page = await context.new_page()
            
            # Capture main dashboard
            print("Capturing dashboard...")
            try:
                await page.goto("http://127.0.0.1:8000", timeout=30000)
                await page.wait_for_load_state("networkidle", timeout=10000)
                await asyncio.sleep(2)  # Wait for rendering
                
                await page.screenshot(path=str(images_dir / "dashboard-live.png"), full_page=True)
                print(f"Screenshot saved: dashboard-live.png")
            except Exception as e:
                print(f"Failed to capture dashboard: {e}")
            
            # Capture API docs
            print("Capturing API docs...")
            try:
                await page.goto("http://127.0.0.1:8000/docs", timeout=30000)
                await page.wait_for_load_state("networkidle", timeout=10000)
                await asyncio.sleep(2)
                
                await page.screenshot(path=str(images_dir / "api-documentation.png"), full_page=True)
                print(f"Screenshot saved: api-documentation.png")
            except Exception as e:
                print(f"Failed to capture API docs: {e}")
            
            await context.close()
            await browser.close()
            
    except Exception as e:
        print(f"Error: {e}")
        return False
    finally:
        app_process.terminate()
        try:
            app_process.wait(timeout=5)
        except:
            app_process.kill()
    
    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(capture_screenshots())
        if success:
            print("\nScreenshots captured successfully!")
        else:
            print("\nFailed to capture screenshots")
            sys.exit(1)
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)
