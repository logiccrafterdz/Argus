import os
import glob

base_dir = r"c:\Users\Hp\Desktop\Argus"
ea_files = glob.glob(os.path.join(base_dir, "*", "*.mq5"))

patch_code = """
   // --- V2.0 Regime Filter ---
   StrategyManifest m = GetManifest();
   int current_regime = (int)GlobalVariableGet("Argus_Regime");
   if(current_regime > 0 && !CManifestUtils::IsRegimeMatch(current_regime, m.regime_mask)) return;
"""

for fpath in ea_files:
    folder_name = os.path.basename(os.path.dirname(fpath))
    if folder_name == "Argus_Orchestrator": continue
    
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
        
    if "V2.0 Regime Filter" in content:
        print(f"Already patched {folder_name}")
        continue
        
    target_anchor = "if(CArgusCore::IsHalted()) return;"
    
    if target_anchor in content:
        content = content.replace(target_anchor, target_anchor + "\n" + patch_code)
    else:
        print(f"FAILED TO FIND ANCHOR IN: {folder_name}")
        continue
        
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(content)
        
    print(f"Patched: {folder_name}")
