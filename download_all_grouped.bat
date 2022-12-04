@echo off
CALL conda.bat activate reassembly_crawler
CHCP 65001
python reassembly_crawler.py --help
python reassembly_crawler.py --input_dir=Input --output_dir=All_Agents_Grouped --waiting_time=0 --grouped
@echo on
pause
