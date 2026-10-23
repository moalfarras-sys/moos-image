.pragma library
// Generated from the canonical theme profiles. Desktop and login use one map.
var packageImages = {
    "MoOSUI2Graphite": "images_dark/3840x2160.jpg",
    "MoOSUI2Tide": "images/3840x2160.jpg",
    "MoOSUI2Nova": "images_dark/3840x2160.jpg",
    "MoOSUI2NovaLight": "images/3840x2160.jpg",
    "MoOSUI2Amethyst": "images_dark/3840x2160.jpg",
    "MoOSUI2AmethystLight": "images/3840x2160.jpg",
    "MoOSUI2Midnight": "images_dark/3840x2160.jpg",
    "MoOSUI2Daylight": "images/3840x2160.jpg",
    "MoOSUI2Aurora": "images_dark/3840x2160.jpg",
    "MoOSUI2AuroraLight": "images/3840x2160.jpg",
    "MoOSUI2Arena": "images_dark/3840x2160.jpg",
    "MoOSUI2ArenaLight": "images/3840x2160.jpg",
    "MoOSUI2Forge": "images_dark/3840x2160.jpg",
    "MoOSUI2ForgeLight": "images/3840x2160.jpg",
    "MoOSUI2Scholar": "images_dark/3840x2160.jpg",
    "MoOSUI2ScholarLight": "images/3840x2160.jpg",
    "MoOSUI2Bloom": "images_dark/1672x941.png",
    "MoOSUI2BloomLight": "images/1672x941.png"
};
function imageForPackage(path) {
    var base = String(path || "").replace(/\/+$/, "");
    var name = base.substring(base.lastIndexOf("/") + 1);
    return packageImages[name] ? base + "/contents/" + packageImages[name] : "";
}
