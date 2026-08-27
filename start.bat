@echo off
REM ============================================
REM  Start the Automated Credit Analysis (GUI)
REM ============================================
chcp 65001 >nul
title Análise de Crédito - Serasa
python src\app.py
