#version 330 core

layout(lines) in;
layout(triangle_strip, max_vertices = 4) out;

layout(std140) uniform Camera {
    mat4 ViewProjection;
    mat4 Ortho2dProjection;
    vec3 viewPos;
    vec2 viewportSize;
};

in VertexData {
    vec4 fColor;
} gs_in[];

uniform float u_thickness;

out VertexData {
    vec4 fColor;
} gs_out;

void main() {
    vec4 p1 = gl_in[0].gl_Position;
    vec4 p2 = gl_in[1].gl_Position;

    vec2 dir = normalize((p2.xy / p2.w - p1.xy / p1.w) * viewportSize);
    vec2 offset = vec2(-dir.y, dir.x) * u_thickness / viewportSize;

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
