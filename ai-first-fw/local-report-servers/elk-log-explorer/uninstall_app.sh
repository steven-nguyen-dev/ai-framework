#!/usr/bin/env bash
APP_NAME="ELK AI Log Explorer"
for dir in "/Applications" "$HOME/Applications"; do
    if [ -d "${dir}/${APP_NAME}.app" ]; then
        rm -rf "${dir}/${APP_NAME}.app"
        echo "✔ Uninstalled ${APP_NAME}.app from ${dir}"
    fi
done
