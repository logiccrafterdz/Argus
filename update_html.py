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

# Metrics
comb_ret = results['portfolio']['total_return']
comb_prof = results['portfolio']['net_profit']
max_dd = results['portfolio']['max_drawdown']
rec_fact = results['portfolio'].get('recovery_factor', abs(comb_ret/max_dd) if max_dd != 0 else 0)
win_rate = results['portfolio']['win_rate']

train_ret = train['portfolio']['total_return']
val_ret = val['portfolio']['total_return']
test_ret = test['portfolio']['total_return']

# Formatting
comb_ret_str = f"+{comb_ret:.2f}%" if comb_ret >= 0 else f"{comb_ret:.2f}%"
comb_prof_str = f"${comb_prof/1000:.1f}K" if comb_prof >= 0 else f"-${abs(comb_prof)/1000:.1f}K"
val_ret_str = f"+{val_ret:.2f}%" if val_ret >= 0 else f"{val_ret:.2f}%"
test_ret_str = f"+{test_ret:.2f}%" if test_ret >= 0 else f"{test_ret:.2f}%"

with open(index_file, 'r', encoding='utf-8') as f:
    html = f.read()

# Replace Banner
html = re.sub(
    r'Combined 8\.3yr return [+-]?\d+\.\d+% \([+-]?\$\d+\.\d+K\)\. All 3 splits cover full market cycle including COVID\. Val [+-]?\d+\.\d+% \| Test [+-]?\d+\.\d+%\.?',
    f'Combined 8.3yr return {comb_ret_str} ({comb_prof_str}). All 3 splits cover full market cycle including COVID. Val {val_ret_str} | Test {test_ret_str}.',
    html
)

# Replace Hero Val
html = re.sub(
    r'<span class="hero-metric-value (?:positive|negative|neutral)">[+-]?\d+\.\d+%</span>(\s*<span class="hero-metric-label">Validation \(2023\))',
    f'<span class="hero-metric-value {"positive" if val_ret >= 0 else "negative"}">{val_ret_str}</span>\\1',
    html
)

# Replace Hero Test
html = re.sub(
    r'<span class="hero-metric-value (?:positive|negative|neutral)">[+-]?\d+\.\d+%</span>(\s*<span class="hero-metric-label">Test \(2024 — May 2026\))',
    f'<span class="hero-metric-value {"positive" if test_ret >= 0 else "negative"}">{test_ret_str}</span>\\1',
    html
)

# Replace Hero Win Rate
html = re.sub(
    r'<span class="hero-metric-value neutral">\d+\.\d+%</span>(\s*<span class="hero-metric-label">Positive Years \(WFA\))',
    f'<span class="hero-metric-value neutral">{int(win_rate)}% Win Rate</span>\\1',
    html
)

# Replace Total Return
html = re.sub(
    r'<span class="hero-metric-value (?:positive|negative)">[+-]?\d+\.\d+%</span>(\s*<span class="hero-metric-label">Total Return</span>)',
    f'<span class="hero-metric-value {"positive" if comb_ret >= 0 else "negative"}">{comb_ret_str}</span>\\1',
    html
)
html = re.sub(
    r'<span class="hero-metric-badge">\+[$\d,\s]+Profit</span>',
    f'<span class="hero-metric-badge">+${int(comb_prof):,} Profit</span>',
    html
)

# Replace Max DD
html = re.sub(
    r'<span class="hero-metric-value negative">[+-]?\d+\.\d+%</span>(\s*<span class="hero-metric-label">Max Drawdown</span>)',
    f'<span class="hero-metric-value negative">{max_dd:.2f}%</span>\\1',
    html
)
html = re.sub(
    r'<span class="hero-metric-badge">\d+ bars duration</span>',
    f'<span class="hero-metric-badge">{results["portfolio"].get("max_dd_duration", 0)} bars duration</span>',
    html
)

# Replace Recovery Factor
html = re.sub(
    r'<span class="hero-metric-value neutral">\d+\.\d+</span>(\s*<span class="hero-metric-label">Recovery Factor</span>)',
    f'<span class="hero-metric-value neutral">{rec_fact:.2f}</span>\\1',
    html
)

with open(index_file, 'w', encoding='utf-8') as f:
    f.write(html)
print("Updated index.html successfully.")
