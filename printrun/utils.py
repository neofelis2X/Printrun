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

import os
import platform
import sys
import re
import gettext
import datetime
import subprocess
import shlex
import locale
import logging
from pathlib import Path

import wx
import wx.svg

DATADIR = os.path.join(sys.prefix, 'share')


def set_utf8_locale():
    """Make sure we read/write all text files in UTF-8"""
    lang, encoding = locale.getlocale()
    if encoding != 'UTF-8':
        locale.setlocale(locale.LC_CTYPE, (lang, 'UTF-8'))

# Set up Internationalization using gettext
# searching for installed locales on /usr/share; uses relative folder if not
# found (windows and macOS)
def install_locale(domain):
    shared_locale_dir = os.path.join(DATADIR, 'locale')
    translation = None
    lang = locale.getdefaultlocale()
    osPlatform = platform.system()

    if osPlatform == "Darwin":
        # improvised workaround for macOS crash with gettext.translation, see issue #1154
        gettext.install(domain, './locale')
    else:
        if os.path.exists('./locale'):
            translation = gettext.translation(domain, './locale',
                                              languages=[lang[0]], fallback= True)
        else:
            translation = gettext.translation(domain, shared_locale_dir,
                                              languages=[lang[0]], fallback= True)
        translation.install()

class LogFormatter(logging.Formatter):
    def __init__(self, format_default, format_info):
        super().__init__(format_info)
        self.format_default = format_default
        self.format_info = format_info

    def format(self, record):
        if record.levelno == logging.INFO:
            self._fmt = self.format_info
        else:
            self._fmt = self.format_default
        return super().format(record)

def setup_logging(out, filepath = None, reset_handlers = False):
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    if reset_handlers:
        logger.handlers = []
    formatter = LogFormatter("[%(levelname)s] %(message)s", "%(message)s")
    logging_handler = logging.StreamHandler(out)
    logging_handler.setFormatter(formatter)
    logger.addHandler(logging_handler)
    if filepath:
        if os.path.isdir(filepath):
            filepath = os.path.join(filepath, "printrun.log")
        else:
            # Fallback for logging path of non console windows applications:
            # Use users home directory in case the file path in printrunconf.ini
            # is not valid or do not exist, see issue #1300
            filepath = os.path.join(Path.home(), "printrun.log")
        formatter = LogFormatter("%(asctime)s - [%(levelname)s] %(message)s", "%(asctime)s - %(message)s")
        logging_handler = logging.FileHandler(filepath)
        logging_handler.setFormatter(formatter)
        logger.addHandler(logging_handler)

def get_scaled_icon(iconname: str, width: int, window: wx.Window) -> wx.Icon:
    # Scale the icon correctly without making it blurry
    sc = window.GetContentScaleFactor()
    final_w = int(width * sc)
    raw_icn = get_iconbundle(iconname).GetIcon((final_w, final_w),
                                               wx.IconBundle.FALLBACK_NEAREST_LARGER)
    ic_bmp = wx.Bitmap()
    ic_bmp.CopyFromIcon(raw_icn)
    if raw_icn.GetWidth() != final_w:
        ic_img = ic_bmp.ConvertToImage()
        ic_img.Rescale(final_w, final_w, wx.IMAGE_QUALITY_HIGH)
        ic_bmp = ic_img.ConvertToBitmap()
    ic_bmp.SetScaleFactor(sc)

    return wx.Icon(ic_bmp)

def get_iconbundle(iconname: str) -> wx.IconBundle:
    icons = wx.IconBundle()
    rel_path = os.path.join("assets", "icons", iconname)
    base_filename = iconname + "_32x32.png"
    png_path = os.path.dirname(imagefile(base_filename, rel_path))
    if not os.path.isdir(png_path):
        logging.warning('Icon "%s" not found.' % iconname)
        return icons
    pngs = os.listdir(png_path)
    for file in pngs:
        if file.endswith(".png"):
            icons.AddIcon(os.path.join(png_path, file), wx.BITMAP_TYPE_PNG)

    return icons

