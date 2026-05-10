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
#include "..\Shared\MarketRegimeEngine.mqh"

//--- Input parameters
input string   _RiskSettings        = "------ Circuit Breaker ------";
input double   MaxDailyDrawdown     = 3.0;           // Max Daily Drawdown (%)
input double   MaxWeeklyDrawdown    = 8.0;           // Max Weekly Drawdown (%)
input double   MaxMonthlyDrawdown   = 15.0;          // Max Monthly Drawdown (%)
input bool     CloseAllOnHalt       = true;          // Close all positions when halted
input string   _SessionSettings     = "------ Session Times (Broker Time) ------";
input int      AsianStartHour       = 0;
input int      AsianEndHour         = 8;
input int      LondonStartHour      = 8;
input int      LondonEndHour        = 16;
input int      NYStartHour          = 13;
input int      NYEndHour            = 22;
input string   _GlobalSettings      = "------ Global Variables ------";
input string   HaltVariableName     = "Argus_Halt";

//--- Global variables
double initial_daily_balance = 0;
double initial_weekly_balance = 0;
double initial_monthly_balance = 0;
int last_day = -1;
int last_week = -1;
int last_month = -1;
CMarketRegimeEngine regimeEngine;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   MqlDateTime dt;
   TimeCurrent(dt);
   last_day = dt.day;
   last_week = dt.day_of_year / 7;
   last_month = dt.mon;
   
   initial_daily_balance = AccountInfoDouble(ACCOUNT_BALANCE);
   initial_weekly_balance = initial_daily_balance;
   initial_monthly_balance = initial_daily_balance;
   
   // Recover from global variables if exist
   if(GlobalVariableCheck("Argus_InitDailyBal")) initial_daily_balance = GlobalVariableGet("Argus_InitDailyBal");
   if(GlobalVariableCheck("Argus_InitWeeklyBal")) initial_weekly_balance = GlobalVariableGet("Argus_InitWeeklyBal");
   if(GlobalVariableCheck("Argus_InitMonthlyBal")) initial_monthly_balance = GlobalVariableGet("Argus_InitMonthlyBal");
   
   if(GlobalVariableCheck(HaltVariableName)) GlobalVariableSet(HaltVariableName, 0);
   else GlobalVariableTemp(HaltVariableName);
   
   EventSetTimer(1);
   
   if(!regimeEngine.Init(_Symbol, PERIOD_D1)) {
      Print("Argus Panoptes: Failed to init Regime Engine.");
      return(INIT_FAILED);
   }
   
   trade.SetDeviationInPoints(30);
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   regimeEngine.Deinit();
   if(GlobalVariableCheck(HaltVariableName)) GlobalVariableDel(HaltVariableName);
   if(GlobalVariableCheck("Argus_Regime")) GlobalVariableDel("Argus_Regime");
   if(GlobalVariableCheck("Argus_Session")) GlobalVariableDel("Argus_Session");
   
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
      GlobalVariableSet("Argus_InitDailyBal", initial_daily_balance);
      GlobalVariableSet(HaltVariableName, 0);
   }
   if(dt.day_of_year / 7 != last_week) {
      last_week = dt.day_of_year / 7;
      initial_weekly_balance = AccountInfoDouble(ACCOUNT_BALANCE);
      GlobalVariableSet("Argus_InitWeeklyBal", initial_weekly_balance);
   }
   if(dt.mon != last_month) {
      last_month = dt.mon;
      initial_monthly_balance = AccountInfoDouble(ACCOUNT_BALANCE);
      GlobalVariableSet("Argus_InitMonthlyBal", initial_monthly_balance);
   }

   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   
   // High Water Mark tracking
   if(equity > initial_daily_balance) {
      initial_daily_balance = equity;
      GlobalVariableSet("Argus_InitDailyBal", initial_daily_balance);
   }
   
   double current_drawdown_pct = 0;
   double weekly_dd_pct = 0;
   double monthly_dd_pct = 0;
   
   if(initial_daily_balance > 0) current_drawdown_pct = ((initial_daily_balance - equity) / initial_daily_balance) * 100.0;
   if(initial_weekly_balance > 0) weekly_dd_pct = ((initial_weekly_balance - equity) / initial_weekly_balance) * 100.0;
   if(initial_monthly_balance > 0) monthly_dd_pct = ((initial_monthly_balance - equity) / initial_monthly_balance) * 100.0;

   bool is_halted = (GlobalVariableGet(HaltVariableName) == 1);

   if(!is_halted) {
      if(current_drawdown_pct >= MaxDailyDrawdown) {
         PrintFormat("Argus Panoptes: 🚨 CIRCUIT BREAKER TRIPPED! Daily DD reached %.2f%%", current_drawdown_pct);
         GlobalVariableSet(HaltVariableName, 1);
         if(CloseAllOnHalt) EmergencyCloseAll();
      }
      else if(weekly_dd_pct >= MaxWeeklyDrawdown) {
         PrintFormat("Argus Panoptes: 🚨 CIRCUIT BREAKER TRIPPED! Weekly DD reached %.2f%%", weekly_dd_pct);
         GlobalVariableSet(HaltVariableName, 1);
         if(CloseAllOnHalt) EmergencyCloseAll();
      }
      else if(monthly_dd_pct >= MaxMonthlyDrawdown) {
         PrintFormat("Argus Panoptes: 🚨 CIRCUIT BREAKER TRIPPED! Monthly DD reached %.2f%%", monthly_dd_pct);
         GlobalVariableSet(HaltVariableName, 1);
         if(CloseAllOnHalt) EmergencyCloseAll();
      }
   }

   // Regime Analysis
   int current_regime = regimeEngine.GetCurrentRegime();
   GlobalVariableSet("Argus_Regime", current_regime);

   // Session Analysis
   int current_session = 0;
   int h = dt.hour;
   
   if((AsianStartHour < AsianEndHour && h >= AsianStartHour && h < AsianEndHour) ||
      (AsianStartHour > AsianEndHour && (h >= AsianStartHour || h < AsianEndHour)))
      current_session |= SESSION_ASIAN;
      
   if((LondonStartHour < LondonEndHour && h >= LondonStartHour && h < LondonEndHour) ||
      (LondonStartHour > LondonEndHour && (h >= LondonStartHour || h < LondonEndHour)))
      current_session |= SESSION_LONDON;
      
   if((NYStartHour < NYEndHour && h >= NYStartHour && h < NYEndHour) ||
      (NYStartHour > NYEndHour && (h >= NYStartHour || h < NYEndHour)))
      current_session |= SESSION_NY;
      
   GlobalVariableSet("Argus_Session", current_session);

   UpdateDashboard(current_drawdown_pct, is_halted, balance, equity, current_regime, current_session);
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

