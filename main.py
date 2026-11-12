from pathlib import Path
import sys
from traffic_model.cli import main

DEFAULT_CONFIG = Path(__file__).parent / "configs" / "CedricSt.yaml"
if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:], DEFAULT_CONFIG))
