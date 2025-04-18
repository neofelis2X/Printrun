#version 330 core
layout(location = 0) in vec3 vPos;
layout(location = 1) in vec4 vColor;
layout(location = 2) in vec3 vNormal;

uniform int doOverwriteColor;
uniform vec4 oColor;
uniform mat4 modelViewProjection;
uniform mat4 modelMat;
uniform vec3 viewPos;

out vec4 fragColor;
out vec3 fragPos;
out vec3 fragNormal;
out vec3 fragView;

void main()
{
    gl_Position = modelViewProjection * vec4(vPos.x, vPos.y, vPos.z, 1.0);
    fragColor = (doOverwriteColor == 1) ? oColor : vColor;
    fragPos = vec3(modelMat * vec4(vPos, 1.0));
    fragNormal = vNormal;
    fragView = viewPos;
}
