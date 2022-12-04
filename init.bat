@echo off
CALL conda.bat activate python38
CHCP 65001
pip install BeautifulSoup4
@echo on
pause