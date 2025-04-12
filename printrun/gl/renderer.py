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
from pyglet.graphics import shader

from pyglet.gl import GLfloat, GLuint, \
                      glEnable, glDisable, glGetFloatv, glLineWidth, \
                      glDrawArrays, glDrawRangeElements, \
                      GL_VERTEX_ARRAY, GL_ELEMENT_ARRAY_BUFFER, \
                      GL_UNSIGNED_INT, GL_FLOAT, GL_TRIANGLES, GL_LINES, \
                      GL_ARRAY_BUFFER, GL_STATIC_DRAW, GL_FALSE, GL_TRUE, \
                      GL_CULL_FACE, GL_LINE_SMOOTH, GL_LINE_WIDTH, \
                      glGenVertexArrays, glBindVertexArray, glGenBuffers, \
                      glBindBuffer, glBufferData, glEnableVertexAttribArray, \
                      glVertexAttribPointer, GL_UNSIGNED_INT, glDrawElements, \
                      glGetUniformLocation, glUniformMatrix4fv


def load_shader():
    vert_source = Path("printrun/assets/shader/basic.vert.glsl")
    frag_source = Path("printrun/assets/shader/basic.frag.glsl")

    vert_shader = shader.Shader(vert_source.read_text(encoding="utf-8"), 'vertex')
    frag_shader = shader.Shader(frag_source.read_text(encoding="utf-8"), 'fragment')

    shader_program = shader.ShaderProgram(vert_shader, frag_shader)

    vert_shader.delete()
    frag_shader.delete()

    return shader_program

def load_mvp_uniform(shader_id, camera, actor):
    if actor.is_3d:
        mat = camera.projection @ camera.view @ actor.modelmatrix
    else:
        mat = camera.projection2d

    location = glGetUniformLocation(shader_id, b"modelViewProjection")
    ptr = mat.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
    glUniformMatrix4fv(location, 1, GL_TRUE, ptr)

def interleave_vertex_data(verts, color):
    data = []
    for vertex in verts:
        data.extend(vertex)
        data.extend(color)

    return data

def create_buffers():
    """
    Creates and sets up VAO, VBO and EBO.
    Returns handles to VAO, VBO, EBO.
    """
    vao = GLuint(0)
    vbo = GLuint(0)
    ebo = GLuint(0)

    # Vertex array object
    glGenVertexArrays(1, vao)
    glBindVertexArray(vao)

    # Vertex buffer object
    glGenBuffers(1, vbo)
    glBindBuffer(GL_ARRAY_BUFFER, vbo)

    glEnableVertexAttribArray(0)  # Vertex position
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 7 * ctypes.sizeof(GLfloat), 0)
    glEnableVertexAttribArray(1)  # Vertex colour
    glVertexAttribPointer(1, 4, GL_FLOAT, GL_FALSE, 7 * ctypes.sizeof(GLfloat),
                          3 * ctypes.sizeof(GLfloat))

    # Index buffer object
    glGenBuffers(1, ebo)
    glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo)

    return vao, vbo, ebo

def fill_buffer(buffer, data, kind) -> None:
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

