#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python}"
PYTHON_SCRIPTS_DIR="$(${PYTHON_BIN} - <<'PY'
import sysconfig

print(sysconfig.get_path("scripts"))
PY
)"

if [[ ":${PATH}:" != *":${PYTHON_SCRIPTS_DIR}:"* ]]; then
  export PATH="${PYTHON_SCRIPTS_DIR}:${PATH}"
fi

BASH_PROFILE="${HOME}/.bashrc"
PATH_LINE="export PATH=\"${PYTHON_SCRIPTS_DIR}:\$PATH\""

if ! grep -Fqx "${PATH_LINE}" "${BASH_PROFILE}" 2>/dev/null; then
  {
    printf '\n# ModelGuard Python command-line tools\n'
    printf '%s\n' "${PATH_LINE}"
  } >> "${BASH_PROFILE}"
fi

${PYTHON_BIN} -m pip install --upgrade pip
${PYTHON_BIN} -m pip install -e ".[dev]"
${PYTHON_BIN} -m ruff check .
${PYTHON_BIN} -m pytest

printf '\nModelGuard Codespaces environment is ready.\n'
printf 'Python scripts directory: %s\n' "${PYTHON_SCRIPTS_DIR}"
printf 'Run the CLI with either: modelguard ... or python -m modelguard ...\n'
