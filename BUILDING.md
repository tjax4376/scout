# Building Scout

Build and install Scout (Python package + Rust extension) and the Hawkeye standalone binary on Ubuntu Linux and macOS.

## Prerequisites

### Ubuntu 22.04+

```bash
# System packages
sudo apt update
sudo apt install -y build-essential python3-dev python3-pip pkg-config

# Rust toolchain
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source "$HOME/.cargo/env"

# Python 3.11+ (system python3 on Ubuntu 22.04 is 3.10; use deadsnakes PPA or pyenv)
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt install -y python3.12 python3.12-venv python3.12-dev
```

### macOS 13+

```bash
# Xcode command-line tools
xcode-select --install

# Rust toolchain
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source "$HOME/.cargo/env"

# Python 3.11+ (system Python on macOS or via Homebrew)
# Via Homebrew:
brew install python@3.12
```

### Shared requirements

| Requirement | Version |
|-------------|---------|
| Python | 3.11, 3.12, or 3.13 |
| Rust | Latest stable (via rustup) |
| pip | Latest |
| maturin | 1.7+ |

## Install the Python Package (scout + hawkeye CLI)

### Option A: Install into current environment (pip)

```bash
cd scout
./scripts/scout.sh build install
```

This builds a wheel with `maturin build --release` and installs it into the active Python environment (or `.venv` if present). Verifies `scout --help` and `hawkeye --help` succeed.

### Option B: Install via pipx (isolated venv)

```bash
cd scout
./scripts/scout.sh build install --pipx
```

Builds a wheel and installs it via `pipx install --force <wheel>`. The CLIs are available via `scout` and `hawkeye` on PATH (managed by pipx).

### Option C: Install into a custom prefix

```bash
cd scout
./scripts/scout.sh build install --prefix /opt/scout
```

Creates a venv at `/opt/scout`, builds the wheel, installs it, and verifies the CLIs at `/opt/scout/bin/scout` and `/opt/scout/bin/hawkeye`.

## Install the Hawkeye Standalone Binary

### Default install location

```bash
cd scout
./scripts/scout.sh build hawkeye-install
```

- **Linux:** copies to `~/.local/bin/hawkeye`
- **macOS:** copies to `~/bin/hawkeye`

The binary is verified to run `hawkeye --help` after installation.

### Custom install location

```bash
cd scout
./scripts/scout.sh build hawkeye-install --prefix /usr/local/bin
```

Copies the PyInstaller-built binary to `/usr/local/bin/hawkeye`.

## What Gets Installed

| Artifact | Type | Description |
|----------|------|-------------|
| `scout` | Python CLI | Main Scout CLI (code search, graph, vector search) |
| `hawkeye` (CLI) | Python CLI | Hawkeye code review tool (part of the Python package) |
| `hawkeye` (binary) | Standalone executable | PyInstaller one-file binary (no Python required) |
| `scout_core` | Rust extension | Importable as `import scout_core` (Python module) |

## Troubleshooting

### maturin build fails with "Python library not found"

- Ensure `python3-dev` (Ubuntu) or `python3.framework` (macOS) is installed
- Verify `python3 -c "import sysconfig; print(sysconfig.get_config_var('LIBDIR'))"` prints a path
- If using a pyenv or Homebrew Python, ensure its `lib` directory is on `LD_LIBRARY_PATH` (Linux) or `DYLD_LIBRARY_PATH` (macOS)

### maturin build fails with Rust compilation errors

- Ensure `rustup` is installed and `rustc --version` prints a recent version
- Run `rustup update` and try again
- Clean stale artifacts: `rm -rf scout_core/target`

### PyInstaller hawkeye binary crashes on start

- Ensure PyInstaller is up-to-date: `pip install -U pyinstaller`
- macOS: the binary may need codesigning for execution. Run `codesign --force --deep --sign - ~/bin/hawkeye` (or your install path)
- If `scout_core` is excluded from the PyInstaller spec (as designed), ensure the Python package is installed in the environment where hawkeye runs

### hawkeye binary says "rules pack empty"

- The standalone binary bundles rules from `scout/hawkeye/rules/pack_v1/`
- Verify the rules directory exists: `ls scout/hawkeye/rules/pack_v1/*.yaml`
- If missing, run `./scripts/scout.sh build install` first to ensure the package data is included

### pipx install fails with native extension errors

- Build the wheel first, then install: `./scripts/scout.sh build install --pipx`
- The script builds the wheel with `maturin build --release` and passes the wheel file to pipx, which is more reliable than `pipx install .`
