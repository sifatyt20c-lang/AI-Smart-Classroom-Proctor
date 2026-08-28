#!/usr/bin/env bash

# Exit on error
set -e

echo "===================================================="
echo "   AI SMART CLASSROOM PROCTORING SYSTEM DEPLOYER    "
echo "===================================================="

# 1. Verify Python Installation
if ! command -v python3 &> /dev/null
then
    echo "[ERROR] Python3 could not be found. Please install Python 3.8+."
    exit 1
fi

# 2. Setup Virtual Environment
VENV_DIR="proctor_env"
if [ ! -d "$VENV_DIR" ]; then
    echo "[INFO] Creating Virtual Environment in './$VENV_DIR'..."
    python3 -m venv $VENV_DIR
else
    echo "[INFO] Virtual Environment exists. Skipping creation."
fi

# 3. Activate Environment
source $VENV_DIR/bin/activate

# 4. Upgrade Pip and Install Dependencies
echo "[INFO] Installing required dependencies (OpenCV, MediaPipe, NumPy, Google-GenerativeAI)..."
pip install --upgrade pip
pip install opencv-python mediapipe numpy google-generativeai

# 5. Launch the Application
echo "===================================================="
echo "[SUCCESS] Environment ready! Launching System..."
echo "===================================================="
python3 proctor_system.py
