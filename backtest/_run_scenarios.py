import yaml
import subprocess
import shutil
import json
import os

CONFIG_PATH = 'config.yaml'
RESULTS_PATH = '../docs/data/results.json'

scenarios = {
    'B_Sentiment': {'sentiment': True, 'rl_agent': False},
    'C_RL_Agent': {'sentiment': False, 'rl_agent': True},
    'D_Both': {'sentiment': True, 'rl_agent': True}
}

def update_config(sentiment, rl):
    with open(CONFIG_PATH, 'r') as f:
        config = yaml.safe_load(f)
    
    config['sentiment']['enabled'] = sentiment
    config['rl_agent']['enabled'] = rl
    
    with open(CONFIG_PATH, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

# Baseline is already in results.json, let's copy it to results_A_Baseline.json
if os.path.exists(RESULTS_PATH):
    shutil.copy(RESULTS_PATH, '../docs/data/results_A_Baseline.json')

results_summary = {}

for name, flags in scenarios.items():
    print(f"Running Scenario {name}: Sentiment={flags['sentiment']}, RL={flags['rl_agent']}")
    update_config(flags['sentiment'], flags['rl_agent'])
    
    # Run backtest
    subprocess.run(["python", "run_backtest.py"], check=True)
    
    # Copy results
    dest = f"../docs/data/results_{name}.json"
    shutil.copy(RESULTS_PATH, dest)
    print(f"Finished {name}\n")

# Restore baseline config
update_config(False, False)
print("Done running scenarios.")
