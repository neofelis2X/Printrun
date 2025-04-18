#version 330 core

in vec4 fragColor;
in vec3 fragPos;
in vec3 fragNormal;
in vec3 fragView;

vec3 lightDiffColor = vec3(0.8);
vec3 lightSpecColor = vec3(1.0);
vec3 light1Pos = vec3(900.0, 2800.0, 1700.0);
vec3 light2Pos = vec3(-1200.0, -1000.0, 2200.0);
float ambientStrength = 0.2;
float specularStrength = 0.7;
int shininess = 128; // 2 - 256

out vec4 FragColor;

void main()
{
    // Ambient Light
    vec3 ambient = ambientStrength * lightDiffColor;

    vec3 norm = normalize(fragNormal);
    // Diffuse Light 1
    vec3 light1Dir = normalize(light1Pos - fragPos);
    float diff1 = max(dot(norm, light1Dir), 0.0);
    vec3 diffuse1 = diff1 * lightDiffColor;

    // Diffuse Light 2
    vec3 light2Dir = normalize(light2Pos - fragPos);
    float diff2 = max(dot(norm, light2Dir), 0.0);
    vec3 diffuse2 = diff2 * lightDiffColor;

    vec3 viewDir = normalize(fragView - fragPos);
    // Spec 1
    vec3 reflect1Dir = reflect(-light1Dir, norm);
    float spec1 = pow(max(dot(viewDir, reflect1Dir), 0.0), shininess);
    vec3 specular1 = specularStrength * spec1 * lightSpecColor;

    // Spec 2
    vec3 reflect2Dir = reflect(-light2Dir, norm);
    float spec2 = pow(max(dot(viewDir, reflect2Dir), 0.0), shininess);
    vec3 specular2 = specularStrength * spec2 * lightSpecColor;

    vec3 result = (ambient + diffuse1 + diffuse2 + specular1 + specular2) * fragColor.rgb;
    FragColor = vec4(result, fragColor.a);
}
