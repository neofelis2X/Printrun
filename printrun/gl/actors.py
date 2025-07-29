# -*- coding: utf-8 -*-
# Copyright (C) 2013 Guillaume Seguin
# Copyright (C) 2011 Denis Kobozev
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import time
import array
import math
import logging
import threading
import numpy as np
from abc import ABC, abstractmethod

from ctypes import sizeof

from pyglet.gl import GLfloat, GLuint, \
                      GL_ARRAY_BUFFER, GL_ELEMENT_ARRAY_BUFFER, \
                      GL_UNSIGNED_INT, GL_TRIANGLES, GL_LINES, GL_CULL_FACE, \
                      glEnable, glDisable, glDrawArrays, glDrawElements, \
                      glDrawRangeElements, glBindVertexArray

from .mathutils import mat4_translation, mat4_rotation, mat4_scaling

from . import camera
from . import renderer

from printrun.utils import install_locale
install_locale("pronterface")

# for type hints
from typing import Union, Any, Tuple, List, Iterator, Optional
from printrun import stltool
from printrun import gcoder
Build_Dims = Tuple[int, int, int, int, int, int]


def triangulate_rectangle(i1: int, i2: int, i3: int, i4: int) -> List[int]:
    return [i1, i4, i3, i3, i2, i1]

def triangulate_box(i1: int, i2: int, i3: int, i4: int,
                    j1: int, j2: int, j3: int, j4: int) -> List[int]:
    return [i1, i2, j2, j2, j1, i1, i2, i3, j3, j3, j2, i2,
            i3, i4, j4, j4, j3, i3, i4, i1, j1, j1, j4, i4]

def high_luminance(bg_color: Tuple[float, float, float]) -> bool:
    '''Returns True (bright) or False (dark) based on the
    luminance (brightness) of the background.'''
    # Calcualte luminance of the current background color
    lum = 0.299 * bg_color[0] + 0.587 * bg_color[1] + 0.114 * bg_color[2]
    if lum > 0.5:  # Bright background
        return True
    return False

def blend_colors(color_a: Tuple[float, float, float],
                 color_b: Tuple[float, float, float], blend: float
                 ) -> Tuple[float, float, float, float]:
    r = color_a[0] * (1 - blend) + color_b[0] * blend
    g = color_a[1] * (1 - blend) + color_b[1] * blend
    b = color_a[2] * (1 - blend) + color_b[2] * blend
    return (r, g, b, 1.0)


class BoundingBox:
    """
    A rectangular box (cuboid) enclosing a 3D model, defined by lower and upper corners.
    """
    def __init__(self, upper_corner: Tuple[float, float, float],
                 lower_corner: Tuple[float, float, float]) -> None:
        self.upper_corner = upper_corner
        self.lower_corner = lower_corner

    @property
    def width(self) -> float:
        width = abs(self.upper_corner[0] - self.lower_corner[0])
        return round(width, 2)

    @property
    def depth(self) -> float:
        depth = abs(self.upper_corner[1] - self.lower_corner[1])
        return round(depth, 2)

    @property
    def height(self) -> float:
        height = abs(self.upper_corner[2] - self.lower_corner[2])
        return round(height, 2)


class ActorBaseClass(ABC):
    """
    Cursor where the mouse should be in 3D space.
    """
    shaderlist = {}

    def __init__(self) -> None:
        self.vao = GLuint(0)
        self.vbo = GLuint(0)
        self.ebo = GLuint(0)
        self.ubo = GLuint(0)
        self._modelmatrix = np.eye(4, dtype=np.float32, order='F')

    @property
    def modelmatrix(self) -> np.ndarray:
        return self._modelmatrix

    @abstractmethod
    def load(self, shader, ubo) -> None:
        ...

    @abstractmethod
    def draw(self) -> None:
        ...


