/// The form a title is compared in when somebody searches for it.
///
/// A search box that only lower-cases is a search box that fails Arabic: the
/// same word arrives as `أفلام`, `افلام` and `إفلام` depending on the keyboard
/// and on whoever typed the panel's catalogue, and a harakat mark or a tatweel
/// in the title makes an exact substring miss. Every catalogue title is folded
/// through this once, when the catalogue is built (on a background isolate),
/// and the query is folded the same way — so the per-keystroke work is a
/// `contains` over strings that are already comparable.
String searchKey(String input) {
  if (input.isEmpty) return input;
  final out = StringBuffer();
  var lastWasSpace = true;
  for (final unit in input.toLowerCase().runes) {
    final folded = _fold(unit);
    if (folded == null) continue;
    if (folded == 0x20) {
      if (lastWasSpace) continue;
      lastWasSpace = true;
    } else {
      lastWasSpace = false;
    }
    out.writeCharCode(folded);
  }
  final text = out.toString();
  return text.endsWith(' ') ? text.substring(0, text.length - 1) : text;
}

int? _fold(int c) {
  // Arabic diacritics (harakat, shadda, sukun, superscript alef) and tatweel
  // carry no meaning for matching.
  if (c >= 0x064B && c <= 0x065F) return null;
  if (c == 0x0670 || c == 0x0640) return null;
  switch (c) {
    // Every alef with a mark folds to the bare alef.
    case 0x0622: // آ
    case 0x0623: // أ
    case 0x0625: // إ
    case 0x0671: // ٱ
      return 0x0627;
    case 0x0649: // ى → ي
      return 0x064A;
    case 0x0629: // ة → ه
      return 0x0647;
    case 0x0624: // ؤ → و
      return 0x0648;
    case 0x0626: // ئ → ي
      return 0x064A;
  }
  // Arabic-Indic and extended digits compare as Latin digits.
  if (c >= 0x0660 && c <= 0x0669) return 0x30 + (c - 0x0660);
  if (c >= 0x06F0 && c <= 0x06F9) return 0x30 + (c - 0x06F0);
  // Punctuation and separators collapse to one space, so "Spider-Man" matches
  // "spider man" and a pipe-delimited panel prefix does not glue two words.
  if (c < 0x30 ||
      (c >= 0x3A && c <= 0x40) ||
      (c >= 0x5B && c <= 0x60) ||
      (c >= 0x7B && c <= 0x7F) ||
      c == 0x060C || // Arabic comma
      c == 0x061B ||
      c == 0x061F ||
      c == 0x00A0 ||
      c == 0x2013 ||
      c == 0x2014 ||
      c == 0x2022 ||
      c == 0x00B7 ||
      c == 0x2502 ||
      c == 0x2503 ||
      c == 0x2759) {
    return 0x20;
  }
  return c;
}
