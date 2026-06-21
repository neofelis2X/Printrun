#version 330 core

layout(lines) in;
layout(triangle_strip, max_vertices = 4) out;

layout(std140) uniform General {
    mat4 ViewProjection;
    mat4 Ortho2dProjection;
    vec3 ViewPos;
    vec3 ViewportSize; // width, height, scale
    mat4 Transform;
    mat3 NormalTransform;
};

in VertexData {
    vec4 fColor;
} gs_in[];

uniform float u_Thickness;
const float W_MIN = 0.001f;

out VertexData {
    vec4 fColor;
} gs_out;

void main() {
    vec4 p1 = gl_in[0].gl_Position;
    vec4 p2 = gl_in[1].gl_Position;
    vec4 c1 = gs_in[0].fColor;
    vec4 c2 = gs_in[1].fColor;

    // --- Near-plane clip in clip space (keep w >= W_MIN) ---
    if (p1.w < W_MIN && p2.w < W_MIN) {
        return; // whole segment behind camera
    }
    if (p1.w < W_MIN) {
        float t = (W_MIN - p1.w) / (p2.w - p1.w); // crossing parameter
        p1 = mix(p1, p2, t);
        c1 = mix(c1, c2, t); // interpolate color
    } else if (p2.w < W_MIN) {
        float t = (W_MIN - p2.w) / (p1.w - p2.w);
        p2 = mix(p2, p1, t);
        c2 = mix(c2, c1, t);
    }

    vec2 d = (p2.xy / p2.w - p1.xy / p1.w) * ViewportSize.xy;
    if (dot(d, d) < 0.0001f) {
        return; // skip very short, degenerate lines
    }
    vec2 dir = normalize(d);
    vec2 p_factor = u_Thickness * 2.0 * ViewportSize.p / ViewportSize.xy;
    vec4 line_offset = vec4(vec2(-dir.y, dir.x) * p_factor, 0.0, 0.0);
    vec4 line_extension = vec4(dir * 0.5f * p_factor, 0.0, 0.0);

    gl_Position = p1 + line_offset * p1.w - line_extension;
    gs_out.fColor = c1;
    EmitVertex();
    gl_Position = p1 - line_offset * p1.w - line_extension;
    gs_out.fColor = c1;
    EmitVertex();
    gl_Position = p2 + line_offset * p2.w + line_extension;
    gs_out.fColor = c2;
    EmitVertex();
    gl_Position = p2 - line_offset * p2.w + line_extension;
    gs_out.fColor = c2;
    EmitVertex();

    EndPrimitive();
}
