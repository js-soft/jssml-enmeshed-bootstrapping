#!/usr/bin/env bash

set -euo pipefail

log() {
    echo -- "$@"
}

mkdir -p repos
nmshd_app_dir="repos/nmshd_app"
if [[ ! -d "$nmshd_app_dir" ]]; then
    log "cloning enmeshed app to '$nmshd_app_dir'"
    git clone git@github.com:js-soft/nmshd_app.git "$nmshd_app_dir"
else
    log "found enmeshed app in '$nmshd_app_dir'"
fi

cd "$nmshd_app_dir/apps/enmeshed"
cat >config.json <<<'{
    "app_baseUrl": "http://localhost:8090",
    "app_clientId": "test",
    "app_clientSecret": "test"
}'

dart pub global run melos bootstrap
flutter run --dart-define-from-file="$(realpath config.json)"
# flutter run                                         \
#     --dart-define=app_baseUrl=http://localhost:8090 \
#     --dart-define=app_clientId=test                 \
#     --dart-define=app_clientSecret=test

