#!/bin/sh
optional() {
    command -v jq >/dev/null 2>&1 || return 0
    jq --version
}
jq --version
