#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
if [[ ! -d "${SCRIPT_DIR}/virtual_env" ]]; then
  python3 -m venv ${SCRIPT_DIR}/virtual_env
  source "${SCRIPT_DIR}"/virtual_env/bin/activate
  pip3 install -r ${SCRIPT_DIR}/requirements.txt
else
  source "${SCRIPT_DIR}"/virtual_env/bin/activate
  pip3 install -r ${SCRIPT_DIR}/requirements.txt
fi
