@echo off
cd /d C:\Users\Hp\Desktop\Argus\backtest
echo Starting at %TIME% > bt_out2.log 2>&1
python -u run_backtest.py >> bt_out2.log 2>&1
echo Finished at %TIME% >> bt_out2.log 2>&1
type bt_out2.log
