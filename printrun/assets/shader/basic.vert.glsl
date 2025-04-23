#version 330 core
layout(location = 0) in vec3 vPos;
layout(location = 1) in vec4 vColor;
layout(location = 2) in vec3 vNormal;

uniform int doOverwriteColor;
uniform vec4 oColor;
uniform mat4 modelViewProjection;
uniform mat4 modelMat;

out VertexData
{
    vec4 fColor;
    vec3 fPos;
    vec3 fNormal;
} vs_out;

void main()
{
    gl_Position = modelViewProjection * vec4(vPos.x, vPos.y, vPos.z, 1.0);
    vs_out.fColor = (doOverwriteColor == 1) ? oColor : vColor;
    vs_out.fPos = vec3(modelMat * vec4(vPos, 1.0));
    vs_out.fNormal = vNormal;
}
