#version 440
// Mira's space: a very slow, dark aurora that brightens a little around the core with Mira's state.
layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;
layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    float time;
    float aspect;
    float energy;
    vec2 focusPt;
    vec4 accent;
    vec4 accent2;
};

float hash(vec2 p) { p = fract(p * vec2(123.34, 456.21)); p += dot(p, p + 45.32); return fract(p.x * p.y); }
float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1, 0)), u.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), u.x), u.y);
}
float fbm(vec2 p) {
    float v = 0.0, a = 0.5;
    for (int k = 0; k < 4; k++) { v += a * noise(p); p = p * 2.03 + vec2(1.7, 9.2); a *= 0.5; }
    return v;
}

void main() {
    vec2 uv = qt_TexCoord0;
    vec2 p = (uv - 0.5) * vec2(aspect, 1.0);
    float t = time * 0.025;
    float n = fbm(p * 1.4 + vec2(t, -t * 0.6));
    float n2 = fbm(p * 2.6 - vec2(t * 1.2, t * 0.5) + 1.8 * n);
    vec3 base = mix(vec3(0.020, 0.024, 0.058), vec3(0.012, 0.014, 0.036), uv.y);
    float d = length((uv - focusPt) * vec2(aspect, 1.0));
    float halo = exp(-d * d * 2.4);
    vec3 col = base;
    col += accent.rgb * pow(n2, 3.2) * (0.14 + 0.06 * energy);
    col += accent2.rgb * pow(n, 4.0) * 0.10;
    col += mix(accent2.rgb, accent.rgb, 0.5) * halo * (0.05 + 0.05 * energy);
    col *= 1.0 - 0.28 * dot(p, p);
    // dust
    vec2 g = uv * vec2(aspect, 1.0) * 70.0;
    float h = hash(floor(g));
    float star = step(0.9955, h) * smoothstep(0.42, 0.0, length(fract(g) - 0.5)) * (0.55 + 0.45 * sin(time * 0.7 + h * 60.0));
    col += vec3(0.75, 0.85, 1.0) * star * 0.55;
    fragColor = vec4(col, 1.0) * qt_Opacity;
}
