import os
import glob
import re

base_dir = r"c:\Users\Hp\Desktop\Argus"
files = glob.glob(os.path.join(base_dir, "*", "*.mq5"))

def remove_function(code, func_name):
    # Find start of function
    match = re.search(r'(?:double|bool|void|int)\s+' + func_name + r'\s*\(', code)
    if not match:
        return code
    
    start_idx = match.start()
    
    # Backtrack to remove preceding comments/newlines if possible
    # We'll just cut from start_idx
    
    # Find the opening brace
    brace_start = code.find('{', start_idx)
    if brace_start == -1:
        return code # Something is wrong, leave it
        
    # Balanced brace matching
    brace_count = 0
    end_idx = -1
    in_string = False
    escape = False
    
    for i in range(brace_start, len(code)):
        char = code[i]
        
        if escape:
            escape = False
            continue
            
        if char == '\\':
            escape = True
            continue
            
        if char == '"':
            in_string = not in_string
            continue
            
        if not in_string:
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i + 1
                    break
                    
    if end_idx != -1:
        # Also remove potential trailing newline or comments on the same line...
        # actually let's just slice it out safely
        
        # Remove any preceeding documentation block
        doc_block = code.rfind("//+", 0, start_idx)
        if doc_block != -1 and "\n" not in code[doc_block+3:start_idx].strip():
            # Looks like a comment block attached to it
            start_idx = doc_block
            
        return code[:start_idx] + code[end_idx:]
        
    return code

for fpath in files:
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()

    original_content = content
    
    # 1. Update Includes
    if "#include <Trade\\Trade.mqh>" in content and "#include \"..\\Shared\\ArgusCore.mqh\"" not in content:
        content = content.replace("#include <Trade\\Trade.mqh>", 
                                  "#include <Trade\\Trade.mqh>\n#include \"..\\Shared\\ArgusCore.mqh\"\n#include \"..\\Shared\\ArgusStructure.mqh\"")
    
    # EXACTLY remove StructureUtils.mqh (Keep SMCUtils.mqh etc!)
    content = re.sub(r'#include\s+"StructureUtils\.mqh"\s*\n', '', content)
    
    # 2. Safely Remove Local Helpers
    funcs_to_remove = ["CalculateLotSize", "ValidateStopsLevel", "HasOpenPosition", "NormalizePrice", "PipsToPriceDelta"]
    for fn in funcs_to_remove:
        # We might have multiple definitions? (Should only be 1)
        for _ in range(3):
            content = remove_function(content, fn)

    # 3. Replace Function Calls via Regex
    content = re.sub(r'HasOpenPosition\(\)', r'CArgusCore::HasOpenPosition(_Symbol, MagicNumber)', content)
    content = re.sub(r'NormalizePrice\(([^,]+),\s*([^)]+)\)', r'CArgusCore::NormalizePrice(_Symbol, \1, \2)', content)
    content = re.sub(r'ValidateStopsLevel\(([^,]+),\s*([^)]+)\)', r'CArgusCore::ValidateStopsLevel(_Symbol, \1, \2)', content)
    content = re.sub(r'CalculateLotSize\(([^)]+)\)', r'CArgusCore::CalculateLotSize(_Symbol, RiskPercent, \1, vol_precision)', content)
    content = re.sub(r'PipsToPriceDelta\(([^)]+)\)', r'CArgusCore::PipsToPriceDelta(_Symbol, \1)', content)
    
    # Volume precision fixes
    content = re.sub(r'vol_precision\s*=\s*\(int\)MathMax\(0,\s*MathCeil\(MathLog10\(1\.0\s*/\s*step_vol\)\)\);', r'vol_precision = CArgusCore::GetVolumePrecision(_Symbol);', content)
    content = re.sub(r'double step_vol = SymbolInfoDouble\(_Symbol, SYMBOL_VOLUME_STEP\);\s*\n\s*vol_precision = CArgusCore::GetVolumePrecision\(_Symbol\);', r'vol_precision = CArgusCore::GetVolumePrecision(_Symbol);', content)

    # 4. Structure Utils Call Replacements
    content = re.sub(r'CStructureUtils::IsBullishStructure\(([^)]+)\)', r'CArgusStructure::IsBullishStructure(_Symbol, _Period, \1)', content)
    content = re.sub(r'CStructureUtils::IsBearishStructure\(([^)]+)\)', r'CArgusStructure::IsBearishStructure(_Symbol, _Period, \1)', content)
    content = re.sub(r'CStructureUtils::IsSwingHigh\(([^,]+),\s*([^)]+)\)', r'CArgusStructure::IsSwingHigh(_Symbol, _Period, \1, \2)', content)
    content = re.sub(r'CStructureUtils::IsSwingLow\(([^,]+),\s*([^)]+)\)', r'CArgusStructure::IsSwingLow(_Symbol, _Period, \1, \2)', content)
    content = re.sub(r'CStructureUtils::GetLiquidityHigh\(([^,]+),\s*([^,]+),\s*([^)]+)\)', r'CArgusStructure::GetLiquidityHigh(_Symbol, _Period, \1, \2, \3)', content)
    content = re.sub(r'CStructureUtils::GetLiquidityLow\(([^,]+),\s*([^,]+),\s*([^)]+)\)', r'CArgusStructure::GetLiquidityLow(_Symbol, _Period, \1, \2, \3)', content)
    content = re.sub(r'CStructureUtils::IsBearishMSB\(([^)]+)\)', r'CArgusStructure::IsBearishMSB(_Symbol, _Period, \1)', content)
    content = re.sub(r'CStructureUtils::IsBullishMSB\(([^)]+)\)', r'CArgusStructure::IsBullishMSB(_Symbol, _Period, \1)', content)
    content = re.sub(r'CStructureUtils::GetHTFBias\(([^,]+),\s*([^,]+),\s*([^)]+)\)', r'CArgusStructure::GetHTFBias(_Symbol, \1, \2, \3)', content)
    content = re.sub(r'CStructureUtils::FindLatestSwingLeg\(([^)]+)\)', r'CArgusStructure::FindLatestSwingLeg(_Symbol, _Period, \1)', content)
    content = re.sub(r'CStructureUtils::GetSessionRange\(([^)]+)\)', r'CArgusStructure::GetSessionRange(_Symbol, _Period, \1)', content)
    content = re.sub(r'CStructureUtils::IsStructureBreak\(([^)]+)\)', r'CArgusStructure::IsStructureBreak(_Symbol, _Period, \1)', content)
    content = re.sub(r'CStructureUtils::PipsToPoints\(\)', r'CArgusStructure::PipsToPoints(_Symbol)', content)

    if content != original_content:
        # Clean up empty lines created by deletion
        content = re.sub(r'\n{3,}', '\n\n', content)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Safe Refactored: {os.path.basename(fpath)}")

print("Done.")
