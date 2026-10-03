#!/bin/sh
# Copy Mira's runtime tree from SRC (this directory's parent) into OUT — the image's /usr/lib/mira/app.
# Tests, developer tools, the Echo's own client, the wake-word training code and notes stay out;
# the shipped improved wake model goes into wake-models/, where the app serves it to a paired Echo.
set -eu
src=${1:?usage: stage.sh SRC OUT}
out=${2:?usage: stage.sh SRC OUT}
mkdir -p "$out/wake-models"
# Every top-level module except the suites: app, controller, tools, brain, the chat layer
# (chat_ui.py), the agent approvals (inbox.py), her place in Plasma (kde_integration.py), her
# motion policy (visual_tier.py) and the rest arrive through this one loop, never through a list
# that can forget a new one.
for file in "$src"/*.py; do
    case "$(basename "$file")" in
        test_*) ;;
        *) cp "$file" "$out/" ;;
    esac
done
# Her window's pages (pages/) are a package the controller imports inside a try: a tree without
# it opens with every destination empty and no error (it once shipped that way, every suite green).
# The pages' suites stay in the source tree.
# Lumen, the lighting engine (lumen/): Mira's tools, her Lumen page and /usr/bin/mira-lumen import it.
cp -r "$src/qml" "$src/shaders" "$src/companion" "$src/pages" "$src/lumen" "$out/"
find "$out/pages" "$out/lumen" -name 'test_*' -exec rm -f {} +
cp "$src"/*.png "$src/faces.json" "$src/hey_mira.json" "$src/hey_mira.tflite" "$src/README.md" "$out/"
cp "$src/wake_training/mira_ar_v2.json" "$src/wake_training/mira_ar_v2.tflite" "$out/wake-models/"
find "$out" -name '__pycache__' -type d -prune -exec rm -rf {} +
find "$out" -type d -exec chmod 755 {} +
find "$out" -type f -exec chmod 644 {} +
# The page modules pages/__init__.py names in PAGES (read, never imported: nothing runs here).
page_modules=$(python3 -B -c '
import ast, sys
for node in ast.parse(open(sys.argv[1], encoding="utf-8").read()).body:
    if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "PAGES" for t in node.targets):
        for name, _prop in ast.literal_eval(node.value):
            print("pages/%s.py" % name)
' "$src/pages/__init__.py")
[ -n "$page_modules" ] || { echo "GATE FAIL: Mira's pages/__init__.py names no page in PAGES" >&2; exit 1; }
# A tree without its entry point, its interface, its pages or its faces is not Mira.
for required in app.py controller.py tools.py chat_ui.py inbox.py kde_integration.py visual_tier.py homehub.py \
                lumen/__init__.py lumen/__main__.py lumen/engine.py lumen/service.py lumen/fusion2.py lumen/hue.py \
                lumen/dtls.py lumen/capture.py lumen/sync.py lumen/syncsession.py \
                pages/__init__.py pages/base.py $page_modules \
                qml/Main.qml qml/Mira/qmldir shaders/portal.frag.qsb \
                faces.json mira-icon-v2.png wake-models/mira_ar_v2.tflite; do
    test -f "$out/$required" || { echo "GATE FAIL: staged Mira lacks $required" >&2; exit 1; }
done
# …and every runtime module of the source arrived: the copies above are the only ones.
for module in "$src"/*.py "$src"/pages/*.py "$src"/lumen/*.py; do
    case "$(basename "$module")" in
        test_*) ;;
        *) test -f "$out/${module#"$src"/}" \
               || { echo "GATE FAIL: staged Mira lacks ${module#"$src"/}" >&2; exit 1; } ;;
    esac
done
echo "staged Mira: $(find "$out" -type f | wc -l) files, $(du -sh "$out" | cut -f1)"
