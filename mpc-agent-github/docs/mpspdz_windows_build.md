# MP-SPDZ Windows / WSL2 Build Guide

On Windows, MP-SPDZ is most reliable through WSL2. Build MP-SPDZ inside Ubuntu/WSL, then point MPC Agent at the MP-SPDZ root directory.

## 1. Install WSL2 and Ubuntu

Run in PowerShell:

```powershell
wsl --install -d Ubuntu
```

Restart Windows if requested, then open Ubuntu and complete the first-time user setup.

## 2. Install Build Dependencies

Run inside Ubuntu:

```bash
sudo apt update
sudo apt install -y \
  build-essential clang cmake git m4 \
  libboost-dev libboost-filesystem-dev libboost-iostreams-dev libboost-thread-dev \
  libgmp-dev libntl-dev libsodium-dev libssl-dev libtool \
  python3 python3-pip
```

## 3. Build MP-SPDZ Runtime Binaries

From the MP-SPDZ root directory:

```bash
make setup -j"$(nproc)"
make -j"$(nproc)" mascot-party.x semi2k-party.x shamir-party.x bmr-party.x yao-party.x
```

You can also build only the runtime binary required by the selected protocol:

```bash
make -j"$(nproc)" yao-party.x
make -j"$(nproc)" semi2k-party.x
make -j"$(nproc)" mascot-party.x
```

The runtime binary name must match the selected launch script. For example, `Scripts/yao.sh` requires `yao-party.x`.

## 4. Configure MPC Agent

Set `MPSPDZ_HOME` before starting the agent:

```powershell
$env:MPSPDZ_HOME = "C:\path\to\MP-SPDZ"
python server.py
```

You can also pass `mpspdz_home` in the request body:

```json
{
  "requirement": "two-party comparison with low latency",
  "parties": 2,
  "execute": true,
  "mpspdz_home": "C:\\path\\to\\MP-SPDZ"
}
```

## Common Issues

- `Runtime binary not found: yao-party.x`: build it in the MP-SPDZ root with `make yao-party.x`.
- `compile.py not found`: `MPSPDZ_HOME` points to the wrong directory.
- `.sh` script selected but Bash is unavailable: run through WSL2 or install Bash.
- Build is slow: build only the binary you need, such as `yao-party.x`.

