#version 440
// Mira's face inside a soft circular portal.
// Expressions cross-fade as whole frames; a blink blends ONLY the eye band of the blink frame and
// speech deforms ONLY one mouth patch, so intermediate openings never
// double-expose lips. All patches are registered portraits (faces.json).
layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;
layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    float mixT;
    float speechW;
    float mouthY;
    float blinkW;
    float mouthActive;
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
layout(binding = 5) uniform sampler2D mouthOpen;
layout(binding = 6) uniform sampler2D eyesHalf;

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
    // Separate eyelids: leave the nose bridge, eyebrows and cheeks untouched.
    float eyeMask = max(band(fuv, vec2(0.345, 0.405), vec2(0.125, 0.064), 0.25),
                        band(fuv, vec2(0.655, 0.405), vec2(0.125, 0.064), 0.25));
    float blink = clamp(blinkW, 0.0, 1.0);
    vec4 eyeFrame = blink < 0.5
        ? mix(c, texture(eyesHalf, fuv), blink * 2.0)
        : mix(texture(eyesHalf, fuv), texture(eyes, fuv), (blink - 0.5) * 2.0);
    c = mix(c, eyeFrame, eyeMask);
    // One lip surface, deformed in UV space. Alpha-blending different lip
    // outlines leaves two mouths at intermediate energy, even with an opaque mask.
    // Compress only the inner gap; move each lip without thinning it. The warp
    // reaches zero before the nose/chin so the original face stays stationary.
    float mouthMask = band(fuv, vec2(0.5, mouthY), vec2(0.17, 0.10), 0.22);
    float dx = (fuv.x - 0.5) / 0.103;
    float curve = sqrt(max(0.0, 1.0 - dx * dx));
    float sourceGap = (mouthY > 0.69 ? 0.022 : 0.020) * curve;
    float gap = sourceGap * clamp(speechW, 0.0, 1.0);
    float dy = fuv.y - mouthY;
    vec2 mouthUV = fuv;
    if (abs(dy) < gap && gap > 0.00001) {
        mouthUV.y = mouthY + dy * sourceGap / gap;
    } else {
        float falloff = 1.0 - smoothstep(0.035, 0.095, abs(dy));
        mouthUV.y += sign(dy) * (sourceGap - gap) * falloff;
    }
    vec4 mouthFrame = texture(mouthOpen, mouthUV);
    c = mix(c, mouthFrame, mouthMask * clamp(mouthActive, 0.0, 1.0));
    // depth: darken towards the rim so the face sits inside the light
    c.rgb *= mix(1.0, 0.62, smoothstep(0.26, edge, r));
    float rim = smoothstep(edge - 0.10, edge - 0.005, r) * mask;
    c.rgb += tint.rgb * rim * (0.20 + level * 0.45);
    float line = scan * exp(-pow((uv.y - fract(time * 0.33)) / 0.006, 2.0)) * smoothstep(edge, 0.2, r);
    c.rgb += tint.rgb * line * 0.55;
    c.rgb *= 1.0 - dim;
    fragColor = vec4(c.rgb * mask, mask * c.a) * qt_Opacity;
}
