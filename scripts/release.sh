#!/usr/bin/env bash
# Tag origin/main at the version in esphome/version.yaml and push the tag,
# which runs .github/workflows/release.yml. Run after the PR that bumped
# the version has merged. Never tags anything but origin/main.
set -euo pipefail
cd "$(dirname "$0")/.."
git fetch -q origin main
version=$(git show origin/main:esphome/version.yaml | sed -n 's/^  version: "\(.*\)"/\1/p')
[[ $version =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "bad version '$version' in esphome/version.yaml on origin/main"; exit 1; }
if git ls-remote --exit-code --tags origin "v$version" >/dev/null 2>&1; then
  echo "v$version already exists on origin; bump esphome/version.yaml in a PR first"; exit 1
fi
git tag -a "v$version" -m "Desiccant Dryer $version" origin/main
git push origin "v$version"
echo "pushed v$version; watch with: gh run list --workflow release.yml"
