#version 440
// Mira's face inside a soft circular portal.
// Expressions cross-fade as whole frames; a blink blends ONLY the eye band of the blink frame and
// speech blends ONLY the mouth band of the two speaking frames, so the rest of the face never
// double-exposes. All frames are pre-aligned portraits (faces.json), so the bands line up.
layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;
layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    float mixT;
    float blinkW;
    float roundW;
    float openW;
    float time;
    float level;
    float scan;
    float feather;
    float dim;
    vec2 parallax;
    vec4 tint;
};
layout(binding = 1) uniform sampler2D faceA;
layout(binding = 2) uniform sampler2D faceB;
layout(binding = 3) uniform sampler2D eyes;
layout(binding = 4) uniform sampler2D mouthRound;
layout(binding = 5) uniform sampler2D mouthOpen;

float band(vec2 uv, vec2 centre, vec2 halfSize, float soft) {
    vec2 q = (uv - centre) / halfSize;
    return 1.0 - smoothstep(1.0 - soft, 1.0, length(q));
}

void main() {
    vec2 uv = qt_TexCoord0;
    vec2 p = uv - 0.5;
    float r = length(p);
    float edge = 0.47;
    float mask = 1.0 - smoothstep(edge - feather, edge, r);
    vec2 fuv = uv - parallax * 0.012;
    vec4 c = mix(texture(faceA, fuv), texture(faceB, fuv), clamp(mixT, 0.0, 1.0));
    float eyeMask = band(fuv, vec2(0.5, 0.405), vec2(0.30, 0.085), 0.45);
    c = mix(c, texture(eyes, fuv), clamp(blinkW, 0.0, 1.0) * eyeMask);
    float mouthMask = band(fuv, vec2(0.5, 0.665), vec2(0.17, 0.085), 0.5);
    c = mix(c, texture(mouthRound, fuv), clamp(roundW, 0.0, 1.0) * mouthMask);
    c = mix(c, texture(mouthOpen, fuv), clamp(openW, 0.0, 1.0) * mouthMask);
    // depth: darken towards the rim so the face sits inside the light
    c.rgb *= mix(1.0, 0.62, smoothstep(0.26, edge, r));
    float rim = smoothstep(edge - 0.10, edge - 0.005, r) * mask;
    c.rgb += tint.rgb * rim * (0.20 + level * 0.45);
    float line = scan * exp(-pow((uv.y - fract(time * 0.33)) / 0.006, 2.0)) * smoothstep(edge, 0.2, r);
    c.rgb += tint.rgb * line * 0.55;
    c.rgb *= 1.0 - dim;
    fragColor = vec4(c.rgb * mask, mask * c.a) * qt_Opacity;
}
