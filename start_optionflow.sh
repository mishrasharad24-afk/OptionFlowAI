#!/bin/bash

cd /home/ec2-user/OptionFlowAI || exit 1

source venv/bin/activate

echo "=========================================="
echo "OPTION FLOW AI STARTUP"
echo "=========================================="

echo "Starting m.Stock OTP Login..."
python broker/login.py

if [ $? -ne 0 ]; then
    echo "LOGIN SCRIPT FAILED"
    exit 1
fi

if [ ! -s access_token.txt ]; then
    echo "ERROR: ACCESS TOKEN NOT FOUND"
    exit 1
fi

echo "ACCESS TOKEN READY"
echo "STARTING OPTION FLOW AI BOT..."

python -m bot.optionflow_master
