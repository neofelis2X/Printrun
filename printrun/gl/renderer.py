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

from pyglet.gl import GLfloat, GLuint, GLintptr, GLsizeiptr, \
                      GL_ELEMENT_ARRAY_BUFFER, GL_FLOAT, GL_ARRAY_BUFFER, \
                      GL_STATIC_DRAW, GL_FALSE, GL_UNIFORM_BUFFER, \
                      GL_DYNAMIC_DRAW, GL_MAP_WRITE_BIT, GL_MAP_READ_BIT, \
                      glGenVertexArrays, glBindVertexArray, glGenBuffers, \
                      glBindBuffer, glBufferData, glEnableVertexAttribArray, \
                      glVertexAttribPointer, glGetUniformLocation, \
                      glUniformMatrix4fv, glUniform1i, glUniform1f, glUniform4f, \
                      glUniform3f, glGetUniformBlockIndex, glBindBufferRange, \
                      glUniformBlockBinding, glBufferSubData, glUniformMatrix3fv, \
                      glMapBufferRange, glUnmapBuffer, glDeleteBuffers, \
                      glDeleteVertexArrays

# for type hints
from typing import Optional, Dict

SRC_SHADER_DIR = Path("printrun/assets/shader/")


class MapBufferRange:
    def __init__(self, vao: GLuint, offset: int, size: int,
                 index_buffer: bool = False, read: bool = False):
        self.vao = vao
        self.offset = offset
        self.size = size
        self.target = GL_ELEMENT_ARRAY_BUFFER if index_buffer else GL_ARRAY_BUFFER
        self.access = GL_MAP_READ_BIT if read else GL_MAP_WRITE_BIT
        self.elementtype = GLuint if index_buffer else GLfloat

    def __enter__(self) -> Optional[np.ndarray]:
        glBindVertexArray(self.vao)
        # INFO: offset is given as actual BYTES in memory, as expected
        # size instead is given as elements (GLfloat or GLuint), maybe a quirk of pyglet?
        buffer_ptr = glMapBufferRange(self.target,
                                      GLintptr(self.offset * ctypes.sizeof(self.elementtype)),
                                      GLsizeiptr(self.size),
                                      self.access)

        if not buffer_ptr:
            logging.error("GL: glMapBuffer failed")
            return None

        float_ptr = ctypes.cast(buffer_ptr, ctypes.POINTER(self.elementtype))

        return np.ctypeslib.as_array(float_ptr, shape=(self.size,))

    def __exit__(self, exc_type, exc_value, exc_traceback) -> bool:
        result = glUnmapBuffer(self.target)
        glBindVertexArray(0)
        if not result:
            logging.warning("GL: glUnmapBuffer did not return successfully. Please consider reloading the model.")

        if exc_type:
            logging.exception("GL: Error in MapBufferRange",
                              exc_info=(exc_type, exc_value, exc_traceback))
            return True

        return False


#### SHADER ####
def load_shader() -> Optional[Dict[str, shader.ShaderProgram]]:
    if not SRC_SHADER_DIR.is_dir():
        logging.error("GL: Directory containing the \
        shader is not accessible.\nPath: %s" % SRC_SHADER_DIR.resolve())
        return None

    srcs = SRC_SHADER_DIR.glob("*.glsl")
    shader_kinds: dict[str, shader.ShaderType] = {".vert": "vertex",
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
        logging.error("GL: Error creating the 'basic' shader program: %s" % e)
        return None
    logging.debug("GL: Successfully created the 'basic' shader program.")

    try:
        lines_program = shader.ShaderProgram(shs["lines.vert"],
                                             shs["lines.frag"])
    except shader.ShaderException as e:
        logging.error("GL: Error creating the 'lines' shader program:%s" % e)
        return None
    logging.debug("GL: Successfully created the 'lines' shader program.")

    try:
        thick_program = shader.ShaderProgram(shs["lines.vert"],
                                             shs["thicklines.geom"],
                                             shs["thicklines.frag"])
    except shader.ShaderException as e:
        logging.error("GL: Error creating the 'thicklines' shader program:%s" % e)
        return None
    logging.debug("GL: Successfully created the 'thicklines' shader program.")

    for sh in shs.values():
        sh.delete()

    return {"basic": basic_program,
            "lines": lines_program,
            "thicklines": thick_program}

def _compile_shader(src: Path, kind: shader.ShaderType) -> Optional[shader.Shader]:
    if not src.is_file():
        logging.error("GL: Source file for %s shader is not available." % src.name)
        return None

    try:
        new_shader = shader.Shader(src.read_text(encoding="utf-8"), kind)
    except shader.ShaderException as e:
        logging.error("GL: Error in %s shader:%s" % (kind, e))
        return None

    return new_shader


#### BUFFER AND BUFFER DATA ####
def get_normal_mat(model_mat: np.ndarray) -> np.ndarray:
    sub = model_mat[0:3, 0:3]
    try:
        inv_mat = np.linalg.inv(sub)
    except np.linalg.LinAlgError as e:
        logging.warning("GL: Error inverting normal matrix: %s" % e)
        return sub
    # NOTE: inv() always returns np.float64
    return inv_mat.T.astype(np.float32, copy=False)

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
    # Orphan the buffer before refilling it
    glBufferData(kind, GLsizeiptr(ctypes.sizeof(gl_array)), None, GL_STATIC_DRAW)
    glBufferData(kind, GLsizeiptr(ctypes.sizeof(gl_array)), gl_array, GL_STATIC_DRAW)

def unload_buffers(vao: GLuint, vbo: GLuint, ebo: GLuint = GLuint(0)) -> None:
    glBindVertexArray(vao)

    glBindBuffer(GL_ARRAY_BUFFER, 0)
    glDeleteBuffers(1, vbo)
    vbo = GLuint(0)

    if ebo.value:
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0)
        glDeleteBuffers(1, ebo)
        ebo = GLuint(0)

    glBindVertexArray(0)
    glDeleteVertexArrays(1, vao)
    vao = GLuint(0)

    logging.debug("GL: Successfully deleted VAO %i, VBO %i, EBO %i",
                  vao, vbo, ebo)

