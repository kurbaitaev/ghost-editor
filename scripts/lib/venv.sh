# Shared by the setup_*.sh / denoise.sh scripts: a Python 3.11 and the venv layout on this platform.
#   source "$HERE/lib/venv.sh"      (HERE = the scripts dir)
#   PY=$(find_py311)                 python3.11 on PATH, the Windows `py -3.11` launcher, or Homebrew's
#   VB=$(venv_bin "$V")              "$V/bin" on macOS / Linux, "$V/Scripts" on Windows (after the venv exists)
#   venv_ok "$V"                     true when the venv's python exists
find_py311() {
  if command -v python3.11 >/dev/null 2>&1; then command -v python3.11; return; fi
  if command -v py >/dev/null 2>&1; then
    local p; p=$(py -3.11 -c "import sys; print(sys.executable)" 2>/dev/null | tr -d '\r')
    [ -n "$p" ] && { echo "$p"; return; }
  fi
  echo /opt/homebrew/bin/python3.11
}
venv_bin() { if [ -d "$1/Scripts" ]; then echo "$1/Scripts"; else echo "$1/bin"; fi; }
venv_ok() { [ -x "$1/bin/python" ] || [ -x "$1/Scripts/python.exe" ]; }
