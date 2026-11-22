#!/usr/bin/env bash
# getbuild.sh: install an official SolidCraft release into this lane's own builds folder and run it with an isolated
# profile (kit v2.37, docs/reproducing.md "Builds"). Linux, macOS (CLI only) and Git Bash; Windows lanes may use getbuild.ps1.
#
#   kit/getbuild.sh ensure [latest|newest|rc|nightly|<version>]  install if missing; prints SOLIDCRAFT_BUILD= and SOLIDCRAFT_CLI=
#   kit/getbuild.sh run <which> -- <cli args...>                 ensure, then run solidcraft-cli with the isolated profile
#   kit/getbuild.sh env <which>                                  ensure, then print export lines (CLI, app, profile)
#   kit/getbuild.sh list                                         installed versions, newest first
#   kit/getbuild.sh prune [keep]                                 delete all but the newest <keep> (default 4) installs
#
# latest = newest non-prerelease (the current release), newest = newest of all (rc or nightly included),
# rc / nightly = newest of that kind, <version> = exactly that release (0.45.0-rc.3 or v0.45.0-rc.3).
# Folders: $SC_BUILDS_DIR (default <kit>/builds)/upstream-<version>/ and profile-<version>/{settings,recovery,localappdata,xdg}.
# Only tangency-labs/solidcraft releases; the asset's sha256 must match GitHub's digest (or the release's
# SHA256SUMS.txt). Downloads land in a fresh folder and are extracted by kit/safe_extract.py (python -I) into another
# fresh, empty folder. Nothing outside $SC_BUILDS_DIR is written.
set -euo pipefail

REPO="tangency-labs/solidcraft"
KIT="$(cd "$(dirname "$0")/.." && pwd)"
BUILDS="${SC_BUILDS_DIR:-$KIT/builds}"
VER_RE='^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z]+(\.[0-9A-Za-z]+)*)?$'

die() { echo "getbuild: $*" >&2; exit 1; }

pick_python() {
  local p
  for p in "${SC_PYTHON:-}" python3 python; do
    [ -n "$p" ] && "$p" -I -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1 && { echo "$p"; return; }
  done
  die "no Python 3.11+ found (set SC_PYTHON)"
}

sha256_of() {
  if command -v sha256sum >/dev/null; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi
}

resolve_tag() {
  local which="$1" sel
  case "$which" in
    latest) gh api "repos/$REPO/releases/latest" --jq .tag_name; return ;;
    newest) sel='.' ;;
    rc) sel='select(.tag_name | test("-rc\\."))' ;;
    nightly) sel='select(.tag_name | test("-nightly\\."))' ;;
    *)
      local v="${which#v}"
      [[ "$v" =~ $VER_RE ]] || die "not a version or keyword: $which"
      echo "v$v"; return ;;
  esac
  gh api "repos/$REPO/releases?per_page=30" \
    --jq "[.[] | select(.draft | not) | $sel] | sort_by(.published_at) | last | .tag_name // empty"
}

asset_for() {  # $1 = version without v
  case "$(uname -s)" in
    Linux) local m; m="$(uname -m)"; [ "$m" = aarch64 ] || [ "$m" = arm64 ] && m=aarch64 || m=x86_64
           echo "solidcraft-$1-linux-$m.tar.gz" ;;
    Darwin) echo "solidcraft-cli-$1-macos-universal.zip" ;;
    MINGW*|MSYS*|CYGWIN*) echo "solidcraft-$1-windows-x64-portable.zip" ;;
    *) die "no release asset for $(uname -s)" ;;
  esac
}

find_cli() { find "$1" -type f \( -name solidcraft-cli -o -name solidcraft-cli.exe \) 2>/dev/null | head -n 1; }
find_app() { find "$1" -type f \( -name solidcraft -o -name solidcraft.exe -o -name 'solidcraft*.AppImage' \) 2>/dev/null | head -n 1; }

