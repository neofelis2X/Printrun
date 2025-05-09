#version 330 core

layout(lines) in;
layout(triangle_strip, max_vertices = 4) out;

layout(std140) uniform General {
    mat4 ViewProjection;
    mat4 Ortho2dProjection;
    vec3 ViewPos;
    vec3 ViewportSize;
    mat4 Transform;
    mat3 NormalTransform;
};

in VertexData {
    vec4 fColor;
} gs_in[];

uniform float u_Thickness;

out VertexData {
    vec4 fColor;
} gs_out;

void main() {
    vec4 p1 = gl_in[0].gl_Position;
    vec4 p2 = gl_in[1].gl_Position;

    vec2 dir = normalize((p2.xy / p2.w - p1.xy / p1.w) * ViewportSize.xy);
    vec2 offset = vec2(-dir.y, dir.x) * u_Thickness * ViewportSize.p / ViewportSize.xy;

    gl_Position = p1 + vec4(offset.xy * p1.w, 0.0, 0.0);
    gs_out.fColor = gs_in[0].fColor;
    EmitVertex();
    gl_Position = p1 - vec4(offset.xy * p1.w, 0.0, 0.0);
    gs_out.fColor = gs_in[0].fColor;
    EmitVertex();
    gl_Position = p2 + vec4(offset.xy * p2.w, 0.0, 0.0);
    gs_out.fColor = gs_in[1].fColor;
    EmitVertex();
    gl_Position = p2 - vec4(offset.xy * p2.w, 0.0, 0.0);
    gs_out.fColor = gs_in[1].fColor;
    EmitVertex();

    EndPrimitive();
}
