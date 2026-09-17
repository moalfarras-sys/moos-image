#!/usr/bin/env python3
"""Gate: Wave W5 — MoOS Intelligent Search: inline calculator, unit conversions, and quick actions.

Verifies:
  1. SearchAnswers.js provides pure, safe evaluation (zero eval, zero code execution).
  2. Math expressions (arithmetic, powers, percentages, functions, constants) evaluate correctly.
  3. Unit and currency conversions evaluate accurately with localized formatting.
  4. Code injections, random words, and script tags safely return null without errors.
  5. SearchView.qml integrates HeroAnswerCard, Enter-to-copy, and File Quick Actions.
"""

from pathlib import Path
import json
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SEARCH_VIEW_QML = ROOT / "system_files/usr/share/plasma/plasmoids/org.moos.search/contents/ui/SearchView.qml"
ANSWERS_JS = ROOT / "system_files/usr/share/plasma/plasmoids/org.moos.search/contents/ui/SearchAnswers.js"


def code(path: Path) -> str:
    """QML without // comment lines."""
    return "\n".join(line for line in path.read_text(encoding="utf-8").splitlines()
                     if not line.lstrip().startswith("//"))


def run_js(eval_script: str) -> dict | None:
    """Run evaluation in node.js importing SearchAnswers.js."""
    js_wrapper = f"""
    const fs = require('fs');
    const vm = require('vm');
    let code = fs.readFileSync('{ANSWERS_JS}', 'utf8');
    code = code.replace(/^\\s*\\.pragma\\s+library\\s*;?/m, '');
    const sandbox = {{ exports: {{}} }};
    vm.createContext(sandbox);
    vm.runInContext(code + "\\nexports.evaluate = evaluate;", sandbox);
    const res = sandbox.exports.evaluate({json.dumps(eval_script)});
    console.log(JSON.stringify(res));
    """
    res = subprocess.run(["node", "-e", js_wrapper], capture_output=True, text=True, check=True)
    out = res.stdout.strip()
    if not out or out == "null":
        return None
    data = json.loads(out)
    return data if data.get("valid") else None


class SearchAnswersEngineTests(unittest.TestCase):
    def test_basic_arithmetic(self):
        cases = [
            ("2 + 2", "4"),
            ("100 - 37", "63"),
            ("12 * 12", "144"),
            ("144 / 12", "12"),
            ("2 ^ 10", "1,024"),
            ("10 + 20 * 3", "70"),
            ("(10 + 20) * 3", "90"),
        ]
        for query, expected in cases:
            ans = run_js(query)
            self.assertIsNotNone(ans, f"Expected answer for {query}")
            self.assertEqual(ans["value"], expected, f"Failed for query: {query}")
            self.assertEqual(ans["type"], "math")

    def test_percentages(self):
        cases = [
            ("20% of 150", "30"),
            ("15% * 200", "30"),
            ("50% of 80", "40"),
        ]
        for query, expected in cases:
            ans = run_js(query)
            self.assertIsNotNone(ans, f"Expected percentage answer for {query}")
            self.assertEqual(ans["value"], expected, f"Failed for {query}")

    def test_math_functions_and_constants(self):
        cases = [
            ("sqrt(144)", "12"),
            ("abs(-42)", "42"),
            ("pi", "3.1416"),
        ]
        for query, expected_prefix in cases:
            ans = run_js(query)
            self.assertIsNotNone(ans, f"Expected answer for {query}")
            self.assertTrue(ans["value"].startswith(expected_prefix),
                            f"Expected {expected_prefix} in {ans['value']} for {query}")

    def test_unit_conversions(self):
        cases = [
            ("10 km to m", "10,000 m"),
            ("1000 m to km", "1 km"),
            ("1 kg in g", "1,000 g"),
            ("1024 mb in gb", "1 gb"),
            ("1 gb in mb", "1,024 mb"),
            ("2 hours in minutes", "120 minutes"),
            ("100 c in f", "212 °F"),
            ("32 f in c", "0 °C"),
        ]
        for query, expected in cases:
            ans = run_js(query)
            self.assertIsNotNone(ans, f"Expected answer for {query}")
            self.assertEqual(ans["value"], expected, f"Failed for {query}")
            self.assertEqual(ans["type"], "unit")

    def test_currency_conversions(self):
        cases = [
            ("100 usd in eur", "EUR"),
            ("50 eur in usd", "USD"),
            ("100 sar in usd", "USD"),
            ("100 aed in usd", "USD"),
        ]
        for query, expected_currency in cases:
            ans = run_js(query)
            self.assertIsNotNone(ans, f"Expected answer for {query}")
            self.assertIn(expected_currency, ans["value"], f"Failed currency for {query}")
            self.assertEqual(ans["type"], "currency")

    def test_safety_and_injection_resistance(self):
        # Arbitrary words and injection attempts must return null
        malicious = [
            "firefox",
            "console.log('pwn')",
            "process.exit(1)",
            "<script>alert(1)</script>",
            "rm -rf /",
            "hello world",
            "let a = 5",
            "function() {}",
        ]
        for query in malicious:
            ans = run_js(query)
            self.assertIsNone(ans, f"Query '{query}' should return null but returned {ans}")


class SearchViewIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.view = code(SEARCH_VIEW_QML)

    def test_answers_module_imported_and_wired(self):
        self.assertIn('import "SearchAnswers.js" as Answers', self.view)
        self.assertIn("readonly property var inlineAnswer: Answers.evaluate(root.query)", self.view)
        self.assertIn("readonly property bool hasInlineAnswer: inlineAnswer !== null && inlineAnswer.valid === true", self.view)

    def test_hero_answer_card_rendered(self):
        self.assertIn("id: heroAnswerCard", self.view)
        self.assertIn("visible: surface.hasInlineAnswer", self.view)
        self.assertIn("source: \"moos-spark-symbolic\"", self.view)
        self.assertIn("onClicked: surface.copyAnswer()", self.view)

    def test_file_quick_actions_present(self):
        self.assertIn("readonly property bool isFile: filePath.length > 0", self.view)
        self.assertIn('icon.name: "moos-folder-symbolic"', self.view)
        self.assertIn('icon.name: "moos-copy-symbolic"', self.view)
        self.assertIn("surface.copyText(resultRow.filePath)", self.view)

    def test_nothing_matched_suppressed_when_inline_answer_active(self):
        self.assertIn("visible: surface.hasQuery && !surface.hasInlineAnswer && resultList.count === 0 && !results.querying", self.view)


if __name__ == "__main__":
    unittest.main()
