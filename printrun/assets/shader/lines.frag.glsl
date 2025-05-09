#version 330 core

layout(std140) uniform General {
    mat4 ViewProjection;
    mat4 Ortho2dProjection;
    vec3 ViewPos;
    vec3 ViewportSize;
    mat4 Transform;
    mat3 NormalTransform;
};

in VertexData {
    vec4 fColor;
} fs_in;

flat in vec3 startPos;
in vec3 vertPos;

uniform int u_isDashed;

float dashSize = 5.0 * ViewportSize.p;
float gapSize = 4.0 * ViewportSize.p;

out vec4 FragColor;

void main()
{
    if (u_isDashed == 0) {
        FragColor = fs_in.fColor;
    } else {
        vec2 dir = (vertPos.xy - startPos.xy) * ViewportSize.xy / 2.0;
        float dist = length(dir);

        if (fract(dist / (dashSize + gapSize)) > dashSize / (dashSize + gapSize))
            discard;
        FragColor = vec4(fs_in.fColor);
    }
}
