#version 330 core
layout (location = 0) in vec3 vPos;
layout (location=1) in vec4 vColor;
uniform mat4 modelViewProjection;
out vec4 fragmentColor;

void main()
{
        gl_Position = modelViewProjection * vec4(vPos.x, vPos.y, vPos.z, 1.0);
        fragmentColor = vColor;
}

