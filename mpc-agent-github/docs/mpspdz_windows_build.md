# MP-SPDZ Windows / WSL2 构建指南

在 Windows 上运行 MP-SPDZ 时，推荐通过 WSL2 安装 Linux 发行版并在其中构建 MP-SPDZ。这样可以减少编译依赖、权限和脚本兼容性问题。

## 1. 安装 WSL2 与 Ubuntu

在 PowerShell 中执行：

```powershell
wsl --install -d Ubuntu
```

安装完成后重启系统，并打开 Ubuntu 完成首次用户初始化。

## 2. 安装构建依赖

在 Ubuntu 中执行：

```bash
sudo apt update
sudo apt install -y \
  build-essential clang cmake git m4 \
  libboost-dev libboost-filesystem-dev libboost-iostreams-dev libboost-thread-dev \
  libgmp-dev libntl-dev libsodium-dev libssl-dev libtool \
  python3 python3-pip
```

## 3. 获取并构建 MP-SPDZ

```bash
git clone https://github.com/data61/MP-SPDZ.git
cd MP-SPDZ
make setup -j"$(nproc)"
make -j"$(nproc)" mascot-party.x semi2k-party.x shamir-party.x bmr-party.x
```

如果只想验证本项目默认的恶意安全算术协议路径，可以先构建：

```bash
make -j"$(nproc)" mascot-party.x
```

## 4. 配置 MPC Agent

在启动 MPC Agent 前设置 `MPSPDZ_HOME`。如果 MP-SPDZ 位于 Windows 用户目录，可在 PowerShell 中设置：

```powershell
$env:MPSPDZ_HOME = "C:\path\to\MP-SPDZ"
python server.py
```

也可以在请求体中传入：

```json
{
  "requirement": "3-party malicious secure aggregation",
  "parties": 3,
  "execute": true,
  "mpspdz_home": "C:\\path\\to\\MP-SPDZ"
}
```

## 5. 常见问题

- 找不到 `mascot-party.x`：确认已经在 MP-SPDZ 目录执行对应 `make` 命令。
- Windows 路径无法在 WSL 中访问：确认路径可通过 `/mnt/c/...` 访问。
- 权限不足：优先在 WSL 文件系统中构建 MP-SPDZ，或检查 Windows 目录权限。
- 编译很慢：先只构建当前需要的二进制，例如 `mascot-party.x`。

