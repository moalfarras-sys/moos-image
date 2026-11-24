// SPDX-FileCopyrightText: 2026 Moalfarras — MoOS
// SPDX-License-Identifier: GPL-2.0-or-later
//
// The MoOS Touch Bar's decisions, kept free of QML so tests can run them under Node:
// which word a person is writing, which emoji fit it, and the recent-emoji list.
.pragma library
.import "EmojiData.js" as Data

var MAX_RECENT = 32
// Arabic marks a person does not type: tashkeel, tatweel, superscript alef (the same set
// scripts/generate_keyboard_emoji.py folds out of the keywords).
var ARABIC_MARKS = /[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed\u0640]/g
// Letters, marks and digits of the scripts the keyboard types (Qt's JavaScript engine
// has no \p{...} classes): Latin, Greek, Cyrillic, Hebrew, Arabic and its presentation forms —
// not Arabic punctuation (، ؛ ؟ ٪ ۔), which ends a word like its Latin counterparts.
var WORD_CHAR = /[0-9A-Za-z\u00c0-\u024f\u0370-\u052f\u0590-\u05ff\u0610-\u061a\u0620-\u0669\u066e-\u06d3\u06d5-\u06ff\u0750-\u077f\u08a0-\u08ff\ufb1d-\ufdff\ufe70-\ufefc]/

function normalize(word) {
    return String(word).toLocaleLowerCase().replace(ARABIC_MARKS, "")
        .replace(/[\u0623\u0625\u0622\u0671]/g, "\u0627")   // أ إ آ ٱ → ا
        .replace(/\u0649/g, "\u064a")                       // ى → ي
        .replace(/\u0629/g, "\u0647")                       // ة → ه
}

// The word the Touch Bar answers: the one being composed, or else the last word before
// the cursor when at most one space follows it (so "قلب " still offers ❤️).
function currentWord(preedit, surrounding, cursor) {
    if (preedit && preedit.length > 0)
        return preedit
    var text = String(surrounding || "")
    var end = Math.max(0, Math.min(cursor === undefined || cursor < 0 ? text.length : cursor, text.length))
    if (end > 0 && text[end - 1] === " ")
        end -= 1
    var start = end
    while (start > 0 && WORD_CHAR.test(text[start - 1]))
        start -= 1
    return text.slice(start, end)
}

var sortedKeys = ({})
function keysOf(language) {
    if (!sortedKeys[language])
        sortedKeys[language] = Object.keys(Data.keywords[language]).sort()
    return sortedKeys[language]
}

function lowerBound(keys, prefix) {
    var lo = 0, hi = keys.length
    while (lo < hi) {
        var mid = (lo + hi) >> 1
        if (keys[mid] < prefix) lo = mid + 1
        else hi = mid
    }
    return lo
}

// Light Arabic stemming: a written word carries clitics the keywords do not ("قلبي",
// "والورد", "سعيدة" for قلب، ورد، سعيد). Forms are tried longest first, never below two letters.
var ARABIC_PREFIXES = ["وال", "بال", "فال", "كال", "لل", "ال", "و", "ف", "ب", "ل"]
var ARABIC_SUFFIXES = ["كما", "هما", "كم", "كن", "هم", "هن", "نا", "ها", "ات", "ون", "ين", "ان", "وا", "ي", "ك", "ه", "ت"]
function arabicStems(key) {
    var out = []
    function add(form) { if (form.length >= 2 && form !== key && out.indexOf(form) < 0) out.push(form) }
    var bases = [key]
    for (var p = 0; p < ARABIC_PREFIXES.length; ++p)
        if (key.indexOf(ARABIC_PREFIXES[p]) === 0) { bases.push(key.slice(ARABIC_PREFIXES[p].length)); break }
    for (var b = 0; b < bases.length; ++b) {
        add(bases[b])
        for (var s = 0; s < ARABIC_SUFFIXES.length; ++s) {
            var suffix = ARABIC_SUFFIXES[s]
            if (bases[b].length > suffix.length + 1 && bases[b].slice(-suffix.length) === suffix) {
                add(bases[b].slice(0, -suffix.length))
                break
            }
        }
    }
    return out
}

