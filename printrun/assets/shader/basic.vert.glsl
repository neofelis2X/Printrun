#version 330 core
layout(location = 0) in vec3 vPos;
layout(location = 1) in vec4 vColor;
layout(location = 2) in vec3 vNormal;

layout(std140) uniform General {
    mat4 ViewProjection;
    mat4 Ortho2dProjection;
    vec3 ViewPos;
    vec3 ViewportSize;
    mat4 Transform;
    mat3 NormalTransform;
};

uniform int u_OverwriteColor;
uniform vec4 u_oColor;

out VertexData {
    vec4 fColor;
    vec3 fPos;
    vec3 fNormal;
} vs_out;

void main() {
    gl_Position = ViewProjection * Transform * vec4(vPos.xyz, 1.0);
    vs_out.fColor = (u_OverwriteColor == 1) ? u_oColor : vColor;
    vs_out.fPos = vec3(Transform * vec4(vPos, 1.0));
    vs_out.fNormal = normalize(NormalTransform * vNormal);
}
