@echo off
CALL conda.bat activate python38
CHCP 65001
python reassembly_crawler.py --help
python reassembly_crawler.py --input_dir=All_Agents_Grouped --output_dir=Random_Agents --post_processing --download_num=256
@echo on
pause