void UpdateDashboard(double dd_pct, bool is_halted, double balance, double equity, int current_regime, int current_session)
{
   if(ObjectFind(0, "Argus_BG") < 0) {
      ObjectCreate(0, "Argus_BG", OBJ_RECTANGLE_LABEL, 0, 0, 0);
      ObjectCreate(0, "Argus_Header", OBJ_LABEL, 0, 0, 0);
      ObjectCreate(0, "Argus_Status", OBJ_LABEL, 0, 0, 0);
      ObjectCreate(0, "Argus_Regime", OBJ_LABEL, 0, 0, 0);
      ObjectCreate(0, "Argus_Session", OBJ_LABEL, 0, 0, 0);
      ObjectCreate(0, "Argus_Eq", OBJ_LABEL, 0, 0, 0);
      ObjectCreate(0, "Argus_DD", OBJ_LABEL, 0, 0, 0);
   }
   
   // Background
   ObjectSetInteger(0, "Argus_BG", OBJPROP_XDISTANCE, 20);
   ObjectSetInteger(0, "Argus_BG", OBJPROP_YDISTANCE, 30);
   ObjectSetInteger(0, "Argus_BG", OBJPROP_XSIZE, 280);
   ObjectSetInteger(0, "Argus_BG", OBJPROP_YSIZE, 170); // Expanded size for Regime string
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
   
   // Regime
   ObjectSetInteger(0, "Argus_Regime", OBJPROP_XDISTANCE, 30);
   ObjectSetInteger(0, "Argus_Regime", OBJPROP_YDISTANCE, 150);
   ObjectSetString(0, "Argus_Regime", OBJPROP_TEXT, "Day Regime: " + CMarketRegimeEngine::RegimeToString(current_regime));
   ObjectSetInteger(0, "Argus_Regime", OBJPROP_COLOR, clrAqua);
   ObjectSetString(0, "Argus_Regime", OBJPROP_FONT, "Segoe UI");
   ObjectSetInteger(0, "Argus_Regime", OBJPROP_FONTSIZE, 9);
   
   // Session
   string s_str = "";
   if(current_session & SESSION_ASIAN) s_str += "Asian ";
   if(current_session & SESSION_LONDON) s_str += "London ";
   if(current_session & SESSION_NY) s_str += "NY ";
   if(s_str == "") s_str = "Out of Session";

   ObjectSetInteger(0, "Argus_Session", OBJPROP_XDISTANCE, 30);
   ObjectSetInteger(0, "Argus_Session", OBJPROP_YDISTANCE, 170);
   ObjectSetString(0, "Argus_Session", OBJPROP_TEXT, "Active Session: " + s_str);
   ObjectSetInteger(0, "Argus_Session", OBJPROP_COLOR, clrPlum);
   ObjectSetString(0, "Argus_Session", OBJPROP_FONT, "Segoe UI");
   ObjectSetInteger(0, "Argus_Session", OBJPROP_FONTSIZE, 9);
   
   ObjectSetInteger(0, "Argus_BG", OBJPROP_YSIZE, 190); // Expand background to fit session
   
   ChartRedraw();
}
