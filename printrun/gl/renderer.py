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

import logging
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
                      glUniformMatrix4fv, glUniform1i, glUniform4f, \
                      glUniform3f

# for type hints
from typing import Optional, Dict, List

SRC_VERT_BASIC = Path("printrun/assets/shader/basic.vert.glsl")
SRC_FRAG_BASIC = Path("printrun/assets/shader/basic.frag.glsl")
SRC_VERT_LINES = Path("printrun/assets/shader/lines.vert.glsl")
SRC_GEOM_LINES = Path("printrun/assets/shader/lines.geom.glsl")
SRC_FRAG_LINES = Path("printrun/assets/shader/lines.frag.glsl")


def load_shader() -> Optional[Dict[str, shader.ShaderProgram]]:
    shs = _compile_shaders(SRC_VERT_BASIC, SRC_FRAG_BASIC)
    if shs:
        vert_sh, frag_sh = shs[0], shs[1]
    else:
        return None

    try:
        basic_program = shader.ShaderProgram(vert_sh, frag_sh)
    except shader.ShaderException as e:
        logging.error("Error creating the 'basic' shader program: %s" % e)
        return None

    logging.debug("Successfully created the 'basic' shader program.")
    vert_sh.delete()
    frag_sh.delete()

    shs = _compile_shaders(SRC_VERT_LINES, SRC_FRAG_LINES, SRC_GEOM_LINES)
    if shs:
        vert_sh, frag_sh, geom_sh = shs[0], shs[1], shs[2]
    else:
        return None

    try:
        lines_program = shader.ShaderProgram(vert_sh, frag_sh, geom_sh)
    except shader.ShaderException as e:
        logging.error("Error creating the 'lines' shader program:%s" % e)
        return None

    logging.debug("Successfully created the 'lines' shader program.")
    vert_sh.delete()
    frag_sh.delete()
    geom_sh.delete()

    return {"basic": basic_program, "lines": lines_program}

def _compile_shaders(vert_src: Path, frag_src: Path,
                    geom_src: Optional[Path]=None
                     ) -> Optional[List[shader.Shader]]:

    new_shaders = []
    vert_shader = _compile_shader(vert_src, "vertex")
    new_shaders.append(vert_shader)
    frag_shader = _compile_shader(frag_src, "fragment")
    new_shaders.append(frag_shader)

    if geom_src:
        geom_shader = _compile_shader(geom_src, "geometry")
        new_shaders.append(geom_shader)

    for sh in new_shaders:
        if not sh:
            return None

    return new_shaders

def _compile_shader(src: Path, kind: shader.ShaderType) -> Optional[shader.Shader]:
    if not src.is_file():
        logging.error("Source file for %s shader is not available." % src.name)
        return None

    try:
        new_shader = shader.Shader(src.read_text(encoding="utf-8"), kind)
    except shader.ShaderException as e:
        logging.error("Error in %s shader:%s" % (kind, e))
        return None

    return new_shader

def load_mvp_uniform(shader_id, camera, actor):
    if actor.is_3d:
        mat = camera.projection @ camera.view @ actor.modelmatrix
        modelmat = actor.modelmatrix
    else:
        mat = camera.projection2d
        modelmat = np.identity(4, dtype=GLfloat)
    view = camera.eye

    location = glGetUniformLocation(shader_id, b"modelViewProjection")
    ptr = mat.ctypes.data_as(ctypes.POINTER(GLfloat))
    glUniformMatrix4fv(location, 1, GL_TRUE, ptr)

    location = glGetUniformLocation(shader_id, b"modelMat")
    ptr = modelmat.ctypes.data_as(ctypes.POINTER(GLfloat))
    glUniformMatrix4fv(location, 1, GL_TRUE, ptr)

    location = glGetUniformLocation(shader_id, b"viewPos")
    ptr = view.ctypes.data_as(ctypes.POINTER(GLfloat))
    glUniform3f(location, *view.data)


def load_uniform(shader_id, uniform_name: str, data):
    location = glGetUniformLocation(shader_id, uniform_name.encode())
    if location == -1:
        logging.warning("Could not find Uniform location.")
        return
    if uniform_name == "doOverwriteColor":
        glUniform1i(location, int(data))
    elif uniform_name == "oColor":
        glUniform4f(location, *data)

def interleave_vertex_data(verts, color, normal: Optional[np.ndarray]=None,
                           distinct_colors=False, distinct_normals=False):
    if isinstance(normal, np.ndarray) or normal:
        element_count = 3 + 4 + 3
    else:
        element_count = 3 + 4

    buffersize = len(verts) * element_count
    data = np.zeros(buffersize, dtype=GLfloat)

    for i, vertex in enumerate(verts):
        iv = i * element_count
        data[iv:iv + 3] = vertex
        if distinct_colors:
            data[iv + 3:iv + 7] = color[i]
        else:
            data[iv + 3:iv + 7] = color
        if isinstance(normal, np.ndarray) or normal:
            if distinct_normals:
                data[iv + 7:iv + 10] = normal[i]
            else:
                data[iv + 7:iv + 10] = normal

    return data

def create_buffers(create_ebo=True, lines_only=False):
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

    oc = 7 if lines_only else 10

    glEnableVertexAttribArray(0)  # Vertex position
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE,
                          oc * ctypes.sizeof(GLfloat), 0)
    glEnableVertexAttribArray(1)  # Vertex colour
    glVertexAttribPointer(1, 4, GL_FLOAT, GL_FALSE,
                          oc * ctypes.sizeof(GLfloat),
                          3 * ctypes.sizeof(GLfloat))
    if not lines_only:
        glEnableVertexAttribArray(2)  # Vertex normal direction
        glVertexAttribPointer(2, 3, GL_FLOAT, GL_FALSE,
                              oc * ctypes.sizeof(GLfloat),
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

