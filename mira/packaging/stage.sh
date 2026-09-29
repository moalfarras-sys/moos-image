#!/bin/sh
# Copy Mira's runtime tree from SRC (this directory's parent) into OUT — the image's /usr/lib/mira/app.
# Tests, developer tools, the Echo's own client, the wake-word training code and notes stay out;
# the shipped improved wake model goes into wake-models/, where the app serves it to a paired Echo.
set -eu
src=${1:?usage: stage.sh SRC OUT}
out=${2:?usage: stage.sh SRC OUT}
mkdir -p "$out/wake-models"
for file in "$src"/*.py; do
    case "$(basename "$file")" in
        test_*) ;;
        *) cp "$file" "$out/" ;;
    esac
done
cp -r "$src/qml" "$src/shaders" "$src/companion" "$out/"
cp "$src"/*.png "$src/faces.json" "$src/hey_mira.json" "$src/hey_mira.tflite" "$src/README.md" "$out/"
cp "$src/wake_training/mira_ar_v2.json" "$src/wake_training/mira_ar_v2.tflite" "$out/wake-models/"
find "$out" -name '__pycache__' -type d -prune -exec rm -rf {} +
find "$out" -type d -exec chmod 755 {} +
find "$out" -type f -exec chmod 644 {} +
# A tree without its entry point, its interface or its faces is not Mira.
for required in app.py controller.py tools.py qml/Main.qml qml/Mira/qmldir shaders/portal.frag.qsb \
                faces.json mira-icon-v2.png wake-models/mira_ar_v2.tflite; do
    test -f "$out/$required" || { echo "GATE FAIL: staged Mira lacks $required" >&2; exit 1; }
done
echo "staged Mira: $(find "$out" -type f | wc -l) files, $(du -sh "$out" | cut -f1)"
