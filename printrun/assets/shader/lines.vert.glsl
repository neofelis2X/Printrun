#version 330 core
layout(location = 0) in vec3 vPos;
layout(location = 1) in vec4 vColor;

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
uniform int u_is2d;

out VertexData {
    vec4 fColor;
} vs_out;

flat out vec3 startPos;
out vec3 vertPos;

void main() {
    vec4 pos;
    if (u_is2d == 1) {
        pos = Ortho2dProjection * vec4(vPos, 1.0);
    } else {
        pos = ViewProjection * Transform * vec4(vPos, 1.0);
    }
    gl_Position = pos;
    vertPos = pos.xyz / pos.w;
    startPos = vertPos;

    vs_out.fColor = (u_OverwriteColor == 1) ? u_oColor : vColor;
}
