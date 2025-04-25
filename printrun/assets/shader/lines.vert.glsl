#version 330 core
layout(location = 0) in vec3 vPos;
layout(location = 1) in vec4 vColor;

layout(std140) uniform Camera {
    mat4 ViewProjection;
    mat4 Ortho2dProjection;
    vec3 viewPos;
    vec2 viewportSize;
};

uniform mat4 modelMat;
uniform int doOverwriteColor;
uniform vec4 oColor;
uniform int is_2d;

out VertexData {
    vec4 fColor;
} vs_out;

void main() {
    if (is_2d == 1) {
        gl_Position = Ortho2dProjection * vec4(vPos.x, vPos.y, vPos.z, 1.0);
    } else {
        gl_Position = ViewProjection * modelMat * vec4(vPos.x, vPos.y, vPos.z, 1.0);
    }
    vs_out.fColor = (doOverwriteColor == 1) ? oColor : vColor;
}
