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

from ctypes import sizeof

from pyglet.gl import GLfloat, GLuint, \
                      glEnable, glDisable, glGetFloatv, glLineWidth, \
                      glDrawArrays, glDrawRangeElements, \
                      GL_VERTEX_ARRAY, GL_ELEMENT_ARRAY_BUFFER, \
                      GL_UNSIGNED_INT, GL_TRIANGLES, GL_LINE_LOOP, \
                      GL_ARRAY_BUFFER, GL_STATIC_DRAW, GL_LINES, GL_FLOAT, \
                      GL_CULL_FACE, GL_LINE_SMOOTH, GL_LINE_WIDTH

# those are legacy calls which need to be replaced
from pyglet.gl import glPushMatrix, glPopMatrix, glMultMatrixd, \
                        glColor4f, glVertex3f, glBegin, glEnd, \
                        glVertexPointer, glColorPointer, glEnableClientState, \
                        glDisableClientState, glNormalPointer, glColor3f, \
                        glNormal3f, glLineStipple, \
                        GL_LINE_STIPPLE, GL_NORMAL_ARRAY, \
                        GL_LIGHTING, GL_COLOR_ARRAY

from .mathutils import mat4_translation, mat4_rotation, np_to_gl_mat

from pyglet.graphics.vertexbuffer import VertexBufferObject as BufferObject
from pyglet.graphics import Batch

from .camera import Camera

# for type hints
from typing import Union, Any, Tuple, List, Iterator
from ctypes import Array
from printrun.stltool import stl
from printrun.gcoder import GCode
Build_Dims = Tuple[int, int, int, int, int, int]

def vec(*args: float) -> Array:
    '''Returns an array of GLfloat values'''
    return (GLfloat * len(args))(*args)

def numpy2vbo(nparray: np.ndarray, target = GL_ARRAY_BUFFER,
              usage = GL_STATIC_DRAW) -> BufferObject:

    vbo = BufferObject(nparray.nbytes, usage=usage, target=target)
    vbo.bind()
    vbo.set_data(nparray.ctypes.data)
    return vbo

def triangulate_rectangle(i1: int, i2: int, i3: int, i4: int) -> List[int]:
    return [i1, i4, i3, i3, i2, i1]

def triangulate_box(i1: int, i2: int, i3: int, i4: int,
                    j1: int, j2: int, j3: int, j4: int) -> List[int]:
    return [i1, i2, j2, j2, j1, i1, i2, i3, j3, j3, j2, i2,
            i3, i4, j4, j4, j3, i3, i4, i1, j1, j1, j4, i4]


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


