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

import math
import logging
import numpy as np
from pyglet import gl

# for type hints
from typing import List, Tuple, Union, TYPE_CHECKING
from ctypes import Array
if TYPE_CHECKING:
    from .camera import Camera

def vec(*args: float) -> Array:
    '''Returns an array of GLfloat values'''
    return (gl.GLfloat * len(args))(*args)

def vec_length(vector: np.ndarray) -> float:
    '''Return the length of a given vector'''
    return np.sqrt(sum(a * a for a in vector))

def cross(v1: List[float], v2: List[float]) -> List[float]:
    return [v1[1] * v2[2] - v1[2] * v2[1],
            v1[2] * v2[0] - v1[0] * v2[2],
            v1[0] * v2[1] - v1[1] * v2[0]]

def trackball(p1x: float, p1y: float,
              p2x: float, p2y: float,
              r: float) -> Tuple[float, float, float, float]:
    TRACKBALLSIZE = r

    if p1x == p2x and p1y == p2y:
        return (0.0, 0.0, 0.0, 1.0)

    p1 = [p1x, p1y, project_to_sphere(TRACKBALLSIZE, p1x, p1y)]
    p2 = [p2x, p2y, project_to_sphere(TRACKBALLSIZE, p2x, p2y)]
    a = cross(p2, p1)

    d = map(lambda x, y: x - y, p1, p2)
    t = math.sqrt(sum(x * x for x in d)) / (2.0 * TRACKBALLSIZE)

    t = min(t, 1.0)
    t = max(t, -1.0)
    phi = 2.0 * math.asin(t)

    return axis_to_quat(np.array(a), phi)

def axis_to_quat(a: np.ndarray,
                 phi: float) -> Tuple[float, float, float, float]:
    lena = vec_length(a)
    q = [x * (1 / lena) for x in a]
    q = [x * math.sin(phi / 2.0) for x in q]
    q.append(math.cos(phi / 2.0))
    return tuple(q)

def build_rotmatrix(q: Tuple[float, float, float, float]) -> np.ndarray:
    m = np.zeros((16, 1), dtype=np.float32) # (GLdouble * 16)()
    m[0] = 1.0 - 2.0 * (q[1] * q[1] + q[2] * q[2])
    m[1] = 2.0 * (q[0] * q[1] - q[2] * q[3])
    m[2] = 2.0 * (q[2] * q[0] + q[1] * q[3])
    m[3] = 0.0

    m[4] = 2.0 * (q[0] * q[1] + q[2] * q[3])
    m[5] = 1.0 - 2.0 * (q[2] * q[2] + q[0] * q[0])
    m[6] = 2.0 * (q[1] * q[2] - q[0] * q[3])
    m[7] = 0.0

    m[8] = 2.0 * (q[2] * q[0] - q[1] * q[3])
    m[9] = 2.0 * (q[1] * q[2] + q[0] * q[3])
    m[10] = 1.0 - 2.0 * (q[1] * q[1] + q[0] * q[0])
    m[11] = 0.0

    m[12] = 0.0
    m[13] = 0.0
    m[14] = 0.0
    m[15] = 1.0
    return m.reshape((4, 4))

def project_to_sphere(r: float, x: float, y: float) -> float:
    d = math.sqrt(x * x + y * y)
    if d < r * 0.70710678118654752440:
        return math.sqrt(r * r - d * d)

    t = r / 1.41421356237309504880
    return t * t / d

def mulquat(q1: Tuple[float, float, float, float],
            rq: Tuple[float, float, float, float]
            ) -> Tuple[float, float, float, float]:
    return (q1[3] * rq[0] + q1[0] * rq[3] + q1[1] * rq[2] - q1[2] * rq[1],
            q1[3] * rq[1] + q1[1] * rq[3] + q1[2] * rq[0] - q1[0] * rq[2],
            q1[3] * rq[2] + q1[2] * rq[3] + q1[0] * rq[1] - q1[1] * rq[0],
            q1[3] * rq[3] - q1[0] * rq[0] - q1[1] * rq[1] - q1[2] * rq[2])

