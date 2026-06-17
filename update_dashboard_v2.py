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

p = results['portfolio']
comb_ret = p['total_return']
comb_prof = p['net_profit']
max_dd = p['max_drawdown']
dd_duration = p['max_dd_duration']
rec_fact = p.get('recovery_factor', abs(comb_ret/max_dd) if max_dd != 0 else 0)

val_ret = val['portfolio']['total_return']
test_ret = test['portfolio']['total_return']

comb_ret_str = "+%.2f%%" % comb_ret if comb_ret >= 0 else "%.2f%%" % comb_ret
comb_prof_str = "+$%.1fK" % (comb_prof/1000) if comb_prof >= 0 else "-$%.1fK" % (abs(comb_prof)/1000)
val_ret_str = "+%.2f%%" % val_ret if val_ret >= 0 else "%.2f%%" % val_ret
test_ret_str = "+%.2f%%" % test_ret if test_ret >= 0 else "%.2f%%" % test_ret

with open(index_file, 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Banner
html = re.sub(
    r'Combined 8\.3yr return [^<]+',
    'Combined 8.3yr return %s (%s)' % (comb_ret_str, comb_prof_str),
    html
)
html = re.sub(
    r'Val [^|]+ \| Test [^.]+\.',
    'Val %s | Test %s.' % (val_ret_str, test_ret_str),
    html
)

# 2. Hero metrics — update data-target using context to be unique
# Total Return: find data-target= before Total Return label
html = re.sub(
    r'(data-target=")[\d.]+(" data-prefix="\+" data-suffix="%"[^>]*></span></span>\s*<span class="hero-metric-label">Total Return</span>)',
    lambda m: m.group(1) + ("%.2f" % abs(comb_ret)) + m.group(2),
    html
)
# Max Drawdown: find data-target= before Max Drawdown label
html = re.sub(
    r'(data-target=")[\d.]+(" data-prefix="-" data-suffix="%"[^>]*></span></span>\s*<span class="hero-metric-label">Max Drawdown</span>)',
    lambda m: m.group(1) + ("%.2f" % abs(max_dd)) + m.group(2),
    html
)
# Recovery Factor: find data-target= before Recovery Factor label
html = re.sub(
    r'(data-target=")[\d.]+(" data-suffix=""[^>]*></span></span>\s*<span class="hero-metric-label">Recovery Factor</span>)',
    lambda m: m.group(1) + ("%.2f" % rec_fact) + m.group(2),
    html
)

# 3. Net profit badge
html = re.sub(
    r'(\+\$)[\d,]+( Profit)',
    r'\1%s\2' % ('%d' % int(comb_prof)),
    html
)
# 4. DD duration
html = re.sub(
    r'(\d+) bars duration',
    '%d bars duration' % dd_duration,
    html
)

# 5. Hero title
if test_ret > 0 and val_ret > 0:
    html = re.sub(
        r'<h1 class="text-display">.*?</h1>',
        '<h1 class="text-display">Out-of-Sample Positive in<br>Both Val &amp; Test</h1>',
        html
    )

with open(index_file, 'w', encoding='utf-8') as f:
    f.write(html)
print("Done")