class Platform:
    """
    Platform grid on which models are placed.
    """

    def __init__(self, build_dimensions: Build_Dims,
                 light: bool = False,
                 circular: bool = False,
                 grid: Tuple[int, int] = (1, 10)) -> None:
        self.light = light
        self.is_circular = circular
        self.width = build_dimensions[0]
        self.depth = build_dimensions[1]
        self.height = build_dimensions[2]
        self.xoffset = build_dimensions[3]
        self.yoffset = build_dimensions[4]
        self.zoffset = build_dimensions[5]
        self.grid = grid

        self.color_minor = (15 / 255, 15 / 255, 15 / 255, 0.1)
        self.color_interm = (15 / 255, 15 / 255, 15 / 255, 0.2)
        self.color_major = (15 / 255, 15 / 255, 15 / 255, 0.33)

        self.vertices = ()
        self.indices = ()
        self.colors = ()
        self._initialise_data()

        self.loaded = True

    def update_colour(self, bg_color: Tuple[float, float, float]) -> None:
        '''Update the colour of the focus based on the
        luminance (brightness) of the background.'''
        # Calcualte luminance of the current background colour
        lum = 0.299 * bg_color[0] + 0.587 * bg_color[1] + 0.114 * bg_color[2]
        if lum > 0.5:
            # Dark lines
            base_color = (64 / 255, 64 / 255, 64 / 255)
        else:
            # Bright lines
            base_color = (172 / 255, 172 / 255, 172 / 255)

        self.color_minor = (*base_color, 0.1)
        self.color_interm = (*base_color, 0.2)
        self.color_major = (*base_color, 0.33)

        self._initialise_data()

    def _color(self, i: float) -> tuple:
        if i % self.grid[1] == 0:
            return self.color_major
        if i % (self.grid[1] // 2) == 0:
            return self.color_interm
        if self.light:
            return ()
        return self.color_minor

    def _get_transformation(self) -> Array:
        mat = mat4_translation(self.xoffset, self.yoffset, self.zoffset)
        return np_to_gl_mat(mat)

    def _initialise_data(self):
        if self.is_circular:
            self._load_circular()
        else:
            self._load_rectangular()

    def _origin_arrows(self) -> tuple[float, float, float]:
        arrow_offset = self.width * 0.01
        arrow_side_length = self.width * 0.015
        arrow_height = arrow_side_length * 0.866

        return (arrow_offset, arrow_side_length, arrow_height)

    def _load_grid(self):
        vertices = []
        indices = []
        colors = []
        x_half = self.width / 2
        y_half = self.depth / 2

        # Grid lines in X
        for x_val in np.arange(self.grid[0], int(math.ceil(x_half)), self.grid[0], dtype=float):
            if self.is_circular:
                k_val = x_val / x_half
                y_val = y_half * math.sqrt(1 - (k_val * k_val))
            else:
                y_val = y_half

            col = self._color(x_val)
            if col:
                colors.extend(4 * [col])
                vertices.append((x_half + x_val, y_half + y_val, 0.0))
                vertices.append((x_half + x_val, y_half - y_val, 0.0))
                vertices.append((x_half - x_val, y_half + y_val, 0.0))
                vertices.append((x_half - x_val, y_half - y_val, 0.0))

        # Grid lines in Y
        for y_val in np.arange(self.grid[0], int(math.ceil(y_half)), self.grid[0], dtype=float):
            if self.is_circular:
                k_val = y_val / y_half
                x_val = x_half * math.sqrt(1 - (k_val * k_val))
            else:
                x_val = x_half

            col = self._color(y_val)
            if col:
                colors.extend(4 * [col])
                vertices.append((x_half + x_val, y_half + y_val, 0.0))
                vertices.append((x_half - x_val, y_half + y_val, 0.0))
                vertices.append((x_half + x_val, y_half - y_val, 0.0))
                vertices.append((x_half - x_val, y_half - y_val, 0.0))

        # Center lines
        colors.extend(4 * [self.color_major])
        vertices.append((2 * x_half, y_half, 0.0))
        vertices.append((0.0, y_half, 0.0))
        vertices.append((x_half, 2 * y_half, 0.0))
        vertices.append((x_half, 0.0, 0.0))

        indices.extend(range(0, len(vertices)))

        return (vertices, indices, colors)

    def _load_circular(self):
        x_half = self.width / 2
        y_half = self.depth / 2

        # Grid
        vertices, indices, colors = self._load_grid()

        # Circle outline
        for deg in range(0, 361):
            rad = math.radians(deg)
            colors.append(self.color_major)
            vertices.append(((math.cos(rad) + 1) * x_half,
                             (math.sin(rad) + 1) * y_half,
                             0.0))
            if deg != 360:
                indices.extend((len(vertices) - 1, len(vertices)))

        # Triangle to indicate front
        ao, al, ah = self._origin_arrows()
        vertices.extend(((x_half, -ao, 0.0),
                         (x_half - al / 2, -(ao + ah), 0.0),
                         (x_half + al / 2, -(ao + ah), 0.0)))
        colors.extend(3 * [self.color_major])
        idx = len(vertices)
        indices.extend((idx - 3, idx - 2, idx - 2, idx - 1, idx - 1, idx - 3))

        self.vertices = vertices
        self.indices = indices
        self.colors = colors

    def _load_rectangular(self):
        # Grid
        vertices, indices, colors = self._load_grid()

        # Arrows at origin point
        ao, al, ah = self._origin_arrows()
        op_verts = [(ao / 4, -ao, 0.0),
                   (ao / 4 + ah, -(ao + al / 2), 0.0),
                   (ao / 4, -(ao + al), 0.0),
                   (-ao, ao / 4, 0.0),
                   (-(ao + al / 2), ao / 4 + ah, 0.0),
                   (-(ao + al), ao / 4, 0.0),
                   (0.0, -ao, 0.0),
                   (0.0, -(ao + al), 0.0),
                   (-ao, 0.0, 0.0),
                   (-(ao + al), 0.0, 0.0),
                   # Outline
                   (0.0, 0.0, 0.0),
                   (0.0, self.depth, 0.0),
                   (self.width, self.depth, 0.0),
                   (self.width, 0.0, 0.0)]

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
        self.colors = colors

    def draw(self) -> None:
        glPushMatrix()
        glMultMatrixd(self._get_transformation())

        # draw the grid
        glDisable(GL_LIGHTING)

        glBegin(GL_LINES)
        for index in self.indices:
            glColor4f(*self.colors[index])
            glVertex3f(*self.vertices[index])
        glEnd()

        glPopMatrix()
        glEnable(GL_LIGHTING)


class MouseCursor:
    """
    Cursor where the mouse should be in 3D space.
    """
    def __init__(self) -> None:
        self.colour = (225 / 255, 0 / 255, 45 / 255, 1.0)  # Red
        self.position = (0.0, 0.0, 0.0)
        self.vertices = []
        self.indices = []
        self._prepare_data()

    def update_position(self, position_3d: Tuple[float, float, float]) -> None:
        self.position = position_3d

    def _prepare_data(self) -> None:
        self.vertices, self.indices = self._circle()
        #self.vertices, self.indices = self._rectangle()

    def _circle(self) -> Tuple[List[Tuple[float, float, float]], List[int]]:
        radius = 2.0
        segments = 24  #  Resolution of the circle.
        z_value = 0.02
        vertices = [(0.0, 0.0, z_value),  # this is the center point
                    (0.0, radius, z_value)]  # this is first point on the top
        indices = []

        vert_n = 0
        for i in range(segments):
            alpha = 2 * math.pi / segments * i
            new_x = radius * math.sin(alpha)
            new_y = radius * math.cos(alpha)
            # Add one new vertex coordinate
            vertices.append((new_x, new_y, z_value))
            vert_n = len(vertices) - 1
            # Add three new indices
            indices.extend((0, vert_n - 1, vert_n))
        # Add last triangle
        indices.extend((0, vert_n, 1))

        return (vertices, indices)

    def _rectangle(self) -> Tuple[List[Tuple[float, float, float]], List[int]]:
        half_a = 2.0  # Half of the rectangle side length
        z_value = 0.02

        vertices = [(half_a, half_a, z_value),
                    (-half_a, half_a, z_value),
                    (-half_a, -half_a, z_value),
                    (half_a, -half_a, z_value)]

        indices = [0, 1, 2,
                   2, 3, 0]

        return (vertices, indices)

    def _get_transformation(self) -> Array:
        mat = mat4_translation(*self.position)
        return np_to_gl_mat(mat)

    def draw(self) -> None:
        glPushMatrix()

        glMultMatrixd(self._get_transformation())

        glDisable(GL_CULL_FACE)

        glColor4f(*self.colour)
        glNormal3f(0, 0, 1)

        glBegin(GL_TRIANGLES)
        for index in self.indices:
            glVertex3f(*self.vertices[index])
        glEnd()

        glEnable(GL_CULL_FACE)
        glPopMatrix()


class Focus:
    """
    Outline around the currently active OpenGL panel.
    """
    def __init__(self, camera: Camera) -> None:
        self.colour = (15 / 255, 15 / 255, 15 / 255, 0.6)  # Black Transparent
        self.camera = camera
        self.vertices = ()
        self.indices = ()
        self._prepare_data()

    def _prepare_data(self) -> None:
        # Starts at the lower left corner, x, y
        offset = 2.0 * self.camera.display_ppi_factor
        self.vertices = ((offset, offset, 0.0),
                         (self.camera.width - offset, offset, 0.0),
                         (self.camera.width - offset, self.camera.height - offset, 0.0),
                         (offset, self.camera.height - offset, 0.0))
        self.indices = (0, 1, 1, 2, 2, 3, 3, 0)

    def update_size(self) -> None:
        self._prepare_data()

    def update_colour(self, bg_colour: Tuple[float, float, float]) -> None:
        '''Update the colour of the focus based on the
        luminance (brightness) of the background.'''
        # Calcualte luminance of the current background colour
        lum = 0.299 * bg_colour[0] + 0.587 * bg_colour[1] + 0.114 * bg_colour[2]
        if lum > 0.5:
            self.colour = (15 / 255, 15 / 255, 15 / 255, 0.6)  # Dark Transparent
        else:
            self.colour = (205 / 255, 205 / 255, 205 / 255, 0.4)  # Light Transparent

    def draw(self) -> None:
        self.camera.create_pseudo2d_matrix()

        glDisable(GL_LIGHTING)
        # Draw a stippled line around the vertices
        glLineStipple(1, 0xff00)
        glColor4f(*self.colour)
        glEnable(GL_LINE_STIPPLE)

        glBegin(GL_LINES)
        for index in self.indices:
            glVertex3f(*self.vertices[index])
        glEnd()

        glDisable(GL_LINE_STIPPLE)
        glEnable(GL_LIGHTING)

        self.camera.revert_pseudo2d_matrix()


class CuttingPlane:
    """
    A plane that indicates the axis and position
    on which the stl model will be cut.
    """
    def __init__(self, build_dimensions: Build_Dims) -> None:
        self.width = build_dimensions[0]
        self.depth = build_dimensions[1]
        self.height = build_dimensions[2]

        self.colour = (0 / 255, 229 / 255, 38 / 255, 0.3)  # Light Green
        self.colour_outline = (0 / 255, 204 / 255, 38 / 255, 1.0)  # Green
        self.axis = ''
        self.dist = 0.0
        self.cutting_direction = -1
        self.plane_width = 0.0
        self.plane_height = 0.0

    def update(self, axis: str, cutting_direction: int, dist: float) -> None:
        self.axis = axis
        self.cutting_direction = cutting_direction
        self.dist = dist
        self._set_plane_dimensions(self.axis)

    def _set_plane_dimensions(self, cutting_axis: str) -> None:
        cutting_plane_sizes = {"x": (self.depth, self.height),
                               "y": (self.width, self.height),
                               "z": (self.width, self.depth)}
        self.plane_width, self.plane_height = cutting_plane_sizes[cutting_axis]

    def _get_transformation(self) -> Array:

        if self.axis == "x":
            rm1 = mat4_rotation(0.0, 1.0, 0.0, 90.0)
            rm2 = mat4_rotation(0.0, 0.0, 1.0, 90.0)
            tm = mat4_translation(0.0, 0.0, self.dist)
            mat = tm @ rm2 @ rm1
        elif self.axis == "y":
            rm = mat4_rotation(1.0, 0.0, 0.0, 90.0)
            tm = mat4_translation(0.0, 0.0, -self.dist)
            mat = tm @ rm
        elif self.axis == "z":
            mat = mat4_translation(0.0, 0.0, self.dist)
        else:
            mat = np.identity(4)

        return np_to_gl_mat(mat)

    def draw(self) -> None:
        if self.dist is None:
            return

        glPushMatrix()
        glMultMatrixd(self._get_transformation())

        glDisable(GL_CULL_FACE)
        # Draw the plane
        glBegin(GL_TRIANGLES)
        glColor4f(*self.colour)
        glNormal3f(0, 0, self.cutting_direction)
        glVertex3f(self.plane_width, self.plane_height, 0)
        glVertex3f(0, self.plane_height, 0)
        glVertex3f(0, 0, 0)
        glVertex3f(self.plane_width, 0, 0)
        glVertex3f(self.plane_width, self.plane_height, 0)
        glVertex3f(0, 0, 0)
        glEnd()
        glEnable(GL_CULL_FACE)
        glEnable(GL_LINE_SMOOTH)
        # Save the current linewidth and insert a new value
        orig_linewidth = (GLfloat)()
        glGetFloatv(GL_LINE_WIDTH, orig_linewidth)
        glLineWidth(4.0)
        # Draw the outline on the plane
        glBegin(GL_LINE_LOOP)
        glColor4f(*self.colour_outline)
        glVertex3f(0, 0, 0)
        glVertex3f(0, self.plane_height, 0)
        glVertex3f(self.plane_width, self.plane_height, 0)
        glVertex3f(self.plane_width, 0, 0)
        glEnd()
        # Restore the original linewidth
        glLineWidth(orig_linewidth)
        glDisable(GL_LINE_SMOOTH)
        glPopMatrix()


'''
# TODO: A 3D printhead vis is currently not implemented. Would be nice to have.
class PrintHead:
    """
    A representation of the printhead.
    This is currently not used.
    """
    def __init__(self) -> None:
        self.color = (43 / 255, 0.0, 175 / 255, 1.0)
        self.scale = 5
        self.height = 5

        self.initialized = False
        self.loaded = True
        self.display_list = None

    def init(self) -> None:
        self.display_list = compile_display_list(self.draw)
        self.initialized = True

    def draw(self) -> None:
        glPushMatrix()

        glBegin(GL_LINES)
        glColor3f(*self.color[:-1])
        for di in [-1, 1]:
            for dj in [-1, 1]:
                glVertex3f(0, 0, 0)
                glVertex3f(self.scale * di, self.scale * dj, self.height)
        glEnd()

        glPopMatrix()

    def display(self, mode_2d: bool = False) -> None:
        glEnable(GL_LINE_SMOOTH)
        orig_linewidth = (GLfloat)()
        glGetFloatv(GL_LINE_WIDTH, orig_linewidth)
        glLineWidth(3.0)
        glCallList(self.display_list)
        glLineWidth(orig_linewidth)
        glDisable(GL_LINE_SMOOTH)
'''


class MeshModel:
    """
    Model geometries based on triangulated
    meshes such as .stl, .obj, .3mf etc.
    """
    def __init__(self, model: stl) -> None:
        self.colour = (77 / 255, 178 / 255, 128 / 255, 1.0)  # Greenish
        # Every model is placed into it's own batch.
        # This is not ideal, but good enough for the moment.
        self.batch = Batch()
        self.vl = None
        self._fill_batch(model)

    def _fill_batch(self, model: stl) -> None:
        # Create the vertex and normal arrays.
        vertices = []
        normals = []

        for facet in model.facets:
            for coords in facet[1]:
                vertices.extend(coords)
                normals.extend(facet[0])

        """
        if hasattr(model, 'indices') and model.indices:
            # Some file formats provide indexed vertices,
            # which is more efficient for rendering
            self.vertex_list = self.batch.add_indexed(len(vertices) // 3,
                                                GL_TRIANGLES,
                                                None,  # group
                                                model.indices,
                                                ('v3f/static', vertices),
                                                ('n3f/static', normals),
                                                ('c3f/static', self.colour[:-1] * (len(vertices) // 3)))
        """

        self.vl = self.batch.add(len(vertices) // 3,
                                GL_TRIANGLES,
                                None,  # group
                                ('v3f/static', vertices),
                                ('n3f/static', normals),
                                ('c3f/static', self.colour[:-1] * (len(vertices) // 3)))

        model.batch = self.batch  # type: ignore

    def delete(self) -> None:
        if self.vl:
            self.vl.delete()

    def draw(self) -> None:
        if self.vl:
            self.vl.draw(GL_TRIANGLES)


class Model:
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

    def __init__(self, offset_x: float = 0.0, offset_y: float = 0.0) -> None:
        self.offset_x = offset_x
        self.offset_y = offset_y
        self._bounding_box = None

        self.lock = threading.Lock()

        self.init_model_attributes()

        self.vertices = np.zeros(0, dtype = GLfloat)

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
            a_delta += math.pi * 2
        elif gline.command == "G2" and a_delta >= 0:
            a_delta -= math.pi * 2

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

    color_travel = (0.6, 0.6, 0.6, 0.6)
    color_tool0 = (1.0, 0.0, 0.0, 1.0)
    color_tool1 = (0.67, 0.05, 0.9, 1.0)
    color_tool2 = (1.0, 0.8, 0., 1.0)
    color_tool3 = (1.0, 0., 0.62, 1.0)
    color_tool4 = (0., 1.0, 0.58, 1.0)
    color_printed = (0.2, 0.75, 0, 1.0)
    color_current = (0, 0.9, 1.0, 1.0)
    color_current_printed = (0.1, 0.4, 0, 1.0)

    display_travels = True

    buffers_created = False
    loaded = False
    fully_loaded = False

    path_halfwidth = 0.2
    path_halfheight = 0.2

    def set_path_size(self, path_halfwidth: float, path_halfheight: float) -> None:
        with self.lock:
            self.path_halfwidth = path_halfwidth
            self.path_halfheight = path_halfheight

    def load_data(self, model_data: GCode, callback = None) -> Iterator[Union[int, None]]:
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
        # Nicely enough we have 3 per kind of thing for all kinds.
        coordspervertex = 3
        buffered_color_len = 3  # 4th color component (alpha) is ignored
        verticesperline = 8
        coordsperline = coordspervertex * verticesperline

        def coords_count(line_count: int) -> int:
            return line_count * coordsperline

        travelverticesperline = 2
        travelcoordsperline = coordspervertex * travelverticesperline

        def travel_coords_count(line_count: int) -> int:
            return line_count * travelcoordsperline

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

        ntravelcoords = travel_coords_count(nlines)
        ncoords = coords_count(nlines)
        nindices = indices_count(nlines)

        travel_vertices = self.travels = np.zeros(ntravelcoords, dtype = GLfloat)
        travel_vertex_k = 0
        vertices = self.vertices = np.zeros(ncoords, dtype = GLfloat)
        vertex_k = 0
        colors = self.colors = np.zeros(ncoords, dtype = GLfloat)

        color_k = 0
        normals = self.normals = np.zeros(ncoords, dtype = GLfloat)
        indices = self.indices = np.zeros(nindices, dtype = GLuint)
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
                ntravelcoords = travel_coords_count(remaining_lines) + travel_vertex_k
                ncoords = coords_count(remaining_lines) + vertex_k
                nindices = indices_count(remaining_lines) + index_k
                if ncoords > vertices.size:
                    self.travels.resize(ntravelcoords, refcheck = False)
                    self.vertices.resize(ncoords, refcheck = False)
                    self.colors.resize(ncoords, refcheck = False)
                    self.normals.resize(ncoords, refcheck = False)
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
                            if self.travels.size < (travel_vertex_k + 100 * 6):
                                # arc interpolation extra points allocation
                                # if not enough room for another 100 points now,
                                # allocate enough and 50% extra to minimize separate allocations
                                ratio = (travel_vertex_k + 100 * 6) / self.travels.size * 1.5
                                logging.debug("gl realloc travel %d -> %d" % \
                                              (self.travels.size, int(self.travels.size * ratio)))
                                self.travels.resize(int(self.travels.size * ratio),
                                                    refcheck = False)

                            travel_vertices[travel_vertex_k : travel_vertex_k+3] = prev_pos
                            travel_vertices[travel_vertex_k + 3 : travel_vertex_k + 6] = current_pos
                            travel_vertex_k += 6
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
                                new_norms.extend((0, 0, 1))
                                new_norms.extend((-move_x, -move_y, 0))
                                new_norms.extend((0, 0, -1))
                                new_norms.extend((move_x, move_y, 0))

                            if prev_gline and prev_gline.extruding or prev_extruding:
                                # Store previous vertices indices
                                prev_id = vertex_k // 3 - 4
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
                                delta_angle = (delta_angle + 2 * math.pi) % (2 * math.pi)
                                fact = abs(math.cos(delta_angle / 2))
                                # If move is turning too much, avoid creating a big peak
                                # by adding an intermediate box
                                if fact < 0.5:
                                    compute_vertices(prev_move_normal_x, prev_move_normal_y,
                                                     new_vertices, new_normals)
                                    first = vertex_k // 3
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
                                    first = vertex_k // 3
                                    # Link to previous
                                    new_indices += triangulate_box(prev_id, prev_id + 1,
                                                                prev_id + 2, prev_id + 3,
                                                                first, first + 1,
                                                                first + 2, first + 3)
                            else:
                                # Compute vertices normal to the current move and cap it
                                compute_vertices(move_normal_x, move_normal_y,
                                                 new_vertices, new_normals)
                                first = vertex_k // 3
                                new_indices = triangulate_rectangle(first, first + 1,
                                                                    first + 2, first + 3)

                            next_move = get_next_move(model_data, layer_idx, gline_idx)
                            next_is_extruding = interpolated or next_move and next_move.extruding
                            if not next_is_extruding:
                                # Compute caps and link everything
                                compute_vertices(move_normal_x, move_normal_y,
                                                 new_vertices, new_normals, pos = current_pos)
                                end_first = vertex_k // 3 + len(new_vertices) // 3 - 4

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
                                logging.debug("gl realloc print %d -> %d" % \
                                              (self.vertices.size, int(self.vertices.size * ratio)))
                                self.vertices.resize(int(self.vertices.size * ratio),
                                                     refcheck = False)
                                self.colors.resize(int(self.colors.size * ratio),
                                                   refcheck = False)
                                self.normals.resize(int(self.normals.size * ratio),
                                                    refcheck = False)
                                self.indices.resize(int(self.indices.size * ratio),
                                                    refcheck = False)

                            for new_i, item in enumerate(new_indices):
                                indices[index_k + new_i] = item
                            index_k += len(new_indices)

                            new_vertices_len = len(new_vertices)
                            vertices[vertex_k : vertex_k + new_vertices_len] = new_vertices
                            normals[vertex_k : vertex_k + new_vertices_len] = new_normals
                            vertex_k += new_vertices_len

                            new_vertices_count = new_vertices_len // coordspervertex
                            # settings support alpha (transparency), but it is ignored here
                            gline_color = self.movement_color(gline)[:buffered_color_len]
                            for vi in range(new_vertices_count):
                                colors[color_k : color_k + buffered_color_len] = gline_color
                                color_k += buffered_color_len

                            prev_move_normal_x = move_normal_x
                            prev_move_normal_y = move_normal_y
                            prev_move_angle = move_angle

                        prev_pos = current_pos
                        prev_extruding = gline.extruding

                    prev_gline = gline
                    prev_extruding = gline.extruding
                    count_travel_indices.append(travel_vertex_k // 3)
                    count_print_indices.append(index_k)
                    count_print_vertices.append(vertex_k // 3)
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

            self.travels.resize(travel_vertex_k, refcheck = False)
            self.vertices.resize(vertex_k, refcheck = False)
            self.colors.resize(color_k, refcheck = False)
            self.normals.resize(vertex_k, refcheck = False)
            self.indices.resize(index_k, refcheck = False)

            self.layer_stops = array.array('L', self.layer_stops)
            self.count_travel_indices = array.array('L', count_travel_indices)
            self.count_print_indices = array.array('L', count_print_indices)
            self.count_print_vertices = array.array('L', count_print_vertices)

            self.max_layers = len(self.layer_stops) - 1
            self.num_layers_to_draw = self.max_layers + 1
            self.loaded = True
            self.initialized = False
            self.loaded = True
            self.fully_loaded = True

        t_end = time.time()

        logging.debug('Initialized 3D visualization in %.2f seconds' % (t_end - t_start))
        logging.debug('Vertex count: %d' % ((len(self.vertices) + len(self.travels)) // 3))
        yield None

    def copy(self) -> 'GcodeModel':
        copy = GcodeModel()
        for var in ["vertices", "colors", "travels", "indices", "normals",
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
        colors = np.empty(ncoords * 3, dtype = GLfloat)
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
        if self.vertex_color_buffer:
            self.vertex_color_buffer.delete()
        self.vertex_color_buffer = numpy2vbo(colors)

    # ------------------------------------------------------------------------
    # DRAWING
    # ------------------------------------------------------------------------

    def init(self) -> None:
        with self.lock:
            self.layers_loaded = self.max_layers
            self.initialized = True
            if self.buffers_created:
                self.travel_buffer.delete()
                self.index_buffer.delete()
                self.vertex_buffer.delete()
                self.vertex_color_buffer.delete()
                self.vertex_normal_buffer.delete()
            self.travel_buffer = numpy2vbo(self.travels)
            self.index_buffer = numpy2vbo(self.indices,
                                          target = GL_ELEMENT_ARRAY_BUFFER)
            self.vertex_buffer = numpy2vbo(self.vertices)
            self.vertex_color_buffer = numpy2vbo(self.colors)
            self.vertex_normal_buffer = numpy2vbo(self.normals)
            if self.fully_loaded:
                # Delete numpy arrays after creating VBOs after full load
                self.travels = np.zeros(0, dtype = GLfloat)
                self.indices = np.zeros(0, dtype = GLuint)
                self.vertices = np.zeros(0, dtype = GLfloat)
                self.colors = np.zeros(0, dtype = GLfloat)
                self.normals = np.zeros(0, dtype = GLfloat)
            self.buffers_created = True

    def _get_transformation(self) -> Array:
        mat = mat4_translation(self.offset_x, self.offset_y, 0.0)
        return np_to_gl_mat(mat)

    def display(self, mode_2d: bool = False) -> None:
        with self.lock:
            glPushMatrix()
            glMultMatrixd(self._get_transformation())

            glEnableClientState(GL_VERTEX_ARRAY)

            if self.display_travels:
                self._display_travels()

            glEnable(GL_LIGHTING)
            glEnableClientState(GL_NORMAL_ARRAY)
            glEnableClientState(GL_COLOR_ARRAY)

            self._display_movements()

            glDisable(GL_LIGHTING)

            glDisableClientState(GL_COLOR_ARRAY)
            glDisableClientState(GL_VERTEX_ARRAY)
            glDisableClientState(GL_NORMAL_ARRAY)

            glPopMatrix()

    def _display_travels(self) -> None:
        self.travel_buffer.bind()
        glVertexPointer(3, GL_FLOAT, 0, self.travel_buffer.ptr)

        # Prevent race condition by using the number of currently loaded layers
        max_layers = self.layers_loaded
        # TODO: show current layer travels in a different color
        end = self.layer_stops[min(self.num_layers_to_draw, max_layers)]
        end_index = self.count_travel_indices[end]
        glColor4f(*self.color_travel)
        if self.only_current:
            if self.num_layers_to_draw < max_layers:
                end_prev_layer = self.layer_stops[self.num_layers_to_draw - 1]
                start_index = self.count_travel_indices[end_prev_layer + 1]
                glDrawArrays(GL_LINES, start_index, end_index - start_index + 1)
        else:
            glDrawArrays(GL_LINES, 0, end_index)

        self.travel_buffer.unbind()

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
        self.vertex_buffer.bind()
        glVertexPointer(3, GL_FLOAT, 0, self.vertex_buffer.ptr)

        self.vertex_color_buffer.bind()
        glColorPointer(3, GL_FLOAT, 0, self.vertex_color_buffer.ptr)

        self.vertex_normal_buffer.bind()
        glNormalPointer(GL_FLOAT, 0, self.vertex_normal_buffer.ptr)

        # Pyglet 2.0: target=GL_ELEMENT_ARRAY_BUFFER
        self.index_buffer.bind()

        # Prevent race condition by using the number of currently loaded layers
        max_layers = self.layers_loaded

        start = 1
        layer_selected = self.num_layers_to_draw <= max_layers
        if layer_selected:
            end_prev_layer = self.layer_stops[self.num_layers_to_draw - 1]
        else:
            end_prev_layer = 0
        end = self.layer_stops[min(self.num_layers_to_draw, max_layers)]

        glDisableClientState(GL_COLOR_ARRAY)

        glColor3f(*self.color_printed[:-1])

        # Draw printed stuff until end or end_prev_layer
        cur_end = min(self.printed_until, end)
        if not self.only_current:
            if 1 <= end_prev_layer <= cur_end:
                self._draw_elements(1, end_prev_layer)
            elif cur_end >= 1:
                self._draw_elements(1, cur_end)

        glEnableClientState(GL_COLOR_ARRAY)

        # Draw nonprinted stuff until end_prev_layer
        start = max(cur_end, 1)
        if end_prev_layer >= start:
            if not self.only_current:
                self._draw_elements(start, end_prev_layer)
            cur_end = end_prev_layer

        # Draw current layer
        if layer_selected:
            glDisableClientState(GL_COLOR_ARRAY)

            glColor3f(*self.color_current_printed[:-1])

            if cur_end > end_prev_layer:
                self._draw_elements(end_prev_layer + 1, cur_end)

            glColor3f(*self.color_current[:-1])

            if end > cur_end:
                self._draw_elements(cur_end + 1, end)

            glEnableClientState(GL_COLOR_ARRAY)

        # Draw non printed stuff until end (if not ending at a given layer)
        start = max(self.printed_until, 1)
        if not layer_selected and end >= start:
            self._draw_elements(start, end)

        self.index_buffer.unbind()
        self.vertex_buffer.unbind()
        self.vertex_color_buffer.unbind()
        self.vertex_normal_buffer.unbind()

class GcodeModelLight(Model):
    """
    Model for displaying Gcode data.
    """

    color_travel = (0.6, 0.6, 0.6, 0.6)
    color_tool0 = (1.0, 0.0, 0.0, 0.6)
    color_tool1 = (0.67, 0.05, 0.9, 0.6)
    color_tool2 = (1.0, 0.8, 0., 0.6)
    color_tool3 = (1.0, 0., 0.62, 0.6)
    color_tool4 = (0., 1.0, 0.58, 0.6)
    color_printed = (0.2, 0.75, 0, 0.6)
    color_current = (0, 0.9, 1.0, 0.8)
    color_current_printed = (0.1, 0.4, 0, 0.8)

    buffers_created = False
    loaded = False
    fully_loaded = False

    gcode = None

    def load_data(self, model_data: GCode, callback = None) -> Iterator[Union[int, None]]:
        t_start = time.time()
        self.gcode = model_data

        self.layer_idxs_map = {}
        self.layer_stops = [0]

        prev_pos = (0, 0, 0)
        layer_idx = 0
        nlines = len(model_data)
        vertices = self.vertices = np.zeros(nlines * 6, dtype = GLfloat)
        vertex_k = 0
        colors = self.colors = np.zeros(nlines * 8, dtype = GLfloat)
        color_k = 0
        self.printed_until = -1
        self.only_current = False
        prev_gline = None
        while layer_idx < len(model_data.all_layers):
            with self.lock:
                nlines = len(model_data)
                if nlines * 6 > vertices.size:
                    self.vertices.resize(nlines * 6, refcheck = False)
                    self.colors.resize(nlines * 8, refcheck = False)
                layer = model_data.all_layers[layer_idx]
                has_movement = False
                for gline in layer:
                    if not gline.is_move:
                        continue
                    if gline.x is None and gline.y is None and gline.z is None:
                        continue

                    has_movement = True
                    for (current_pos, interpolated) in interpolate_arcs(gline, prev_gline):

                        if self.vertices.size < (vertex_k + 100 * 6):
                            # arc interpolation extra points allocation
                            ratio = (vertex_k + 100 * 6) / self.vertices.size * 1.5
                            logging.debug("gl realloc lite %d -> %d" % \
                                          (self.vertices.size, int(self.vertices.size * ratio)))
                            self.vertices.resize(int(self.vertices.size * ratio), refcheck = False)
                            self.colors.resize(int(self.colors.size * ratio), refcheck = False)

                        vertices[vertex_k] = prev_pos[0]
                        vertices[vertex_k + 1] = prev_pos[1]
                        vertices[vertex_k + 2] = prev_pos[2]
                        vertices[vertex_k + 3] = current_pos[0]
                        vertices[vertex_k + 4] = current_pos[1]
                        vertices[vertex_k + 5] = current_pos[2]
                        vertex_k += 6

                        vertex_color = self.movement_color(gline)
                        colors[color_k] = vertex_color[0]
                        colors[color_k + 1] = vertex_color[1]
                        colors[color_k + 2] = vertex_color[2]
                        colors[color_k + 3] = vertex_color[3]
                        colors[color_k + 4] = vertex_color[0]
                        colors[color_k + 5] = vertex_color[1]
                        colors[color_k + 6] = vertex_color[2]
                        colors[color_k + 7] = vertex_color[3]
                        color_k += 8

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

        logging.debug('Initialized 3D visualization in %.2f seconds' % (t_end - t_start))
        logging.debug('Vertex count: %d' % (len(self.vertices) // 3))
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

    def init(self) -> None:
        with self.lock:
            self.layers_loaded = self.max_layers
            self.initialized = True
            if self.buffers_created:
                self.vertex_buffer.delete()
                self.vertex_color_buffer.delete()
            self.vertex_buffer = numpy2vbo(self.vertices)
            # each pair of vertices shares the color
            self.vertex_color_buffer = numpy2vbo(self.colors)
            if self.fully_loaded:
                # Delete numpy arrays after creating VBOs after full load
                self.vertices = np.zeros(0, dtype = GLfloat)
                self.colors = np.zeros(0, dtype = GLfloat)
            self.buffers_created = True

    def _get_transformation(self) -> Array:
        mat = mat4_translation(self.offset_x, self.offset_y, 0.0)
        return np_to_gl_mat(mat)

    def display(self, mode_2d: bool = False) -> None:
        with self.lock:
            glPushMatrix()
            glMultMatrixd(self._get_transformation())

            glEnableClientState(GL_VERTEX_ARRAY)
            glEnableClientState(GL_COLOR_ARRAY)

            self._display_movements(mode_2d)

            glDisableClientState(GL_COLOR_ARRAY)
            glDisableClientState(GL_VERTEX_ARRAY)
            glPopMatrix()

    def _display_movements(self, mode_2d: bool = False) -> None:
        self.vertex_buffer.bind()
        glVertexPointer(3, GL_FLOAT, 0, None)

        self.vertex_color_buffer.bind()
        glColorPointer(4, GL_FLOAT, 0, None)

        # Prevent race condition by using the number of currently loaded layers
        max_layers = self.layers_loaded

        start = 0
        if self.num_layers_to_draw <= max_layers:
            end_prev_layer = self.layer_stops[self.num_layers_to_draw - 1]
        else:
            end_prev_layer = -1
        end = self.layer_stops[min(self.num_layers_to_draw, max_layers)]

        glDisableClientState(GL_COLOR_ARRAY)

        glColor4f(*self.color_printed)

        # Draw printed stuff until end or end_prev_layer
        cur_end = min(self.printed_until, end)
        if not self.only_current:
            if 0 <= end_prev_layer <= cur_end:
                glDrawArrays(GL_LINES, start, end_prev_layer)
            elif cur_end >= 0:
                glDrawArrays(GL_LINES, start, cur_end)

        glEnableClientState(GL_COLOR_ARRAY)

        # Draw nonprinted stuff until end_prev_layer
        start = max(cur_end, 0)
        if end_prev_layer >= start:
            if not self.only_current:
                glDrawArrays(GL_LINES, start, end_prev_layer - start)
            cur_end = end_prev_layer

        # Draw current layer
        if end_prev_layer >= 0:
            glDisableClientState(GL_COLOR_ARRAY)

            # Backup & increase line width
            orig_linewidth = (GLfloat)()
            glGetFloatv(GL_LINE_WIDTH, orig_linewidth)
            glLineWidth(2.0)

            glColor4f(*self.color_current_printed)

            if cur_end > end_prev_layer:
                glDrawArrays(GL_LINES, end_prev_layer, cur_end - end_prev_layer)

            glColor4f(*self.color_current)

            if end > cur_end:
                glDrawArrays(GL_LINES, cur_end, end - cur_end)

            # Restore line width
            glLineWidth(orig_linewidth)

            glEnableClientState(GL_COLOR_ARRAY)

        # Draw non printed stuff until end (if not ending at a given layer)
        start = max(self.printed_until, 0)
        end = end - start
        if end_prev_layer < 0 < end and not self.only_current:
            glDrawArrays(GL_LINES, start, end)

        self.vertex_buffer.unbind()
        self.vertex_color_buffer.unbind()
