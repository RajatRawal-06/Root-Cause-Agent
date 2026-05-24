import os
import sys
from pathlib import Path

# Add the parent directory of backend/ to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.store import IncidentStore
from backend.sample_data import build_seed_incidents

def main():
    db_path = Path(__file__).resolve().parents[1] / "data" / "incidents.db"
    print(f"Target database path: {db_path}")
    if not db_path.parent.exists():
        db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Initialize store and reset with the seed incidents
    store = IncidentStore(db_path=db_path)
    store.reset(build_seed_incidents())
    print("Successfully reset all incidents in the database to 'open'.")

if __name__ == "__main__":
    main()
