#version 330 core

in VertexData {
    vec4 fColor;
    vec3 fPos;
    vec3 fNormal;
} fs_in;

uniform vec3 viewPos;

const vec3 lightDiffColor = vec3(0.8);
const vec3 lightSpecColor = vec3(1.0);
const float ambientStrength = 0.2;
const float specularStrength = 0.7;
const int shininess = 128; // 2 - 256

const int NUM_LIGHTS = 2;
const vec3 lightPos[NUM_LIGHTS] = vec3[](
        vec3(900.0, 2800.0, 1700.0),
        vec3(-1200.0, -1000.0, 2200.0)
    );

out vec4 FragColor;

void main()
{
    // Ambient Light
    vec3 ambient = ambientStrength * lightDiffColor;

    vec3 norm = normalize(fs_in.fNormal);
    vec3 viewDir = normalize(viewPos - fs_in.fPos);
    vec3 lightResult = vec3(0.0);

    for (int i = 0; i < NUM_LIGHTS; ++i) {
        // Diffuse Light
        vec3 lightDir = normalize(lightPos[i] - fs_in.fPos);
        float diff = max(dot(norm, lightDir), 0.0);
        vec3 diffuse = diff * lightDiffColor;

        // Spec
        vec3 reflectDir = reflect(-lightDir, norm);
        float spec = pow(max(dot(viewDir, reflectDir), 0.0), shininess);
        vec3 specular = specularStrength * spec * lightSpecColor;

        lightResult += diffuse + specular;
    }

    vec3 result = lightResult * fs_in.fColor.rgb;
    FragColor = vec4(result, fs_in.fColor.a);
}
