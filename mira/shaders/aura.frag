#version 440
// The ring of light around Mira's face. Every term is state-bearing:
// level = live microphone or voice energy; think/exec/err/off = animated state weights.
layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;
layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    float time;
    float level;
    float radius;
    float think;
    float exec;
    float err;
    float off;
    float hover;
    vec4 colorA;
    vec4 colorB;
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
    vec2 p = qt_TexCoord0 - 0.5;
    float r = length(p);
    float a = atan(p.y, p.x);
    vec2 q = vec2(cos(a), sin(a));
    float calm = 1.0 - off;
    float t = time;
    float n = fbm(q * 1.7 + vec2(t * 0.16, -t * 0.11));
    float n2 = fbm(q * 3.3 - vec2(t * 0.27, t * 0.19) + 1.6 * n);
    float lv = clamp(level, 0.0, 1.0);
    float wob = (n - 0.5) * (0.018 + lv * 0.085) * calm;
    float d = r - (radius + 0.010 + wob);
    float ring = exp(-pow(d / (0.0065 + lv * 0.010), 2.0));
    float outer = exp(-max(d, 0.0) * (15.0 - lv * 7.0)) * smoothstep(-0.015, 0.004, d);
    float inner = exp(-pow(min(d, 0.0) / 0.028, 2.0)) * (1.0 - smoothstep(0.0, 0.012, d)) * smoothstep(-0.09, -0.02, d);
    float hue = 0.5 + 0.5 * sin(a * 2.0 + t * 0.45 + n2 * 3.0);
    vec3 col = mix(colorA.rgb, colorB.rgb, hue);
    float I = ring * (0.85 + 0.3 * hover) + outer * (0.34 + lv * 0.9) * (0.55 + 0.9 * n2) + inner * 0.28;
    // thinking: two comets chasing around the ring
    float comet = pow(max(0.0, cos(a - t * 2.3)), 22.0) + pow(max(0.0, cos(a + 3.14159 - t * 2.3)), 22.0);
    I += think * comet * exp(-pow(d / 0.018, 2.0)) * 1.6;
    // executing: a segmented orbit just outside the ring
    float seg = smoothstep(0.35, 0.5, fract((a / 6.28318 + 0.5) * 36.0 - t * 0.9)) * smoothstep(0.65, 0.5, fract((a / 6.28318 + 0.5) * 36.0 - t * 0.9));
    I += exec * seg * exp(-pow((r - radius - 0.055) / 0.0055, 2.0)) * 1.2;
    // speaking/listening energy rays
    I += lv * pow(n2, 2.2) * outer * 1.1;
    // motes: a few sparks orbiting just outside the ring; faster while thinking, brighter with voice
    float motes = 0.0;
    for (int i = 0; i < 18; i++) {
        float fi = float(i);
        float h1 = hash(vec2(fi, 3.7));
        float h2 = hash(vec2(fi, 9.1));
        float ang = h1 * 6.28318 + t * (0.05 + 0.10 * h2) * (1.0 + 3.0 * think) * (h2 > 0.5 ? 1.0 : -1.0);
        float rad = radius + 0.035 + 0.085 * h2 + 0.008 * sin(t * 0.7 + fi);
        vec2 m = rad * vec2(cos(ang), sin(ang));
        float dm = length(p - m);
        float twinkle = 0.55 + 0.45 * sin(t * (1.3 + h1 * 2.0) + fi * 1.7);
        motes += exp(-pow(dm / (0.0032 + 0.002 * h1), 2.0)) * twinkle;
    }
    I += motes * (0.55 + 0.6 * lv + 0.4 * think) * calm;
    // error: slow warning pulse; offline: dim and still
    I *= mix(1.0, 0.72 + 0.28 * sin(t * 3.2), err);
    I *= mix(1.0, 0.35, off);
    col = mix(col, vec3(dot(col, vec3(0.33))), off * 0.8);
    float alpha = clamp(I * 0.62, 0.0, 1.0);
    fragColor = vec4(col * I, alpha) * qt_Opacity;
}
