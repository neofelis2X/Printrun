#!/usr/bin/env python3

import os
import shutil
import subprocess

def create_icons() -> None:
    """
    Converts the chosen resolutions into a Windows .ico file and
    a macOS .icns file. This script uses 'iconutil' and can therefore only
    work on macOS.
    """
    rootpath = os.path.dirname(os.path.realpath(__file__))
    os.chdir(rootpath)
    icondirs = [f for f in os.scandir(rootpath) if f.is_dir()]
    ico_res = ("16x16", "24x24", "32x32", "48x48", "64x64", "128x128", "256x256")
    icns_res = ("16x16", "16x16@2x", "32x32", "32x32@2x", "128x128",
                "128x128@2x", "256x256", "256x256@2x", "512x512", "512x512@2x")

    ico_pngs = {}
    icns_pngs = {}

    for dir_name in icondirs:

        if dir_name.path.endswith("_all") or dir_name.path.endswith("_win"):
            pngs = []
            iconname = os.path.split(dir_name)[1].split('_')[0]
            for res in ico_res:
                png = os.path.join(dir_name, iconname + '_' + res + ".png")
                if not os.path.isfile(png):
                    print(f"WARNING: The resolution does not exist: {png}")
                else:
                    pngs.append(png)
            if pngs:
                ico_pngs[iconname] = pngs

        if dir_name.path.endswith("_all") or dir_name.path.endswith("_mac"):
            pngs = []
            iconname = os.path.split(dir_name)[1].split('_')[0]
            for res in icns_res:
                png = os.path.join(dir_name, iconname + '_' + res + ".png")
                if not os.path.isfile(png):
                    print(f"WARNING: The resolution does not exist: {png}")
                else:
                    pngs.append(png)
            if pngs:
                icns_pngs[iconname] = pngs

    for iconname, files in ico_pngs.items():
        ico_file = iconname + ".ico"
        # Convert collected files to ICO format
        try:
            subprocess.run(["magick", *files, ico_file], check=True)
            print(f"Successfully created ICO file: {ico_file}")
        except subprocess.CalledProcessError as e:
            print(f"Error occurred while creating ICO file: {e}")

    for iconname, files in icns_pngs.items():
        iconpath = os.path.join(rootpath, iconname)
        icns_output = iconname + ".icns"

        iconset = iconpath + ".iconset"
        os.mkdir(iconset)
        for png in files:
            name = os.path.split(png)[1].replace(iconname, "icon")
            shutil.copyfile(png, os.path.join(iconset, name))

        # Convert collected files to ICNS format
        try:
            subprocess.run(['iconutil', '--convert', 'icns', iconset,
                            '--output', icns_output], check=True)
            print(f"Successfully created ICNS file: {icns_output}")
        except subprocess.CalledProcessError as e:
            print(f"Error occurred while creating ICNS file: {e}")
        finally:
            shutil.rmtree(iconset)

    copy_icons(ico_pngs)

def copy_icons(ico_pths: dict) -> None:
    rootpath = os.path.dirname(os.path.realpath(__file__))
    os.chdir(rootpath)
    pths = (os.path.normpath(os.path.join(rootpath,
                                          "../../printrun/assets/icons/plater/")),
            os.path.normpath(os.path.join(rootpath,
                                          "../../printrun/assets/icons/pronterface/")))

    for pth in pths:
        if os.path.isdir(pth):
            shutil.rmtree(pth)

        os.mkdir(pth)
        for png in ico_pths[os.path.basename(pth)]:
            shutil.copy(png, pth)
            
    iconpngs = ("./plater_all/plater_256x256.png",
                "./pronsole_all/pronsole_256x256.png",
                "./pronterface_win/pronterface_256x256.png")

    for icn in iconpngs:
        shutil.copyfile(icn, os.path.split(icn)[1].split("_")[0] + ".png")


if __name__ == "__main__":
    create_icons()

