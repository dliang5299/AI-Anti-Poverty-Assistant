#!/usr/bin/env python3
"""
BenefitsFlow HTML + FastAPI Startup Script
Starts the FastAPI backend and opens the HTML frontend
"""

import subprocess
import os
import sys
import webbrowser
import time
import threading
from pathlib import Path

def main():
    print("Starting BenefitsFlow HTML + FastAPI Application...")
    
    # Ensure we are in the UI directory
    ui_dir = Path(__file__).parent
    os.chdir(ui_dir)
    
    # Check if required files exist
    if not Path("benefitsflow_frontend.html").exists():
        print("ERROR: benefitsflow_frontend.html not found!")
        return
    
    if not Path("fastapi_backend.py").exists():
        print("ERROR: fastapi_backend.py not found!")
        return
    
    # Install dependencies if not already installed
    print("Installing/updating dependencies...")
    try:
        # Try requirements_ui.txt first, fallback to requirements.txt
        req_file = "requirements_ui.txt" if Path("requirements_ui.txt").exists() else "requirements.txt"
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", req_file], 
                      check=True, capture_output=True)
        print("Dependencies verified.")
    except subprocess.CalledProcessError as e:
        print(f"WARNING: Could not install dependencies: {e}")
    
    # Start FastAPI backend in a separate process
    # Set UI_PORT environment variable so backend runs on 8501 (RAG service uses 8000)
    env = os.environ.copy()
    env["UI_PORT"] = "8501"
    print("Starting FastAPI backend on port 8501 (RAG service uses 8000)...")
    try:
        backend_process = subprocess.Popen([sys.executable, "fastapi_backend.py"], env=env)
        
        # Give FastAPI a moment to start
        time.sleep(3)
        
        # Check if backend is running (UI runs on 8501, RAG on 8000)
        ui_port = int(os.getenv("UI_PORT", "8501"))
        try:
            import requests
            response = requests.get(f"http://localhost:{ui_port}/api/health", timeout=5)
            if response.status_code == 200:
                print("FastAPI backend is running successfully.")
            else:
                print("WARNING: FastAPI backend may not be responding properly")
        except ImportError:
            print("WARNING: requests not available - cannot verify backend status")
        except Exception as e:
            print(f"WARNING: Could not verify backend status: {e}")
        
    except Exception as e:
        print(f"ERROR starting FastAPI backend: {e}")
        return
    
    # Open the HTML frontend in the browser
    ui_port = int(os.getenv("UI_PORT", "8501"))
    print("Opening BenefitsFlow in browser...")
    time.sleep(1)  # Give backend a moment to fully start
    webbrowser.open_new_tab(f"http://localhost:{ui_port}")
    
    print("\n" + "="*60)
    print("BenefitsFlow Application Status: RUNNING")
    print(f"Frontend + Backend: http://localhost:{ui_port}")
    print(f"API Documentation: http://localhost:{ui_port}/api/docs")
    print(f"RAG Service (Deric's): http://localhost:8000")
    print("="*60)
    print("\nNotes:")
    print("- The HTML frontend will work even if the API is not running (demo mode)")
    print("- Check the browser console for any connection issues")
    print("- Press Ctrl+C to stop the backend server")
    print("\nApplication ready. You can now test the benefits navigation system.")
    
    try:
        backend_process.wait()  # Wait for the FastAPI process to terminate
    except KeyboardInterrupt:
        print("\nStopping FastAPI backend...")
        backend_process.terminate()
        backend_process.wait()
        print("Backend stopped.")
    except Exception as e:
        print(f"An error occurred: {e}")
        backend_process.terminate()
        backend_process.wait()

if __name__ == "__main__":
    main()
