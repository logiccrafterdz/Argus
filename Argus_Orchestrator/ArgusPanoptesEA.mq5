//+------------------------------------------------------------------+
//|                                             ArgusPanoptesEA.mq5  |
//|                                  Copyright 2026, LogicCrafterDz |
//|                                             https://example.com |
//|                                                                  |
//|  WARNING: FOR EDUCATIONAL PURPOSES ONLY. NO WARRANTY PROVIDED.   |
//|  USE AT YOUR OWN RISK.                                           |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, LogicCrafterDz"
#property link      "https://example.com"
#property version   "1.00"
#property description "Portfolio Orchestrator: Manages global circuit breakers and regimes."
#property strict

//--- Input parameters
input string   _RiskSettings        = "------ Circuit Breaker ------";
input double   MaxDailyDrawdown     = 3.0;           // Max Daily Drawdown (%)
input bool     CloseAllOnHalt       = true;          // Close all positions when halted
input string   _GlobalSettings      = "------ Global Variables ------";
input string   HaltVariableName     = "Argus_Halt";

//--- Global variables
double initial_daily_balance = 0;
int last_day = -1;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   MqlDateTime dt;
   TimeCurrent(dt);
   last_day = dt.day;
   initial_daily_balance = AccountInfoDouble(ACCOUNT_BALANCE);
   
   if(GlobalVariableCheck(HaltVariableName)) GlobalVariableSet(HaltVariableName, 0);
   else GlobalVariableTemp(HaltVariableName);
   
   EventSetTimer(1);
   
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   if(GlobalVariableCheck(HaltVariableName)) GlobalVariableDel(HaltVariableName);
   Comment("");
}

void OnTimer()
{
   MqlDateTime dt;
   TimeCurrent(dt);
   if(dt.day != last_day) {
      last_day = dt.day;
      initial_daily_balance = AccountInfoDouble(ACCOUNT_BALANCE);
      GlobalVariableSet(HaltVariableName, 0);
   }

   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   
   double current_drawdown_pct = 0;
   if(initial_daily_balance > 0) {
      current_drawdown_pct = ((initial_daily_balance - equity) / initial_daily_balance) * 100.0;
   }

   bool is_halted = (GlobalVariableGet(HaltVariableName) == 1);

   if(!is_halted && current_drawdown_pct >= MaxDailyDrawdown) {
      PrintFormat("Argus Panoptes: 🚨 CIRCUIT BREAKER TRIPPED! Daily DD reached %.2f%%", current_drawdown_pct);
      GlobalVariableSet(HaltVariableName, 1);
      
      if(CloseAllOnHalt) EmergencyCloseAll();
   }

   UpdateDashboard(current_drawdown_pct, is_halted, balance, equity);
}

void EmergencyCloseAll()
{
   #include <Trade\Trade.mqh>
   CTrade trade;
   int failed_closes = 0;
   
   for(int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket)) {
         if(!trade.PositionClose(ticket, -1)) failed_closes++;
      }
   }
   
   if(failed_closes > 0) PrintFormat("Argus Panoptes: Warning, failed to close %d positions.", failed_closes);
   else Print("Argus Panoptes: Successfully closed all open positions.");
}

void UpdateDashboard(double dd_pct, bool is_halted, double balance, double equity)
{
   string status = is_halted ? "HALTED (Circuit Breaker Tripped)" : "ACTIVE";
   string text = "=== 👁️ ARGUS PANOPTES === \n\n";
   text += StringFormat("Status: %s\n", status);
   text += StringFormat("Start Balance: %.2f\n", initial_daily_balance);
   text += StringFormat("Current Equity: %.2f\n", equity);
   text += StringFormat("Daily PnL: %.2f (%.2f%%)\n", equity - initial_daily_balance, -dd_pct);
   text += StringFormat("Max DD Allowed: %.2f%%\n", MaxDailyDrawdown);
   
   Comment(text);
}
