@echo off
cd /d C:\Users\user\Desktop\stock-agent
call venv\Scripts\activate
python run.py
git add daily_report.html
git commit -m "Daily report update" --allow-empty
git push