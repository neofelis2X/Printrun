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

import wx

from .xybuttons import XYButtons, XYButtonsMini
from .zbuttons import ZButtons, ZButtonsMini
from .graph import Graph
from .widgets import TempGauge, get_space
from wx.lib.agw.floatspin import FloatSpin

from .utils import make_button, make_custom_button

class XYZControlsSizer(wx.GridBagSizer):

    def __init__(self, root, parentpanel = None):
        super(XYZControlsSizer, self).__init__()
        if not parentpanel: parentpanel = root.panel
        root.xyb = XYButtons(parentpanel, root.moveXY, root.homeButtonClicked, root.spacebarAction, root.bgcolor, zcallback=root.moveZ)
        root.xyb.SetToolTip(_('[J]og controls. (Shift)+TAB ESC Shift/Ctrl+(arrows PgUp/PgDn)'))
        self.Add(root.xyb, pos = (0, 1), flag = wx.ALIGN_CENTER)
        root.zb = ZButtons(parentpanel, root.moveZ, root.bgcolor)
        self.Add(root.zb, pos = (0, 2), flag = wx.ALIGN_CENTER)

def add_extra_controls(self, root, parentpanel, extra_buttons = None, mini_mode = False):
    standalone_mode = extra_buttons is not None
    base_line = 1 if standalone_mode else 2

    if standalone_mode:
        gauges_base_line = base_line + 9
    elif mini_mode and root.display_graph:
        gauges_base_line = base_line + 6
    else:
        gauges_base_line = base_line + 5
    tempdisp_line = gauges_base_line + (2 if root.display_gauges else 0)
    if mini_mode and root.display_graph:
        e_base_line = base_line + 3
    else:
        e_base_line = base_line + 2

    pos_mapping = {
        "htemp": (base_line, 0),
        "btemp": (base_line + 1, 0),
        "speedcontrol": (e_base_line, 0),
        "flowcontrol": (e_base_line + 1, 0),
        "esettings": (e_base_line + 2, 0),
        "htemp_gauge": (gauges_base_line + 0, 0),
        "btemp_gauge": (gauges_base_line + 1, 0),
        "tempdisp": (tempdisp_line, 0),
    }

    span_mapping = {
        "htemp": (1, 5 if root.display_graph else 6),
        "btemp": (1, 5 if root.display_graph else 6),
        "speedcontrol": (1, 5 if root.display_graph else 6),
        "flowcontrol": (1, 5 if root.display_graph else 6),
        "esettings": (1, 5 if root.display_graph else 6),
        "tempdisp": (1, 5 if mini_mode else 6),
        "htemp_gauge": (1, 6),
        "btemp_gauge": (1, 6),
    }

    if standalone_mode:
        pos_mapping["tempgraph"] = (base_line + 6, 0)
        span_mapping["tempgraph"] = (3, 2)
    elif mini_mode:
        pos_mapping["tempgraph"] = (base_line + 2, 0)
        span_mapping["tempgraph"] = (1, 5)
    else:
        pos_mapping["tempgraph"] = (base_line + 0, 5)
        span_mapping["tempgraph"] = (5, 1)

    if mini_mode:
        pos_mapping["edist_val"] = (0, 0)
        pos_mapping["edist_unit"] = (0, 1)
        pos_mapping["efeed_val"] = (0, 2)
        pos_mapping["efeed_unit"] = (0, 3)
        pos_mapping["ebuttons"] = (1, 0)
        span_mapping["ebuttons"] = (1, 4)
    else:
        pos_mapping["edist_label"] = (0, 0)
        pos_mapping["edist_val"] = (1, 0)
        pos_mapping["edist_unit"] = (1, 1)
        pos_mapping["efeed_label"] = (0, 2)
        pos_mapping["efeed_val"] = (1, 2)
        pos_mapping["efeed_unit"] = (1, 3)
        pos_mapping["ebuttons"] = (2, 0)
        span_mapping["ebuttons"] = (1, 4)

    def add(name, widget, *args, **kwargs):
        kwargs["pos"] = pos_mapping[name]
        if name in span_mapping:
            kwargs["span"] = span_mapping[name]
        if "container" in kwargs:
            container = kwargs["container"]
            del kwargs["container"]
        else:
            container = self
        container.Add(widget, *args, **kwargs)

    # Hotend & bed temperatures #

    # Hotend temp
    etempsizer = wx.BoxSizer()
    etemp_label = wx.StaticText(parentpanel, -1, _("Heat:"))
    etempsizer.Add(etemp_label, flag = wx.ALIGN_CENTER_VERTICAL)
    etempsizer.AddSpacer(get_space("mini"))

    root.settoff = make_button(parentpanel, _("Off"), lambda e: root.do_settemp("0.0"), _("Switch Hotend Off"), style = wx.BU_EXACTFIT)
    root.printerControls.append(root.settoff)
    etempsizer.Add(root.settoff)
    etempsizer.AddSpacer(get_space("mini"))

    root.htemp = wx.ComboBox(parentpanel, style = wx.CB_DROPDOWN)
    root.htemp.SetToolTip(wx.ToolTip(_("Select Temperature for [H]otend")))
    root.htemp.Bind(wx.EVT_COMBOBOX, root.htemp_change)
    etempsizer.Add(root.htemp, 1, flag = wx.EXPAND)
    etempsizer.AddSpacer(get_space("mini"))
    etempsizer.Add(wx.StaticText(parentpanel, -1, _("°C")), flag = wx.ALIGN_CENTER_VERTICAL)
    etempsizer.AddSpacer(get_space("minor"))

    root.settbtn = make_button(parentpanel, _("Set"), root.do_settemp, _("Switch Hotend On"), style = wx.BU_EXACTFIT)
    root.printerControls.append(root.settbtn)
    etempsizer.Add(root.settbtn)
    add("htemp", etempsizer, flag = wx.EXPAND | wx.BOTTOM,
        border = get_space("mini"))

    # Bed temp
    btempsizer = wx.BoxSizer()
    btempsizer.Add(wx.StaticText(parentpanel, -1, _("Bed:"), size = etemp_label.GetSize()), flag = wx.ALIGN_CENTER_VERTICAL)
    btempsizer.AddSpacer(get_space("mini"))

    root.setboff = make_button(parentpanel, _("Off"), lambda e: root.do_bedtemp("0.0"), _("Switch Heated Bed Off"), style = wx.BU_EXACTFIT)
    root.printerControls.append(root.setboff)
    btempsizer.Add(root.setboff)
    btempsizer.AddSpacer(get_space("mini"))

    root.btemp = wx.ComboBox(parentpanel, style = wx.CB_DROPDOWN)
    root.btemp.SetToolTip(wx.ToolTip(_("Select Temperature for Heated [B]ed")))
    root.btemp.Bind(wx.EVT_COMBOBOX, root.btemp_change)
    btempsizer.Add(root.btemp, 1)
    btempsizer.AddSpacer(get_space("mini"))
    btempsizer.Add(wx.StaticText(parentpanel, -1, _("°C")), flag = wx.ALIGN_CENTER_VERTICAL)
    btempsizer.AddSpacer(get_space("minor"))

    root.setbbtn = make_button(parentpanel, _("Set"), root.do_bedtemp, _("Switch Heated Bed On"), style = wx.BU_EXACTFIT)
    root.printerControls.append(root.setbbtn)
    btempsizer.Add(root.setbbtn)
    add("btemp", btempsizer, flag = wx.EXPAND | wx.BOTTOM,
        border = get_space("mini"))

    def set_labeled(temp, choices, widget):
        choices = [(float(p[1]), p[0]) for p in choices.items()]
        if not next((1 for p in choices if p[0] == temp), False):
            choices.append((temp, 'user'))

        choices = sorted(choices)
        widget.Items = ['%s (%s)'%tl for tl in choices]
        widget.Selection = next((i for i, tl in enumerate(choices) if tl[0] == temp), -1)

    set_labeled(root.settings.last_bed_temperature, root.bedtemps, root.btemp)
    set_labeled(root.settings.last_temperature, root.temps, root.htemp)

    # Speed control #
    speedpanel = root.newPanel(parentpanel)
    speedsizer = wx.BoxSizer(wx.HORIZONTAL)
    speed_label = wx.StaticText(speedpanel, -1, _("Print Speed:"))
    speedsizer.Add(speed_label, flag = wx.ALIGN_CENTER_VERTICAL)
    speedsizer.AddSpacer(get_space("minor"))

    root.speed_slider = wx.Slider(speedpanel, -1, 100, 1, 300)
    speedsizer.Add(root.speed_slider, 1, flag = wx.EXPAND)
    speedsizer.AddSpacer(get_space("minor"))

    root.speed_spin = wx.SpinCtrlDouble(speedpanel, -1, initial = 100, min = 1, max = 300, style = wx.ALIGN_LEFT, size = wx.Size(60, -1))
    root.speed_spin.SetDigits(0)
    speedsizer.Add(root.speed_spin, 0, flag = wx.ALIGN_CENTER_VERTICAL)
    speedsizer.AddSpacer(get_space("mini"))
    root.speed_label = wx.StaticText(speedpanel, -1, _("%"))
    speedsizer.Add(root.speed_label, flag = wx.ALIGN_CENTER_VERTICAL)
    speedsizer.AddSpacer(get_space("minor"))

    def speedslider_set(event):
        root.do_setspeed()
        root.speed_setbtn.SetBackgroundColour(wx.NullColour)
    root.speed_setbtn = make_button(speedpanel, _("Set"), speedslider_set,
                                    _("Set print speed factor"), style = wx.BU_EXACTFIT)
    root.printerControls.append(root.speed_setbtn)
    speedsizer.Add(root.speed_setbtn, flag = wx.ALIGN_CENTER)
    speedpanel.SetSizer(speedsizer)
    add("speedcontrol", speedpanel, flag = wx.EXPAND | wx.BOTTOM,
        border = get_space("mini"))

    def speedslider_spin(event):
        value = root.speed_spin.GetValue()
        root.speed_setbtn.SetBackgroundColour(wx.RED)
        root.speed_slider.SetValue(int(value))
    root.speed_spin.Bind(wx.EVT_SPINCTRLDOUBLE, speedslider_spin)

    def speedslider_scroll(event):
        value = root.speed_slider.GetValue()
        root.speed_setbtn.SetBackgroundColour(wx.RED)
        root.speed_spin.SetValue(value)
    root.speed_slider.Bind(wx.EVT_SCROLL, speedslider_scroll)

    # Flow control #
    flowpanel = root.newPanel(parentpanel)
    flowsizer = wx.BoxSizer(wx.HORIZONTAL)
    flowsizer.Add(wx.StaticText(flowpanel, -1, _("Print Flow:"), size = speed_label.GetSize()), flag = wx.ALIGN_CENTER_VERTICAL)
    flowsizer.AddSpacer(get_space("minor"))

    root.flow_slider = wx.Slider(flowpanel, -1, 100, 1, 300)
    flowsizer.Add(root.flow_slider, 1, flag = wx.EXPAND)
    flowsizer.AddSpacer(get_space("minor"))

    root.flow_spin = wx.SpinCtrlDouble(flowpanel, -1, initial = 100, min = 1, max = 300, style = wx.ALIGN_LEFT, size = wx.Size(60, -1))
    flowsizer.Add(root.flow_spin, 0, flag = wx.ALIGN_CENTER_VERTICAL)
    flowsizer.AddSpacer(get_space("mini"))
    root.flow_label = wx.StaticText(flowpanel, -1, _("%"))
    flowsizer.Add(root.flow_label, flag = wx.ALIGN_CENTER_VERTICAL)
    flowsizer.AddSpacer(get_space("minor"))

    def flowslider_set(event):
        root.do_setflow()
        root.flow_setbtn.SetBackgroundColour(wx.NullColour)
    root.flow_setbtn = make_button(flowpanel, _("Set"), flowslider_set, _("Set print flow factor"), style = wx.BU_EXACTFIT)
    root.printerControls.append(root.flow_setbtn)
    flowsizer.Add(root.flow_setbtn, flag = wx.ALIGN_CENTER)
    flowpanel.SetSizer(flowsizer)
    add("flowcontrol", flowpanel, flag = wx.EXPAND)

    def flowslider_spin(event):
        value = root.flow_spin.GetValue()
        root.flow_setbtn.SetBackgroundColour(wx.RED)
        root.flow_slider.SetValue(int(value))
    root.flow_spin.Bind(wx.EVT_SPINCTRLDOUBLE, flowslider_spin)

    def flowslider_scroll(event):
        value = root.flow_slider.GetValue()
        root.flow_setbtn.SetBackgroundColour(wx.RED)
        root.flow_spin.SetValue(value)
    root.flow_slider.Bind(wx.EVT_SCROLL, flowslider_scroll)

    # Temperature gauges #

    if root.display_gauges:
        root.hottgauge = TempGauge(parentpanel, size = (-1, 24), title = _("Heater:"), maxval = 300, bgcolor = root.bgcolor)
        root.hottgauge.SetTarget(root.settings.last_temperature)
        # root.hsetpoint = root.settings.last_temperature
        add("htemp_gauge", root.hottgauge, flag = wx.EXPAND | wx.BOTTOM, border = get_space("mini"))
        root.bedtgauge = TempGauge(parentpanel, size = (-1, 24), title = _("Bed:"), maxval = 150, bgcolor = root.bgcolor)
        root.bedtgauge.SetTarget(root.settings.last_bed_temperature)
        # root.bsetpoint = root.settings.last_bed_temperature
        add("btemp_gauge", root.bedtgauge, flag = wx.EXPAND)

        def scroll_gauge(rot, cmd, setpoint):
            if rot:
                temp = setpoint + (1 if rot > 0 else -1)
                cmd(str(max(0, temp)))

        def hotend_handler(e):
            scroll_gauge(e.WheelRotation, root.do_settemp, root.hsetpoint)

        def bed_handler(e):
            scroll_gauge(e.WheelRotation, root.do_bedtemp, root.bsetpoint)
        root.hottgauge.Bind(wx.EVT_MOUSEWHEEL, hotend_handler)
        root.bedtgauge.Bind(wx.EVT_MOUSEWHEEL, bed_handler)

        def updateGauge(e, gauge):
            gauge.SetTarget(float(e.String.split()[0]))

        root.htemp.Bind(wx.EVT_TEXT, lambda e: updateGauge(e, root.hottgauge))
        root.btemp.Bind(wx.EVT_TEXT, lambda e: updateGauge(e, root.bedtgauge))

    # Temperature (M105) feedback display #
    root.tempdisp = wx.StaticText(parentpanel, -1, "", style = wx.ST_NO_AUTORESIZE)

    def on_tempdisp_size(evt):
        root.tempdisp.Wrap(root.tempdisp.GetSize().width)
    root.tempdisp.Bind(wx.EVT_SIZE, on_tempdisp_size)

    def tempdisp_setlabel(label):
        wx.StaticText.SetLabel(root.tempdisp, label)
        root.tempdisp.Wrap(root.tempdisp.GetSize().width)
        root.tempdisp.SetSize((-1, root.tempdisp.GetBestSize().height))
    root.tempdisp.SetLabel = tempdisp_setlabel
    add("tempdisp", root.tempdisp, flag = wx.EXPAND)

    # Temperature graph #

    if root.display_graph:
        root.graph = Graph(parentpanel, wx.ID_ANY, root)
        flag = wx.EXPAND | wx.BOTTOM
        spacer = "mini"
        if not mini_mode:
            flag = flag | wx.LEFT
            spacer = "minor"
        add("tempgraph", root.graph, flag = flag, border = get_space(spacer))
        root.graph.Bind(wx.EVT_LEFT_DOWN, root.graph.show_graph_window)

    # Extrusion controls #

    # Extrusion settings
    esettingspanel = root.newPanel(parentpanel)
    esettingssizer = wx.GridBagSizer(vgap = get_space("mini"), hgap = get_space("mini"))
    esettingssizer.SetEmptyCellSize(wx.Size(-1, -1))
    esettingssizer.SetFlexibleDirection(wx.BOTH)
    root.edist = wx.SpinCtrlDouble(esettingspanel, -1, initial = root.settings.last_extrusion, min = 0, max = 1000)
    root.edist.SetMinSize(wx.Size(120, -1))
    root.edist.SetDigits(1)
    root.edist.Bind(wx.EVT_SPINCTRLDOUBLE, root.setfeeds)
    root.edist.Bind(wx.EVT_TEXT, root.setfeeds)

    add("edist_val", root.edist, container = esettingssizer,
        flag = wx.EXPAND | wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)
    add("edist_unit", wx.StaticText(esettingspanel, -1, _("mm @")),
        container = esettingssizer, flag = wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)
    root.edist.SetToolTip(wx.ToolTip(_("Amount to Extrude or Retract (mm)")))
    root.efeedc = wx.SpinCtrlDouble(esettingspanel, -1,
                                    initial = root.settings.e_feedrate,
                                    min = 0, max = 50000)
    root.efeedc.SetMinSize(wx.Size(120, -1))
    root.efeedc.SetDigits(1)
    root.efeedc.Bind(wx.EVT_SPINCTRLDOUBLE, root.setfeeds)
    root.efeedc.SetToolTip(wx.ToolTip(_("Extrude / Retract speed (mm/min)")))
    root.efeedc.Bind(wx.EVT_TEXT, root.setfeeds)
    add("efeed_val", root.efeedc, container = esettingssizer,
        flag =  wx.EXPAND | wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)
    add("efeed_unit", wx.StaticText(esettingspanel, -1, _("mm/min")),
        container = esettingssizer, flag = wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)

    if not mini_mode:
        add("edist_label", wx.StaticText(esettingspanel, -1, _("Length:")),
            container = esettingssizer, flag = wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)
        add("efeed_label", wx.StaticText(esettingspanel, -1, _("Speed:")),
            container = esettingssizer, flag = wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)

    ebuttonssizer = wx.BoxSizer(wx.HORIZONTAL)
    if root.settings.extruders > 1:
        etool_label = wx.StaticText(esettingspanel, -1, _("Tool:"))
        if root.settings.extruders == 2:
            root.extrudersel = wx.Button(esettingspanel, -1, "0", style = wx.BU_EXACTFIT)
            root.extrudersel.SetToolTip(wx.ToolTip(_("Click to switch current extruder")))

            def extrudersel_cb(event):
                if root.extrudersel.GetLabel() == "1":
                    new = "0"
                else:
                    new = "1"
                root.extrudersel.SetLabel(new)
                root.tool_change(event)
            root.extrudersel.Bind(wx.EVT_BUTTON, extrudersel_cb)
            root.extrudersel.GetValue = root.extrudersel.GetLabel
            root.extrudersel.SetValue = root.extrudersel.SetLabel
        else:
            choices = [str(i) for i in range(0, root.settings.extruders)]
            root.extrudersel = wx.ComboBox(esettingspanel, -1, choices = choices,
                                           style = wx.CB_DROPDOWN | wx.CB_READONLY,
                                           size = wx.Size(50, -1))
            root.extrudersel.SetToolTip(wx.ToolTip(_("Select current extruder")))
            root.extrudersel.SetValue(choices[0])
            root.extrudersel.Bind(wx.EVT_COMBOBOX, root.tool_change)

        root.printerControls.append(root.extrudersel)
        ebuttonssizer.Add(etool_label, proportion = 0, flag = wx.ALIGN_CENTER)
        ebuttonssizer.AddSpacer(get_space("mini"))
        ebuttonssizer.Add(root.extrudersel, proportion = 0)
        ebuttonssizer.AddSpacer(get_space("mini"))

    for key in ["extrude", "reverse"]:
        desc = root.cpbuttons[key]
        btn = make_custom_button(root, esettingspanel, desc,
                                 style = wx.BU_EXACTFIT)
        ebuttonssizer.Add(btn, proportion = 1, flag = wx.EXPAND)

    n = ebuttonssizer.GetItemCount()
    ebuttonssizer.InsertSpacer(n - 1, get_space("mini"))
    add("ebuttons", ebuttonssizer, container = esettingssizer, flag = wx.EXPAND)

    esettingssizer.AddGrowableCol(0)
    esettingssizer.AddGrowableCol(2)
    esettingspanel.SetSizer(esettingssizer)
    add("esettings", esettingspanel, flag = wx.EXPAND | wx.ALIGN_LEFT | wx.TOP | wx.BOTTOM,
        border = get_space("minor"))

