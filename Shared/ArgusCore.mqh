//+------------------------------------------------------------------+
//|                                                    ArgusCore.mqh |
//|                                  Copyright 2026, LogicCrafterDz |
//|                                             https://example.com |
//|                                                                  |
//|  WARNING: FOR EDUCATIONAL PURPOSES ONLY. NO WARRANTY PROVIDED.   |
//|  USE AT YOUR OWN RISK.                                           |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, LogicCrafterDz"
#property link      "https://example.com"
#property strict

#ifndef ARGUS_CORE_MQH
#define ARGUS_CORE_MQH

//+------------------------------------------------------------------+
//| Class for Core Operations (Risk, Validation, Helpers)            |
//+------------------------------------------------------------------+
class CArgusCore
{
public:
   //+------------------------------------------------------------------+
   //| Standard Volume Calculation                                      |
   //+------------------------------------------------------------------+
   static double CalculateLotSize(string symbol, double risk_percent, double risk_dist_points, int vol_precision)
   {
      double balance = AccountInfoDouble(ACCOUNT_BALANCE);
      double risk_amount = balance * (risk_percent / 100.0);
      double tick_value = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);
      double tick_size = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
      
      if(risk_dist_points <= 0 || tick_value <= 0) return 0;
      
      double lot = risk_amount / (risk_dist_points / tick_size * tick_value);
      double min_vol = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
      double max_vol = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
      double step_vol = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
      
      lot = MathFloor(lot / step_vol) * step_vol;
      lot = MathMax(min_vol, MathMin(max_vol, lot));
      return NormalizeDouble(lot, vol_precision);
   }

   //+------------------------------------------------------------------+
   //| Logic for Validating Stops against BOTH Stops and Freeze levels  |
   //+------------------------------------------------------------------+
   static double ValidateStopsLevel(string symbol, double price, double target)
   {
      int stops_level = (int)SymbolInfoInteger(symbol, SYMBOL_TRADE_STOPS_LEVEL);
      int freeze_level = (int)SymbolInfoInteger(symbol, SYMBOL_TRADE_FREEZE_LEVEL);
      int max_level = MathMax(stops_level, freeze_level);
      
      double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
      double min_dist = max_level * point;
      double actual_dist = MathAbs(price - target);
      
      if(actual_dist < min_dist)
      {
         double new_target = (target > price) ? price + min_dist + point : price - min_dist - point;
         PrintFormat("Warning: SL/TP too close to price (MaxLevel: %d). Adjusted to respect Broker limits. RR Impact possible.", max_level);
         return NormalizePrice(symbol, new_target, SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE));
      }
      return target;
   }

   //+------------------------------------------------------------------+
   //| Check if an EA has open positions                                |
   //+------------------------------------------------------------------+
   static bool HasOpenPosition(string symbol, int magic_number)
   {
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         ulong ticket = PositionGetTicket(i);
         if(PositionSelectByTicket(ticket) && PositionGetInteger(POSITION_MAGIC) == magic_number && PositionGetString(POSITION_SYMBOL) == symbol) return true;
      }
      return false;
   }

   //+------------------------------------------------------------------+
   //| Helpers                                                          |
   //+------------------------------------------------------------------+
   static double NormalizePrice(string symbol, double price, double tick_size) 
   { 
      return MathRound(price / tick_size) * tick_size; 
   }

   static double PipsToPriceDelta(string symbol, double pips)
   {
      int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
      double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
      return (digits == 3 || digits == 5) ? pips * 10 * point : pips * point;
   }
   
   static int GetVolumePrecision(string symbol)
   {
       double step_vol = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
       return (int)MathMax(0, MathCeil(MathLog10(1.0 / step_vol)));
   }
   
   //+------------------------------------------------------------------+
   //| Global Orchestrator Checks                                       |
   //+------------------------------------------------------------------+
   static bool IsHalted()
   {
       if(GlobalVariableCheck("Argus_Halt") && GlobalVariableGet("Argus_Halt") == 1) return true;
       return false;
   }
   //+------------------------------------------------------------------+
   //| Trade Journaling & Analytics                                     |
   //+------------------------------------------------------------------+
   static void LogTradeData(string symbol, int magic_number, ENUM_ORDER_TYPE type, double lot, double price, double sl, double tp, string comment, ulong ticket)
   {
      string date_str = TimeToString(TimeCurrent(), TIME_DATE);
      StringReplace(date_str, ".", "-"); // Format: YYYY-MM-DD
      string filename = "ArgusJournal_" + date_str + ".csv";
      
      int handle = FileOpen(filename, FILE_CSV|FILE_READ|FILE_WRITE|FILE_ANSI, ",");
      if(handle != INVALID_HANDLE)
      {
         // If file is empty, write header
         if(FileSize(handle) == 0) {
            FileWrite(handle, "Time", "Ticket", "Symbol", "Magic", "Type", "Lot", "EntryPrice", "SL", "TP", "Comment");
         }
         FileSeek(handle, 0, SEEK_END);
         string t_type = (type == ORDER_TYPE_BUY) ? "BUY" : "SELL";
         string time_str = TimeToString(TimeCurrent(), TIME_DATE|TIME_MINUTES|TIME_SECONDS);
         FileWrite(handle, time_str, ticket, symbol, magic_number, t_type, lot, price, sl, tp, comment);
         FileClose(handle);
         
         // Telegram Dispatch
         int tg_handle = FileOpen("Argus_TelegramConfig.txt", FILE_READ|FILE_TXT|FILE_ANSI);
         if(tg_handle != INVALID_HANDLE) {
            string token = FileReadString(tg_handle);
            string chat  = FileReadString(tg_handle);
            FileClose(tg_handle);
            
            if(token != "" && chat != "") {
               string msg = StringFormat("🔔 <b>Argus Trade Opened</b>\n\n%s <b>%s</b>\nPrice: %.5f\nSL: %.5f\nTP: %.5f\nLot: %.2f\nStrategy: %s (%d)", 
                                          symbol, t_type, price, sl, tp, lot, comment, magic_number);
               SendTelegramAlert(token, chat, msg);
            }
         }
      }
      else
      {
         PrintFormat("ArgusCore: Failed to write to journal %s. Error: %d", filename, GetLastError());
      }
   }

   //+------------------------------------------------------------------+
   //| Telegram Integration                                             |
   //+------------------------------------------------------------------+
   static void SendTelegramAlert(string bot_token, string chat_id, string message)
   {
      string url = "https://api.telegram.org/bot" + bot_token + "/sendMessage";
      string body = "chat_id=" + chat_id + "&text=" + message + "&parse_mode=HTML";
      
      char post_data[];
      StringToCharArray(body, post_data, 0, WHOLE_ARRAY, CP_UTF8);
      char result[];
      string headers = "Content-Type: application/x-www-form-urlencoded\r\n";
      
      ResetLastError();
      // Use POST with body
      int res = WebRequest("POST", url, headers, 5000, post_data, result, headers);
      if(res != 200 && res != -1) PrintFormat("Telegram Alert Failed. Code: %d", res);
   }
};

#endif