ensure() {
  local which="${1:-latest}" tag ver dest asset info digest expected got how dl x py cli
  command -v gh >/dev/null || die "gh (GitHub CLI) is required"
  tag="$(resolve_tag "$which")" || exit 1
  [ -n "$tag" ] || die "no release matches '$which' in $REPO"
  ver="${tag#v}"
  [[ "$ver" =~ $VER_RE ]] || die "unexpected tag from $REPO: $tag"
  dest="$BUILDS/upstream-$ver"
  if [ -f "$dest/.getbuild.json" ] && cli="$(find_cli "$dest")" && [ -n "$cli" ]; then
    echo "getbuild: $ver already installed in $dest" >&2
    echo "SOLIDCRAFT_BUILD=$dest"; echo "SOLIDCRAFT_CLI=$cli"; return
  fi
  [ -e "$dest" ] && die "$dest exists but was not installed by getbuild: move it aside or delete it yourself"

  asset="$(asset_for "$ver")"
  # The release must exist in tangency-labs/solidcraft, be published (not a draft) and carry this exact asset.
  info="$(gh api "repos/$REPO/releases/tags/$tag" \
    --jq "if .draft then \"DRAFT\" else ([.assets[] | select(.name == \"$asset\") | (.digest // \"none\")] | first // \"MISSING\") end")" \
    || die "release $tag not found in $REPO"
  case "$info" in
    DRAFT) die "$tag is a draft release" ;;
    MISSING) die "release $tag in $REPO has no asset $asset" ;;
  esac

  mkdir -p "$BUILDS"
  dl="$(mktemp -d "$BUILDS/.dl-$ver-XXXXXX")"
  x="$(mktemp -d "$BUILDS/.x-$ver-XXXXXX")"
  trap 'rm -rf "$dl" "$x"' EXIT
  echo "getbuild: downloading $asset from $REPO $tag" >&2
  gh release download "$tag" -R "$REPO" -p "$asset" -D "$dl" || die "download failed"
  got="$(sha256_of "$dl/$asset")"
  if [ "${info#sha256:}" != "$info" ]; then
    expected="${info#sha256:}"; how="GitHub asset digest"
  else
    if gh release download "$tag" -R "$REPO" -p SHA256SUMS.txt -D "$dl" 2>/dev/null; then
      expected="$(awk -v a="$asset" '{n=$2; sub(/^\*/, "", n); if (n == a) print $1}' "$dl/SHA256SUMS.txt" | head -n 1)"
      how="the release's SHA256SUMS.txt"
    fi
  fi
  if [ -n "${expected:-}" ]; then
    [ "$got" = "$expected" ] || die "sha256 mismatch for $asset: got $got, $how says $expected. Not installed."
    echo "getbuild: sha256 matches $how" >&2
  else
    how="none listed"
    echo "getbuild: WARNING: GitHub lists no digest for $asset; installed unverified (sha256 $got)" >&2
  fi

  py="$(pick_python)"
  "$py" -I "$KIT/kit/safe_extract.py" "$dl/$asset" "$x" >&2 || die "extract refused or failed"
  cli="$(find_cli "$x")"
  [ -n "$cli" ] || die "no solidcraft-cli in $asset"
  printf '{"tag": "%s", "asset": "%s", "sha256": "%s", "verified_by": "%s", "installed_at": "%s"}\n' \
    "$tag" "$asset" "$got" "$how" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$x/.getbuild.json"
  if ! mv "$x" "$dest" 2>/dev/null; then
    [ -f "$dest/.getbuild.json" ] || die "could not move the build into $dest"
    echo "getbuild: another run installed $ver first; using it" >&2
  fi
  rm -rf "$dl"
  trap - EXIT
  cli="$(find_cli "$dest")"
  chmod +x "$cli" 2>/dev/null || true
  echo "getbuild: installed $ver in $dest" >&2
  echo "SOLIDCRAFT_BUILD=$dest"; echo "SOLIDCRAFT_CLI=$cli"
}

profile_env() {  # $1 = install dir; prints KEY=VALUE lines for the isolated profile
  local ver="${1##*/upstream-}" p
  p="$BUILDS/profile-$ver"
  mkdir -p "$p/settings" "$p/recovery" "$p/localappdata" "$p/xdg/config" "$p/xdg/data" "$p/xdg/cache"
  echo "SOLIDCRAFT_SETTINGS_DIR=$p/settings"
  echo "SOLIDCRAFT_RECOVERY_DIR=$p/recovery"
  echo "LOCALAPPDATA=$p/localappdata"
  echo "XDG_CONFIG_HOME=$p/xdg/config"
  echo "XDG_DATA_HOME=$p/xdg/data"
  echo "XDG_CACHE_HOME=$p/xdg/cache"
}

cmd="${1:-}"; shift || true
case "$cmd" in
  ensure) ensure "${1:-latest}" ;;
  env)
    out="$(ensure "${1:-latest}")"; dir="$(sed -n 's/^SOLIDCRAFT_BUILD=//p' <<<"$out")"; cli="$(sed -n 's/^SOLIDCRAFT_CLI=//p' <<<"$out")"
    echo "export SOLIDCRAFT_CLI='$cli'"
    app="$(find_app "$dir")"; [ -n "$app" ] && echo "export SOLIDCRAFT_APP='$app'"
    profile_env "$dir" | sed "s/^\([A-Z_]*\)=\(.*\)$/export \1='\2'/"
    ;;
  run)
    which="${1:-latest}"; shift || true
    [ "${1:-}" = "--" ] && shift
    out="$(ensure "$which")"; dir="$(sed -n 's/^SOLIDCRAFT_BUILD=//p' <<<"$out")"; cli="$(sed -n 's/^SOLIDCRAFT_CLI=//p' <<<"$out")"
    envs=(); while IFS= read -r l; do envs+=("$l"); done < <(profile_env "$dir")  # no mapfile: macOS bash 3.2
    exec env "${envs[@]}" "$cli" "$@"
    ;;
  list)
    for d in "$BUILDS"/upstream-*/; do
      [ -f "$d.getbuild.json" ] && echo "$(basename "$d" | sed 's/^upstream-//')  $(cat "$d.getbuild.json")"
    done | sort -rV || true
    ;;
  prune)
    keep="${1:-4}"; [[ "$keep" =~ ^[0-9]+$ ]] || die "keep must be a number"
    ls -d "$BUILDS"/upstream-*/ 2>/dev/null | sort -rV | tail -n +"$((keep + 1))" | while read -r d; do
      if [ -f "$d.getbuild.json" ]; then
        v="$(basename "$d")"; v="${v#upstream-}"
        echo "getbuild: removing $v" >&2; rm -rf "$d" "$BUILDS/profile-$v"
      fi
    done
    ;;
  *) sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//'; [ -z "$cmd" ] || exit 2 ;;
esac
