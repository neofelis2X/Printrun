#version 330 core
layout (location = 0) in vec3 vPos;
layout (location=1) in vec4 vColor;
layout (location=2) in vec3 vNormal;

uniform int doOverwriteColor;
uniform vec4 oColor;
uniform mat4 modelViewProjection;

out vec4 fragmentColor;
out vec3 normal;

void main()
{
        gl_Position = modelViewProjection * vec4(vPos.x, vPos.y, vPos.z, 1.0);
        fragmentColor = (doOverwriteColor == 1) ? oColor : vColor;
        normal = vNormal;
}

