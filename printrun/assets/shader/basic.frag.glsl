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
    vec3 fPos;
    vec3 fNormal;
} fs_in;

out vec4 FragColor;

struct Material {
    vec3 albedo;
    vec3 specular;
    float shininess;
};

struct Light {
    vec3 position;
    vec3 ambient;
    vec3 diffuse;
    vec3 specular;
};

Material material = Material(fs_in.fColor.rgb, vec3(0.4f), 80.0f);

const uint NUM_LIGHTS = 3u;
const Light light[NUM_LIGHTS] = Light[](
        Light(vec3(1300.0f, 200.0f, 1100.0f), vec3(0.12f), vec3(0.4f), vec3(1.0f)),
        Light(vec3(-1200.0f, 1400.0f, 1100.0f), vec3(0.12f), vec3(0.5f), vec3(1.0f)),
        Light(vec3(-1000.0f, -900.0f, 1100.0f), vec3(0.12f), vec3(0.3f), vec3(1.0f))
    );

void main() {
    vec3 viewDirection = normalize(ViewPos - fs_in.fPos);
    vec3 normal = normalize(fs_in.fNormal);
    vec3 ambientSum = vec3(0.0);
    vec3 diffuseSum = vec3(0.0);
    vec3 specularSum = vec3(0.0);

    for (uint i = 0u; i < NUM_LIGHTS; i++) {
        // Ambient Light
        ambientSum += light[i].ambient;

        // Diffuse Light
        vec3 lightDirection = normalize(light[i].position - fs_in.fPos);
        float faceToLightDirection = dot(normal, lightDirection);
        float diff = max(faceToLightDirection, 0.0);
        diffuseSum += light[i].diffuse * diff;

        // Specular Light
        vec3 halfway = normalize(lightDirection + viewDirection);
        float spec = pow(max(dot(normal, halfway), 0.0), material.shininess);
        spec *= step(0.0, faceToLightDirection);
        specularSum += light[i].specular * spec;
    }

    vec3 base_shading = clamp((ambientSum + diffuseSum) * material.albedo, 0.0, 1.0);
    vec3 specular_mapped = specularSum / (specularSum + 1.0);
    specular_mapped *= material.specular;
    vec3 result = min(base_shading + specular_mapped, 1.0);

    if (!gl_FrontFacing) {
        result *= 0.4;
    }

    FragColor = vec4(result, fs_in.fColor.a);
}
