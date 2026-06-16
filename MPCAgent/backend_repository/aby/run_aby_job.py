"""ABY backend runner placeholder.

Replace this with a real ABY execution bridge after building ABY locally.
"""

from __future__ import annotations

import argparse
import json


def main() -> None:
    parser = argparse.ArgumentParser(description="ABY backend runner placeholder")
    parser.add_argument("--protocol", default="ABY-Mixed")
    args = parser.parse_args()
    print(json.dumps({"backend": "aby", "protocol": args.protocol, "status": "adapter_stub"}))


if __name__ == "__main__":
    main()
