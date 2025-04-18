# This file is part of the Printrun suite.
#
# Printrun is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Printrun is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Printrun.  If not, see <http://www.gnu.org/licenses/>.

from pathlib import Path
import ctypes
import numpy as np
from pyglet.graphics import shader

from pyglet.gl import GLfloat, GLuint, \
                      GL_ELEMENT_ARRAY_BUFFER, GL_FLOAT, GL_ARRAY_BUFFER, \
                      GL_STATIC_DRAW, GL_FALSE, GL_TRUE, \
                      glGenVertexArrays, glBindVertexArray, glGenBuffers, \
                      glBindBuffer, glBufferData, glEnableVertexAttribArray, \
                      glVertexAttribPointer, glGetUniformLocation, \
                      glUniformMatrix4fv, glUniform1i, glUniform4f

def load_shader():
    vert_source = Path("printrun/assets/shader/basic.vert.glsl")
    frag_source = Path("printrun/assets/shader/basic.frag.glsl")

    try:
        vert_shader = shader.Shader(vert_source.read_text(encoding="utf-8"),
                                    'vertex')
    except shader.ShaderException as e:
        print("Error in vertex shader:", e)
        return None
    try:
        frag_shader = shader.Shader(frag_source.read_text(encoding="utf-8"),
                                    'fragment')
    except shader.ShaderException as e:
        print("Error in fragment shader:",e)
        return None

    try:
        shader_program = shader.ShaderProgram(vert_shader, frag_shader)
    except shader.ShaderException as e:
        print("Error creating the shader program:",e)
        return None

    vert_shader.delete()
    frag_shader.delete()

    return shader_program

def load_mvp_uniform(shader_id, camera, actor):
    if actor.is_3d:
        mat = camera.projection @ camera.view @ actor.modelmatrix
    else:
        mat = camera.projection2d

    location = glGetUniformLocation(shader_id, b"modelViewProjection")
    ptr = mat.ctypes.data_as(ctypes.POINTER(GLfloat))
    glUniformMatrix4fv(location, 1, GL_TRUE, ptr)

def load_uniform(shader_id, uniform_name: str, data):
    location = glGetUniformLocation(shader_id, uniform_name.encode())
    if location == -1:
        print("Could not find Uniform location.")
        return
    if uniform_name == "doOverwriteColor":
        glUniform1i(location, data)
    elif uniform_name == "oColor":
        glUniform4f(location, *data)

def interleave_vertex_data(verts, color, normal, distinct_colors=False,
                           distinct_normals=False):
    buffersize = len(verts) * 3 + len(verts) * 4 + len(verts) * 3
    data = np.zeros(buffersize, dtype=GLfloat)
    for i, vertex in enumerate(verts):
        iv = i * (3 + 4 + 3)
        data[iv:iv + 3] = vertex
        if distinct_colors:
            data[iv + 3:iv + 7] = color[i]
        else:
            data[iv + 3:iv + 7] = color
        if distinct_normals:
            data[iv + 7:iv + 10] = normal[i]
        else:
            data[iv + 7:iv + 10] = normal

    return data

def create_buffers(create_ebo=True):
    """
    Creates and sets up VAO, VBO and EBO.
    Returns handles to VAO, VBO, EBO.
    """
    # Vertex array object
    vao = GLuint(0)
    glGenVertexArrays(1, vao)
    glBindVertexArray(vao)

    # Vertex buffer object
    vbo = GLuint(0)
    glGenBuffers(1, vbo)
    glBindBuffer(GL_ARRAY_BUFFER, vbo)

    glEnableVertexAttribArray(0)  # Vertex position
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 10 * ctypes.sizeof(GLfloat), 0)
    glEnableVertexAttribArray(1)  # Vertex colour
    glVertexAttribPointer(1, 4, GL_FLOAT, GL_FALSE, 10 * ctypes.sizeof(GLfloat),
                          3 * ctypes.sizeof(GLfloat))
    glEnableVertexAttribArray(2)  # Vertex normal direction
    glVertexAttribPointer(2, 3, GL_FLOAT, GL_FALSE, 10 * ctypes.sizeof(GLfloat),
                          7 * ctypes.sizeof(GLfloat))

    if create_ebo:
        # Index buffer object
        ebo = GLuint(0)
        glGenBuffers(1, ebo)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo)
    else:
        ebo = None

    return vao, vbo, ebo

def fill_buffer(buffer, data, kind) -> None:
    #print(type(data), data[:10], len(data))
    gl_array = get_gl_array(data)
    glBindBuffer(kind, buffer)
    glBufferData(kind, ctypes.sizeof(gl_array), gl_array, GL_STATIC_DRAW)

def get_gl_array(pylist):
    if isinstance(pylist[0], int):
        casttype = GLuint
    else:
        casttype = GLfloat

    array_type = casttype * len(pylist)
    return array_type(*pylist)

