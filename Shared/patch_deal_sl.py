import os
import glob
import re

base_dir = r"c:\Users\Hp\Desktop\Argus"
# Ensure we map only over Strategy subfolders, excluding Orchestrator
files = glob.glob(os.path.join(base_dir, "*", "*.mq5"))

broken_snippet = """void OnTradeTransaction(const MqlTradeTransaction& trans, const MqlTradeRequest& request, const MqlTradeResult& result)
{
   if(trans.type == TRADE_TRANSACTION_DEAL_ADD) {
      if(HistoryDealSelect(trans.deal)) {
         if(HistoryDealGetInteger(DEAL_MAGIC) == MagicNumber && HistoryDealGetInteger(DEAL_ENTRY) == DEAL_ENTRY_IN) {
            CArgusCore::LogTradeData(_Symbol, MagicNumber, (ENUM_ORDER_TYPE)HistoryDealGetInteger(DEAL_TYPE), HistoryDealGetDouble(DEAL_VOLUME), HistoryDealGetDouble(DEAL_PRICE), HistoryDealGetDouble(DEAL_SL), HistoryDealGetDouble(DEAL_TP), HistoryDealGetString(DEAL_COMMENT), trans.order);
         }
      }
   }
}"""

fixed_snippet = """void OnTradeTransaction(const MqlTradeTransaction& trans, const MqlTradeRequest& request, const MqlTradeResult& result)
{
   if(trans.type == TRADE_TRANSACTION_DEAL_ADD) {
      if(HistoryDealSelect(trans.deal)) {
         if(HistoryDealGetInteger(DEAL_MAGIC) == MagicNumber && HistoryDealGetInteger(DEAL_ENTRY) == DEAL_ENTRY_IN) {
            double sl = 0, tp = 0;
            if(PositionSelectByTicket(trans.position)) {
               sl = PositionGetDouble(POSITION_SL);
               tp = PositionGetDouble(POSITION_TP);
            }
            CArgusCore::LogTradeData(_Symbol, MagicNumber, (ENUM_ORDER_TYPE)HistoryDealGetInteger(DEAL_TYPE), HistoryDealGetDouble(DEAL_VOLUME), HistoryDealGetDouble(DEAL_PRICE), sl, tp, HistoryDealGetString(DEAL_COMMENT), trans.order);
         }
      }
   }
}"""


for fpath in files:
    if "ArgusPanoptes" in fpath:
        continue # Skip the orchestrator itself
        
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
        
    original = content
    # Handle newline discrepancies (\r\n vs \n)
    normalized_content = content.replace("\r\n", "\n")
    normalized_broken = broken_snippet.replace("\r\n", "\n")
    
    if normalized_broken in normalized_content:
        new_content = normalized_content.replace(normalized_broken, fixed_snippet.replace("\r\n", "\n"))
        
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(new_content)
        print("Patched:", os.path.basename(fpath))
    else:
        print("Snippet not found in:", os.path.basename(fpath))
