#version 330 core

in VertexData {
    vec4 fColor;
} fs_in;

out vec4 FragColor;

void main()
{
    FragColor = fs_in.fColor;
}
