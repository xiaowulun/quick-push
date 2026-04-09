import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

import uvicorn
from web.backend.app import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
