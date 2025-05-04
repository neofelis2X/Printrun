#version 330 core
layout(location = 0) in vec3 vPos;
layout(location = 1) in vec4 vColor;
layout(location = 2) in vec3 vNormal;

layout(std140) uniform Camera {
    mat4 ViewProjection;
    mat4 Ortho2dProjection;
    vec3 viewPos;
    vec3 viewportSize;
};

uniform mat4 modelMat;
uniform mat3 u_NormalMat;
uniform int doOverwriteColor;
uniform vec4 oColor;

out VertexData {
    vec4 fColor;
    vec3 fPos;
    vec3 fNormal;
} vs_out;

void main() {
    gl_Position = ViewProjection * modelMat * vec4(vPos.xyz, 1.0);
    vs_out.fColor = (doOverwriteColor == 1) ? oColor : vColor;
    vs_out.fPos = vec3(modelMat * vec4(vPos, 1.0));
    vs_out.fNormal = normalize(u_NormalMat * vNormal);
}
