#version 330 core

const uint MAX_LIGHTS = 4u;

struct Light {
    vec3 position;
    vec3 ambient;
    vec3 diffuse;
    vec3 specular;
};

layout(std140) uniform General {
    mat4 ViewProjection;
    mat4 Ortho2dProjection;
    vec3 ViewPos;
    vec3 ViewportSize;
    mat4 Transform;
    mat3 NormalTransform;
    vec3 SpecularColor;
    float SpecularValue;
    uint NumLights;
    Light lights[MAX_LIGHTS];
};

in VertexData {
    vec4 fColor;
    vec3 fPos;
    vec3 fNormal;
} fs_in;

out vec4 FragColor;

void main() {
    vec3 viewDirection = normalize(ViewPos - fs_in.fPos);
    vec3 normal = normalize(fs_in.fNormal);
    vec3 ambientSum = vec3(0.0);
    vec3 diffuseSum = vec3(0.0);
    vec3 specularSum = vec3(0.0);

    for (uint i = 0u; i < NumLights; i++) {
        // Ambient Light
        ambientSum += lights[i].ambient;

        // Diffuse Light
        vec3 lightDirection = normalize(lights[i].position - fs_in.fPos);
        float faceToLightDirection = dot(normal, lightDirection);
        float diff = max(faceToLightDirection, 0.0);
        diffuseSum += lights[i].diffuse * diff;

        // Specular Light
        vec3 halfway = normalize(lightDirection + viewDirection);
        float spec = pow(max(dot(normal, halfway), 0.0), SpecularValue);
        spec *= step(0.0, faceToLightDirection);
        specularSum += lights[i].specular * spec;
    }

    vec3 base_shading = clamp((ambientSum + diffuseSum) * fs_in.fColor.rgb, 0.0, 1.0);
    vec3 specular_mapped = specularSum / (specularSum + 1.0);
    specular_mapped *= SpecularColor;
    vec3 result = min(base_shading + specular_mapped, 1.0);

    if (!gl_FrontFacing) {
        result *= 0.4;
    }

    FragColor = vec4(result, fs_in.fColor.a);
}
