"""SPU backend runner placeholder.

Replace this file with a real SecretFlow/SPU execution bridge after installing SPU.
"""

from __future__ import annotations

import argparse
import json


def main() -> None:
    parser = argparse.ArgumentParser(description="SPU backend runner placeholder")
    parser.add_argument("--protocol", default="SEMI2K")
    args = parser.parse_args()
    print(json.dumps({"backend": "spu", "protocol": args.protocol, "status": "adapter_stub"}))


if __name__ == "__main__":
    main()
