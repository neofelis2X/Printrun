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

import sys
import locale
import logging
import re
import subprocess

from datetime import date  # Write current year into About
import platform  # Basic hardware and os information
from urllib import request, error  # Used to check for updates on api.github
try:
    import simplejson as json
except ImportError:
    import json  # To load the response of api.github
import webbrowser  # Used to open the github/releases website
import wx
import wx.adv  # Contains HyperlinkCtrl
import psutil  # Provides RAM information
from pyglet import version as pyglet_version

from printrun import printcore  # Needed for Printrun __version__
from printrun.utils import install_locale
from .utils import get_scaled_icon, get_italic_font
from platformdirs import user_config_dir  # Provides path to the settings directory
from .widgets import get_space

install_locale('pronterface')

class AboutDialog(wx.Dialog):
    '''
    About Printrun Dialog, built from standard widgets.
    '''
    def __init__(self, parent, printed_filament: float):
        '''Create the About Printrun Dialog'''
        wx.Dialog.__init__(self, parent, title = _("About Printrun"),
                           style = wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.SetIcon(parent.GetIcon())

        major = get_space('major')
        minor = get_space('minor')
        mini = get_space('mini')
        wrap_width = self.FromDIP(380)

        # Header: icon, name, version
        icon = get_scaled_icon("pronterface", 72, self,
                               iconbundle = parent.GetIcons())
        bmp = wx.StaticBitmap(self, -1, wx.BitmapBundle(icon))

        name = wx.StaticText(self, -1, "Printrun")
        name.SetFont(name.GetFont().Scaled(2.0).Bold())
        version = wx.StaticText(self, -1, _("Version %s") % printcore.__version__)

        description = wx.StaticText(self, -1,
            _("Printrun is a pure Python host software for") + "\n" +
            _("3D printing and other types of CNC machines.") + "\n" +
            _("Pronterface is Printrun's graphical user interface."),
            style = wx.ALIGN_CENTER_HORIZONTAL)
        description.Wrap(wrap_width)

        filament = wx.StaticText(self, -1,
            _("%.02f mm of filament have been extruded during prints.") %
            printed_filament, style = wx.ALIGN_CENTER_HORIZONTAL)
        filament.Wrap(wrap_width)
        filament.SetFont(get_italic_font(filament.GetFont()))

        copyright_ = wx.StaticText(self, -1, f"(C) 2011 - {date.today().year}")
        copyright_.SetFont(copyright_.GetFont().Scaled(0.9))
        website = wx.adv.HyperlinkCtrl(self, -1, "github.com/kliment/Printrun",
                                       "https://github.com/kliment/Printrun")

        # Credits and licence
        notebook = wx.Notebook(self, -1)
        pages = ((_("Developers"), "\n".join(self.DEVELOPERS)),
                 (_("Documentation"), "\n".join(self.DOC_WRITERS)),
                 (_("Artwork"), "\n".join(self.ARTISTS)),
                 (_("Translations"), "\n".join(self.TRANSLATORS)),
                 (_("License"), self.LICENCE))
        for label, text in pages:
            notebook.AddPage(self._text_page(notebook, text), label)

        # Layout
        topsizer = wx.BoxSizer(wx.VERTICAL)
        center = wx.ALIGN_CENTER_HORIZONTAL
        titlesizer = wx.BoxSizer(wx.VERTICAL)
        titlesizer.Add(name, 0, wx.ALIGN_LEFT)
        titlesizer.Add(version, 0, wx.ALIGN_LEFT | wx.TOP, mini)
        headersizer = wx.BoxSizer(wx.HORIZONTAL)
        headersizer.Add(bmp, 0, wx.ALIGN_CENTER_VERTICAL)
        headersizer.Add(titlesizer, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, major)
        topsizer.Add(headersizer, 0, center | wx.TOP, major)
        topsizer.Add(description, 0, center | wx.LEFT | wx.RIGHT | wx.TOP, major)
        topsizer.Add(filament, 0, center | wx.LEFT | wx.RIGHT | wx.TOP, minor)
        topsizer.Add(copyright_, 0, center | wx.TOP, minor)
        topsizer.Add(website, 0, center | wx.TOP, mini)
        topsizer.Add(notebook, 1, wx.EXPAND | wx.ALL, major)

        btns = self.CreateStdDialogButtonSizer(wx.CLOSE)
        self.SetEscapeId(wx.ID_CLOSE)
        self.SetAffirmativeId(wx.ID_CLOSE)
        topsizer.Add(btns, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
                     get_space('stddlg'))

        self.SetSizer(topsizer)
        min_w = max(topsizer.GetMinSize()[0], wrap_width + 2 * major,
                    self._tabs_width(notebook) + 2 * major)
        self.SetMinClientSize(wx.Size(min_w, self.FromDIP(560)))
        self.SetClientSize(self.GetMinClientSize())
        self.Layout()
        self.CenterOnParent()

        self.Bind(wx.EVT_BUTTON, lambda e: self.Close(), id = wx.ID_CLOSE)
        self.Bind(wx.EVT_CLOSE, lambda e: self.Destroy())

    def _tabs_width(self, notebook: wx.Notebook) -> int:
        '''Approximate width needed to show all tab labels untruncated,
        since wx.Notebook does not report it reliably on all platforms.'''
        padding = self.FromDIP(28)
        return sum(notebook.GetTextExtent(notebook.GetPageText(i))[0] + padding
                   for i in range(notebook.GetPageCount()))

    @staticmethod
    def _text_page(parent: wx.Window, text: str) -> wx.Panel:
        '''Notebook page holding a read-only, multiline text box'''
        panel = wx.Panel(parent)
        textctrl = wx.TextCtrl(panel, -1, text,
                               style = wx.TE_READONLY | wx.TE_CENTRE | wx.TE_MULTILINE |
                               wx.TE_NOHIDESEL | wx.TE_WORDWRAP)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(textctrl, 1, wx.EXPAND | wx.ALL, get_space('mini'))
        panel.SetSizer(sizer)
        return panel

    LICENCE = ('Printrun is free software: you can redistribute it '
               'and / or modify it under the terms of the GNU General '
               'Public License as published by the Free Software '
               'Foundation, either version 3 of the License, or (at your '
               'option) any later version.\n\n'

               'Printrun is distributed in the hope that it will be useful, '
               'but WITHOUT ANY WARRANTY; without even the implied '
               'warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR '
               'PURPOSE.  See the GNU General Public License for more details.\n\n'

               'You should have received a copy of the GNU General Public '
               'License along with Printrun. If not, see '
               '<http://www.gnu.org/licenses/>.')

    DEVELOPERS = ['Kliment Yanev @kliment',
                  'Guillaume Seguin @iXce',
                  '@DivingDuck',
                  '@volconst',
                  'Rock Storm @rockstorm101 (code, packaging)',
                  'Miro Hrončok @hroncok (code, packaging)',
                  'Rob Gilson @D1plo1d',
                  'Gary Hodgson @garyhodgson',
                  'Duane Johnson (code, graphics)',
                  'Alessandro Ranellucci @alranel',
                  'Travis Howse @tjhowse',
                  'edef',
                  'Steven Devijver',
                  'Christopher Keller',
                  'Igor Yeremin',
                  'Jeremy Hammett @jezmy',
                  'Spencer Bliven',
                  "Václav 'ax' Hůla  @AxTheB",
                  'Félix Sipma',
                  'Maja M. @SparkyCola',
                  'Francesco Santini @fsantini',
                  'Cristopher Olah @colah',
                  'Jeremy Kajikawa',
                  'Markus Hitter',
                  'SkateBoss',
                  'Kaz Walker',
                  'Elias',
                  'Jordan Miller',
                  'Mikko Sivulainen',
                  'Clarence Risher',
                  'Guillaume Revaillot',
                  'John Tapsell',
                  'Youness Alaoui',
                  '@eldir',
                  '@hg42',
                  '@jglauche (docs, code)',
                  'Ahmet Cem TURAN @ahmetcemturan (icons, code)',
                  'Andrew Dalgleish',
                  'Chillance',
                  'Ilya Novoselov',
                  'Joeri Hendriks',
                  'Kevin Cole',
                  'pinaise',
                  'Dratone',
                  'ERoth3',
                  'Erik Zalm',
                  'Felipe Corrêa da Silva Sanches',
                  'Geordie Bilkey',
                  'Ken Aaker',
                  'Loxgen',
                  'Matthias Urlichs',
                  'N Oliver',
                  '@nexus511',
                  'Sergey Shepelev',
                  'Simon Maillard',
                  'Vanessa Dannenberg',
                  '@beardface',
                  '@hurzl',
                  'Justin Hawkins @beardface',
                  'tobbelobb',
                  '5ilver (packaging)',
                  'Alexander Hiam',
                  'Alexander Zangerl',
                  'Cameron Currie',
                  'Colin Gilgenbach',
                  'DanLipsitt',
                  'Daniel Holth',
                  'Denis B',
                  'Erik Jonsson',
                  'Felipe Acebes',
                  'Florian Gilcher',
                  'Henrik Brix Andersen',
                  'Javier Rios',
                  'Jay Proulx',
                  'Jim Morris',
                  'Kyle Evans',
                  'Lenbok',
                  'Lukas Erlacher',
                  'Matthias @neofelis2X',
                  'Michael Andresen @blddk',
                  'NeoTheFox',
                  'OhmEye',
                  'OliverEngineer',
                  'Paul Telfort',
                  "Sebastian 'Swift Geek' Grzywna",
                  'Sigma-One',
                  'Stefan Glatzel',
                  'Stefanowicz',
                  'Steven',
                  'Xabi Xab',
                  'Xoan Sampaiño',
                  "Yuri D'Elia",
                  'drf5n',
                  'fieldOfView',
                  'jbh',
                  'kludgineer',
                  'l4nce0',
                  'palob',
                  'russ'
                  ]

    DOC_WRITERS = ['Brendan Erwin',
                   '@jglauche (docs, code)',
                   'Benny',
                   'Lawrence',
                   'siorai',
                   'Chris DeLuca',
                   'Jan Wildeboer',
                   'Nicolas Dandrimont',
                   'Senthil',
                   'Spacexula',
                   'Tyler Hovanec',
                   'evilB',
                   ]

    ARTISTS = ['Ahmet Cem TURAN @ahmetcemturan (icons, code)',
               'Duane Johnson (graphics, code)'
               ]

    TRANSLATORS = ['freddii (German)',
                   'Christian Metzen @metzench (German)',
                   'Cyril Laguilhon-Debat (French)',
                   '@AvagSayan (Armenian)',
                   'Jonathan Marsden (French)',
                   'Ruben Lubbes (Dutch)',
                   'aboobed (Arabic)',
                   'Alessandro Ranellucci @alranel (Italian)'
                   ]

class SystemInfo(wx.Dialog):
    '''
    Collect basic information about the system, os and Printrun
    Report the information in a window with TextCtrl.
    '''
    def __init__(self, parent, log_path: str):
        '''Show System Info Dialog'''
        wx.Dialog.__init__(self, parent,
                           title = _("System Information"),
                           size = wx.Size(400, 450),
                           style = wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)

        self.SetIcon(parent.GetIcon())
        self.CenterOnParent()

        message = _('Basic information about Printrun and your operating '
                    'system.\nIf you open a Printrun issue on GitHub, please '
                    'consider\nadding this information to your bug report.')

        self.log = log_path
        info = self.collect_info()

        topsizer = wx.BoxSizer(wx.VERTICAL)
        description = wx.StaticText(self, -1, message)
        self.infotext = wx.TextCtrl(self, -1, info,
                                    style = wx.TE_READONLY | wx.TE_MULTILINE | wx.TE_NOHIDESEL)
        copy_button = wx.Button(self, -1, _("Copy to Clipboard"))
        copy_button.Bind(wx.EVT_BUTTON, self.copy_all)

        topsizer.Add(description, 0, wx.EXPAND | wx.ALL, get_space('minor'))
        topsizer.Add(self.infotext, 1, wx.EXPAND | wx.ALL, get_space('none'))
        topsizer.Add(copy_button, 0, wx.EXPAND | wx.ALL, get_space('mini'))
        topsizer.Add(wx.StaticLine(self, -1, style = wx.LI_HORIZONTAL), 0, wx.EXPAND)
        topsizer.Add(self.CreateButtonSizer(wx.OK), 0, wx.ALIGN_RIGHT | wx.ALL, get_space('stddlg'))
        self.SetSizer(topsizer)
        self.SetMinClientSize(wx.Size(description.GetBestSize()[0] + 16, 300))
        self.Layout()

    def copy_all(self, event):
        self.infotext.SelectAll()
        self.infotext.Copy()
        self.infotext.SetFocus()

    def collect_info(self):
        locale.setlocale(locale.LC_ALL, '')
        lang, encoding = locale.getlocale()

        mem = psutil.virtual_memory()

        info = (f"```\n"
                f"----------------- Printrun ----------------\n"
                f"Printrun {printcore.__version__}, argv: {sys.argv[1:]}\n"
                f"Log path: {self.log}\n"
                f"wxPython: {wx.version()}\n"
                f"pyglet: {pyglet_version}\n"
                f"------------------ System -----------------\n"
                f"{platform.system()}, Kernel {platform.release()}\n"
                f"{os_name()}, {platform.machine()}, {platform.architecture()[0]}\n"
                f"Locale: {lang}, {encoding} (from locale.getlocale)\n"
                f"RAM total: {mem.total / (1024 ** 2)} MB, used: {mem.percent} %\n"
                f"------------------ Python ------------------\n"
                f"{platform.python_implementation()} {platform.python_version()}, "
                f"build: {', '.join(platform.python_build())}\n"
                f"Python Compiler: {platform.python_compiler()}\n"
                f"```"
                )

        return info


def os_name() -> str:
    '''Human readable name and version of the operating system'''
    system = platform.system()
    if system == 'Darwin':
        return f"macOS {platform.mac_ver()[0]}"
    if system == 'Windows':
        return f"Windows {platform.release()} {platform.win32_edition()} " \
               f"({platform.version()})"
    try:  # Linux and other systems with /etc/os-release
        return platform.freedesktop_os_release().get('PRETTY_NAME', system)
    except OSError:
        return system

def open_rc_dir():
    """Open the settings directory"""
    def open_folder(arg: str):
        config_dir = user_config_dir("Printrun")
        try:
            subprocess.run([arg, config_dir], check = True)
        except FileNotFoundError:
            logging.info(_("Opening the directory failed. "
                           "Please try to open the path manually:"))
            logging.info(config_dir)

    platformname = platform.system()
    if platformname == 'Windows':
        open_folder('explorer')
    elif platformname == 'Darwin':
        open_folder('open')
    else:  # Linux
        open_folder('xdg-open')

def version_tuple(version: str) -> tuple:
    '''Turn a version string like '2.2.0' into (2, 2, 0) for comparison'''
    return tuple(int(n) for n in re.findall(r'\d+', version))

def check_update(parent):
    '''Request the version on github and compare with this version
        :return: 0, No Update
        :return: 1, Update available
        :return: 2, Connection failed
    '''
    my_version = printcore.__version__
    api_url = "https://api.github.com/repos/kliment/printrun/releases/latest"

    request_ = request.Request(api_url)
    try:
        with request.urlopen(request_) as response:
            gh_response = json.loads(response.read().decode("utf-8"))
    except error.URLError as err:
        if 'CERTIFICATE_VERIFY_FAILED' in str(err):
            logging.warning("Update Checker: Could not connect to github.com " \
                            "because required SSL certificates were not found. " \
                            "Please try 'pip install certifi' to use this function.")
        else:
            logging.warning("Update Checker: Could not connect to github.com.")

        return 2  # Connection failed

    gh_version = gh_response['name'].replace('Printrun ', '')
    if version_tuple(gh_version) > version_tuple(my_version):
        repo_url = "https://github.com/kliment/Printrun/releases"
        message = _("Printrun {0} is available on GitHub, \
                    \nyou are using version {1}.\nWould you like to open \
                    {2} to download it?").format(gh_version, my_version, repo_url)

        dlg = wx.MessageDialog(parent, message,
                               _("Update available!"),
                               wx.YES_NO | wx.NO_DEFAULT | wx.ICON_NONE
                               )
        if dlg.ShowModal() == wx.ID_YES:
            webbrowser.open(repo_url, new = 2)
        dlg.Destroy()
        return 1  # Update available

    message = _("Printrun {0} is the latest version.").format(my_version)
    dlg = wx.MessageDialog(parent, message,
                            _("You are up-to-date."),
                            wx.OK | wx.ICON_NONE
                            )
    dlg.ShowModal()
    dlg.Destroy()
    return 0  # No Update
