#!/bin/sh
# Stage everything the wake word toolchain needs, in one directory.
#
#   sh setup.sh [--prefix DIR] [--seed-from DIR]
#
# On the host (from the VS Code Flatpak sandbox: flatpak-spawn --host sh setup.sh ...). No root.
#   --prefix DIR      where to install; default $MIRA_WAKE_CACHE, else $MIRA_WAKE_TRAIN_ENV, else
#                     ~/.cache/mira-claude/wake. The desktop app looks in ~/.local/share/mira/wake-train
#                     (its venv at .../venv), so for the app: --prefix ~/.local/share/mira/wake-train
#   --seed-from DIR   copy voices, background features, the built corpus, cached Gemini audio and the
#                     front-end cache from an existing install (reflink copies where the filesystem
#                     allows) instead of downloading ~0.9 GB and building the corpus again (~70 min)
#
# Installs:
# - Go (official tarball, checksum-pinned) and a COPY of echod's oww/tflite/vec packages with
#   mira_features_test.go dropped in. The TECHO5 checkout itself is never modified.
# - venv/ with the pinned packages the scripts were tested with (host Python 3.14).
# - voices/ and data/ (fetch_data.py), then the synthetic corpus (synth_corpus.py).
# Gemini voices are optional and need network and the owner's API key: python gemini_tts.py.
set -eu
PREFIX="${MIRA_WAKE_CACHE:-${MIRA_WAKE_TRAIN_ENV:-$HOME/.cache/mira-claude/wake}}"
SEED=""
while [ $# -gt 0 ]; do
	case "$1" in
	--prefix) PREFIX="$2"; shift 2 ;;
	--seed-from) SEED="$2"; shift 2 ;;
	*) echo "usage: sh setup.sh [--prefix DIR] [--seed-from DIR]" >&2; exit 2 ;;
	esac
done
W="$PREFIX"
TECHO5="${TECHO5_SRC:-/var/home/moos/moos-image/test-results/echo-dot/techo5}"
HERE="$(cd "$(dirname "$0")" && pwd)"
GO_VERSION=go1.26.8
GO_SHA256=d0f743b33e8d8945e6b1f432edd15785c70507121d6e2a723b21285eddf8b57b
mkdir -p "$W/downloads"
export MIRA_WAKE_CACHE="$W"

if [ -n "$SEED" ] && [ "$SEED" != "$W" ]; then
	for d in voices data synth gemini featcache; do
		if [ -d "$SEED/$d" ] && [ ! -e "$W/$d" ]; then
			cp -a --reflink=auto "$SEED/$d" "$W/$d"
		fi
	done
	if [ -f "$SEED/downloads/$GO_VERSION.linux-amd64.tar.gz" ] && [ ! -f "$W/downloads/$GO_VERSION.linux-amd64.tar.gz" ]; then
		cp --reflink=auto "$SEED/downloads/$GO_VERSION.linux-amd64.tar.gz" "$W/downloads/"
	fi
fi

if [ ! -x "$W/go/bin/go" ] || [ "$("$W/go/bin/go" version | cut -d' ' -f3)" != "$GO_VERSION" ]; then
	if [ ! -f "$W/downloads/$GO_VERSION.linux-amd64.tar.gz" ]; then
		curl -fsSL -o "$W/downloads/$GO_VERSION.linux-amd64.tar.gz" "https://go.dev/dl/$GO_VERSION.linux-amd64.tar.gz"
	fi
	echo "$GO_SHA256  $W/downloads/$GO_VERSION.linux-amd64.tar.gz" | sha256sum -c -
	rm -rf "$W/go"
	tar -C "$W" -xzf "$W/downloads/$GO_VERSION.linux-amd64.tar.gz"
fi

M="$W/techo5-echod"
rm -rf "$M"
mkdir -p "$M/internal/lib"
cp "$TECHO5/echod/go.mod" "$TECHO5/echod/go.sum" "$M/"
for p in oww tflite vec; do cp -r "$TECHO5/echod/internal/lib/$p" "$M/internal/lib/"; done
cp "$HERE/mira_features_test.go" "$M/internal/lib/oww/"
(
	cd "$M"
	export GOROOT="$W/go" GOPATH="$W/gopath" GOCACHE="$W/gocache" GOFLAGS=-mod=mod GOTOOLCHAIN=local GOPROXY=off GOTELEMETRY=off
	"$W/go/bin/go" test ./internal/lib/oww/ -count=1 -run 'TestMelModelShapes|TestEmbeddingModelShapes|TestProcessSilence'
)

if [ ! -x "$W/venv/bin/python" ]; then
	python3 -m venv "$W/venv"
fi
"$W/venv/bin/pip" install -q --upgrade pip
"$W/venv/bin/pip" install -q numpy==2.5.3 scipy==1.18.1 scikit-learn==1.9.1 piper-tts==1.8.0 \
	flatbuffers==25.12.19 tflite==2.18.0 onnxruntime==1.30.0 faster-whisper==1.2.1

cd "$HERE"
"$W/venv/bin/python" fetch_data.py
# The corpus is built once and cached (without --seed-from: ~50 min of Whisper checks).
"$W/venv/bin/python" synth_corpus.py > "$W/synth_corpus.log" 2>&1 || { tail -20 "$W/synth_corpus.log"; exit 1; }
echo "ready: $W  (python: $W/venv/bin/python)"
