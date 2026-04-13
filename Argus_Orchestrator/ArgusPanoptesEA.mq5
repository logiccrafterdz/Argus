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

#include <Trade\Trade.mqh>

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
   
   ObjectDelete(0, "Argus_BG");
   ObjectDelete(0, "Argus_Header");
   ObjectDelete(0, "Argus_Status");
   ObjectDelete(0, "Argus_Eq");
   ObjectDelete(0, "Argus_DD");
   ChartRedraw();
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
   if(ObjectFind(0, "Argus_BG") < 0) {
      ObjectCreate(0, "Argus_BG", OBJ_RECTANGLE_LABEL, 0, 0, 0);
      ObjectCreate(0, "Argus_Header", OBJ_LABEL, 0, 0, 0);
      ObjectCreate(0, "Argus_Status", OBJ_LABEL, 0, 0, 0);
      ObjectCreate(0, "Argus_Eq", OBJ_LABEL, 0, 0, 0);
      ObjectCreate(0, "Argus_DD", OBJ_LABEL, 0, 0, 0);
   }
   
   // Background
   ObjectSetInteger(0, "Argus_BG", OBJPROP_XDISTANCE, 20);
   ObjectSetInteger(0, "Argus_BG", OBJPROP_YDISTANCE, 30);
   ObjectSetInteger(0, "Argus_BG", OBJPROP_XSIZE, 280);
   ObjectSetInteger(0, "Argus_BG", OBJPROP_YSIZE, 150);
   ObjectSetInteger(0, "Argus_BG", OBJPROP_BGCOLOR, clrBlack);
   ObjectSetInteger(0, "Argus_BG", OBJPROP_BORDER_COLOR, clrDimGray);
   ObjectSetInteger(0, "Argus_BG", OBJPROP_CORNER, CORNER_LEFT_UPPER);
   
   // Header
   ObjectSetInteger(0, "Argus_Header", OBJPROP_XDISTANCE, 30);
   ObjectSetInteger(0, "Argus_Header", OBJPROP_YDISTANCE, 40);
   ObjectSetString(0, "Argus_Header", OBJPROP_TEXT, "👁️ ARGUS PANOPTES");
   ObjectSetInteger(0, "Argus_Header", OBJPROP_COLOR, clrGold);
   ObjectSetString(0, "Argus_Header", OBJPROP_FONT, "Segoe UI");
   ObjectSetInteger(0, "Argus_Header", OBJPROP_FONTSIZE, 12);
   
   // Status
   ObjectSetInteger(0, "Argus_Status", OBJPROP_XDISTANCE, 30);
   ObjectSetInteger(0, "Argus_Status", OBJPROP_YDISTANCE, 70);
   ObjectSetString(0, "Argus_Status", OBJPROP_TEXT, "Status: " + (is_halted ? "🚨 HALTED (Circuit Breaker)" : "✅ ACTIVE"));
   ObjectSetInteger(0, "Argus_Status", OBJPROP_COLOR, is_halted ? clrRed : clrLimeGreen);
   ObjectSetString(0, "Argus_Status", OBJPROP_FONT, "Segoe UI");
   ObjectSetInteger(0, "Argus_Status", OBJPROP_FONTSIZE, 10);
   
   // Equity
   ObjectSetInteger(0, "Argus_Eq", OBJPROP_XDISTANCE, 30);
   ObjectSetInteger(0, "Argus_Eq", OBJPROP_YDISTANCE, 100);
   ObjectSetString(0, "Argus_Eq", OBJPROP_TEXT, StringFormat("Equity: $%.2f | Base: $%.2f", equity, initial_daily_balance));
   ObjectSetInteger(0, "Argus_Eq", OBJPROP_COLOR, clrWhite);
   ObjectSetString(0, "Argus_Eq", OBJPROP_FONT, "Segoe UI");
   ObjectSetInteger(0, "Argus_Eq", OBJPROP_FONTSIZE, 9);
   
   // Drawdown
   ObjectSetInteger(0, "Argus_DD", OBJPROP_XDISTANCE, 30);
   ObjectSetInteger(0, "Argus_DD", OBJPROP_YDISTANCE, 130);
   ObjectSetString(0, "Argus_DD", OBJPROP_TEXT, StringFormat("Daily Drawdown: %.2f%% (Max: %.2f%%)", dd_pct, MaxDailyDrawdown));
   ObjectSetInteger(0, "Argus_DD", OBJPROP_COLOR, (dd_pct > MaxDailyDrawdown*0.7) ? clrOrange : clrWhite);
   ObjectSetString(0, "Argus_DD", OBJPROP_FONT, "Segoe UI");
   ObjectSetInteger(0, "Argus_DD", OBJPROP_FONTSIZE, 9);
   
   ChartRedraw();
}
