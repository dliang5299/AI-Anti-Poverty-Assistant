#!/usr/bin/env python3
"""
BenefitsFlow Application Launcher
Simple script to run the Streamlit application with proper configuration.
"""

import subprocess
import sys
import os
from pathlib import Path

def check_dependencies():
    """Check if required dependencies are installed"""
    try:
        import streamlit
        print("✅ Streamlit is installed")
    except ImportError:
        print("❌ Streamlit not found. Installing dependencies...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dependencies installed")

def main():
    """Main function to run the application"""
    print("🌍 Starting BenefitsFlow - California Benefits Navigator")
    print("=" * 60)
    
    # Check if we're in the right directory
    if not Path("app.py").exists():
        print("❌ Error: app.py not found. Please run this script from the UI directory.")
        sys.exit(1)
    
    # Check dependencies
    check_dependencies()
    
    # Set environment variables for better performance
    os.environ["STREAMLIT_SERVER_HEADLESS"] = "true"
    os.environ["STREAMLIT_SERVER_PORT"] = "8501"
    os.environ["STREAMLIT_SERVER_ADDRESS"] = "localhost"
    
    print("\n🚀 Launching BenefitsFlow...")
    print("📱 The app will open in your default browser")
    print("🔗 URL: http://localhost:8501")
    print("\n💡 Tips:")
    print("   - Use Ctrl+C to stop the server")
    print("   - Refresh the browser if the page doesn't load")
    print("   - Check the terminal for any error messages")
    print("\n" + "=" * 60)
    
    try:
        # Run Streamlit
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", "app.py",
            "--server.port", "8501",
            "--server.address", "localhost",
            "--browser.gatherUsageStats", "false",
            "--server.enableCORS", "false",
            "--server.enableXsrfProtection", "false"
        ])
    except KeyboardInterrupt:
        print("\n\n👋 BenefitsFlow stopped. Thank you for using our service!")
    except Exception as e:
        print(f"\n❌ Error starting BenefitsFlow: {e}")
        print("Please check your installation and try again.")

if __name__ == "__main__":
    main()
