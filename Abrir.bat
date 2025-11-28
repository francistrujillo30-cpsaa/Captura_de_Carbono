@echo off
cd C:\Users\Pulgi\captura_carbono
start Home.py
timeout /t 2 /nobreak
python -m streamlit run Home.py