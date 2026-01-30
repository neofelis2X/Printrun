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

import numpy as np

from .mathutils import vec_length, mulquat, trackball, mouse_to_3d, \
                       mat4_orthographic, mat4_perspective, axis_to_quat, \
                       quat_rotate_vec, mouse_to_plane

# for type hints
from typing import Optional, Tuple, TYPE_CHECKING
from wx import MouseEvent
Build_Dims = Tuple[int, int, int, int, int, int]
if TYPE_CHECKING:
    from .panel import wxGLPanel


def debug_info(method):
    def wrapper(self, *args, **kwargs):
        output = method(self, *args, **kwargs)
        v = self._target
        print(f"Target: \t({v[0]:.3f}, {v[1]:.3f}, {v[2]:.3f})")
        v = self._eye
        print(f"Eye: \t({v[0]:.3f}, {v[1]:.3f}, {v[2]:.3f})")
        print("")
        return output
    return wrapper


class Camera():

    LOCK = Lock()
    FOV = 45.0
    MIN_DISTANCE = 3.0  # mm
    MAX_DISTANCE = 1000.0

    def __init__(self, parent: 'wxGLPanel', build_dimensions: Build_Dims,
                 ortho: bool = True) -> None:

        self.canvas = parent
        self.is_orthographic = ortho
        self.orbit_control = True
        self.view_matrix_initialized = False
        self._has_changed = False

        self.width = 1.0
        self.height = 1.0
        self.display_ppi_factor = 1.0

        self.platformcenter = np.array((0.0, 0.0, 0.0))
        self.platform = (1.0, 1.0, 1.0)
        self.dist = 1.0
        self.scene_bounds = np.zeros((2, 3))
        self.update_build_dims(build_dimensions, setview=False)

        self._eye = np.array((0.0, 0.0, 1.0))
        self._target = np.array((0.0, 0.0, 0.0))
        self._up = np.array((0.0, 1.0, 0.0))
        self.x_axis = np.array((-1.0, 0.0, 0.0))
        self.dolly_factor = 1.0

        self.init_rot_pos = None
        self.init_trans_pos = None
        self._view_mat = np.identity(4, dtype=np.float32)
        self._proj_mat = np.identity(4, dtype=np.float32)
        self._ortho2d_mat = np.identity(4, dtype=np.float32)

    @property
    def has_changed(self) -> bool:
        return self._has_changed

    @property
    def eye(self) -> np.ndarray:
        self._has_changed = False
        return self._eye.astype(dtype=np.float32)

    @property
    def view(self) -> np.ndarray:
        self._has_changed = False
        return self._view_mat

    @property
    def projection(self) -> np.ndarray:
        self._has_changed = False
        return self._proj_mat

    @property
    def projection2d(self) -> np.ndarray:
        return self._ortho2d_mat

    def update_size(self, width: int, height: int, scalefactor: float) -> None:
        self.width = width
        self.height = height
        self.display_ppi_factor = scalefactor
        self._rebuild_proj_mat()
        self._rebuild_ortho2d_mat()

    def update_build_dims(self, build_dimensions: Build_Dims,
                          setview: bool = True) -> None:
        """
        Update the printer dimensions which the 3D view uses to set the
        initial view and the dolly distance to the print platform.
        """
        dims = build_dimensions
        self.platformcenter[0] = dims[3] + dims[0] / 2
        self.platformcenter[1] = dims[4] + dims[1] / 2
        self.platformcenter[2] = 0.0
        self.platform = (dims[0], dims[1], dims[2])
        self.dist = max(dims[:2])
        self.MAX_DISTANCE = 6.0 * self.dist
        self._calc_scene_bounds()

        if setview:
            self._set_initial_view()

    def _calc_scene_bounds(self):
        offset = 1.5
        self.scene_bounds[0][0] = - offset * self.platform[0]
        self.scene_bounds[0][1] = - offset * self.platform[1]
        self.scene_bounds[0][2] = - offset * self.platform[2]
        self.scene_bounds[1][0] = (1 + offset) * self.platform[0]
        self.scene_bounds[1][1] = (1 + offset) * self.platform[1]
        self.scene_bounds[1][2] = (1 + offset) * self.platform[2]

    def _set_initial_view(self) -> None:
        self._eye = np.array((self.platformcenter[0],
                             self.platformcenter[1],
                             self.dist * 1.5))

        self._target = self.platformcenter.copy()
        self._rebuild_view_mat()

    def reset_view_matrix(self) -> None:
        self._up = np.array((0.0, 1.0, 0.0))
        self.x_axis = np.array((-1.0, 0.0, 0.0))
        self._set_initial_view()

        if self.width / self.platform[0] < self.height / self.platform[1]:
            min_side = self.width * self.display_ppi_factor
            dolly_length = self.platform[0]
        else:
            min_side = self.height * self.display_ppi_factor
            dolly_length = self.platform[1]

        # conversion between millimeter and pixel
        dolly_constant = 1.05 * self.display_ppi_factor
        self.dolly_factor = dolly_length / min_side * dolly_constant
        self._rebuild_proj_mat()

        self._rebuild_view_mat()
        self.view_matrix_initialized = True

    def _rebuild_proj_mat(self) -> None:
        if self.is_orthographic:
            ddf = self.dolly_factor * 0.5
            self._proj_mat = mat4_orthographic(-self.width * ddf,
                                               self.width * ddf,
                                               -self.height * ddf,
                                               self.height * ddf,
                                               0.1, 2.0 * self.MAX_DISTANCE)
        else:
            self._proj_mat = mat4_perspective(self.FOV, self.width / self.height,
                                              0.1, 2.0 * self.MAX_DISTANCE)
        self._has_changed = True

    def _rebuild_ortho2d_mat(self) -> None:
        '''Create orthogonal matrix to render
        coordinates directly on the canvas, quasi 2D.'''

        self._ortho2d_mat = mat4_orthographic(0.0, self.width, 0.0,
                                              self.height, -1.0, 1.0)
        self._has_changed = True

    # @debug_info
    def fit_to_model(self,
                     bounding_sphere: Tuple[Tuple[float, float, float], float]
                     ) -> None:
        """
        Takes the bounding sphere of a model (center, radius) and zooms / moves
        the current view so that the view focues on the model.
        """
        forward = self._target - self._eye
        uforward = forward / vec_length(forward)
        aspect = self.width / self.height

        half_min_fov_rad = 0.5 * np.radians(self.FOV)
        if aspect < 1.0:
            half_min_fov_rad = np.atan(aspect * np.tan(half_min_fov_rad))

        distance_to_center = bounding_sphere[1] / np.sin(half_min_fov_rad)
        self._target = np.array(bounding_sphere[0])
        self._eye = self._target - uforward * distance_to_center

        if self.is_orthographic:
            if aspect < 1.0:
                min_side = self.width * self.display_ppi_factor
            else:
                min_side = self.height * self.display_ppi_factor

            dolly_constant = 0.95 * self.display_ppi_factor
            self.dolly_factor = 2 * bounding_sphere[1] / min_side * dolly_constant
            self._rebuild_proj_mat()

        self._rebuild_view_mat()

    # @debug_info
    def zoom(self, factor: float,
             to_cursor: Optional[Tuple[float, float]] = None,
             rebuild_mat: bool = True) -> None:

        if self.is_orthographic:
            self._dolly_orthographic(factor, to_cursor)
        else:
            self._dolly_perspective(factor, to_cursor)

        if rebuild_mat:
            self._rebuild_view_mat()

    def _dolly_perspective(self, factor: float,
                           to_cursor: Optional[Tuple[float, float]] = None
                           ) -> None:
            if not to_cursor:
                # Use screen center
                to_cursor = (self.width / 2, self.height / 2)

            current_forward = self._target - self._eye
            current_distance = vec_length(current_forward)
            current_direction = current_forward / current_distance

            cursor_vec = mouse_to_plane(to_cursor[0], to_cursor[1],
                                        (0.0, 0.0, 1.0), 0.0, self,
                                        (self.width, self.height))

            if cursor_vec is None:
                # No intersection with platform has been found, use camera target plane
                cursor_vec = mouse_to_plane(to_cursor[0], to_cursor[1],
                                            tuple(-current_direction), 0.0, self,
                                            (self.width, self.height))
            if cursor_vec is None:
                # No valid intersection has been found, don't move camera
                return

            new_distance = np.clip(current_distance / factor,
                                   self.MIN_DISTANCE, self.MAX_DISTANCE)

            t = (current_distance - new_distance) / current_distance

            self._target += (cursor_vec - self._target) * t
            self._target = self._clamp_to_boundaries(self._target)
            self._eye = self._target - current_direction * new_distance

    def _dolly_orthographic(self, factor: float,
                            to_cursor: Optional[Tuple[float, float]] = None
                            ) -> None:
        df = self.dolly_factor / factor
        if df <= 0.001 or df >= 0.8:
            return
        self.dolly_factor = df
        self._rebuild_proj_mat()

        if not to_cursor:
            return

        cursor_vec = mouse_to_3d(to_cursor[0], to_cursor[1], 1.0,
                                 self, (self.width, self.height))
        center_vec = mouse_to_3d(self.width / 2, self.height / 2, 1.0,
                                 self, (self.width, self.height))
        dolly_delta = (cursor_vec - center_vec) * (1.0 - 1 / factor)
        self._eye = dolly_delta + self._eye
        self._target = dolly_delta + self._target

    def _clamp_to_boundaries(self, target_vec: np.ndarray) -> np.ndarray:
        # padding
        scene_min = self.scene_bounds[0]
        scene_max = self.scene_bounds[1]

        # center + comfort sphere
        scene_center = (scene_min + scene_max) * 0.5
        scene_center[2] = 15.0  # set center-z close to build platform
        scene_radius = self.MAX_DISTANCE

        # hard physical clamp
        target = np.minimum(np.maximum(target_vec, scene_min), scene_max)

        # soft orbit clamp
        center_vec = target - scene_center
        center_distance = np.linalg.norm(center_vec)
        if center_distance > scene_radius:
            target = scene_center + center_vec / center_distance * scene_radius

        return target

    def _validate_delta(self, target_vec: np.ndarray,
                        delta: np.ndarray) -> np.ndarray:
        for i in range(3):
            coord = target_vec[i] + delta[i]
            if coord < self.scene_bounds[0][i]:
                delta[i] = self.scene_bounds[0][i] - target_vec[i]
                pass
            elif coord > self.scene_bounds[1][i]:
                delta[i] = self.scene_bounds[1][i] - target_vec[i]
                pass

        return delta

    def _orbit(self, p1x: float, p1y: float,
               p2x: float, p2y: float) -> Tuple[float, float, float, float]:
        rz = p2x - p1x
        rot_z = axis_to_quat(np.array((0.0, 0.0, -1.0)), -rz)

        rx = p2y - p1y
        rot_a = axis_to_quat(self.x_axis, rx)

        return mulquat(rot_a, rot_z)

    # @debug_info
    def handle_rotation(self, event: MouseEvent) -> None:
        if self.init_rot_pos is None:
            self.init_rot_pos = [self.display_ppi_factor * val for val in event.GetPosition()]
        else:
            p1 = self.init_rot_pos
            p2 = [self.display_ppi_factor * val for val in event.GetPosition()]

            p1x = p1[0] / (self.width / 2) - 1
            p1y = 1 - p1[1] / (self.height / 2)
            p2x = p2[0] / (self.width / 2) - 1
            p2y = 1 - p2[1] / (self.height / 2)

            with self.LOCK:
                if self.orbit_control:
                    delta_quat = self._orbit(p1x, p1y, p2x, p2y)
                else:
                    # TODO: Is trackball still useable?
                    delta_quat = trackball(p1x, p1y, p2x, p2y, self.dist / 250.0)

            forward = self._eye - self._target
            rotated_forward, self._up, self.x_axis, *_ = quat_rotate_vec(delta_quat,
                                                        [forward, self._up, self.x_axis])

            self._eye = rotated_forward + self._target
            self._rebuild_view_mat()
            self.init_rot_pos = p2

    # @debug_info
    def handle_translation(self, event: MouseEvent) -> None:
        if self.init_trans_pos is None:
            self.init_trans_pos = [self.display_ppi_factor * val for val in event.GetPosition()]
        else:
            p1 = self.init_trans_pos
            p2 = [self.display_ppi_factor * val for val in event.GetPosition()]

            vec1 = mouse_to_3d(p1[0], p1[1], 1.0, self, (self.width, self.height))
            vec2 = mouse_to_3d(p2[0], p2[1], 1.0, self, (self.width, self.height))

            if self.is_orthographic:
                delta = vec1 - vec2
            else:
                df = self._current_dolly_factor()
                delta = (vec1 - vec2) * df

            delta = self._validate_delta(self._target, delta)
            self._eye = delta + self._eye
            self._target = delta + self._target

            self._rebuild_view_mat()
            self.init_trans_pos = p2

    def _current_dolly_factor(self) -> float:
        """
        Returns a factor of the current dolly distance relativ to
        the max. dolly distance.
        """
        forward = self._eye - self._target
        dolly_dist = vec_length(forward)
        dolly_limits = self.MAX_DISTANCE - self.MIN_DISTANCE

        return dolly_dist / (2 * dolly_limits)

    def _rebuild_view_mat(self) -> None:
        self._view_mat = self._look_at(self._eye , self._target, self._up)
        self._has_changed = True

    def _look_at(self, eye: np.ndarray,
                       center: np.ndarray,
                       up: np.ndarray) -> np.ndarray:
        """
        Classic gluLookAt implementation that takes in numpy arrays for
        the vector eye, center (target) and global up and returns a 4x4
        view matrix as a numpy array
        """
        # Calculate the forward vector (z-axis in camera space)
        forward = center - eye
        forward = forward / np.linalg.norm(forward)

        # Calculate the right vector (x-axis in camera space)
        right = np.cross(forward, up)
        right = right / np.linalg.norm(right)

        # Recalculate the up vector (y-axis in camera space)
        true_up = np.cross(right, forward)

        view_matrix = np.eye(4, dtype=np.float32, order='F')

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

        return view_matrix

