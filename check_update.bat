@echo off
CALL conda.bat activate reassembly_crawler
CHCP 65001
python reassembly_crawler.py --help
python reassembly_crawler.py --input_dir=Input --output_dir=All_Agents --crawler_mode=GetLinks --check_update
@echo on
pause
