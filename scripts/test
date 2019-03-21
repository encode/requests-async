#!/bin/sh -e

export PACKAGE="requests_async"
export PREFIX=""
if [ -d 'venv' ] ; then
    export PREFIX="venv/bin/"
fi

set -x

PYTHONPATH=. ${PREFIX}pytest --ignore venv --cov tests --cov ${PACKAGE} --cov-report= ${@}
${PREFIX}coverage report
