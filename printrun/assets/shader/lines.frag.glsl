#version 330 core

layout(std140) uniform Camera {
    mat4 ViewProjection;
    mat4 Ortho2dProjection;
    vec3 viewPos;
    vec3 viewportSize;
};

in VertexData {
    vec4 fColor;
} fs_in;

flat in vec3 startPos;
in vec3 vertPos;

uniform int is_dashed;

float dashSize = 5.0 * viewportSize.p;
float gapSize = 4.0 * viewportSize.p;

out vec4 FragColor;

void main()
{
    if (is_dashed == 0) {
        FragColor = fs_in.fColor;
    } else {
        vec2 dir = (vertPos.xy - startPos.xy) * viewportSize.xy / 2.0;
        float dist = length(dir);

        if (fract(dist / (dashSize + gapSize)) > dashSize / (dashSize + gapSize))
            discard;
        FragColor = vec4(fs_in.fColor);
    }
}
