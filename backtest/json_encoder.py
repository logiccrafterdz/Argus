import json
import numpy as np
import pandas as pd
from datetime import datetime

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer): return int(obj)
        elif isinstance(obj, np.floating): return float(obj)
        elif isinstance(obj, np.ndarray): return obj.tolist()
        elif isinstance(obj, pd.Series): return obj.tolist()
        elif isinstance(obj, datetime): return obj.strftime('%Y-%m-%d %H:%M:%S')
        else:
            try:
                if pd.isna(obj): return None
            except:
                pass
            return super(NumpyEncoder, self).default(obj)