def mouse_to_3d(x: float, y: float, z: float, camera: 'Camera',
                canvas_size: Tuple[float, float]) -> np.ndarray:
    """Point in 3D space from cursor position and z-value"""
    y = canvas_size[1] - y
    mvmat = camera.view
    pmat = camera.projection
    viewport = (0.0, 0.0, canvas_size[0], canvas_size[1])

    return np_unproject(x, y, z, mvmat, pmat, viewport)

def mouse_to_ray(x: float, y: float, camera: 'Camera',
                 canvas_size: Tuple[float, float]
                 ) -> Tuple[np.ndarray, np.ndarray]:
    """Ray from z-depth 1.0 to 0.0"""
    y = canvas_size[1] - y
    mvmat = camera.view
    pmat = camera.projection
    viewport = (0.0, 0.0, canvas_size[0], canvas_size[1])

    ray_far = np_unproject(x, y, 1.0, mvmat, pmat, viewport)
    ray_near = np_unproject(x, y, 0.0, mvmat, pmat, viewport)
    return ray_near, ray_far

def mouse_to_plane(x: float, y: float,
                   plane_normal: Tuple[float, float, float],
                   plane_offset: float,
                   camera: 'Camera',
                   canvas_size: Tuple[float, float]
                   ) -> Union[np.ndarray, None]:
    """Ray/plane intersection"""
    ray_near, ray_far = mouse_to_ray(x, y, camera, canvas_size)
    ray_forward = ray_far - ray_near
    ray_dir = ray_forward / np.linalg.norm(ray_forward)

    plane_normal_np = np.array(plane_normal)
    q = ray_dir.dot(plane_normal_np)
    if q == 0:
        return None

    t = - (ray_near.dot(plane_normal_np) + plane_offset) / q
    if t < 0:
        return None

    return np.add(ray_near, t * ray_dir)

def quat_rotate_vec(quat: Tuple[float, float, float, float],
                     vector_list: List[np.ndarray]) -> List[np.ndarray]:
    """
    Apply the rotation of a given quaterion on all of the given vectors.
    This implementation uses a rotation matrix.
    """
    rmat = build_rotmatrix(quat)
    vecs_out = []
    for v in vector_list:
        vec_in = np.append(v, 0.0)
        vecs_out.append(np.matmul(vec_in, rmat)[:3])

    return vecs_out

def quat_rotate_vec_dev(quat: Tuple[float, float, float, float],
                        vector_list: List[np.ndarray]) -> List[np.ndarray]:
    """
    Apply the rotation of a given quaterion on all of the given vectors.
    This implementation uses quaternion multiplication.
    """
    vecs_out = []
    quat_inv = (-quat[0], -quat[1], -quat[2], quat[3])
    for v in vector_list:
        vec_in = (v[0], v[1], v[2], 0.0)
        a = mulquat(quat_inv, vec_in)
        b = mulquat(a, quat)
        vecs_out.append(np.array(b[:3]))

    return vecs_out

def mat4_orthographic(left: float, right: float, bottom: float, top: float,
                      z_near: float, z_far: float) -> np.ndarray:
    """
    Returns a 4x4 orthographic matrix
    """

    matrix = np.eye(4, dtype=np.float32, order='F')
    tx = - (right + left) / (right - left)
    ty = - (top + bottom) / (top - bottom)
    tz = - (z_far + z_near) / (z_far - z_near)

    matrix[0][0] = 2 / (right - left)
    matrix[1][1] = 2 / (top - bottom)
    matrix[2][2] = - 2 / (z_far - z_near)
    matrix[0][3] = tx
    matrix[1][3] = ty
    matrix[2][3] = tz

    return matrix

def mat4_perspective(fov_deg: float, aspect: float,
                     z_near: float, z_far: float) -> np.ndarray:
    """
    Returns a 4x4 perspective matrix
    """

    matrix = np.eye(4, dtype=np.float32, order='F')
    f = 1.0 / np.tan(np.deg2rad(fov_deg) / 2.0)

    matrix[0][0] = f / aspect
    matrix[1][1] = f
    matrix[2][2] = (z_near + z_far) / (z_near - z_far)
    matrix[2][3] = (2 * z_near * z_far) / (z_near - z_far)
    matrix[3][2] = -1.0
    matrix[3][3] = 0.0

    return matrix

