"""Regression checks for optional reader-history reset UI and state logic."""

import re
import unittest
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "reader" / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "reader" / "app.js").read_text(encoding="utf-8")
CSS = (ROOT / "reader" / "styles.css").read_text(encoding="utf-8")


class IdParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = {}

    def handle_starttag(self, tag, attrs):
        props = dict(attrs)
        if "id" in props:
            if props["id"] in self.ids:
                raise ValueError("Duplicate element ID: " + props["id"])
            self.ids[props["id"]] = (tag, props)


class ReaderResetTests(unittest.TestCase):
    def test_accessible_confirm_dialog_is_wired(self):
        parsed = IdParser()
        parsed.feed(HTML)
        required = [
            "manage-progress-button", "reset-progress-dialog", "reset-progress-title",
            "reset-progress-description", "reset-bookmarks-checkbox",
            "cancel-progress-reset", "confirm-progress-reset", "reset-notice",
        ]
        for element_id in required:
            with self.subTest(element_id=element_id):
                self.assertIn(element_id, parsed.ids)
        dialog = parsed.ids["reset-progress-dialog"]
        self.assertEqual(dialog[0], "dialog")
        self.assertEqual(dialog[1]["aria-labelledby"], "reset-progress-title")
        self.assertEqual(dialog[1]["aria-describedby"], "reset-progress-description")
        self.assertEqual(parsed.ids["reset-bookmarks-checkbox"][0], "input")
        self.assertNotIn("checked", parsed.ids["reset-bookmarks-checkbox"][1])
        self.assertIn("默认不勾选", HTML)
        self.assertIn("无法恢复", HTML)
        self.assertIn("当前浏览器", HTML)

    def test_reset_clears_just_reading_history_by_default(self):
        start = JS.index("  function resetReadingHistory() {")
        end = JS.index("  function toggleBookmark() {", start)
        body = JS[start:end]
        for operation in [
            "clearTimeout(saveTimer);",
            "state.positions = {};",
            "state.completed = [];",
            'state.lastPath = "";',
            "if (clearBookmarks) state.bookmarks = [];",
            "showHome({ savePrevious: false });",
            "saveState();",
        ]:
            with self.subTest(operation=operation):
                self.assertIn(operation, body)
        self.assertNotIn("state.theme =", body)
        self.assertNotIn("state.font =", body)
        self.assertRegex(
            JS,
            re.compile(r"function showHome\(\{ route = true, savePrevious = true \} = \{\}\) \{\s*"
                       r"if \(savePrevious\) saveReadingPosition\(\);\s*else clearTimeout\(saveTimer\);"),
        )
        self.assertIn('els.resetBookmarks.checked = false;', JS)
        self.assertIn('els.resetDialog.showModal();', JS)
        self.assertIn('els.resetConfirm.addEventListener("click", resetReadingHistory);', JS)

    def test_ui_is_present_on_desktop_and_mobile(self):
        self.assertIn(".manage-progress-button", CSS)
        self.assertIn(".reset-progress-dialog", CSS)
        self.assertIn(".reset-progress-dialog::backdrop", CSS)
        self.assertIn('href="./styles.css?v=11"', HTML)
        self.assertIn('src="./app.js?v=13"', HTML)
        self.assertIn("从头开始阅读", HTML)


if __name__ == "__main__":
    unittest.main()
