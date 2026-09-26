# PyInstaller spec.
# Build with:  pyinstaller sysadmin_swissknife.spec
#   macOS   -> dist/Sysadmin Swissknife.app
#   Windows -> dist/Sysadmin Swissknife.exe  (portable, single file)
import re
import sys

__version__ = re.search(r'__version__ = "([^"]+)"',
                        open("sysadmin_swissknife/__init__.py").read()).group(1)

a = Analysis(
    ["app.py"],
    datas=[("assets/icon.png", "assets")],
    excludes=[
        "tkinter", "matplotlib", "numpy", "scipy", "pandas", "IPython",
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
        "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.QtQuick", "PySide6.QtQml",
        "PySide6.QtMultimedia", "PySide6.QtCharts", "PySide6.QtDataVisualization",
        "PySide6.QtPdf", "PySide6.QtSql", "PySide6.QtBluetooth", "PySide6.QtSerialPort",
    ],
)
pyz = PYZ(a.pure)

if sys.platform == "win32":
    # portable single-file exe, nothing to install
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, name="Sysadmin Swissknife",
              console=False, icon="assets/icon.ico", upx=False)
else:
    exe = EXE(pyz, a.scripts, exclude_binaries=True, name="Sysadmin Swissknife",
              console=False, icon="assets/icon.png", upx=False)
    coll = COLLECT(exe, a.binaries, a.datas, name="Sysadmin Swissknife", upx=False)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Sysadmin Swissknife.app",
        icon="assets/icon.png",
        bundle_identifier="com.renero82.sysadmin-swissknife",
        info_plist={
            "CFBundleName": "Sysadmin Swissknife",
            "CFBundleDisplayName": "Sysadmin Swissknife",
            "CFBundleShortVersionString": __version__,
            "CFBundleVersion": __version__,
            "NSHighResolutionCapable": True,
            "LSApplicationCategoryType": "public.app-category.developer-tools",
        },
    )
