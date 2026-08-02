#!/usr/bin/env bash
# Bootstrap ModelGuard's development, DataHub SDK and MCP client dependencies.
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

${PYTHON_BIN} -m pip install --upgrade pip wheel setuptools
${PYTHON_BIN} -m pip install -e ".[dev,phase2]"
${PYTHON_BIN} -m ruff check .
${PYTHON_BIN} -m pytest

printf '\nModelGuard Codespaces environment is ready.\n'
printf 'Python version: %s\n' "$(${PYTHON_BIN} --version 2>&1)"
printf 'Python scripts directory: %s\n' "${PYTHON_SCRIPTS_DIR}"
printf 'Run the CLI with either: modelguard ... or python -m modelguard ...\n'
printf 'Start local DataHub with: datahub docker quickstart\n'
printf 'Run complete live evidence with: python scripts/run_live_datahub_evidence.py --install-mcp-server --promote\n'