class ControlsSizer(wx.GridBagSizer):

    def __init__(self, root, parentpanel = None, standalone_mode = False, mini_mode = False):
        super(ControlsSizer, self).__init__()
        if not parentpanel: parentpanel = root.panel
        if mini_mode: self.make_mini(root, parentpanel)
        else: self.make_standard(root, parentpanel, standalone_mode)

    def make_standard(self, root, parentpanel, standalone_mode):
        lltspanel = root.newPanel(parentpanel)
        llts = wx.BoxSizer(wx.HORIZONTAL)
        lltspanel.SetSizer(llts)
        self.Add(lltspanel, pos = (0, 0), span = (1, 6), flag = wx.EXPAND)
        xyzpanel = root.newPanel(parentpanel)
        self.xyzsizer = XYZControlsSizer(root, xyzpanel)
        xyzpanel.SetSizer(self.xyzsizer)
        self.Add(xyzpanel, pos = (1, 0), span = (1, 6), flag = wx.ALIGN_CENTER)

        self.extra_buttons = {}
        pos_mapping = {"extrude": (4, 0),
                       "reverse": (4, 2),
                       }
        span_mapping = {"extrude": (1, 2),
                        "reverse": (1, 3),
                        }
        for key, desc in root.cpbuttons.items():
            if not standalone_mode and key in ["extrude", "reverse"]:
                continue
            panel = lltspanel if key == "motorsoff" else parentpanel
            btn = make_custom_button(root, panel, desc)
            if key == "motorsoff":
                llts.Add(btn)
                llts.AddSpacer(get_space("minor"))
            elif not standalone_mode:
                self.Add(btn, pos = pos_mapping[key], span = span_mapping[key], flag = wx.EXPAND)
            else:
                self.extra_buttons[key] = btn

        llts.Add(wx.StaticText(lltspanel, -1, _("XY:")), flag = wx.ALIGN_CENTER_VERTICAL)
        llts.AddSpacer(get_space("mini"))
        root.xyfeedc = wx.SpinCtrl(lltspanel, -1, str(root.settings.xy_feedrate), min = 0, max = 50000)
        root.xyfeedc.SetToolTip(wx.ToolTip(_("Set Maximum Speed for X & Y axes (mm/min)")))
        root.xyfeedc.SetMinSize(wx.Size(100, -1))
        llts.Add(root.xyfeedc, 1)
        llts.AddSpacer(get_space("minor"))
        llts.Add(wx.StaticText(lltspanel, -1, _("Z:")), flag = wx.ALIGN_CENTER_VERTICAL)
        llts.AddSpacer(get_space("mini"))
        root.zfeedc = wx.SpinCtrl(lltspanel, -1, str(root.settings.z_feedrate), min = 0, max = 50000)
        root.zfeedc.SetToolTip(wx.ToolTip(_("Set Maximum Speed for Z axis (mm/min)")))
        root.zfeedc.SetMinSize(wx.Size(100, -1))
        llts.Add(root.zfeedc, 1)
        llts.AddSpacer(get_space("minor"))
        llts.Add(wx.StaticText(lltspanel, -1, _("mm/min")), flag = wx.ALIGN_CENTER_VERTICAL)

        root.xyfeedc.Bind(wx.EVT_SPINCTRL, root.setfeeds)
        root.zfeedc.Bind(wx.EVT_SPINCTRL, root.setfeeds)
        root.xyfeedc.Bind(wx.EVT_TEXT, root.setfeeds)
        root.zfeedc.Bind(wx.EVT_TEXT, root.setfeeds)

        if not standalone_mode:
            add_extra_controls(self, root, parentpanel, None)

    def make_mini(self, root, parentpanel):
        root.xyb = XYButtonsMini(parentpanel, root.moveXY, root.homeButtonClicked,
                                 root.spacebarAction, root.bgcolor,
                                 zcallback = root.moveZ)
        self.Add(root.xyb, pos = (1, 0), span = (1, 4), flag = wx.ALIGN_CENTER)
        root.zb = ZButtonsMini(parentpanel, root.moveZ, root.bgcolor)
        self.Add(root.zb, pos = (0, 4), span = (2, 1), flag = wx.ALIGN_CENTER)
        wx.CallAfter(root.xyb.SetFocus)

        pos_mapping = {"motorsoff": (0, 0),
                       }
        span_mapping = {"motorsoff": (1, 4),
                        }
        btn = make_custom_button(root, parentpanel, root.cpbuttons["motorsoff"])
        self.Add(btn, pos = pos_mapping["motorsoff"], span = span_mapping["motorsoff"], flag = wx.EXPAND)

        add_extra_controls(self, root, parentpanel, None, True)
