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

from threading import Lock

from pyglet.gl import GLdouble, glGetDoublev, glLoadIdentity, \
    glMatrixMode, GL_MODELVIEW, GL_MODELVIEW_MATRIX, glOrtho, \
    GL_PROJECTION, gluPerspective, glPushMatrix, glPopMatrix, \
    glLoadMatrixd

from .mathutils import trackball, mulquat, axis_to_quat, quat_rotate_vec

import numpy as np

# for type hints
from typing import Optional, List, Tuple, TYPE_CHECKING
from wx import MouseEvent
from ctypes import Array
Build_Dims = Tuple[int, int, int, int, int, int]
if TYPE_CHECKING:
    from .panel import wxGLPanel


class Camera():

    rot_lock = Lock()

    def __init__(self, parent: 'wxGLPanel', build_dimensions: Build_Dims, 
                 ortho: bool = True) -> None:

        self.canvas = parent
        self.is_orthographic = ortho
        self.orbit_control = True
        self.view_matrix_initialized = False

        self.width = 1.0
        self.height = 1.0
        self.display_ppi_factor = 1.0

        self.platformcenter = (-build_dimensions[3] - build_dimensions[0] / 2,
                               -build_dimensions[4] - build_dimensions[1] / 2)
        self.dist = max(build_dimensions[:2])

        self.eye = np.array((0.0, 0.0, 1.0))
        self.target = np.array((0.0, 0.0, 0.0))
        self.up = np.array((0.0, 1.0, 0.0))
        self.zoom_factor = 1.0

        self.orientation = [0.0, 0.0, 0.0, 1.0]
        self.angle_z = 0
        self.angle_x = 0
        self.init_rot_pos = None
        self.init_trans_pos = None
        self.view_mat = np.identity(4)
        self._set_initial_view()

    def update_size(self, width: int, height: int, scalefactor: float) -> None:
        self.width = width
        self.height = height
        self.display_ppi_factor = scalefactor

    def update_build_dims(self, build_dimensions: Build_Dims) -> None:
        self.dist = max(build_dimensions[:2])
        self.platformcenter = (-build_dimensions[3] - build_dimensions[0] / 2,
                               -build_dimensions[4] - build_dimensions[1] / 2)
        self._set_initial_view()

    def _set_initial_view(self) -> None:
        self.eye = np.array((-self.platformcenter[0],
                             -self.platformcenter[1],
                             self.dist * 1.5))

        self.target = np.array((-self.platformcenter[0],
                                -self.platformcenter[1],
                                0.0))
        self._rebuild_view_mat()

    def reset_view_matrix(self) -> None:
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        self.reset_rotation()
        self._set_initial_view()

        if self.width < self.height:
            min_side = self.width * self.display_ppi_factor
            zoom_length = 2 * abs(self.platformcenter[0])
        else:
            min_side = self.height * self.display_ppi_factor
            zoom_length = 2 * abs(self.platformcenter[1])

        # TODO: Check this value on other displays and resolutions
        zoom_constant = 2.1  # conversion between millimeter and pixel
        self.zoom_factor = zoom_length / min_side * zoom_constant
        self.create_projection_matrix()

        self._rebuild_view_mat()
        self.view_matrix_initialized = True

    def reset_rotation(self) -> None:
        self.orientation = [0.0, 0.0, 0.0, 1.0]
        self.angle_x = 0.0
        self.angle_z = 0.0

    def create_projection_matrix(self) -> None:
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()

        if self.is_orthographic:
            glOrtho(-self.width / 2 * self.zoom_factor,
                    self.width / 2 * self.zoom_factor,
                    -self.height / 2 * self.zoom_factor,
                    self.height / 2 * self.zoom_factor,
                    0.01, 3 * self.dist)
        else:
            gluPerspective(45.0, self.width / self.height, 0.1, 5.5 * self.dist)

        glMatrixMode(GL_MODELVIEW)

    def create_pseudo2d_matrix(self) -> None:
        '''Create untransformed matrices to render
        coordinates directly on the canvas, quasi 2D.
        Use always in conjunction with revert_...'''

        glPushMatrix()  # backup and clear MODELVIEW
        glLoadIdentity()

        glMatrixMode(GL_PROJECTION)
        glPushMatrix()  # backup and clear PROJECTION
        glLoadIdentity()
        glOrtho(0, self.width, 0, self.height, -1, 1)

    def revert_pseudo2d_matrix(self) -> None:
        '''Revert current matrices back to the normal,
        saved matrices'''

        glPopMatrix()  # restore PROJECTION

        glMatrixMode(GL_MODELVIEW)
        glPopMatrix()  # restore MODELVIEW

    def get_view_matrix(self) -> Array:
        return self._np_to_gl_mat(self.view_mat)

    def move_rel(self, x: float, y: float, z: float):
        delta = np.array((x, y, z))

        self.eye = delta + self.eye
        self.target = delta + self.target

        self._rebuild_view_mat()

    def zoom(self, factor: float,
             to: Optional[Tuple[float, float]] = None,
             rebuild_mat: bool = True) -> None:
        # TODO: Implement zoom to point
        '''
        delta_x = 0.0
        delta_y = 0.0

        if to:
            delta_x = to[0]
            delta_y = to[1]
            glTranslatef(delta_x, delta_y, 0)
        '''
        if self.is_orthographic:
            zf = self.zoom_factor * 1 / factor
            self.zoom_factor = max(min(zf, 0.8), 0.01)
            self.create_projection_matrix()
        else:
            eye = self.target + (self.eye - self.target) * 1 / factor
            forward = eye - self.target
            length = np.sqrt(sum(a * a for a in forward))

            if length > 5 * self.dist or length < 6.0:
                return

            self.eye = eye

            if rebuild_mat:
                self._rebuild_view_mat()

        '''
        if to:
            glTranslatef(-delta_x, -delta_y, 0)
        '''

    def _orbit(self, p1x: float, p1y: float,
               p2x: float, p2y: float) -> List[float]:
        rz = p2x - p1x
        self.angle_z -= rz
        rot_z = axis_to_quat([0.0, 0.0, -1.0], self.angle_z)

        rx = p2y - p1y
        self.angle_x += rx
        rot_a = axis_to_quat([-1.0, 0.0, 0.0], self.angle_x)

        return mulquat(rot_a, rot_z)

    def handle_rotation(self, event: MouseEvent) -> None:
        if self.init_rot_pos is None:
            self.init_rot_pos = event.GetPosition() * self.display_ppi_factor
        else:
            p1 = self.init_rot_pos
            p2 = event.GetPosition() * self.display_ppi_factor

            p1x = p1[0] / (self.width / 2) - 1
            p1y = 1 - p1[1] / (self.height / 2)
            p2x = p2[0] / (self.width / 2) - 1
            p2y = 1 - p2[1] / (self.height / 2)

            with self.rot_lock:
                if self.orbit_control:
                    self.orientation = self._orbit(p1x, p1y, p2x, p2y)
                else:
                    # TODO: Is trackball still useable?
                    quat = trackball(p1x, p1y, p2x, p2y, self.dist / 250.0)
                    self.orientation = mulquat(self.orientation, quat)

            self._rebuild_view_mat()
            self.init_rot_pos = p2

    def handle_translation(self, event: MouseEvent) -> None:
        if self.init_trans_pos is None:
            self.init_trans_pos = event.GetPosition() * self.display_ppi_factor
        else:
            p1 = self.init_trans_pos
            p2 = event.GetPosition() * self.display_ppi_factor

            vec1 = np.array(self.canvas.mouse_to_3d(p1[0], p1[1]))
            vec2 = np.array(self.canvas.mouse_to_3d(p2[0], p2[1]))

            delta = (vec1 - vec2) if self.is_orthographic \
                                  else (vec1 - vec2) / 15.0

            self.eye = delta + self.eye
            self.target = delta + self.target

            self._rebuild_view_mat()
            self.init_trans_pos = p2

    def _np_to_gl_mat(self, np_matrix: np.ndarray) -> Array:
        array_type = GLdouble * np_matrix.size
        return array_type(*np_matrix.reshape((np_matrix.size, 1)))

    def _rebuild_view_mat(self) -> None:
        forward = self.eye - self.target
        rotated_forward, rotated_up = quat_rotate_vec(self.orientation,
                                                      [forward, self.up])
        rotated_eye = rotated_forward + self.target
        self.view_mat = self._look_at(rotated_eye , self.target, rotated_up)

        glMatrixMode(GL_MODELVIEW)
        #glLoadIdentity()
        #gluLookAt(*rotated_eye, *self.target, *rotated_up)
        glLoadMatrixd(self._np_to_gl_mat(self.view_mat))

    def _look_at(self, eye: np.ndarray,
                       center: np.ndarray,
                       up: np.ndarray) -> np.ndarray:
        # Calculate the forward vector (z-axis in camera space)
        forward = center - eye
        forward = forward / np.linalg.norm(forward)

        # Calculate the right vector (x-axis in camera space)
        right = np.cross(forward, up)
        right = right / np.linalg.norm(right)

        # Recalculate the up vector (y-axis in camera space)
        true_up = np.cross(right, forward)

        view_matrix = np.identity(4)

        # Negate z-vector to look at the viewer
        forward = -forward

        # Set rotation part of the view matrix
        view_matrix[0, :3] = right
        view_matrix[1, :3] = true_up
        view_matrix[2, :3] = forward

        # Set translation part (position of the camera)
        view_matrix[0, 3] = -np.dot(right, eye)
        view_matrix[1, 3] = -np.dot(true_up, eye)
        view_matrix[2, 3] = -np.dot(forward, eye)

        return view_matrix.T

