@echo off
CALL conda.bat activate python38
CHCP 65001
python reassembly_crawler.py --help
python reassembly_crawler.py --input_dir=All_Agents_Grouped --output_dir="C:\Users\hydz2\Saved Games\Reassembly\data\agents" --post_processing
@echo on
pause