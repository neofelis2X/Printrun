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
                      GL_STATIC_DRAW, GL_FALSE, GL_TRUE, GL_UNIFORM_BUFFER, \
                      GL_DYNAMIC_DRAW, \
                      glGenVertexArrays, glBindVertexArray, glGenBuffers, \
                      glBindBuffer, glBufferData, glEnableVertexAttribArray, \
                      glVertexAttribPointer, glGetUniformLocation, \
                      glUniformMatrix4fv, glUniform1i, glUniform4f, \
                      glUniform3f, glGetUniformBlockIndex, glBindBufferRange, \
                      glUniformBlockBinding, glBufferSubData

# for type hints
from typing import Optional, Dict, List

SRC_SHADER_DIR = Path("printrun/assets/shader/")


def load_shader() -> Optional[Dict[str, shader.ShaderProgram]]:
    if not SRC_SHADER_DIR.is_dir():
        logging.error("Directory containing the \
        shader is not accessible.\nPath: %s" % SRC_SHADER_DIR.resolve())
        return None

    srcs = SRC_SHADER_DIR.glob("*.glsl")
    shader_kinds = {".vert": "vertex",
                    ".frag": "fragment",
                    ".geom": "geometry"}
    shs = {}
    for src in srcs:
        kind = shader_kinds[src.suffixes[0]]
        sh = _compile_shader(src, kind)
        if not sh:
            return None
        shs[src.stem] = sh

    try:
        basic_program = shader.ShaderProgram(shs["basic.vert"],
                                             shs["basic.frag"])
    except shader.ShaderException as e:
        logging.error("Error creating the 'basic' shader program: %s" % e)
        return None
    logging.debug("Successfully created the 'basic' shader program.")

    try:
        lines_program = shader.ShaderProgram(shs["lines.vert"],
                                             shs["lines.frag"])
    except shader.ShaderException as e:
        logging.error("Error creating the 'lines' shader program:%s" % e)
        return None
    logging.debug("Successfully created the 'lines' shader program.")

    try:
        thick_program = shader.ShaderProgram(shs["lines.vert"],
                                             shs["thicklines.geom"],
                                             shs["lines.frag"])
    except shader.ShaderException as e:
        logging.error("Error creating the 'thicklines' shader program:%s" % e)
        return None
    logging.debug("Successfully created the 'thicklines' shader program.")

    for sh in shs.values():
        sh.delete()

    return {"basic": basic_program,
            "lines": lines_program,
            "thicklines": thick_program}

def _compile_shader(src: Path, kind: str) -> Optional[shader.Shader]:
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
    modelmat = actor.modelmatrix
    location = glGetUniformLocation(shader_id, b"modelMat")
    ptr = modelmat.ctypes.data_as(ctypes.POINTER(GLfloat))
    glUniformMatrix4fv(location, 1, GL_TRUE, ptr)

    view = camera.eye
    location = glGetUniformLocation(shader_id, b"viewPos")
    ptr = view.ctypes.data_as(ctypes.POINTER(GLfloat))
    glUniform3f(location, *view.data)


def load_uniform(shader_id, uniform_name: str, data):
    location = glGetUniformLocation(shader_id, uniform_name.encode())
    if location == -1:
        logging.warning("Could not find Uniform location.")
        return

    if uniform_name in ("doOverwriteColor", "is_2d"):
        glUniform1i(location, int(data))
    elif uniform_name == "oColor":
        glUniform4f(location, *data)
    elif uniform_name == "viewPos":
        glUniform3f(location, *data.data)  # FIXME: looks strange
    elif uniform_name == "modelMat":
        ptr = data.ctypes.data_as(ctypes.POINTER(GLfloat))
        glUniformMatrix4fv(location, 1, GL_TRUE, ptr)

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

def create_ubo():
    """
    Creates a uniform buffer object
    """
    ubo = GLuint(0)
    bytesize = ctypes.sizeof(GLfloat)
    glGenBuffers(1, ubo)
    glBindBuffer(GL_UNIFORM_BUFFER, ubo)
    glBufferData(GL_UNIFORM_BUFFER, 32 * bytesize, None, GL_DYNAMIC_DRAW)
    glBindBuffer(GL_UNIFORM_BUFFER, 0)

    glBindBufferRange(GL_UNIFORM_BUFFER, 0, ubo, 0, 32 * bytesize)
    #glBindBufferRange(GL_UNIFORM_BUFFER, 1, ubo, 64 * bytesize, 8 * bytesize)

    return ubo

def bind_shader_ublock(shaderlist, ublock_name: str) -> None:
    ublock_index = GLuint(0)
    binding_point = 0
    byte_name = ublock_name.encode(encoding="utf-8")
    for sh in shaderlist.values():
        ublock_index = glGetUniformBlockIndex(sh.id, byte_name)
        glUniformBlockBinding(sh.id, ublock_index, binding_point)

def update_ubo_data(ubo, camera, ortho2d: bool=False):
    if ortho2d:
        mat = camera.projection2d
        mat = mat.T.copy()
        offset = mat.nbytes
    else:
        mat = camera.projection @ camera.view
        mat = mat.T.copy()
        offset = 0
    glBindBuffer(GL_UNIFORM_BUFFER, ubo)
    glBufferSubData(GL_UNIFORM_BUFFER, offset, mat.nbytes, mat.ctypes.data)
    glBindBuffer(GL_UNIFORM_BUFFER, 0)

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
    #glBindBuffer(kind, 0)

def get_gl_array(pylist):
    if isinstance(pylist[0], int):
        casttype = GLuint
    else:
        casttype = GLfloat

    array_type = casttype * len(pylist)
    return array_type(*pylist)

