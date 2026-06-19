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
    vec3 ambient;
    vec3 diffuse;
    vec3 specular;
    uint shininess;
};

struct Light {
    vec3 position;
    vec3 ambient;
    vec3 diffuse;
    vec3 specular;
};

Material material = Material(fs_in.fColor.rgb, fs_in.fColor.rgb, vec3(1.0f), 140u);

const uint NUM_LIGHTS = 3u;
const Light light[NUM_LIGHTS] = Light[](
        Light(vec3(1300.0f, 200.0f, 1100.0f), vec3(0.12f), vec3(0.4f), vec3(1.0f)),
        Light(vec3(-1200.0f, 1400.0f, 1100.0f), vec3(0.12f), vec3(0.5f), vec3(1.0f)),
        Light(vec3(-1000.0f, -900.0f, 1100.0f), vec3(0.12f), vec3(0.3f), vec3(1.0f))
    );

void main() {
    vec3 viewDirection = normalize(ViewPos - fs_in.fPos);
    vec3 normal = normalize(fs_in.fNormal);
    vec3 lightResult = vec3(0.0);

    for (uint i = 0u; i < NUM_LIGHTS; i++) {
        // Ambient Light
        vec3 ambient = light[i].ambient * material.ambient;

        // Diffuse Light
        vec3 lightDirection = normalize(light[i].position - fs_in.fPos);
        float diff = max(dot(normal, lightDirection), 0.0);
        vec3 diffuse = light[i].diffuse * (diff * material.diffuse);

        // Spec
        vec3 reflectDirection = reflect(-lightDirection, normal);
        float spec = pow(max(dot(viewDirection, reflectDirection), 0.0), material.shininess);
        vec3 specular = light[i].specular * (spec * material.specular);

        lightResult += ambient + diffuse + specular;
    }

    vec3 result;
    if (gl_FrontFacing) {
        result = lightResult * fs_in.fColor.rgb;
    } else {
        result = lightResult * fs_in.fColor.rgb * vec3(0.4f);
    }
    FragColor = vec4(result, fs_in.fColor.a);
}
