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

# Extract metrics
comb_ret = results['portfolio']['total_return']
comb_prof = results['portfolio']['net_profit']
max_dd = results['portfolio']['max_drawdown']
rec_fact = results['portfolio'].get('recovery_factor', abs(comb_ret/max_dd) if max_dd != 0 else 0)

val_ret = val['portfolio']['total_return']
test_ret = test['portfolio']['total_return']

# Formatting
comb_ret_str = f"+{comb_ret:.2f}%" if comb_ret >= 0 else f"{comb_ret:.2f}%"
comb_prof_str = f"${comb_prof/1000:.1f}K" if comb_prof >= 0 else f"-${abs(comb_prof)/1000:.1f}K"
val_ret_str = f"+{val_ret:.2f}%" if val_ret >= 0 else f"{val_ret:.2f}%"
test_ret_str = f"+{test_ret:.2f}%" if test_ret >= 0 else f"{test_ret:.2f}%"

with open(index_file, 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Update banner
html = re.sub(
    r'Combined 8\.3yr return [+-]?\d+\.\d+% \([+-]?\$\d+\.\d+K\)\. All 3 splits cover full market cycle including COVID\. Val [+-]?\d+\.\d+% \| Test [+-]?\d+\.\d+%\.',
    f'Combined 8.3yr return {comb_ret_str} ({comb_prof_str}). All 3 splits cover full market cycle including COVID. Val {val_ret_str} | Test {test_ret_str}.',
    html
)

# 2. Update Hero Metrics
# Total Return
html = re.sub(
    r'<span class="hero-metric-value positive">[+-]?\d+\.\d+%</span>\s*<span class="hero-metric-label">Total Return</span>\s*<span class="hero-metric-badge">\+\$\d+(?:,\d+)? Profit</span>',
    f'<span class="hero-metric-value positive">{comb_ret_str}</span>\n                            <span class="hero-metric-label">Total Return</span>\n                            <span class="hero-metric-badge">+${int(comb_prof):,} Profit</span>',
    html
)
# Max Drawdown
html = re.sub(
    r'<span class="hero-metric-value negative">[+-]?\d+\.\d+%</span>\s*<span class="hero-metric-label">Max Drawdown</span>\s*<span class="hero-metric-badge">\d+ bars duration</span>',
    f'<span class="hero-metric-value negative">{max_dd:.2f}%</span>\n                            <span class="hero-metric-label">Max Drawdown</span>\n                            <span class="hero-metric-badge">{results["portfolio"]["max_dd_duration"]} bars duration</span>',
    html
)
# Recovery Factor
html = re.sub(
    r'<span class="hero-metric-value neutral">\d+\.\d+</span>\s*<span class="hero-metric-label">Recovery Factor</span>',
    f'<span class="hero-metric-value neutral">{rec_fact:.2f}</span>\n                            <span class="hero-metric-label">Recovery Factor</span>',
    html
)

# 3. Restore Hero title if test is positive
if test_ret > 0 and val_ret > 0:
    html = re.sub(
        r'<h1 class="text-display">Algorithmic Portfolio<br>Intelligence Engine</h1>',
        f'<h1 class="text-display">Out-of-Sample Positive in<br>Both Val &amp; Test</h1>',
        html
    )

with open(index_file, 'w', encoding='utf-8') as f:
    f.write(html)
print("Done")
