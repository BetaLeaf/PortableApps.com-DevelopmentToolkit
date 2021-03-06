# -*- coding: utf-8 -*-

from os.path import exists, isdir, isfile, join, abspath
import os
import config
from utils import path_insensitive, path_local, _
from languages import LANG
from shutil import copy2 as copy
import paf
from paf import PAFException


__all__ = ['Package', 'create_package', 'valid_package']


class Package(object):
    """
    Manages all the details of a package in (or not in!) PortableApps.com
    Format.
    """
    current_package = None

    _mandatory_dirs = [
            ('App',),
            ('App', 'AppInfo'),
            ('Other',),
            ('Other', 'Source'),
    ]

    _mandatory_files = [
            ('help.html',),
            ('App', 'AppInfo', 'appinfo.ini'),
            ('App', 'AppInfo', 'appicon.ico'),
            ('App', 'AppInfo', 'appicon_16.png'),
            ('App', 'AppInfo', 'appicon_32.png'),
    ]

    _recommended_dirs = [
            ('Other', 'Help'),
            ('Other', 'Help', 'Images'),
    ]

    __instances = {}

    def __new__(cls, *args, **kwargs):
        """
        Cache packages by package directory. Later we may be saving stuff that
        actually takes a while to load.
        """

        if args[0] not in cls.__instances:
            cls.__instances[args[0]] = object.__new__(cls)
        return cls.__instances[args[0]]

    @property
    def _recommended_files(self):
        files = []
        if not self.launcher_is_pal:
            # With PAL we expect to use the app template which includes all of
            # these values, so we make it errors.
            files += [
                # Always used, so recommended, but not in spec so not mandatory
                ('App', 'readme.txt'),
                ('Other', 'Help', 'Images', 'help_logo_top.png'),
                ('Other', 'Help', 'Images', 'favicon.ico'),
                ('Other', 'Help', 'Images', 'donation_button.png'),
                ('Other', 'Help', 'Images', 'help_background_footer.png'),
                ('Other', 'Help', 'Images', 'help_background_header.png'),
                ('Other', 'Source', 'Readme.txt'),
                ('Other', 'Source', 'LauncherLicense.txt')]
        return files

    _suggested_files = [
            ('App', 'AppInfo', 'appicon_75.png'),
            ('App', 'AppInfo', 'appicon_128.png'),
            ('Other', 'Source', 'License.txt'),
    ]

    _pal_dirs = [
            ('App', 'AppInfo', 'Launcher'),
    ]

    _pal_recommended_files = [
            ('App', 'AppInfo', 'Launcher', 'Splash.jpg'),
    ]

    @property
    def _pal_mandatory_files(self):
        files = [
            # Files from the template
            ('App', 'readme.txt'),
            ('Other', 'Help', 'Images', 'Donation_Button.png'),
            ('Other', 'Help', 'Images', 'Favicon.ico'),
            ('Other', 'Help', 'Images', 'Help_Background_Footer.png'),
            ('Other', 'Help', 'Images', 'Help_Background_Header.png'),
            ('Other', 'Help', 'Images', 'Help_Logo_Top.png'),
            ('Other', 'Source', 'AppNamePortable.ini'),
            ('Other', 'Source', 'LauncherLicense.txt'),
            ('Other', 'Source', 'Readme.txt')]
        if self.appid is not None:
            # If the AppID isn't set we don't want to complain about
            # App\AppInfo\Launcher\None.ini not existing
            files.insert(0,
                    ('App', 'AppInfo', 'Launcher', '%s.ini' % self.appid))
        return files

    @property
    def appid(self):
        "Get the AppID of the package."
        if self.appinfo.ini is None:
            return None
        if 'AppID' in self.appinfo.ini.Details:
            return self.appinfo.ini.Details.AppID
        # Compatibility with a former typo in the PAF spec
        elif 'AppId' in self.appinfo.ini.Details:
            return self.appinfo.ini.Details.AppId
        else:
            return None

    def __init__(self, package, launcher_is_pal=None):
        Package.current_package = self
        self._directory = package

        if abspath(package) == join(config.ROOT_DIR, 'app-template'):
            # No-one's meant to know about this ;-)
            raise PAFException("Nice try. That's a skeleton package - it's " +
                    "not *meant* to be valid. Try somethin' else.")

        if not isdir(package):
            raise PAFException(_("Package directory does not exist!"))

        # Check if it's a plugin installer
        if isfile(self.path('Other', 'Source', 'plugininstaller.ini')):
            self.plugin = True
            self._mandatory_files = self._mandatory_files[:]
            self._mandatory_files[self._mandatory_files.index(('App',
                'AppInfo', 'appinfo.ini'))] = \
                        ('Other', 'Source', 'plugininstaller.ini')
        else:
            self.plugin = False

        if launcher_is_pal == None:
            # Auto-detect; new apps: yes. Old apps: no
            if isdir(self.path('App', 'AppInfo')):
                # App/AppInfo exists, what about App/AppInfo/Launcher?
                self.launcher_is_pal = isdir(self.path('App', 'AppInfo',
                    'Launcher'))
            else:
                # New app, so use PAL.
                self.launcher_is_pal = True
        elif launcher_is_pal in (True, False):
            self.launcher_is_pal = launcher_is_pal
        else:
            raise PAFException("Invalid value given for launcher_is_pal, " +
                "must be None, True or False.")

        self.appinfo = paf.AppInfo(self)
        self.installer = paf.Installer(self)
        self.launcher = paf.Launcher(self)

        self.validate()

    def path(self, *path):
        """
        Get the absolute path to a package-relative path. When given multiple
        arguments, it joins them with the system directory separator.
        """
        return path_insensitive(join(self._directory, *path))

    def _dirlist(self, recommended=False):
        dirlist = self._mandatory_dirs[:]
        if recommended:
            dirlist += self._recommended_dirs
        if self.launcher_is_pal:
            dirlist += self._pal_dirs
        return dirlist

    def fix_missing_directories(self):
        "Create required directories that are missing in the package."
        for dirname in self._dirlist(recommended=True):
            dirpath = self.path(*dirname)
            if exists(dirpath):
                if isdir(dirpath):
                    pass  # Directory exists, fine.
                else:
                    raise PAFException(_('%s should be a directory but a ' +
                        'file with that name already exists') % join(*dirname))
            else:
                os.mkdir(dirpath)

    def _filelist(self, recommended=False):
        filelist = self._mandatory_files[:]
        if recommended:
            filelist += self._recommended_files
        if self.launcher_is_pal:
            filelist += self._pal_mandatory_files
            if recommended:
                filelist += self._pal_recommended_files
        return filelist

    def fix_missing_files(self):
        "Create required files that are missing in the package."
        for filename in self._filelist(recommended=True):
            filepath = self.path(*filename)
            if exists(filepath):
                if isfile(filepath):
                    pass  # File exists, fine.
                else:
                    raise PAFException(_('%s should be a file but a ' +
                    'directory with that name already exists') %
                    join(*filename))
            elif isfile(join(config.ROOT_DIR, 'app-template', *filename)):
                copy(join(config.ROOT_DIR, 'app-template', *filename),
                        filepath)

    def fix(self):
        "Fix everything possible in the package."
        self.fix_missing_directories()
        self.fix_missing_files()
        self.validate()

    def validate(self):
        """
        Validate or revalidate the package to check PortableApps.com Format™
        compliance.
        """

        self.appinfo.load()
        appcompactor = paf.AppCompactor(self)
        appcompactor.load()

        self.errors = []
        self.warnings = []
        self.info = []

        if not self.launcher_is_pal:
            self.info.append(LANG.GENERAL.NOT_USING_PAL)

        for directory in self._dirlist():
            if not isdir(self.path(*directory)):
                self.errors.append(LANG.GENERAL.DIRECTORY_MISSING %
                        join(*directory))

        for filename in self._filelist():
            if isdir(os.path.dirname(self.path(*filename))) and \
            not isfile(self.path(*filename)):
                self.errors.append(LANG.GENERAL.FILE_MISSING % join(*filename))

        for directory in self._recommended_dirs:
            if not isdir(self.path(*directory)):
                self.warnings.append(LANG.GENERAL.DIRECTORY_MISSING %
                        join(*directory))

        recommended_files = self._recommended_files[:]
        if self.launcher_is_pal:
            recommended_files += self._pal_recommended_files
        for filename in recommended_files:
            if isdir(os.path.dirname(self.path(*filename))) and \
            not isfile(self.path(*filename)):
                self.warnings.append(LANG.GENERAL.FILE_MISSING %
                        join(*filename))

        for filename in self._suggested_files:
            if isdir(os.path.dirname(self.path(*filename))) and \
            not isfile(self.path(*filename)):
                self.info.append(LANG.GENERAL.SUGGESTED_FILE_MISSING %
                        join(*filename))

        for o in (self.appinfo, appcompactor):
            o.validate()
            self.errors.extend(o.errors)
            self.warnings.extend(o.warnings)
            self.info.extend(o.info)

    @property
    def eula(self):
        """
        Checks if an EULA exists and returns the path (relative to the package
        directory). If there is no EULA, returns None.

        For a normal package, the EULA will be Other\Source\EULA.rtf or
        Other\Source\EULA.txt.

        For a plugin package, the EULA will be Other\Source\PluginEULA.rtf or
        Other\Source\PluginEULA.txt.
        """

        if self.plugin:
            eula_path = join('Other', 'Source', 'PluginEULA')
        else:
            eula_path = join('Other', 'Source', 'EULA')

        for extension in ('rtf', 'txt'):
            if isfile(self.path('%s.%s' % (eula_path, extension))):
                return '%s.%s' % (eula_path, extension)

        return None

    def installed_size(self):
        """
        Get the installed size of a package based on the current directory
        contents. Returns (size without optional component, size with optional
        component) in bytes. For packages with no optional component, these
        figures will naturally be the same.
        """

        size_with_optional = 0
        size_without_optional = 0
        optional_dirs = [self.path(path_local(p)) for p in self.installer.optional_component_directories()]
        optional_files = [self.path(path_local(p)) for p in self.installer.optional_component_files()]
        data_dir = self.path('Data')
        for path, dirnames, filenames in os.walk(self.path()):
            dir_optional = any(path == dir or path.startswith(dir + os.path.sep) for dir in optional_dirs)
            # Optional components can include stuff in Data, but for the rest
            # Data is excluded.  So bear that in mind when making calculations.
            in_data = path == data_dir or path.startswith(data_dir + os.path.sep)
            for _f in filenames:
                file_name = os.path.join(path, _f)
                file_size = os.path.getsize(file_name)
                if dir_optional or file_name in optional_files:
                    # Component: no increase when not installed, increase
                    # regardless of whether in Data when installed.
                    size_with_optional += file_size
                elif not in_data:
                    # Main portion: always installed, but Data not included
                    size_without_optional += file_size
                    size_with_optional += file_size

        return size_without_optional, size_with_optional


def create_package(path, create_if_not_exist=False, require_empty=True):
    """
    Create an app package in PortableApps.com Format™.  By default, the
    directory must exist and be empty or a ``PAFException`` will be raised.
    """
    if exists(path):
        if isdir(path):
            pass  # Directory exists, fine.
        else:
            raise PAFException(LANG.GENERAL.FILE_NOT_DIRECTORY)
    elif create_if_not_exist:
        os.mkdir(path)
    else:
        raise PAFException(LANG.GENERAL.DIRECTORY_NOT_EXIST)

    if require_empty and os.listdir(path):
        raise PAFException(LANG.GENERAL.DIRECTORY_NOT_EMPTY)

    package = Package(path)
    package.fix()
    return package


def valid_package(path):
    """
    Method to check if a given directory is a PAF package.  At present this
    does nothing more than check that the path exists and is a directory. The
    Package class can fix up anything if it's got a directory.
    """
    return isdir(path)
