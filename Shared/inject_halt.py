import os
import glob
import re

base_dir = r"c:\Users\Hp\Desktop\Argus"
# Ensure we map only over Strategy subfolders, excluding Orchestrator
files = glob.glob(os.path.join(base_dir, "*", "*.mq5"))

for fpath in files:
    if "ArgusPanoptes" in fpath:
        continue # Skip the orchestrator itself
        
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
        
    original = content
    # Handle single or multi-line OnTick
    content = re.sub(r'void\s+OnTick\(\)\s*\{', 'void OnTick()\n{\n   if(CArgusCore::IsHalted()) return;\n', content)
    
    if content != original:
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)
        print("Updated:", os.path.basename(fpath))