def get_gl_array(pylist):
    if isinstance(pylist[0], int):
        casttype = GLuint
    else:
        casttype = GLfloat

    array_type = casttype * len(pylist)
    return array_type(*pylist)


### UNIFORMS ####
def load_uniform(shader_id, uniform_name: str, data):
    location = glGetUniformLocation(shader_id, uniform_name.encode())
    if location == -1:
        logging.warning("GL: Could not find Uniform location: %s" % uniform_name)
        return

    if isinstance(data, bool):
        glUniform1i(location, int(data))
    elif isinstance(data, float):
        glUniform1f(location, data)
    elif uniform_name == "u_oColor":
        glUniform4f(location, *data)

#### UNIFORM BUFFER OJECTS ####
# STD140 padding rules
vec3p = GLfloat * (3 + 1)
vec4p = GLfloat * 4
mat3p = vec4p * 3
mat4p = vec4p * 4

class GeneralUBOStruct(ctypes.Structure):
    _fields_ = [
            ("ViewProjection", mat4p),
            ("Ortho2dProjection", mat4p),
            ("ViewPos", vec3p),
            ("ViewportSize", vec3p),
            ("Transform", mat4p),
            ("NormalTransform", mat3p)
            ]

class UniformBuffer:
    def __init__(self):
        self.ubo = GLuint(0)
        self.data = GeneralUBOStruct()
        self.is_initialised = False

    def create_ubo(self):
        """
        Creates a uniform buffer object on the gpu
        """
        glGenBuffers(1, self.ubo)
        glBindBuffer(GL_UNIFORM_BUFFER, self.ubo)
        glBufferData(GL_UNIFORM_BUFFER, GLsizeiptr(ctypes.sizeof(self.data)), None, GL_DYNAMIC_DRAW)
        glBindBuffer(GL_UNIFORM_BUFFER, 0)

        glBindBufferRange(GL_UNIFORM_BUFFER, 0, self.ubo, GLintptr(0), GLsizeiptr(ctypes.sizeof(self.data)))
        self.is_initialised = True

    def _upload_field(self, name: str) -> None:
        """Push a single named field to the GPU."""
        field = getattr(GeneralUBOStruct, name)
        glBindBuffer(GL_UNIFORM_BUFFER, self.ubo)
        glBufferSubData(GL_UNIFORM_BUFFER,
                        GLintptr(field.offset),
                        GLsizeiptr(field.size),
                        ctypes.byref(self.data, field.offset))
        glBindBuffer(GL_UNIFORM_BUFFER, 0)

    @staticmethod
    def _set_mat(field, mat: np.ndarray, order: np._OrderKACF = 'F'):
        flat = mat.flatten(order=order).astype(np.float32, copy=False)
        assert flat.nbytes == ctypes.sizeof(field), \
        f"UBO field size {ctypes.sizeof(field)} != data {flat.nbytes}"

        ctypes.memmove(field, flat.ctypes.data, flat.nbytes)

    def update_view(self, camera):
        vp_mat = camera.projection @ camera.view
        self._set_mat(self.data.ViewProjection, vp_mat)
        self.data.ViewPos[:3] = camera.eye[:3]
        self._upload_field("ViewProjection")
        self._upload_field("ViewPos")

    def update_viewport(self, camera, viewport):
        self._set_mat(self.data.Ortho2dProjection, camera.projection2d)
        self.data.ViewportSize[:3] = viewport[:3]
        self._upload_field("Ortho2dProjection")
        self._upload_field("ViewportSize")

    def update_transform(self, transform_mat):
        self._set_mat(self.data.Transform, transform_mat)
        nm = get_normal_mat(transform_mat)  # 3x3
        # std140 mat3: each column padded to vec4, 4x3
        nm_padded = np.pad(nm, ((0, 1), (0, 0)), mode="constant")
        self._set_mat(self.data.NormalTransform, nm_padded)
        self._upload_field("Transform")
        self._upload_field("NormalTransform")

def bind_shader_ublock(shaderlist, ublock_name: str) -> None:
    ublock_index = GLuint(0)
    binding_point = 0
    byte_name = ublock_name.encode(encoding="utf-8")
    for sh in shaderlist.values():
        ublock_index = glGetUniformBlockIndex(sh.id, byte_name)
        glUniformBlockBinding(sh.id, ublock_index, binding_point)

