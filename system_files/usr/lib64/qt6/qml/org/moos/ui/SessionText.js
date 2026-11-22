.pragma library
// The session surfaces' words, in the Arabic MoOS speaks.
//
// What the login and lock screens SAY is mostly not MoOS's: the action
// captions come from plasma_login's catalogue, and every prompt and refusal
// is a PAM message. Measured on the V3 (2026-11-22): plasma_login's Arabic
// uses dated imperatives that disagree with the MoOS power screen («أعد
// التّشغيل», «أطفئ», «علّق», «أسبِت»), misspells «مستخدم أخر…», and
// pam_fprintd speaks ENGLISH on the Arabic login screen because the login
// daemon runs PAM in the C locale («Place your right index finger on the
// fingerprint reader»); its partial catalogue even mixes both («ضع سبابتك
// اليمنى على the fingerprint reader»).
//
// present(text, arabic) is presentation only: it returns the words MoOS
// shows for an EXACT known string and the original for anything else. It
// never sees or changes a password, a prompt's meaning or what a caller
// compares (a refusal is still recognised from the raw text). A notice made
// of several parts joined by " • " is presented part by part.

var labels = {
    "أعد التّشغيل": "إعادة التشغيل",
    "أعد التشغيل": "إعادة التشغيل",
    "أطفئ": "إيقاف التشغيل",
    "علّق": "السكون",
    "أسبِت": "إسبات",
    "مستخدم أخر…": "مستخدم آخر…",
    "مستخدم أخر...": "مستخدم آخر…",
    "اسرد المستخدمين": "قائمة المستخدمين",
    "فشل الولوج": "تعذّر تسجيل الدخول",
    "فشل فكّ القفل": "تعذّر فتح القفل",
    "اكتب اسم المستخدم و كلمة السّر": "اكتب اسم المستخدم وكلمة السر"
};

var fingers = {
    "left thumb": "إبهامك الأيسر",
    "left index finger": "سبابتك اليسرى",
    "left middle finger": "إصبعك الوسطى اليسرى",
    "left ring finger": "بنصرك الأيسر",
    "left little finger": "خنصرك الأيسر",
    "right thumb": "إبهامك الأيمن",
    "right index finger": "سبابتك اليمنى",
    "right middle finger": "إصبعك الوسطى اليمنى",
    "right ring finger": "بنصرك الأيمن",
    "right little finger": "خنصرك الأيمن",
    "finger": "إصبعك"
};

var fingerprint = {
    "Failed to match fingerprint": "لم تتطابق البصمة، حاول مرة أخرى",
    "Verification timed out": "انتهت مهلة التحقق من البصمة",
    "Place your finger on the reader again": "ضع إصبعك على القارئ مرة أخرى",
    "Swipe your finger again": "مرّر إصبعك مرة أخرى",
    "Swipe was too short, try again": "كان التمرير قصيرًا، حاول مرة أخرى",
    "Swipe was too fast, try again": "كان التمرير سريعًا، حاول مرة أخرى",
    "Finger scan was too fast, try again": "كان المسح سريعًا، حاول مرة أخرى",
    "Your finger was not centered, try swiping your finger again": "لم يكن إصبعك في المنتصف، مرّره مرة أخرى",
    "Your finger was not centered, try touching the sensor again": "لم يكن إصبعك في المنتصف، المس القارئ مرة أخرى",
    "Remove your finger, and try swiping your finger again": "ارفع إصبعك ثم مرّره مرة أخرى",
    "Remove your finger, and try touching the sensor again": "ارفع إصبعك ثم المس القارئ مرة أخرى",
    "An unknown error occurred": "حدث خطأ غير معروف"
};

function reader(name) {
    return (name === "the fingerprint reader" || name === "the reader") ? "قارئ البصمة" : name;
}

function arabicPart(text) {
    if (labels.hasOwnProperty(text)) return labels[text];
    if (fingerprint.hasOwnProperty(text)) return fingerprint[text];
    var match = /^Place your (.+?) on (.+)$/.exec(text);
    if (match && fingers.hasOwnProperty(match[1])) {
        return "ضع " + fingers[match[1]] + " على " + reader(match[2]);
    }
    match = /^Swipe your (.+?) across (.+)$/.exec(text);
    if (match && fingers.hasOwnProperty(match[1])) {
        return "مرّر " + fingers[match[1]] + " على " + reader(match[2]);
    }
    // fprintd's own partial Arabic leaves the device phrase in English.
    match = /^(ضِ?ع|مرّر) (.+) على the fingerprint reader$/.exec(text);
    if (match && Object.keys(fingers).some(function(key) {
        return fingers[key] === match[2].replace("أصبعك", "إصبعك");
    })) {
        return match[1] + " " + match[2] + " على قارئ البصمة";
    }
    return text;
}

function isArabic(localeName) {
    return /^ar(?:[_-]|$)/i.test(localeName);
}

function present(text, arabic) {
    var value = String(text === undefined || text === null ? "" : text);
    if (!arabic || value === "") return value;
    return value.split(" • ").map(arabicPart).join(" • ");
}
