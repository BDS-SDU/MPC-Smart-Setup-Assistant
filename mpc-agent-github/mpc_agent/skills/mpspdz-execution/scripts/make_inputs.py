from __future__ import annotations

import argparse
from pathlib import Path


def make_inputs(mpspdz_home: str, parties: int, *, overwrite: bool = False) -> dict[str, object]:
    root = Path(mpspdz_home).expanduser()
    player_data = root / "Player-Data"
    player_data.mkdir(parents=True, exist_ok=True)

    created: list[str] = []
    skipped = 0
    for idx in range(max(2, int(parties))):
        path = player_data / f"Input-P{idx}-0"
        if path.exists() and not overwrite:
            skipped += 1
            continue
        path.write_text("0\n", encoding="utf-8")
        created.append(str(path))

    return {
        "player_data_dir": str(player_data),
        "created_input_files": created,
        "skipped_existing_files": skipped,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Create default MP-SPDZ input files.")
    parser.add_argument("--mpspdz-home", required=True)
    parser.add_argument("--parties", required=True, type=int)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    result = make_inputs(args.mpspdz_home, args.parties, overwrite=args.overwrite)
    print(result)


if __name__ == "__main__":
    main()

