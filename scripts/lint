#!/bin/sh -e

export PACKAGE="requests_async"
export PREFIX=""
if [ -d 'venv' ] ; then
    export PREFIX="venv/bin/"
fi

set -x

${PREFIX}black ${PACKAGE} tests setup.py
${PREFIX}isort --multi-line=3 --trailing-comma --force-grid-wrap=0 --combine-as --line-width 88 --recursive --apply ${PACKAGE} tests setup.py