// Emoji indices for a word, best first: exact keyword matches in every language, then
// its Arabic stems, then (from four letters) keywords the word begins — a shorter
// beginning matches too much to mean anything.
function matchIndices(word, limit) {
    var key = normalize(word)
    var found = []
    var seen = ({})
    function take(list) {
        var parts = list.split(",")
        for (var i = 0; i < parts.length && found.length < limit; ++i) {
            var n = Number(parts[i])
            if (!seen[n]) { seen[n] = true; found.push(n) }
        }
    }
    if (key.length < 2)
        return found
    var languages = Object.keys(Data.keywords)
    for (var l = 0; l < languages.length && found.length < limit; ++l) {
        var exact = Data.keywords[languages[l]][key]
        if (exact) take(exact)
    }
    if (/[\u0600-\u06ff]/.test(key)) {
        var stems = arabicStems(key)
        for (var s = 0; s < stems.length && found.length < limit; ++s) {
            var stem = Data.keywords.ar[stems[s]]
            if (stem) take(stem)
        }
    }
    if (key.length < 4)
        return found
    for (l = 0; l < languages.length && found.length < limit; ++l) {
        var keys = keysOf(languages[l])
        for (var k = lowerBound(keys, key); k < keys.length && found.length < limit; ++k) {
            if (keys[k].indexOf(key) !== 0) break
            if (keys[k] !== key) take(Data.keywords[languages[l]][keys[k]])
        }
    }
    return found
}

function emojiFor(word, limit) {
    return matchIndices(word, limit).map(function (i) { return Data.emoji[i] })
}

function parseRecent(stored) {
    try {
        var list = JSON.parse(stored || "[]")
        if (Array.isArray(list))
            return list.filter(function (e) { return typeof e === "string" && e.length > 0 && e.length <= 32 })
                       .slice(0, MAX_RECENT)
    } catch (e) {}
    return []
}

function pushRecent(list, emoji) {
    var out = [emoji]
    for (var i = 0; i < list.length && out.length < MAX_RECENT; ++i)
        if (list[i] !== emoji) out.push(list[i])
    return out
}

// Recent emoji, topped up with the most used ones so a new account's bar is never empty.
function recentOrPopular(list, size) {
    var out = list.slice(0, size)
    for (var i = 0; i < Data.popular.length && out.length < size; ++i) {
        var e = Data.emoji[Data.popular[i]]
        if (out.indexOf(e) < 0) out.push(e)
    }
    return out
}

function indexOfEmoji(emoji) {
    if (!indexOfEmoji.map) {
        indexOfEmoji.map = ({})
        for (var i = 0; i < Data.emoji.length; ++i) indexOfEmoji.map[Data.emoji[i]] = i
        for (var base in Data.tones)
            for (var t = 0; t < Data.tones[base].length; ++t) indexOfEmoji.map[Data.tones[base][t]] = Number(base)
    }
    var found = indexOfEmoji.map[emoji]
    return found === undefined ? -1 : found
}

function nameOf(emoji, language) {
    var i = indexOfEmoji(emoji)
    var names = Data.names[language] || Data.names.en
    return i < 0 ? emoji : names[i]
}

function tonesOf(emoji) {
    var i = Data.emoji.indexOf(emoji)
    return i >= 0 && Data.tones[i] ? [emoji].concat(Data.tones[i]) : []
}

// Which sheet section an index of [recent..., all emoji...] falls in: -1 recent, else a category.
function sectionAt(index, recentCount) {
    if (index < recentCount)
        return -1
    var n = index - recentCount
    var found = 0
    for (var c = 0; c < Data.categories.length; ++c)
        if (Data.categories[c].start <= n) found = c
    return found
}

