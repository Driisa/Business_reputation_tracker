import sys
from pathlib import Path

# Add the project root directory to Python path
project_root = str(Path(__file__).parent.parent)
sys.path.append(project_root)

from data.pipeline_db_config import init_db

if __name__ == "__main__":
    init_db()
    print("Initialized SQLite object_store.db")