def toolbaricon(iconname: str) -> wx.BitmapBundle:
    icons = wx.BitmapBundle()
    rel_path = os.path.join("assets", "toolbar")

    # On windows the application is light grey, even in 'dark mode',
    # therefore on windows we always use the dark icons on bright background.
    os_name = wx.PlatformInformation().Get().GetOperatingSystemFamilyName()
    if wx.SystemSettings.GetAppearance().IsDark() and \
        os_name != "Windows":
        base_filename = iconname + "_w.svg"
    else:
        base_filename = iconname + ".svg"

    svg_path = imagefile(base_filename, rel_path)

    if not os.path.isfile(svg_path):
        logging.warning('Toolbar icon "%s" not found.' % iconname)
        return icons

    return icons.FromSVGFile(svg_path, (24, 24))

def iconfile(filename):
    '''
    Get the full path to filename by checking in standard icon locations
    ("pixmaps" directories) or use the frozen executable if applicable
    (See the lookup_file function's documentation for behavior).
    '''
    if hasattr(sys, "frozen") and sys.frozen == "windows_exe":
        return sys.executable
    return pixmapfile(filename)

def imagefile(filename, img_directory="images"):
    '''
    Get the full path to filename by checking standard image locations,
    those being possible locations of the pronterface "images" directory
    (See the lookup_file function's documentation for behavior).
    '''

    return lookup_file(filename, [img_directory, "pronterface/" + img_directory])


def lookup_file(filename, folders=None, locations=None):
    """Look for a file in different locations.

    Get the full path to `filename` by checking in one or several combinations
    of folders and locations, or in the frozen data (for bundled packages) if
    applicable.

    If a result from this is used for the wx.Image constructor and `filepath`
    isn't found, the C++ part of wx will raise an exception
    (wx._core.wxAssertionError): "invalid image".

    Parameters
    ----------
    filename : str
        Name of file to look for (without any path).
    folders : list of str or pathlib.Path
        List of relative paths to potential folders containing `filename`.
    locations : optional, list of pathlib.Path
        Additional absolute locations to search for `filename`.

    Returns
    -------
    A string containing the full path if found, or the name of the file if not
    found.

    """

    script_location = Path(sys.argv[0]).resolve().parent
    dirs = [
        Path('.').resolve(),           # Pure local
        script_location,               # Local to script
        script_location / "share",     # Script local share (for pip install)
        Path(sys.prefix) / "share",    # Global share
    ]
    if getattr(sys, "frozen", False):  # Local to pyinstaller bundle
        dirs += [Path(getattr(sys, "_MEIPASS")).resolve()]
    if locations is not None:
        dirs += locations

    _folders = ["."]
    if folders is not None:
        _folders += folders

    for location in dirs:
        for folder in _folders:
            candidate = location / folder / filename
            if candidate.exists():
                return str(candidate)
    return filename


def pixmapfile(filename):
    '''
    Get the full path to filename by checking in standard icon
    ("pixmaps") directories (See the lookup_file function's
    documentation for behavior).
    '''
    return lookup_file(filename, ["pixmaps"])


def decode_utf8(s):
    """Attempt to decode a string, return the string otherwise"""
    if isinstance(s, bytes):
        return s.decode()
    return s

def format_time(timestamp):
    return datetime.datetime.fromtimestamp(timestamp).strftime("%H:%M:%S")

def format_duration(delta):
    return str(datetime.timedelta(seconds = int(delta)))

def prepare_command(command, replaces = None):
    command = shlex.split(command.replace("\\", "\\\\"))
    if replaces:
        replaces["$python"] = sys.executable
        for pattern, rep in replaces.items():
            command = [bit.replace(pattern, rep) for bit in command]
    return command

def run_command(command, replaces = None, stdout = subprocess.STDOUT,
                stderr = subprocess.STDOUT, blocking = False,
                universal_newlines = False):
    command = prepare_command(command, replaces)
    if blocking:
        return subprocess.call(command, universal_newlines = universal_newlines)
    return subprocess.Popen(command, stderr = stderr, stdout = stdout,
                            universal_newlines = universal_newlines)

def get_command_output(command, replaces):
    p = run_command(command, replaces,
                    stdout = subprocess.PIPE, stderr = subprocess.STDOUT,
                    blocking = False, universal_newlines = True)
    return p.stdout.read()

def dosify(name):
    return os.path.split(name)[1].split(".")[0][:8] + ".g"

