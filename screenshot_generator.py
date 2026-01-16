"""
Automated screenshot generator for the OTT Compliance Dashboard
Uses Playwright to capture dashboard UI screenshots for documentation
"""

import asyncio
import subprocess
import time
import sys
from pathlib import Path
from playwright.async_api import async_playwright


async def generate_screenshots():
    """Generate dashboard screenshots using Playwright"""
    
    # Create docs/images directory if it doesn't exist
    images_dir = Path("docs/images")
    images_dir.mkdir(parents=True, exist_ok=True)
    
    print("🚀 Starting dashboard screenshot generation...")
    print(f"📁 Saving screenshots to: {images_dir}")
    
    # Start the FastAPI application in the background
    print("\n⏳ Starting FastAPI application...")
    app_process = subprocess.Popen(
        ["python", "-m", "uvicorn", "src.app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait for the app to start
    await asyncio.sleep(5)
    
    try:
        async with async_playwright() as p:
            print("🌐 Launching Chromium browser...")
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(viewport={"width": 1400, "height": 900})
            page = await context.new_page()
            
            # Main dashboard
            print("📸 Capturing main dashboard...")
            try:
                await page.goto("http://localhost:8000", wait_until="networkidle", timeout=30000)
                await page.wait_for_load_state("networkidle")
                await page.screenshot(path=str(images_dir / "dashboard-main.png"), full_page=True)
                print(f"✅ Saved: dashboard-main.png")
            except Exception as e:
                print(f"⚠️  Could not capture main dashboard: {e}")
            
            # Try to capture GraphQL endpoint
            print("📸 Capturing GraphQL playground...")
            try:
                await page.goto("http://localhost:8000/graphql", wait_until="networkidle", timeout=30000)
                await page.wait_for_load_state("networkidle")
                await page.screenshot(path=str(images_dir / "graphql-playground.png"), full_page=True)
                print(f"✅ Saved: graphql-playground.png")
            except Exception as e:
                print(f"⚠️  Could not capture GraphQL: {e}")
            
            # Try to capture API docs
            print("📸 Capturing API documentation...")
            try:
                await page.goto("http://localhost:8000/docs", wait_until="networkidle", timeout=30000)
                await page.wait_for_load_state("networkidle")
                await page.screenshot(path=str(images_dir / "api-docs.png"), full_page=True)
                print(f"✅ Saved: api-docs.png")
            except Exception as e:
                print(f"⚠️  Could not capture API docs: {e}")
            
            # Try to capture alternative docs
            print("📸 Capturing ReDoc documentation...")
            try:
                await page.goto("http://localhost:8000/redoc", wait_until="networkidle", timeout=30000)
                await page.wait_for_load_state("networkidle")
                await page.screenshot(path=str(images_dir / "redoc-docs.png"), full_page=True)
                print(f"✅ Saved: redoc-docs.png")
            except Exception as e:
                print(f"⚠️  Could not capture ReDoc: {e}")
            
            await context.close()
            await browser.close()
            
    except Exception as e:
        print(f"❌ Error during screenshot generation: {e}")
        sys.exit(1)
    finally:
        # Stop the FastAPI application
        print("\n🛑 Stopping FastAPI application...")
        app_process.terminate()
        app_process.wait(timeout=5)
    
    print("\n✅ Screenshot generation complete!")
    print(f"📁 Screenshots saved to: {images_dir}")
    
    # List generated files
    files = list(images_dir.glob("*.png"))
    if files:
        print(f"\n📸 Generated {len(files)} screenshot(s):")
        for f in files:
            print(f"   - {f.name}")
    
    return images_dir


if __name__ == "__main__":
    print("=" * 70)
    print("OTT Compliance Dashboard - Automated Screenshot Generator")
    print("=" * 70)
    
    try:
        asyncio.run(generate_screenshots())
    except KeyboardInterrupt:
        print("\n\n⚠️  Screenshot generation interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)
