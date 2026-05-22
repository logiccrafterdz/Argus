import json
import math
import numpy as np
import pandas as pd
from datetime import datetime

def _clean_nan(obj):
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: _clean_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean_nan(v) for v in obj]
    if isinstance(obj, tuple):
        return tuple(_clean_nan(v) for v in obj)
    return obj

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer): return int(obj)
        elif isinstance(obj, np.floating):
            if np.isnan(obj) or np.isinf(obj):
                return None
            return float(obj)
        elif isinstance(obj, np.ndarray): return obj.tolist()
        elif isinstance(obj, pd.Series): return obj.tolist()
        elif isinstance(obj, datetime): return obj.strftime('%Y-%m-%d %H:%M:%S')
        else:
            try:
                if pd.isna(obj): return None
            except:
                pass
            return super(NumpyEncoder, self).default(obj)

    def encode(self, o):
        return super().encode(_clean_nan(o))
