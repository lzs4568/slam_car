@echo off
set MSYSTEM=
set IDF_PATH=C:\esp\v6.0.1\esp-idf
set IDF_PYTHON_ENV_PATH=C:\Users\77898\.espressif\python_env\idf6.0_py3.12_env
set ESP_IDF_VERSION=6.0.1
set PATH=C:\Espressif\tools\cmake\4.0.3\bin;C:\Espressif\tools\ninja\1.12.1;C:\Espressif\tools\xtensa-esp-elf\esp-15.2.0_20251204\xtensa-esp-elf\bin;C:\Espressif\tools\python\v6.0.1\venv\Scripts;C:\Users\77898\.espressif\python_env\idf6.0_py3.12_env\Scripts;%PATH%
C:\Espressif\tools\python\v6.0.1\venv\Scripts\python.exe C:\esp\v6.0.1\esp-idf\tools\idf.py build
