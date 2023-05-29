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
'''
Write the module docstring here
'''

import wx
import wx.adv
from printrun import printcore
from printrun.utils import iconfile, install_locale
install_locale('pronterface')

class AboutDialog:
    '''
    Creates the About Dialog Widget
    '''

    def __init__(self, printed_filament):
        """Show about dialog"""

        info = wx.adv.AboutDialogInfo()

        info.SetIcon(wx.Icon(iconfile("pronterface.png"), wx.BITMAP_TYPE_PNG))
        info.SetName('Printrun')
        info.SetVersion(printcore.__version__)

        description = ("      " +
                       _("Printrun is a pure Python 3D printing") +
                       " " +
                       _("(and other types of CNC) host software.") +
                       "      \n      " +
                       _("%.02fmm of filament have been extruded during prints.") %
                       printed_filament)
        info.SetDescription(description)

        info.SetCopyright('(C) 2011 - 2023')
        info.SetWebSite('https://github.com/kliment/Printrun')

        licence = ('Printrun is free software: you can redistribute it '
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

        info.SetLicence(licence)
        info.SetDevelopers(self.DEVELOPERS)
        info.SetDocWriters(self.DOC_WRITERS)
        info.SetArtists(self.ARTISTS)
        info.SetTranslators(self.TRANSLATORS)
        wx.adv.AboutBox(info)

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