def mat4_translation(x_val: float, y_val: float,
                     z_val: float) -> np.ndarray:
    """
    Returns a 4x4 translation matrix
    """

    matrix = np.eye(4, dtype=np.float32, order='C')
    matrix[3][0] = x_val
    matrix[3][1] = y_val
    matrix[3][2] = z_val

    return matrix

def mat4_rotation(x: float, y: float,
                  z: float, angle_deg: float) -> np.ndarray:
    """
    Returns a 4x4 rotation matrix, enter rotation angle in degree
    """

    matrix = np.eye(4, dtype=np.float32, order='C')
    co = np.cos(np.radians(angle_deg))
    si = np.sin(np.radians(angle_deg))
    matrix[0][0] = x * x * (1 - co) + co
    matrix[1][0] = x * y * (1 - co) - z * si
    matrix[2][0] = x * z * (1 - co) + y * si
    matrix[0][1] = x * y * (1 - co) + z * si
    matrix[1][1] = y * y * (1 - co) + co
    matrix[2][1] = y * z * (1 - co) - x * si
    matrix[0][2] = x * z * (1 - co) - y * si
    matrix[1][2] = y * z * (1 - co) + x * si
    matrix[2][2] = z * z * (1 - co) + co

    return matrix

def mat4_scaling(x_val: float, y_val: float, z_val: float) -> np.ndarray:
    """
    Returns a 4x4 scaling matrix
    """

    matrix = np.eye(4, dtype=np.float32, order='C')
    matrix[0][0] = x_val
    matrix[1][1] = y_val
    matrix[2][2] = z_val

    return matrix

def pyg_to_np_mat4(pyg_matrix) -> np.ndarray:
    """
    Converts a pyglet Mat4() matrix into a numpy array.
    """
    return np.array((pyg_matrix.row(0),
                     pyg_matrix.row(1),
                     pyg_matrix.row(2),
                     pyg_matrix.row(3)), dtype=np.float32)

def np_to_gl_mat(np_matrix: np.ndarray) -> Array:
    """
    Converts a numpy matrix into a c_types_Array which
    can be directly passed into OpenGL calls.
    """
    return (gl.GLdouble * np_matrix.size)(*np_matrix.ravel())

def np_unproject(winx: float, winy: float, winz: float,
                 mv_mat: np.ndarray, p_mat: np.ndarray,
                 viewport: Tuple[float, float, float, float]
                 ) -> np.ndarray:
    '''
    gluUnProject in Python with numpy. This is a direct
    implementation of the Khronos OpenGL Wiki code:
    https://www.khronos.org/opengl/wiki/GluProject_and_gluUnProject_code

    Parameters:
        winx, winy, winz: Window coordinates.
        mv_mat: Model-view matrix as a ctypes array.
        p_mat: Projection matrix as a ctypes array.
        viewport: Viewport as a ctypes array [x, y, width, height].

    Returns:
        bool: Vector if successful, 0.0 otherwise.
    '''
    point = np.zeros(3)
    mat_a = p_mat @ mv_mat

    try:
        mat_inv = np.linalg.inv(mat_a)
    except np.linalg.LinAlgError:
        logging.warning(_("GL: np_unproject could calculate inverse of matrix, result will be 0.0."))
        return point

    # Normalized screen coordinates between -1 and 1
    coords_in = np.zeros(4)
    coords_in[0] = (winx - viewport[0]) / viewport[2] * 2.0 - 1.0
    coords_in[1] = (winy - viewport[1]) / viewport[3] * 2.0 - 1.0
    coords_in[2] = 2.0 * winz - 1.0
    coords_in[3] = 1.0

    # Object coordinates
    coords_out = mat_inv @ coords_in
    if coords_out[3] == 0.0:
        logging.warning(_("GL: np_unproject failed, division by 0 is not allowed. Result will be 0.0."))
        return point

    coords_out[3] = 1.0 / coords_out[3]
    point[0] = coords_out[0] * coords_out[3]
    point[1] = coords_out[1] * coords_out[3]
    point[2] = coords_out[2] * coords_out[3]

    return point