class RemainingTimeEstimator:

    drift = None
    gcode = None

    def __init__(self, gcode):
        self.drift = 1
        self.previous_layers_estimate = 0
        self.current_layer_estimate = 0
        self.current_layer_lines = 0
        self.gcode = gcode
        self.last_idx = -1
        self.last_estimate = None
        self.remaining_layers_estimate = sum(layer.duration for layer in gcode.all_layers)
        if len(gcode) > 0:
            self.update_layer(0, 0)

    def update_layer(self, layer, printtime):
        self.previous_layers_estimate += self.current_layer_estimate
        if self.previous_layers_estimate > 1. and printtime > 1.:
            self.drift = printtime / self.previous_layers_estimate
        self.current_layer_estimate = self.gcode.all_layers[layer].duration
        self.current_layer_lines = len(self.gcode.all_layers[layer])
        self.remaining_layers_estimate -= self.current_layer_estimate
        self.last_idx = -1
        self.last_estimate = None

    def __call__(self, idx, printtime):
        if not self.current_layer_lines:
            return (0, 0)
        if idx == self.last_idx:
            return self.last_estimate
        if idx >= len(self.gcode.layer_idxs):
            return self.last_estimate
        layer, line = self.gcode.idxs(idx)
        layer_progress = (1 - (float(line + 1) / self.current_layer_lines))
        remaining = layer_progress * self.current_layer_estimate + self.remaining_layers_estimate
        estimate = self.drift * remaining
        total = estimate + printtime
        self.last_idx = idx
        self.last_estimate = (estimate, total)
        return self.last_estimate

def parse_build_dimensions(bdim):
    # a string containing up to six numbers delimited by almost anything
    # first 0-3 numbers specify the build volume, no sign, always positive
    # remaining 0-3 numbers specify the coordinates of the "southwest" corner of the build platform
    # "XXX,YYY"
    # "XXXxYYY+xxx-yyy"
    # "XXX,YYY,ZZZ+xxx+yyy-zzz"
    # etc
    bdl = re.findall(r"([-+]?[0-9]*\.?[0-9]*)", bdim)
    defaults = [200, 200, 100, 0, 0, 0, 0, 0, 0]
    bdl = [b for b in bdl if b]
    bdl_float = [float(value) if value else defaults[i] for i, value in enumerate(bdl)]
    if len(bdl_float) < len(defaults):
        bdl_float += [defaults[i] for i in range(len(bdl_float), len(defaults))]
    for i in range(3):  # Check for nonpositive dimensions for build volume
        if bdl_float[i] <= 0:
            bdl_float[i] = 1
    return bdl_float

def get_home_pos(build_dimensions):
    return build_dimensions[6:9] if len(build_dimensions) >= 9 else None

def hexcolor_to_float(color, components):
    color = color[1:]
    numel = len(color)
    ndigits = numel // components
    div = 16 ** ndigits - 1
    return tuple(round(float(int(color[i:i + ndigits], 16)) / div, 2)
                 for i in range(0, numel, ndigits))

def check_rgb_color(color):
    if len(color[1:]) % 3 != 0:
        ex = ValueError(_("Color must be specified as #RGB"))
        ex.from_validator = True
        raise ex

def check_rgba_color(color):
    if len(color[1:]) % 4 != 0:
        ex = ValueError(_("Color must be specified as #RGBA"))
        ex.from_validator = True
        raise ex


tempreport_exp = re.compile(r"([TB]\d*):([-+]?\d*\.?\d*)(?: ?\/)?([-+]?\d*\.?\d*)")
def parse_temperature_report(report):
    matches = tempreport_exp.findall(report)
    return dict((m[0], (m[1], m[2])) for m in matches)

def compile_file(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        return compile(f.read(), filename, 'exec')


def read_history_from(history_file):
    # Parameters:
    #   history_file : pathlib.Path
    history_list = []
    with history_file.open('r', encoding='utf-8') as hf:
        for line in hf:
            history_list.append(line.rstrip())
    return history_list


def write_history_to(history_file, history_list):
    # Parameters:
    #   history_file : pathlib.Path
    #   history_list : list of str
    with history_file.open('w', encoding='utf-8') as hf:
        for item in history_list:
            hf.write(item + '\n')

