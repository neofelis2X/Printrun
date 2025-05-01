#version 330 core
layout(location = 0) in vec3 vPos;
layout(location = 1) in vec4 vColor;

layout(std140) uniform Camera {
    mat4 ViewProjection;
    mat4 Ortho2dProjection;
    vec3 viewPos;
    vec3 viewportSize;
};

uniform mat4 modelMat;
uniform int doOverwriteColor;
uniform vec4 oColor;
uniform int is_2d;

out VertexData {
    vec4 fColor;
} vs_out;

flat out vec3 startPos;
out vec3 vertPos;

void main() {
    vec4 pos;
    if (is_2d == 1) {
        pos = Ortho2dProjection * vec4(vPos, 1.0);
    } else {
        pos = ViewProjection * modelMat * vec4(vPos, 1.0);
    }
    gl_Position = pos;
    vertPos = pos.xyz / pos.w;
    startPos = vertPos;

    vs_out.fColor = (doOverwriteColor == 1) ? oColor : vColor;
}
