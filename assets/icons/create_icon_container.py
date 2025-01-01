#!/usr/bin/env python3

import os
import shutil
import subprocess

def create_icons():
    """
    Converts the chosen resolutions into a Windows .ico file and
    a macOS .icns file. This script uses 'iconutil' and can therefore only
    work on macOS.
    """
    dir_path = os.path.dirname(os.path.realpath(__file__))
    os.chdir(dir_path)
    icondirs = ("pronterface", "pronterface_mac", "pronsole", "g_plater", "stl_plater")
    ico_res = ("16x16", "24x24", "32x32", "48x48", "64x64", "128x128", "256x256")
    icns_res = ("16x16", "16x16@2x", "32x32", "32x32@2x", "128x128", "128x128@2x", "256x256", "256x256@2x", "512x512", "512x512@2x")

    ico_pngs = {}
    icns_pngs = {}

    for iconname in icondirs:
        basepath = os.path.join(dir_path, iconname)
        if not os.path.isdir(basepath):
            print(f"WARNING: The folder does not exist: {basepath}")
            continue

        if iconname != "pronterface_mac":
            pngs = []
            for res in ico_res:
                png = os.path.join(basepath, iconname + '_' + res + ".png")
                if not os.path.isfile(png):
                    print(f"WARNING: The resolution does not exist: {png}")
                else:
                    pngs.append(png)
            ico_pngs[iconname] = pngs

        if iconname != "pronterface":
            pngs = []
            for res in icns_res:
                png = os.path.join(basepath, iconname + '_' + res + ".png")
                if not os.path.isfile(png):
                    print(f"WARNING: The resolution does not exist: {png}")
                else:
                    pngs.append(png)
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
        basepath = os.path.join(dir_path, iconname)
        icns_output = iconname + ".icns"
        if icns_output == "pronterface_mac.icns":
            icns_output = "pronterface.icns"

        iconset = basepath + ".iconset"
        os.mkdir(iconset)
        for png in files:
            name = os.path.split(png)[1].replace(iconname, "icon")
            shutil.copyfile(png, os.path.join(iconset, name))

        # Convert collected files to ICNS format
        try:
            subprocess.run(['iconutil', '--convert', 'icns', iconset, '--output', icns_output], check=True)
            print(f"Successfully created ICNS file: {icns_output}")
        except subprocess.CalledProcessError as e:
            print(f"Error occurred while creating ICNS file: {e}")
        finally:
            shutil.rmtree(iconset)


if __name__ == "__main__":
    create_icons()

