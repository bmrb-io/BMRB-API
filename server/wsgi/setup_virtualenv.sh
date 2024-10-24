#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
if [[ ! -d "${SCRIPT_DIR}/venv" ]]; then
  python3 -m venv ${SCRIPT_DIR}/venv
  source "${SCRIPT_DIR}"/venv/bin/activate
  pip3 install --upgrade pip
  pip3 install -r ${SCRIPT_DIR}/requirements.txt
else
  source "${SCRIPT_DIR}"/venv/bin/activate
  pip3 install --upgrade pip --quiet
  pip3 install -r ${SCRIPT_DIR}/requirements.txt --quiet
fi
