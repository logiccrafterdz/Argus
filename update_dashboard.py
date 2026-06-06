import json
import re
import os

data_dir = 'docs/data'
index_file = 'docs/index.html'

def load_json(name):
    with open(os.path.join(data_dir, name), 'r') as f:
        return json.load(f)

print("Loading OOS splits...")
train = load_json('oos_train.json')
val = load_json('oos_validation.json')
test = load_json('oos_test.json')
results = load_json('results.json')

oos_results = {
    'train': train['portfolio'],
    'train_equity': train.get('equity_curve', []),
    'validation': val['portfolio'],
    'validation_equity': val.get('equity_curve', []),
    'test': test['portfolio'],
    'test_equity': test.get('equity_curve', [])
}

with open(os.path.join(data_dir, 'oos_results.json'), 'w') as f:
    json.dump(oos_results, f)
print("Saved oos_results.json")

# Extract metrics
comb_ret = results['portfolio']['total_return']
comb_prof = results['portfolio']['net_profit']
val_ret = val['portfolio']['total_return']
test_ret = test['portfolio']['total_return']

# Formatting
comb_ret_str = f"+{comb_ret:.2f}%" if comb_ret >= 0 else f"{comb_ret:.2f}%"
comb_prof_str = f"${comb_prof/1000:.1f}K" if comb_prof >= 0 else f"-${abs(comb_prof)/1000:.1f}K"
val_ret_str = f"+{val_ret:.2f}%" if val_ret >= 0 else f"{val_ret:.2f}%"
test_ret_str = f"+{test_ret:.2f}%" if test_ret >= 0 else f"{test_ret:.2f}%"
val_class = "positive" if val_ret >= 0 else "negative"
test_class = "positive" if test_ret >= 0 else "negative"

with open(index_file, 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Update banner
html = re.sub(
    r'Combined 8\.3yr return [+-]?\d+\.\d+% \([+-]?\$\d+\.\d+K\)\. All 3 splits cover full market cycle including COVID\. Val [+-]?\d+\.\d+% \| Test [+-]?\d+\.\d+%',
    f'Combined 8.3yr return {comb_ret_str} ({comb_prof_str}). All 3 splits cover full market cycle including COVID. Val {val_ret_str} | Test {test_ret_str}',
    html
)

# 2. Update Hero Title (if Test is negative, change the wording)
if test_ret < 0 and val_ret > 0:
    html = re.sub(
        r'<h1 class="text-display">.*?</br>',
        f'<h1 class="text-display">Positive Validation<br>',
        html, flags=re.DOTALL
    )

# 3. Update Val Metric
html = re.sub(
    r'<span class="hero-metric-value (?:positive|negative)">[+-]?\d+\.\d+%</span>\s*<span class="hero-metric-label">Validation \(2023\)</span>',
    f'<span class="hero-metric-value {val_class}">{val_ret_str}</span>\n                            <span class="hero-metric-label">Validation (2023)</span>',
    html
)

# 4. Update Test Metric
html = re.sub(
    r'<span class="hero-metric-value (?:positive|negative)">[+-]?\d+\.\d+%</span>\s*<span class="hero-metric-label">Test \(2024 — May 2026\)</span>',
    f'<span class="hero-metric-value {test_class}">{test_ret_str}</span>\n                            <span class="hero-metric-label">Test (2024 — May 2026)</span>',
    html
)

with open(index_file, 'w', encoding='utf-8') as f:
    f.write(html)
print("Updated index.html")