// ── Words the person writes ─────────────────────────────────────────────────────────
// Plasma's keyboard switches Qt Virtual Keyboard's own prediction off (its pre-edit text
// fights external cursor moves), so the Touch Bar suggests from the words this person
// has finished on this keyboard: letters only (no digits, so no codes or numbers), two to
// 24 characters, never from a password, sensitive, e-mail or web-address field. They stay
// in the person's own config; holding a suggestion forgets it.
var MAX_WORDS = 4000
var MIN_WORD = 2
var MAX_WORD = 24

function isLearnable(word) {
    if (!word || word.length < MIN_WORD || word.length > MAX_WORD)
        return false
    for (var i = 0; i < word.length; ++i)
        if (!WORD_CHAR.test(word[i]) || (word[i] >= "0" && word[i] <= "9")
                || (word[i] >= "\u0660" && word[i] <= "\u0669") || (word[i] >= "\u06f0" && word[i] <= "\u06f9"))
            return false
    return true
}

function parseWords(stored) {
    var out = ({})
    try {
        var map = JSON.parse(stored || "{}")
        for (var word in map)
            if (isLearnable(word) && typeof map[word] === "number" && map[word] > 0)
                out[word] = Math.min(Math.floor(map[word]), 100000)
    } catch (e) {}
    return out
}

// Count one finished word. Latin words are kept in lower case unless written in capitals
// after the first letter (a name stays a name, "MoOS" stays "MoOS").
function learn(words, word) {
    if (!isLearnable(word))
        return false
    var key = /^[A-Z\u00c0-\u00de][^A-Z\u00c0-\u00de]*$/.test(word) ? word.toLowerCase() : word
    words[key] = (words[key] || 0) + 1
    var keys = Object.keys(words)
    if (keys.length > MAX_WORDS) {
        keys.sort(function (a, b) { return words[a] - words[b] })
        for (var i = 0; i < keys.length - MAX_WORDS; ++i)
            delete words[keys[i]]
    }
    return true
}

function forget(words, word) {
    delete words[word]
    delete words[word.toLowerCase()]
}

// Completions for the word being written: most used first, then shorter. Matching folds
// case and the Arabic letter shapes a person may skip (أ/إ/آ, ى, ة).
function suggestWords(words, prefix, limit) {
    var key = normalize(prefix)
    if (key.length < 1)
        return []
    var found = []
    for (var word in words) {
        var folded = normalize(word)
        if (folded.length > key.length && folded.indexOf(key) === 0)
            found.push(word)
    }
    found.sort(function (a, b) { return (words[b] - words[a]) || (a.length - b.length) || (a < b ? -1 : 1) })
    found = found.slice(0, limit)
    var capital = /^[A-Z\u00c0-\u00de]/.test(prefix)
    return found.map(function (w) { return capital ? w.charAt(0).toUpperCase() + w.slice(1) : w })
}

// A key that ends a word: space, return, or one character that is not part of a word.
function endsWord(key, text, keySpace, keyReturn) {
    if (key === keySpace || key === keyReturn)
        return true
    return text && text.length >= 1 && text.length <= 2 && !WORD_CHAR.test(text[0])
}

// The word being written: letters directly before the cursor, none after it (a cursor
// inside a word is editing, not writing).
function partialWord(surrounding, cursor) {
    var text = String(surrounding || "")
    var end = Math.max(0, Math.min(cursor === undefined || cursor < 0 ? text.length : cursor, text.length))
    if (end < text.length && WORD_CHAR.test(text[end]))
        return ""
    var start = end
    while (start > 0 && WORD_CHAR.test(text[start - 1]))
        start -= 1
    return text.slice(start, end)
}

// Plasma Login Manager's greeter runs this keyboard as the plasmalogin account, whose home
// is /var/lib/plasmalogin. Nobody's emoji, words or settings belong on the login screen.
function isGreeterHome(homeUrl) {
    return /\/var\/lib\/plasmalogin\/?$/.test(String(homeUrl || ""))
}
