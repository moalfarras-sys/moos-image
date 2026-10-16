.pragma library

// Reviewed product identities. Never merge by display name: unrelated calculators,
// editions and similarly named publishers must keep independent identities.
var groups = [
    ["ai.lmstudio.lm-studio", "lmstudio"],
    ["uk.org.greenend.chiark.sgtatham.putty", "putty"],
    ["app.organicmaps.desktop", "app.organicmaps"],
    ["org.videolan.VLC", "org.videolan.vlc"],
    ["chatgpt", "native.chatgpt", "native.org.moos.vendor.chatgpt"]
]
var identities = ({})
for (var g = 0; g < groups.length; ++g)
    for (var i = 0; i < groups[g].length; ++i) identities[groups[g][i]] = groups[g][0]

function key(app) {
    if (identities[app.id]) return identities[app.id]
    var id = app.kind === "native" && app.id.indexOf("native.") === 0 ? app.id.substring(7) : app.id
    if (app.kind === "native" && !/^[A-Za-z_][A-Za-z0-9_-]*(?:\.[A-Za-z_][A-Za-z0-9_-]*){2,}$/.test(id)) return app.id
    return identities[id] || id
}
function preference(app, installed) {
    return (installed(app) ? 100 : 0)
        + ((app.compat || {}).verdict === "blocked" ? -20 : 0)
        + (app.kind === "flatpak" ? 4 : app.kind === "appdrop" || app.kind === "vendor" ? 3 : 0)
}
function unique(apps, installed) {
    var out = [], places = ({})
    for (var i = 0; i < apps.length; ++i) {
        var app = apps[i], product = key(app)
        if (places[product] === undefined) { places[product] = out.length; out.push(app); continue }
        var at = places[product]
        if (preference(app, installed) > preference(out[at], installed)) out[at] = app
    }
    return out
}
function variants(app, apps) {
    if (!app) return []
    var product = key(app), out = []
    for (var i = 0; i < apps.length; ++i)
        if (key(apps[i]) === product) out.push(apps[i])
    return out
}
