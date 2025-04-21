#version 330 core

layout(lines) in;
layout(line_strip, max_vertices = 2) out;

in vec4 fColor[];

out vec4 fragColor;

void main() {
    gl_Position = gl_in[0].gl_Position;
    fragColor = fColor[0];
    EmitVertex();
    gl_Position = gl_in[1].gl_Position;
    fragColor = fColor[1];
    EmitVertex();
    EndPrimitive();
}
