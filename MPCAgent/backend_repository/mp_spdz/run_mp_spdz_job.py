"""MP-SPDZ backend runner placeholder.

Replace this file with a bridge that writes/compiles an .mpc program and starts MP-SPDZ parties.
"""

from __future__ import annotations

import argparse
import json


def main() -> None:
    parser = argparse.ArgumentParser(description="MP-SPDZ backend runner placeholder")
    parser.add_argument("--protocol", default="semi2k")
    args = parser.parse_args()
    print(json.dumps({"backend": "mp_spdz", "protocol": args.protocol, "status": "adapter_stub"}))


if __name__ == "__main__":
    main()