class Platform(ActorBaseClass):
    """
    Platform grid on which models are placed.
    """

    COLOR_LIGHT = (172 / 255, 172 / 255, 172 / 255)
    COLOR_DARK = (64 / 255, 64 / 255, 64 / 255)

    def __init__(self, build_dimensions: Build_Dims,
                 light: bool = False,
                 circular: bool = False,
                 grid: Tuple[int, int] = (1, 10)) -> None:
        super().__init__()
        self.light = light
        self.is_circular = circular
        self.width = build_dimensions[0]
        self.depth = build_dimensions[1]
        self.height = build_dimensions[2]
        self.xoffset = build_dimensions[3]
        self.yoffset = build_dimensions[4]
        self.zoffset = build_dimensions[5]
        self.grid = grid

        self.color_minor = (*self.COLOR_DARK, 0.1)
        self.color_interm = (*self.COLOR_DARK, 0.2)
        self.color_major = (*self.COLOR_DARK, 0.33)

        self.vertices = ()
        self.indices = []
        self.color = ()
        self._initialise_data()

        self.loaded = True

    @property
    def modelmatrix(self):
        return self._modelmatrix

    def update_colour(self, bg_color: Tuple[float, float, float]) -> None:
        '''Update the color of the platform grid based on the
        luminance (brightness) of the background.'''
        if high_luminance(bg_color):
            base_color = self.COLOR_DARK  # Dark lines
        else:
            base_color = self.COLOR_LIGHT  # Bright lines

        self.color_minor = (*base_color, 0.1)
        self.color_interm = (*base_color, 0.2)
        self.color_major = (*base_color, 0.33)

        # This blends the grid colors with the background color into a
        # solid color without alpha. Current solution bares better results.
        # self.color_minor = blend_colors(bg_color, base_color, 0.1)
        # self.color_interm = blend_colors(bg_color, base_color, 0.2)
        # self.color_major = blend_colors(bg_color, base_color, 0.33)

        self._initialise_data()

    def _color(self, i: float) -> Tuple:
        if i % self.grid[1] == 0:
            return self.color_major
        if i % (self.grid[1] // 2) == 0:
            return self.color_interm
        if self.light:
            return ()
        return self.color_minor

    def _initialise_data(self) -> None:
        self._modelmatrix = mat4_translation(self.xoffset,
                                             self.yoffset,
                                             self.zoffset)
        if self.is_circular:
            self._load_circular()
        else:
            self._load_rectangular()

    def _update_vbo(self):
        vb = renderer.interleave_vertex_data(self.vertices, self.color,
                                             distinct_colors=True)
        renderer.fill_buffer(self.vbo, vb, GL_ARRAY_BUFFER)

    def load(self, shader, ubo) -> None:
        self.shaderlist = shader
        self.ubo = ubo
        self.vao, self.vbo, self.ebo = renderer.create_buffers(lines_only=True)
        renderer.fill_buffer(self.ebo, self.indices, GL_ELEMENT_ARRAY_BUFFER)
        self._update_vbo()

    def _origin_arrows(self) -> Tuple[float, float, float]:
        arrow_offset = self.width * 0.01
        arrow_side_length = self.width * 0.015
        arrow_height = arrow_side_length * 0.866

        return (arrow_offset, arrow_side_length, arrow_height)

    def _load_grid(self, z_val):
        vertices = []
        colors = []
        indices = []
        x_half = self.width / 2
        y_half = self.depth / 2

        # Grid lines in X
        vert_x = []
        col_x = []
        for x_val in np.arange(self.grid[0], int(math.ceil(x_half)),
                               self.grid[0], dtype=float):
            if self.is_circular:
                k_val = x_val / x_half
                y_val = y_half * math.sqrt(1 - (k_val * k_val))
            else:
                y_val = y_half

            col = self._color(x_val)
            if col:
                vert_x.append(((x_half + x_val, y_half + y_val, z_val),
                                 (x_half + x_val, y_half - y_val, z_val)))
                vert_x.append(((x_half - x_val, y_half + y_val, z_val),
                                 (x_half - x_val, y_half - y_val, z_val)))
                col_x.append((col, col))
                col_x.append((col, col))

        # Centerline
        vert_x.append(((x_half, 2 * y_half, z_val), (x_half, 0.0, z_val)))
        col_x.append((self.color_major, self.color_major))

        # Lines are sorted to avoid transparency rendering issues
        l = sorted(zip(vert_x, col_x))
        l.sort()
        vert_x, col_x = zip(*l)

        for duo in vert_x:
            vertices.append(duo[0])
            vertices.append(duo[1])

        for duo in col_x:
            colors.append(duo[0])
            colors.append(duo[1])

        # Grid lines in Y
        vert_y = []
        col_y = []
        for y_val in np.arange(self.grid[0], int(math.ceil(y_half)),
                               self.grid[0], dtype=float):
            if self.is_circular:
                k_val = y_val / y_half
                x_val = x_half * math.sqrt(1 - (k_val * k_val))
            else:
                x_val = x_half

            col = self._color(y_val)
            if col:
                vert_y.append(((x_half + x_val, y_half + y_val, z_val),
                              (x_half - x_val, y_half + y_val, z_val)))
                vert_y.append(((x_half + x_val, y_half - y_val, z_val),
                               (x_half - x_val, y_half - y_val, z_val)))
                col_y.append((col, col))
                col_y.append((col, col))

        # Centerline
        vert_y.append(((2 * x_half, y_half, z_val), (0.0, y_half, z_val)))
        col_y.append((self.color_major, self.color_major))

        # Lines are sorted to avoid transparency rendering issues
        l = sorted(zip(vert_y, col_y))
        l.sort()
        vert_y, col_y = zip(*l)

        for duo in vert_y:
            vertices.append(duo[0])
            vertices.append(duo[1])

        for duo in col_y:
            colors.append(duo[0])
            colors.append(duo[1])

        indices.extend(range(0, len(vertices)))

        return (vertices, indices, colors)

    def _load_circular(self):
        x_half = self.width / 2
        y_half = self.depth / 2
        z_height = -0.01

        # Grid
        vertices, indices, colors = self._load_grid(z_height)

        # Circle outline
        for deg in range(0, 361):
            rad = math.radians(deg)
            colors.append(self.color_major)
            vertices.append(((math.cos(rad) + 1) * x_half,
                             (math.sin(rad) + 1) * y_half,
                             z_height))
            if deg != 360:
                indices.extend((len(vertices) - 1, len(vertices)))

        # Triangle to indicate front
        ao, al, ah = self._origin_arrows()
        vertices.extend(((x_half, -ao, z_height),
                         (x_half - al / 2, -(ao + ah), z_height),
                         (x_half + al / 2, -(ao + ah), z_height)))
        colors.extend(3 * [self.color_major])
        idx = len(vertices)
        indices.extend((idx - 3, idx - 2, idx - 2, idx - 1, idx - 1, idx - 3))

        self.vertices = vertices
        self.indices = indices
        self.color = colors

    def _load_rectangular(self):
        z_height = -0.01
        # Grid
        vertices, indices, colors = self._load_grid(z_height)

        # Arrows at origin point
        ao, al, ah = self._origin_arrows()
        op_verts = [(ao / 4, -ao, z_height),
                   (ao / 4 + ah, -(ao + al / 2), z_height),
                   (ao / 4, -(ao + al), z_height),
                   (-ao, ao / 4, z_height),
                   (-(ao + al / 2), ao / 4 + ah, z_height),
                   (-(ao + al), ao / 4, z_height),
                   (0.0, -ao, z_height),
                   (0.0, -(ao + al), z_height),
                   (-ao, 0.0, z_height),
                   (-(ao + al), 0.0, z_height),
                   # Outline
                   (0.0, 0.0, z_height),
                   (0.0, self.depth, z_height),
                   (self.width, self.depth, z_height),
                   (self.width, 0.0, z_height)]

        op_cols = len(op_verts) * [self.color_major]

        rel_idxs = (0, 1, 1, 2, 2, 0,
                    3, 4, 4, 5, 5, 3,
                    6, 7, 8, 9,
                    10, 11, 11, 12, 12, 13, 13, 10)

        abs_idxs = [i + len(vertices) for i in rel_idxs]

        vertices.extend(op_verts)
        self.vertices = vertices
        indices.extend(abs_idxs)
        self.indices = indices
        colors.extend(op_cols)
        self.color = colors

    def draw(self) -> None:
        renderer.update_ubo_transform(self.ubo, self.modelmatrix)
        self.shaderlist["lines"].use()

        glBindVertexArray(self.vao)
        glDrawElements(GL_LINES, len(self.indices), GL_UNSIGNED_INT, 0)


class MouseCursor(ActorBaseClass):
    """
    Cursor where the mouse should be in 3D space.
    """
    def __init__(self) -> None:
        super().__init__()
        self.vertices: List[Tuple[float, float, float]] = []
        self.indices: List[int] = []
        self.color = (225 / 255, 0 / 255, 45 / 255, 1.0)  # Red
        self._initialise_data()

    @property
    def modelmatrix(self):
        return self._modelmatrix

    def update(self, position_3d: Tuple[float, float, float]) -> None:
        self._modelmatrix = mat4_translation(*position_3d)

    def load(self, shader, ubo) -> None:
        self.shaderlist = shader
        self.ubo = ubo
        self.vao, self.vbo, self.ebo = renderer.create_buffers()
        normal = np.array((0.0, 0.0, 1.0))
        vb = renderer.interleave_vertex_data(self.vertices, self.color, normal)
        renderer.fill_buffer(self.vbo, vb, GL_ARRAY_BUFFER)
        renderer.fill_buffer(self.ebo, self.indices, GL_ELEMENT_ARRAY_BUFFER)

    def _initialise_data(self) -> None:
        self.vertices, self.indices = self._circle()
        # self.vertices, self.indices = self._rectangle()

    def _circle(self) -> Tuple[List[Tuple[float, float, float]], List[int]]:
        radius = 2.0
        segments = 32  # Resolution of the circle.
        z_height = 0.025
        vertices = [(0.0, 0.0, z_height),  # this is the center point
                    (0.0, radius, z_height)]  # this is first point on the top
        indices: List[int] = []

        vert_n = 0
        for i in range(segments):
            alpha = -math.tau / segments * i
            new_x = radius * math.sin(alpha)
            new_y = radius * math.cos(alpha)
            # Add one new vertex coordinate
            vertices.append((new_x, new_y, z_height))
            vert_n = len(vertices) - 1
            # Add three new indices
            indices.extend((0, vert_n - 1, vert_n))
        # Add last triangle
        indices.extend((0, vert_n, 1))

        return (vertices, indices)

    def _rectangle(self) -> Tuple[List[Tuple[float, float, float]], List[int]]:
        half_a = 2.0  # Half of the rectangle side length
        z_height = 0.01

        vertices = [(half_a, half_a, z_height),
                    (-half_a, half_a, z_height),
                    (-half_a, -half_a, z_height),
                    (half_a, -half_a, z_height)]

        indices = [0, 1, 2,
                   2, 3, 0]

        return (vertices, indices)

    def draw(self) -> None:
        renderer.update_ubo_transform(self.ubo, self.modelmatrix)
        self.shaderlist["basic"].use()

        glDisable(GL_CULL_FACE)
        glBindVertexArray(self.vao)
        glDrawElements(GL_TRIANGLES, len(self.indices), GL_UNSIGNED_INT, 0)
        glEnable(GL_CULL_FACE)


class Focus(ActorBaseClass):
    """
    Outline around the currently active OpenGL panel.
    """

    COLOR_LIGHT = (205 / 255, 205 / 255, 205 / 255)
    COLOR_DARK = (15 / 255, 15 / 255, 15 / 255)

    def __init__(self, cam: camera.Camera) -> None:
        super().__init__()
        self.camera = cam
        self.vertices = ()
        self.indices = []
        self.color = (15 / 255, 15 / 255, 15 / 255, 0.6)  # Black Transparent
        self.is_initialised = False

    def load(self, shader, ubo) -> None:
        self.shaderlist = shader
        self.ubo = ubo
        self.vao, self.vbo, self.ebo = renderer.create_buffers(lines_only=True)

        self.is_initialised = True
        self.update_size()
        self.indices = [1, 0, 1, 2, 2, 3, 0, 3]
        renderer.fill_buffer(self.ebo, self.indices, GL_ELEMENT_ARRAY_BUFFER)

    def update_size(self) -> None:
        if not self.is_initialised:
            return

        # Starts at the lower left corner, x, y
        offset = 1.0 * self.camera.display_ppi_factor
        self.vertices = ((offset, offset, 0.0),
                         (self.camera.width - offset, offset, 0.0),
                         (self.camera.width - offset, self.camera.height - offset, 0.0),
                         (offset, self.camera.height - offset, 0.0))
        vs = renderer.interleave_vertex_data(self.vertices, self.color)
        renderer.fill_buffer(self.vbo, vs, GL_ARRAY_BUFFER)

    def update_colour(self, bg_color: Tuple[float, float, float]) -> None:
        '''Update the color of the focus based on the
        luminance (brightness) of the background.'''
        if high_luminance(bg_color):
            self.color = (*self.COLOR_DARK, 0.6)  # Dark Transparent
        else:
            self.color = (*self.COLOR_LIGHT, 0.4)  # Light Transparent
        self.update_size()

    def draw(self) -> None:
        renderer.update_ubo_transform(self.ubo, self.modelmatrix)
        self.shaderlist["lines"].use()
        sid = self.shaderlist["lines"].id
        renderer.load_uniform(sid, "u_is2d", True)
        renderer.load_uniform(sid, "u_isDashed", True)
        glBindVertexArray(self.vao)
        glDrawElements(GL_LINES, len(self.indices), GL_UNSIGNED_INT, 0)
        renderer.load_uniform(sid, "u_isDashed", False)
        renderer.load_uniform(sid, "u_is2d", False)


class CuttingPlane(ActorBaseClass):
    """
    A plane that indicates the axis and position
    on which the stl model will be cut.
    """
    def __init__(self, build_dimensions: Build_Dims) -> None:
        super().__init__()
        self.width = float(build_dimensions[0])
        self.depth = float(build_dimensions[1])
        self.height = float(build_dimensions[2])
        self.offsets = (float(build_dimensions[3]),
                        float(build_dimensions[4]),
                        float(build_dimensions[5]))

        self.axis = 'w'
        self.dist = 0.0
        self.cutting_direction = -1.0
        self.plane_mat = np.eye(4, dtype=GLfloat, order='C')

        self.vertices = ()
        self.indices = []
        self.color = (0 / 255, 229 / 255, 38 / 255, 0.3)  # Light Green
        self.color_outline = (0 / 255, 204 / 255, 38 / 255, 1.0)  # Green

    def load(self, shader, ubo) -> None:
        self.shaderlist = shader
        self.ubo = ubo
        self.vao, self.vbo, self.ebo = renderer.create_buffers()
        self.vertices = 2 * ((0.5, 0.5, 0.0),
                             (-0.5, 0.5, 0.0),
                             (-0.5, -0.5, 0.0),
                             (0.5, -0.5, 0.0))

        colors = 4 * [self.color] + 4 * [self.color_outline]
        normal = np.array((0.0, 0.0, 1.0))
        vb = renderer.interleave_vertex_data(self.vertices, colors, normal,
                                             distinct_colors=True)
        renderer.fill_buffer(self.vbo, vb, GL_ARRAY_BUFFER)

        self.indices = [0, 1, 2, 3, 0, 2,  # plane
                        6, 5, 5, 4, 4, 7, 7, 6]  # outline
        renderer.fill_buffer(self.ebo, self.indices, GL_ELEMENT_ARRAY_BUFFER)

    def update_plane(self, axis: str, cutting_direction: int) -> None:
        if self.axis == axis and self.cutting_direction == cutting_direction:
            return

        self.axis = axis
        self.cutting_direction = float(cutting_direction)

        if self.axis == 'x':
            if self.cutting_direction < 0.0:
                rm = mat4_rotation(0.0, 1.0, 0.0, 270.0)
            else:
                rm = mat4_rotation(0.0, 1.0, 0.0, 90.0)
            tm = mat4_translation(0.0, 0.5, 0.5)
            sm = mat4_scaling(1.0, self.depth, self.height)

        elif self.axis == 'y':
            if self.cutting_direction < 0.0:
                rm = mat4_rotation(1.0, 0.0, 0.0, 270.0)
            else:
                rm = mat4_rotation(1.0, 0.0, 0.0, 90.0)
            tm = mat4_translation(0.5, 0.0, 0.5)
            sm = mat4_scaling(self.width, 1.0, self.height)

        else:
            if self.cutting_direction < 0.0:
                rm = mat4_rotation(1.0, 0.0, 0.0, 180.0)
            else:
                rm = mat4_rotation(1.0, 0.0, 0.0, 0.0)
            tm = mat4_translation(0.5, 0.5, 0.0)
            sm = mat4_scaling(self.width, self.depth, 1.0)

        om = mat4_translation(*self.offsets)
        self.plane_mat = rm @ tm @ sm @ om

    def update_position(self, dist: float) -> None:
        self.dist = dist
        if self.dist is None:
            return

        if self.axis == 'x':
            tm = mat4_translation(self.dist, 0.0, 0.2)
        elif self.axis == 'y':
            tm = mat4_translation(0.0, self.dist, 0.2)
        else:
            tm = mat4_translation(0.0, 0.0, self.dist)

        self._modelmatrix = self.plane_mat @ tm

    def draw(self) -> None:
        if self.dist is None:
            return

        renderer.update_ubo_transform(self.ubo, self.modelmatrix)
        self.shaderlist["basic"].use()
        # Draw the plane
        glDisable(GL_CULL_FACE)
        glBindVertexArray(self.vao)
        glDrawElements(GL_TRIANGLES, 6, GL_UNSIGNED_INT, 0)

        # Draw the outline on the plane
        self.shaderlist["thicklines"].use()
        renderer.load_uniform(self.shaderlist["thicklines"].id,
                              "u_Thickness", 1.5)
        glDrawElements(GL_LINES, 8, GL_UNSIGNED_INT, 6 * sizeof(GLuint))
        glEnable(GL_CULL_FACE)


# TODO: It would be nice to have a visual representation of the printhead
# or the nozzle. Due to different printer configurations this would need
# to be adjustable by the user.


class MeshModel(ActorBaseClass):
    """
    Model geometries based on triangulated
    meshes such as .stl, .obj, .3mf etc.
    """
    def __init__(self, model: stltool.stl) -> None:
        super().__init__()
        self.color = (77 / 255, 178 / 255, 128 / 255, 1.0)  # Greenish
        self.indices = []
        self.meshdata = model

    def load(self, shader, ubo) -> None:
        self.shaderlist = shader
        self.ubo = ubo
        self.vao, self.vbo, self.ebo = renderer.create_buffers()
        self._initialise_data()
        self.update()

    def update(self):
        model = self.meshdata
        tm = mat4_translation(*model.offsets)
        rm = mat4_rotation(0.0, 0.0, 1.0, model.rot)
        tc = mat4_translation(*model.centeroffset)
        sm = mat4_scaling(*model.scale)

        self._modelmatrix = sm @ tc @ rm @ tm

    def _initialise_data(self) -> None:
        # Create the vertex and normal arrays.
        # TODO: The whole data pipeline here can surely be optimised.
        stride = 3 + 4 + 3
        vb = np.zeros(len(self.meshdata.facets) * 3 * stride, dtype=GLfloat)

        for i, facet in enumerate(self.meshdata.facets):
            iv = i * 3 * stride
            for j, vertex in enumerate(facet[1]):
                jv = iv + j * stride
                vb[jv:jv + 3] = vertex
                vb[jv + 3:jv + 7] = self.color
                vb[jv + 7:jv + 10] = facet[0]

        renderer.fill_buffer(self.vbo, vb, GL_ARRAY_BUFFER)

        # TODO: This is pointless, create proper indices for meshes
        self.indices = np.arange(vb.size // 10, dtype=GLuint)
        renderer.fill_buffer(self.ebo, self.indices.data, GL_ELEMENT_ARRAY_BUFFER)

    def draw(self) -> None:
        renderer.update_ubo_transform(self.ubo, self.modelmatrix)
        self.shaderlist["basic"].use()

        glBindVertexArray(self.vao)
        glDrawElements(GL_TRIANGLES, len(self.indices), GL_UNSIGNED_INT, 0)

    def delete(self) -> None:
        pass


class Model(ActorBaseClass):
    """
    Parent class for models that provides common functionality.
    """
    AXIS_X = (1, 0, 0)
    AXIS_Y = (0, 1, 0)
    AXIS_Z = (0, 0, 1)

    letter_axis_map = {
        'x': AXIS_X,
        'y': AXIS_Y,
        'z': AXIS_Z,
    }

    color_tool0 = (1.0, 0.0, 0.0, 1.0)
    color_tool1 = (1.0, 0.0, 0.0, 1.0)
    color_tool2 = (1.0, 0.0, 0.0, 1.0)
    color_tool3 = (1.0, 0.0, 0.0, 1.0)
    color_tool4 = (1.0, 0.0, 0.0, 1.0)
    color_travel = (1.0, 0.0, 0.0, 1.0)

    axis_letter_map = {(v, k) for k, v in letter_axis_map.items()}

    lock = threading.Lock()

    def __init__(self, offset_x: float = 0.0, offset_y: float = 0.0) -> None:
        super().__init__()
        self.offset_x = offset_x
        self.offset_y = offset_y
        self._bounding_box = None
        self.gcode: Optional[gcoder.GCode] = None

        self.vertices = np.zeros(0, dtype = GLfloat)
        self.colors = np.zeros(0, dtype = GLfloat)
        self.layers_loaded = 0
        self.initialized = False
        self.max_layers = 0
        self.num_layers_to_draw = 0
        self.dims = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        self.layer_idxs_map = {}
        self.layer_stops = [0]
        self.printed_until = -1
        self.only_current = False

        self.init_model_attributes()

    def init_model_attributes(self) -> None:
        """
        Set/reset saved properties.
        """
        self.invalidate_bounding_box()
        self.modified = False

    def invalidate_bounding_box(self) -> None:
        self._bounding_box = None

    @property
    def bounding_box(self) -> BoundingBox:
        """
        Get a bounding box for the model.
        """
        if self._bounding_box is None:
            self._bounding_box = self._calculate_bounding_box()
        return self._bounding_box

    def update(self, modelwrapper):
        model = modelwrapper
        tm = mat4_translation(*model.offsets)
        rm = mat4_rotation(0.0, 0.0, 1.0, model.rot)
        tc = mat4_translation(*model.centeroffset)
        sm = mat4_scaling(*model.scale)

        self._modelmatrix = sm @ tc @ rm @ tm

    def _calculate_bounding_box(self) -> BoundingBox:
        """
        Calculate an axis-aligned box enclosing the model.
        """
        # swap rows and columns in our vertex arrays so that we can do max and
        # min on axis 1
        xyz_rows = self.vertices.reshape(-1, order='F').reshape(3, -1)
        lower_corner = xyz_rows.min(1)
        upper_corner = xyz_rows.max(1)
        box = BoundingBox(upper_corner, lower_corner)
        return box

    @property
    def width(self) -> float:
        return self.bounding_box.width

    @property
    def depth(self) -> float:
        return self.bounding_box.depth

    @property
    def height(self) -> float:
        return self.bounding_box.height

    def movement_color(self, move) -> Tuple[float, float, float, float]:
        """
        Return the color to use for particular type of movement.
        """
        if move.extruding:
            if move.current_tool == 0:
                return self.color_tool0
            if move.current_tool == 1:
                return self.color_tool1
            if move.current_tool == 2:
                return self.color_tool2
            if move.current_tool == 3:
                return self.color_tool3
            return self.color_tool4

        return self.color_travel

def movement_angle(src: List[float], dst: List[float], precision: int = 0) -> float:
    x = dst[0] - src[0]
    y = dst[1] - src[1]
    angle = math.degrees(math.atan2(y, -x))  # negate x for clockwise rotation angle
    return round(angle, precision)

def get_next_move(gcode, layer_idx: int, gline_idx: int) -> Union[Any, None]:
    gline_idx += 1
    while layer_idx < len(gcode.all_layers):
        layer = gcode.all_layers[layer_idx]
        while gline_idx < len(layer):
            gline = layer[gline_idx]
            if gline.is_move:
                return gline
            gline_idx += 1
        layer_idx += 1
        gline_idx = 0
    return None

def interpolate_arcs(gline, prev_gline) -> Iterator[Tuple[Tuple[float, float, float], bool]]:
    if gline.command in ('G2', 'G3'):
        rx = gline.i if gline.i is not None else 0.0
        ry = gline.j if gline.j is not None else 0.0
        r = math.sqrt(rx*rx + ry*ry)

        cx = prev_gline.current_x + rx
        cy = prev_gline.current_y + ry

        a_start = math.atan2(-ry, -rx)
        dx = gline.current_x - cx
        dy = gline.current_y - cy
        a_end = math.atan2(dy, dx)
        a_delta = a_end - a_start

        if gline.command == "G3" and a_delta <= 0:
            a_delta += math.tau
        elif gline.command == "G2" and a_delta >= 0:
            a_delta -= math.tau

        z0 = prev_gline.current_z
        dz = gline.current_z - z0

        # max segment size: 0.5mm, max num of segments: 100
        segments = math.ceil(abs(a_delta) * r * 2 / 0.5)
        segments = min(segments, 100)

        for t in range(segments):
            a = t / segments * a_delta + a_start

            mid = ((
                cx + math.cos(a) * r,
                cy + math.sin(a) * r,
                z0 + t / segments * dz
            ), True)

            yield mid

    # last segment of this line
    yield ((gline.current_x, gline.current_y, gline.current_z), False)


class GcodeModel(Model):
    """
    Model for displaying Gcode data.
    """

    color_travel =  (0.8, 0.8, 0.8, 1.0)
    color_tool0 =   (1.0, 0.0, 0.0, 1.0)
    color_tool1 =   (0.67, 0.05, 0.9, 1.0)
    color_tool2 =   (1.0, 0.8, 0.0, 1.0)
    color_tool3 =   (1.0, 0.0, 0.62, 1.0)
    color_tool4 =   (0.0, 1.0, 0.58, 1.0)
    color_printed = (0.2, 0.75, 0.0, 1.0)
    color_current = (0.0, 0.9, 1.0, 1.0)
    color_current_printed = (0.1, 0.4, 0, 1.0)
    # TODO: Add this color to settings
    color_current_travel =  (0.8, 0.0, 1.0, 1.0)

    display_travels = True

    buffers_created = False
    loaded = False
    fully_loaded = False

    path_halfwidth = 0.2
    path_halfheight = 0.2

    def __init__(self):
        super().__init__()
        self.count_travel_indices = [0]
        self.count_print_indices = [0]
        self.count_print_vertices = [0]

        self.travels = np.zeros(0, dtype = GLfloat)
        self.indices = np.zeros(0, dtype = GLuint)
        self.travels_offset = 0

    def set_path_size(self, path_halfwidth: float, path_halfheight: float) -> None:
        with self.lock:
            self.path_halfwidth = path_halfwidth
            self.path_halfheight = path_halfheight

    def load_data(self, model_data: gcoder.GCode,
                  callback = None) -> Iterator[Union[int, None]]:
        t_start = time.time()
        self.gcode = model_data

        self.count_travel_indices = count_travel_indices = [0]
        self.count_print_indices = count_print_indices = [0]
        self.count_print_vertices = count_print_vertices = [0]

        # Some trivial computations, but that's mostly for documentation :)
        # Not like 10 multiplications are going to cost much time vs what's
        # about to happen :)

        # Max number of values which can be generated per gline
        # to store coordinates/colors/normals.
        coordspervertex = 3  # xyz components
        buffered_color_len = 4  # rgba components
        # xyz position + rgba color + xyz normal vector per vertex
        bufferlen_per_vertex = 2 * coordspervertex + buffered_color_len
        verticesperline = 2 * 4  # each end of the line has 4 vertices

        def coords_count(line_count: int) -> int:
            return line_count * verticesperline * bufferlen_per_vertex

        def travel_coords_count(line_count: int) -> int:
            travelverticesperline = 2
            # Normals are included to keep the memory layout the same
            return line_count * travelverticesperline * bufferlen_per_vertex

        trianglesperface = 2
        facesperbox = 4
        trianglesperbox = trianglesperface * facesperbox
        verticespertriangle = 3
        indicesperbox = verticespertriangle * trianglesperbox
        boxperline = 2
        indicesperline = indicesperbox * boxperline

        def indices_count(line_count: int) -> int:
            return line_count * indicesperline

        nlines = len(model_data)

        ncoords = coords_count(nlines)
        ntravelcoords = travel_coords_count(nlines)
        travel_attributes = np.array((*self.color_travel, 0.0, 0.0, 1.0))
        nindices = indices_count(nlines)

        vertices = self.vertices = np.zeros(ncoords, dtype = GLfloat)
        travel_vertices = self.travels = np.zeros(ntravelcoords, dtype = GLfloat)
        indices = self.indices = np.zeros(nindices, dtype = GLuint)
        vertex_k = 0  # amount of loaded vertices, one vertex has multiple vertex attributes
        travel_vertex_k = 0
        index_k = 0
        self.layer_idxs_map = {}
        self.layer_stops = [0]

        prev_move_normal_x = 0.0
        prev_move_normal_y = 0.0
        prev_move_angle = 0.0
        prev_pos = (0, 0, 0)
        prev_gline = None
        prev_extruding = False
        layer_idx = 0

        self.printed_until = 0
        self.only_current = False

        processed_lines = 0

        while layer_idx < len(model_data.all_layers):
            with self.lock:
                nlines = len(model_data)
                remaining_lines = nlines - processed_lines
                # Only reallocate memory which might be needed, not memory
                # for everything
                ncoords = coords_count(remaining_lines) + vertex_k * bufferlen_per_vertex
                ntravelcoords = travel_coords_count(remaining_lines) + travel_vertex_k * bufferlen_per_vertex
                nindices = indices_count(remaining_lines) + index_k
                if ncoords > vertices.size:
                    self.vertices.resize(ncoords, refcheck = False)
                    self.travels.resize(ntravelcoords, refcheck = False)
                    self.indices.resize(nindices, refcheck = False)
                layer = model_data.all_layers[layer_idx]
                has_movement = False
                for gline_idx, gline in enumerate(layer):
                    if not gline.is_move:
                        continue
                    if gline.x is None and gline.y is None \
                        and gline.z is None and gline.j is None \
                            and gline.i is None:
                        continue
                    has_movement = True
                    for (current_pos, interpolated) in interpolate_arcs(gline, prev_gline):
                        if not gline.extruding:
                            if self.travels.size < (travel_vertex_k * bufferlen_per_vertex + 2 * bufferlen_per_vertex):
                                # arc interpolation extra points allocation
                                # if the array is full, extend its size by +50%
                                logging.debug(_("GL: Reallocate GCode travel buffer %d -> %d") % \
                                              (self.travels.size, int(self.travels.size * 1.5)))

                                self.travels.resize(int(self.travels.size * 1.5),
                                                    refcheck = False)

                            buff_idx = travel_vertex_k * bufferlen_per_vertex
                            travel_vertices[buff_idx : buff_idx + 3] = prev_pos
                            travel_vertices[buff_idx + 3 : buff_idx + 10] = travel_attributes
                            travel_vertices[buff_idx + 10 : buff_idx + 13] = current_pos
                            travel_vertices[buff_idx + 13 : buff_idx + 20] = travel_attributes
                            travel_vertex_k += 2
                        else:
                            delta_x = current_pos[0] - prev_pos[0]
                            delta_y = current_pos[1] - prev_pos[1]
                            norm = delta_x * delta_x + delta_y * delta_y
                            if norm == 0:  # Don't draw anything if this move is Z+E only
                                continue
                            norm = math.sqrt(norm)
                            move_normal_x = - delta_y / norm
                            move_normal_y = delta_x / norm
                            move_angle = math.atan2(delta_y, delta_x)

                            # FIXME: compute these dynamically
                            path_halfwidth = self.path_halfwidth * 1.2
                            path_halfheight = self.path_halfheight * 1.2

                            new_indices = []
                            new_vertices = []
                            new_normals = []

                            def compute_vertices(move_x, move_y, new_verts, new_norms,
                                                 pos = prev_pos, divisor: float = 1.0,
                                                 path_hw: float = path_halfwidth,
                                                 path_hh: float = path_halfheight) -> None:

                                hw = path_hw / divisor
                                p1x = pos[0] - hw * move_x
                                p2x = pos[0] + hw * move_x
                                p1y = pos[1] - hw * move_y
                                p2y = pos[1] + hw * move_y
                                new_verts.extend((pos[0], pos[1], pos[2] + path_hh))
                                new_verts.extend((p1x, p1y, pos[2]))
                                new_verts.extend((pos[0], pos[1], pos[2] - path_hh))
                                new_verts.extend((p2x, p2y, pos[2]))
                                new_norms.extend((0.0, 0.0, 1.0))
                                new_norms.extend((-move_x, -move_y, 0.0))
                                new_norms.extend((0.0, 0.0, -1.0))
                                new_norms.extend((move_x, move_y, 0.0))

                            if prev_gline and prev_gline.extruding or prev_extruding:
                                # Store previous vertices indices
                                prev_id = vertex_k - 4
                                avg_move_normal_x = (prev_move_normal_x + move_normal_x) / 2
                                avg_move_normal_y = (prev_move_normal_y + move_normal_y) / 2
                                norm = avg_move_normal_x * avg_move_normal_x + \
                                       avg_move_normal_y * avg_move_normal_y
                                if norm == 0:
                                    avg_move_normal_x = move_normal_x
                                    avg_move_normal_y = move_normal_y
                                else:
                                    norm = math.sqrt(norm)
                                    avg_move_normal_x /= norm
                                    avg_move_normal_y /= norm
                                delta_angle = move_angle - prev_move_angle
                                delta_angle = (delta_angle + math.tau) % math.tau
                                fact = abs(math.cos(delta_angle / 2))
                                # If move is turning too much, avoid creating a big peak
                                # by adding an intermediate box
                                if fact < 0.5:
                                    compute_vertices(prev_move_normal_x, prev_move_normal_y,
                                                     new_vertices, new_normals)
                                    first = vertex_k
                                    # Link to previous
                                    new_indices += triangulate_box(prev_id, prev_id + 1,
                                                                prev_id + 2, prev_id + 3,
                                                                first, first + 1,
                                                                first + 2, first + 3)

                                    compute_vertices(move_normal_x, move_normal_y,
                                                     new_vertices, new_normals)
                                    prev_id += 4
                                    first += 4
                                    # Link to previous
                                    new_indices += triangulate_box(prev_id, prev_id + 1,
                                                                prev_id + 2, prev_id + 3,
                                                                first, first + 1,
                                                                first + 2, first + 3)
                                else:
                                    # Compute vertices
                                    compute_vertices(avg_move_normal_x, avg_move_normal_y,
                                                     new_vertices, new_normals, divisor = fact)
                                    first = vertex_k
                                    # Link to previous
                                    new_indices += triangulate_box(prev_id, prev_id + 1,
                                                                prev_id + 2, prev_id + 3,
                                                                first, first + 1,
                                                                first + 2, first + 3)
                            else:
                                # Compute vertices normal to the current move and cap it
                                compute_vertices(move_normal_x, move_normal_y,
                                                 new_vertices, new_normals)
                                first = vertex_k
                                new_indices = triangulate_rectangle(first, first + 1,
                                                                    first + 2, first + 3)

                            next_move = get_next_move(model_data, layer_idx, gline_idx)
                            next_is_extruding = interpolated or next_move and next_move.extruding
                            if not next_is_extruding:
                                # Compute caps and link everything
                                compute_vertices(move_normal_x, move_normal_y,
                                                 new_vertices, new_normals, pos = current_pos)
                                end_first = vertex_k + len(new_vertices) // 3 - 4

                                new_indices += triangulate_rectangle(end_first + 3,
                                                                     end_first + 2,
                                                                     end_first + 1,
                                                                     end_first)

                                new_indices += triangulate_box(first, first + 1,
                                                               first + 2, first + 3,
                                                               end_first,
                                                               end_first + 1,
                                                               end_first + 2,
                                                               end_first + 3)

                            if self.indices.size < (index_k + len(new_indices) +
                                                    100 * indicesperline):
                                # arc interpolation extra points allocation
                                ratio = (index_k + len(new_indices) +
                                         100 * indicesperline) / self.indices.size * 1.5

                                logging.debug(_("GL: Reallocate GCode print buffer %d -> %d") % \
                                              (self.vertices.size, int(self.vertices.size * ratio)))

                                self.vertices.resize(int(self.vertices.size * ratio),
                                                     refcheck = False)
                                self.indices.resize(int(self.indices.size * ratio),
                                                    refcheck = False)

                            for new_i, item in enumerate(new_indices):
                                indices[index_k + new_i] = item
                            index_k += len(new_indices)

                            new_vertices_len = len(new_vertices)
                            gline_color = self.movement_color(gline)[:buffered_color_len]

                            buff_idx = vertex_k * bufferlen_per_vertex
                            for i in range(0, new_vertices_len, 3):
                                vertices[buff_idx : buff_idx + 3] = new_vertices[i : i + 3]
                                vertices[buff_idx + 3 : buff_idx + 7] = gline_color
                                vertices[buff_idx + 7 : buff_idx + 10] = new_normals[i : i + 3]
                                buff_idx += bufferlen_per_vertex

                            vertex_k += new_vertices_len // 3
                            prev_move_normal_x = move_normal_x
                            prev_move_normal_y = move_normal_y
                            prev_move_angle = move_angle

                        prev_pos = current_pos
                        prev_extruding = gline.extruding

                    prev_gline = gline
                    prev_extruding = gline.extruding
                    count_print_indices.append(index_k)
                    count_print_vertices.append(vertex_k)
                    count_travel_indices.append(travel_vertex_k)
                    gline.gcview_end_vertex = len(count_print_indices) - 1

                if has_movement:
                    self.layer_stops.append(len(count_print_indices) - 1)
                    self.layer_idxs_map[layer_idx] = len(self.layer_stops) - 1
                    self.max_layers = len(self.layer_stops) - 1
                    self.num_layers_to_draw = self.max_layers + 1
                    self.initialized = False
                    self.loaded = True

            processed_lines += len(layer)

            if callback:
                callback(layer_idx + 1)

            yield layer_idx
            layer_idx += 1

        with self.lock:
            self.dims = ((model_data.xmin, model_data.xmax, model_data.width),
                         (model_data.ymin, model_data.ymax, model_data.depth),
                         (model_data.zmin, model_data.zmax, model_data.height))

            self.vertices.resize(vertex_k * bufferlen_per_vertex, refcheck = False)
            self.travels.resize(travel_vertex_k * bufferlen_per_vertex, refcheck = False)
            self.indices.resize(index_k, refcheck = False)

            self.layer_stops = array.array('L', self.layer_stops)
            self.count_travel_indices = array.array('L', count_travel_indices)
            self.count_print_indices = array.array('L', count_print_indices)
            self.count_print_vertices = array.array('L', count_print_vertices)

            self.max_layers = len(self.layer_stops) - 1
            self.num_layers_to_draw = self.max_layers + 1
            self.initialized = False
            self.loaded = True
            self.fully_loaded = True

        t_end = time.time()

        logging.debug(_('GL: Initialized GCode model in %.2f seconds') % (t_end - t_start))
        logging.debug(_('GL: GCode model vertex count: %d') % ((len(self.vertices) + len(self.travels)) // 10))
        yield None

    def copy(self) -> 'GcodeModel':
        copy = GcodeModel()
        for var in ["vertices", "travels", "indices",
                    "max_layers", "num_layers_to_draw", "printed_until",
                    "layer_stops", "dims", "only_current",
                    "layer_idxs_map", "count_travel_indices",
                    "count_print_indices", "count_print_vertices",
                    "path_halfwidth", "path_halfheight",
                    "gcode"]:
            setattr(copy, var, getattr(self, var))
        copy.loaded = True
        copy.fully_loaded = True
        copy.initialized = False
        return copy

    def update_colors(self) -> None:
        """Rebuild gl color buffer without loading. Used after color settings edit"""
        ncoords = self.count_print_vertices[-1]
        colors = np.empty(ncoords * 4, dtype = GLfloat)
        cur_vertex = 0
        gline_i = 1
        for gline in self.gcode.lines:
            if gline.gcview_end_vertex:
                gline_color = self.movement_color(gline)[:3]
                last_vertex = self.count_print_vertices[gline_i]
                gline_i += 1
                while cur_vertex < last_vertex:
                    colors[cur_vertex * 3 : cur_vertex * 3 + 3] = gline_color
                    cur_vertex += 1
        #if self.colors:
        #    pass
            #self.vertex_color_buffer.delete()
        # TODO: Find a solution to update the colors

    # ------------------------------------------------------------------------
    # DRAWING
    # ------------------------------------------------------------------------

    def load(self, shader, ubo) -> None:
        self.shaderlist = shader
        self.ubo = ubo
        self._modelmatrix = mat4_translation(self.offset_x, self.offset_y, 0.0)

        with self.lock:
            self.layers_loaded = self.max_layers
            self.initialized = True
            if not self.buffers_created:
                self.vao, self.vbo, self.ebo = renderer.create_buffers()
                self.buffers_created = True

            else:
                glBindVertexArray(self.vao)

            # TODO:
            # Create Buffer big enough for the whole model (size known?)
            # Fill data incremental, use offsets
            # When all model data loaded, add travel data

            self.travels_offset = self.vertices.size // 10
            vb_all = np.concatenate((self.vertices, self.travels))

            renderer.fill_buffer(self.vbo, vb_all, GL_ARRAY_BUFFER)
            renderer.fill_buffer(self.ebo, self.indices.data, GL_ELEMENT_ARRAY_BUFFER)

            if self.fully_loaded:
                # Delete numpy arrays after creating VBOs after full load
                self.vertices = np.zeros(0, dtype = GLfloat)
                self.travels = np.zeros(0, dtype = GLfloat)
                self.indices = np.zeros(0, dtype = GLuint)

    def draw(self) -> None:
        glBindVertexArray(self.vao)
        renderer.update_ubo_transform(self.ubo, self.modelmatrix)
        with self.lock:

            #self.display_travels = False
            if self.display_travels:
                self.shaderlist["lines"].use()
                self._display_travels()

            self.shaderlist["basic"].use()
            self._display_movements()

    def _display_travels(self) -> None:
        sid = self.shaderlist["lines"].id
        # Prevent race condition by using the number of currently loaded layers
        max_layers = self.layers_loaded
        end = self.layer_stops[min(self.num_layers_to_draw, max_layers)]
        end_index = self.count_travel_indices[end]

        # Draw current layer travels
        if self.num_layers_to_draw < max_layers:
            end_prev_layer = self.layer_stops[self.num_layers_to_draw - 1]
            start_index = self.count_travel_indices[end_prev_layer + 1]

            renderer.load_uniform(sid, "u_OverwriteColor", True)
            renderer.load_uniform(sid, "u_oColor",
                                  self.color_current_travel)

            glDrawArrays(GL_LINES, self.travels_offset + start_index,
                         end_index - start_index + 1)

            renderer.load_uniform(sid, "u_OverwriteColor", False)
            end_index = start_index

        # Draw all other visible travels
        if not self.only_current:
            glDrawArrays(GL_LINES, self.travels_offset, end_index - 1)

    def _draw_elements(self, start: int, end: int, draw_type = GL_TRIANGLES) -> None:
        # Don't attempt printing empty layer
        if self.count_print_indices[end] == self.count_print_indices[start - 1]:
            return
        glDrawRangeElements(draw_type,
                            self.count_print_vertices[start - 1],
                            self.count_print_vertices[end] - 1,
                            self.count_print_indices[end] - self.count_print_indices[start - 1],
                            GL_UNSIGNED_INT,
                            sizeof(GLuint) * self.count_print_indices[start - 1])

    def _display_movements(self) -> None:
        sid = self.shaderlist["basic"].id
        # Prevent race condition by using the number of currently loaded layers
        max_layers = self.layers_loaded

        start = 1
        layer_selected = self.num_layers_to_draw <= max_layers
        if layer_selected:
            end_prev_layer = self.layer_stops[self.num_layers_to_draw - 1]
        else:
            end_prev_layer = 0
        end = self.layer_stops[min(self.num_layers_to_draw, max_layers)]

        renderer.load_uniform(sid, "u_OverwriteColor", True)
        renderer.load_uniform(sid, "u_oColor", self.color_printed)

        # Draw printed stuff until end or end_prev_layer
        cur_end = min(self.printed_until, end)
        if not self.only_current:
            if 1 <= end_prev_layer <= cur_end:
                self._draw_elements(1, end_prev_layer)
            elif cur_end >= 1:
                self._draw_elements(1, cur_end)

        renderer.load_uniform(sid, "u_OverwriteColor", False)

        # Draw nonprinted stuff until end_prev_layer
        start = max(cur_end, 1)
        if end_prev_layer >= start:
            if not self.only_current:
                self._draw_elements(start, end_prev_layer)
            cur_end = end_prev_layer

        # Draw current layer
        if layer_selected:
            renderer.load_uniform(sid, "u_OverwriteColor", True)
            renderer.load_uniform(sid, "u_oColor", self.color_current_printed)

            if cur_end > end_prev_layer:
                self._draw_elements(end_prev_layer + 1, cur_end)

            renderer.load_uniform(sid, "u_oColor", self.color_current)

            if end > cur_end:
                self._draw_elements(cur_end + 1, end)

            renderer.load_uniform(sid, "u_OverwriteColor", False)

        # Draw non printed stuff until end (if not ending at a given layer)
        start = max(self.printed_until, 1)
        if not layer_selected and end >= start:
            self._draw_elements(start, end)


class GcodeModelLight(Model):
    """
    Model for displaying Gcode data.
    """

    color_travel =  (0.8, 0.8, 0.8, 1.0)
    color_tool0 =   (0.85, 0.0, 0.0, 0.6)
    color_tool1 =   (0.67, 0.05, 0.9, 0.6)
    color_tool2 =   (1.0, 0.8, 0.0, 0.6)
    color_tool3 =   (1.0, 0.0, 0.62, 0.6)
    color_tool4 =   (0.0, 1.0, 0.58, 0.6)
    color_printed = (0.15, 0.65, 0.0, 1.0)
    color_current = (0.0, 0.9, 1.0, 1.0)
    color_current_printed = (0.1, 0.4, 0.0, 1.0)

    buffers_created = False
    loaded = False
    fully_loaded = False

    def __init__(self):
        super().__init__()

    def load_data(self, model_data: gcoder.GCode,
                  callback = None) -> Iterator[Union[int, None]]:
        t_start = time.time()
        self.gcode = model_data

        self.layer_idxs_map = {}
        self.layer_stops = [0]

        prev_pos = (0, 0, 0)
        layer_idx = 0
        coord_per_line = 2 * 3  # 2x vertex with xyz coordinates
        channels_per_line = 2 * 4  # 2x vertex with rgba color
        nlines = len(model_data)
        vertices = self.vertices = np.zeros(nlines * coord_per_line, dtype = GLfloat)
        vertex_k = 0
        colors = self.colors = np.zeros(nlines * channels_per_line, dtype = GLfloat)
        color_k = 0
        self.printed_until = -1
        self.only_current = False
        prev_gline = None
        while layer_idx < len(model_data.all_layers):
            with self.lock:
                nlines = len(model_data)
                if nlines * coord_per_line > vertices.size:
                    self.vertices.resize(nlines * coord_per_line, refcheck = False)
                    self.colors.resize(nlines * channels_per_line, refcheck = False)
                layer = model_data.all_layers[layer_idx]
                has_movement = False
                for gline in layer:
                    if not gline.is_move:
                        continue
                    if gline.x is None and gline.y is None and gline.z is None:
                        continue

                    has_movement = True
                    for (current_pos, interpolated) in interpolate_arcs(gline, prev_gline):

                        if self.vertices.size < (vertex_k + 100 * coord_per_line):
                            # arc interpolation extra points allocation

                            ratio = (vertex_k + 100 * coord_per_line) / self.vertices.size * 1.5
                            self.vertices.resize(int(self.vertices.size * ratio), refcheck = False)
                            self.colors.resize(int(self.colors.size * ratio), refcheck = False)

                            logging.debug(_("GL: Reallocate GCode lite buffer %d -> %d") % \
                                          (self.vertices.size, int(self.vertices.size * ratio)))

                        vertices[vertex_k] = prev_pos[0]
                        vertices[vertex_k + 1] = prev_pos[1]
                        vertices[vertex_k + 2] = prev_pos[2]
                        vertices[vertex_k + 3] = current_pos[0]
                        vertices[vertex_k + 4] = current_pos[1]
                        vertices[vertex_k + 5] = current_pos[2]
                        vertex_k += coord_per_line

                        vertex_color = self.movement_color(gline)
                        colors[color_k] = vertex_color[0]
                        colors[color_k + 1] = vertex_color[1]
                        colors[color_k + 2] = vertex_color[2]
                        colors[color_k + 3] = vertex_color[3]
                        colors[color_k + 4] = vertex_color[0]
                        colors[color_k + 5] = vertex_color[1]
                        colors[color_k + 6] = vertex_color[2]
                        colors[color_k + 7] = vertex_color[3]
                        color_k += channels_per_line

                        prev_pos = current_pos
                        prev_gline = gline
                        gline.gcview_end_vertex = vertex_k // 3

                if has_movement:
                    self.layer_stops.append(vertex_k // 3)
                    self.layer_idxs_map[layer_idx] = len(self.layer_stops) - 1
                    self.max_layers = len(self.layer_stops) - 1
                    self.num_layers_to_draw = self.max_layers + 1
                    self.initialized = False
                    self.loaded = True

            if callback:
                callback(layer_idx + 1)

            yield layer_idx
            layer_idx += 1

        with self.lock:
            self.dims = ((model_data.xmin, model_data.xmax, model_data.width),
                         (model_data.ymin, model_data.ymax, model_data.depth),
                         (model_data.zmin, model_data.zmax, model_data.height))

            self.vertices.resize(vertex_k, refcheck = False)
            self.colors.resize(color_k, refcheck = False)
            self.max_layers = len(self.layer_stops) - 1
            self.num_layers_to_draw = self.max_layers + 1
            self.initialized = False
            self.loaded = True
            self.fully_loaded = True

        t_end = time.time()

        logging.debug(_('GL: Initialized GCode model lite in %.2f seconds') % (t_end - t_start))
        logging.debug(_('GL: GCode model lite vertex count: %d') % (len(self.vertices) // 3))
        yield None

    def update_colors(self) -> None:
        pass

    def copy(self) -> 'GcodeModelLight':
        copy = GcodeModelLight()
        for var in ["vertices", "colors", "max_layers",
                    "num_layers_to_draw", "printed_until",
                    "layer_stops", "dims", "only_current",
                    "layer_idxs_map", "gcode"]:
            setattr(copy, var, getattr(self, var))
        copy.loaded = True
        copy.fully_loaded = True
        copy.initialized = False
        return copy

    # ------------------------------------------------------------------------
    # DRAWING
    # ------------------------------------------------------------------------

    def load(self, shader, ubo) -> None:
        self.shaderlist = shader
        self.ubo = ubo
        self._modelmatrix = mat4_translation(self.offset_x, self.offset_y, 0.0)

        with self.lock:
            self.layers_loaded = self.max_layers
            self.initialized = True
            if not self.buffers_created:
                self.vao, self.vbo, _ = renderer.create_buffers(create_ebo=False,
                                                                lines_only=True)
                self.buffers_created = True
            else:
                glBindVertexArray(self.vao)

            # TODO: Indexed data would be nice to have?
            vb = renderer.interleave_vertex_data(self.vertices.reshape(-1, 3),
                                                 self.colors.reshape(-1, 4),
                                                 distinct_colors=True)
            renderer.fill_buffer(self.vbo, vb, GL_ARRAY_BUFFER)

            if self.fully_loaded:
                # Delete numpy arrays after creating VBOs after full load
                self.vertices = np.zeros(0, dtype=GLfloat)
                self.colors = np.zeros(0, dtype=GLfloat)


    def draw(self) -> None:
        renderer.update_ubo_transform(self.ubo, self.modelmatrix)
        self.shaderlist["lines"].use()

        glBindVertexArray(self.vao)
        with self.lock:
            self._display_movements()

    def _display_movements(self) -> None:
        sid = self.shaderlist["lines"].id

        # Prevent race condition by using the number of currently loaded layers
        max_layers = self.layers_loaded

        start = 0
        if self.num_layers_to_draw <= max_layers:
            end_prev_layer = self.layer_stops[self.num_layers_to_draw - 1]
        else:
            end_prev_layer = -1
        end = self.layer_stops[min(self.num_layers_to_draw, max_layers)]

        renderer.load_uniform(sid, "u_OverwriteColor", True)
        renderer.load_uniform(sid, "u_oColor", self.color_printed)

        # Draw printed stuff until end or end_prev_layer
        cur_end = min(self.printed_until, end)
        if not self.only_current:
            if 0 <= end_prev_layer <= cur_end:
                glDrawArrays(GL_LINES, start, end_prev_layer)
            elif cur_end >= 0:
                glDrawArrays(GL_LINES, start, cur_end)

        renderer.load_uniform(sid, "u_OverwriteColor", False)

        # Draw nonprinted stuff until end_prev_layer
        start = max(cur_end, 0)
        if end_prev_layer >= start:
            if not self.only_current:
                glDrawArrays(GL_LINES, start, end_prev_layer - start)
            cur_end = end_prev_layer

        # Draw current layer
        if end_prev_layer >= 0:
            self.shaderlist["thicklines"].use()
            sid = self.shaderlist["thicklines"].id

            renderer.load_uniform(sid, "u_Thickness", 2.0)
            renderer.load_uniform(sid, "u_OverwriteColor", True)
            renderer.load_uniform(sid, "u_oColor",
                                  self.color_current_printed)

            if cur_end > end_prev_layer:
                glDrawArrays(GL_LINES, end_prev_layer, cur_end - end_prev_layer)

            renderer.load_uniform(sid, "u_oColor",
                                  self.color_current)

            if end > cur_end:
                glDrawArrays(GL_LINES, cur_end, end - cur_end)

            renderer.load_uniform(sid, "u_OverwriteColor", False)

        # Draw non printed stuff until end (if not ending at a given layer)
        start = max(self.printed_until, 0)
        end = end - start
        if end_prev_layer < 0 < end and not self.only_current:
            glDrawArrays(GL_LINES, start, end)

