#!/usr/bin/env python
# -*- coding: utf-8 -*-

__program__ = 'Podaga'
__version__ = '0.0.5'
__description__ = 'Weather and location display for the terminal'

import os, curses, urllib2, json
from time import strftime
from contextlib import closing
from argparse import ArgumentParser
from ast import literal_eval
from pyspin.spin import Spinner, Spin1
from pyowm import OWM

import locale
locale.setlocale(locale.LC_ALL, '') # for displaying the unicode characters using ncurses

class Pos(object): T, B, C, L, R = range(5)

class Podaga(object):
    kGEO_URL = 'http://freegeoip.net/json/'
    kUPDATE_INTERVAL = 15 # minutes
    kMARGIN = 1
    kDEFAULT_TEMP_UNIT = 'fahrenheit'

    def __init__(self, stdscr, args=None):
        self.stdscr = stdscr
        self.owm = OWM(API_key=args.api_key)

        self.find_location()

        self.loc = self.owm.weather_at_coords(self.location['latitude'], self.location['longitude'])
        self.temp_unit = args.temp_unit
        self.temp_symbol = self.temp_unit[0].upper()
        self.location_name = "{}, {}".format(self.location['city'], self.location['region_name'])
        self.forecast = None
        self.spinner = Spinner(Spin1)
        self.bar_animation = 1
        self.last_update = None
        self.verbose = False

        try: # needed for terminals that don't support all color options
            for i in range(256):
                curses.init_pair(i+1, i, -1)
                self.color_range = i
        except:
            pass

        self.color_pri = curses.color_pair(2) | curses.A_BOLD
        self.color_sec = curses.color_pair(4) | curses.A_BOLD
        self.color_ext = curses.color_pair(5) | curses.A_BOLD

        self.draw_height = 2
        self.draw_width = 0 # generated by view_resized
        self.view_resized()

    def update(self):
        time = int(strftime("%M"))
        if not self.forecast or not self.last_update or self.last_update != time and time % self.kUPDATE_INTERVAL == 0:
            self.forecast = self.loc.get_weather()
            self.last_update = time
            self.last_update_timestamp = "Updated: {}".format(strftime("%I:%M:%S %p"))

        animation = self.spinner.next().encode('utf-8')

        for window in self.windows: window.box()

        self.draw(self.win_l, Pos.T, Pos.L, self.location_name, self.color_pri)
        self.draw(self.win_l, Pos.T, Pos.R, animation, self.color_ext)
        self.draw(self.win_l, Pos.B, Pos.L, self.forecast.get_detailed_status().capitalize(), self.color_sec)

        self.draw(self.win_c, Pos.T, Pos.C, "{} °{}".format(self.forecast.get_temperature(self.temp_unit)["temp"], self.temp_symbol), self.color_pri)
        self.draw(self.win_c, Pos.B, Pos.L, "{} m/s".format(self.forecast.get_wind()["speed"]), self.color_sec)
        self.draw(self.win_c, Pos.B, Pos.R, "{} %".format(self.forecast.get_humidity()), self.color_sec)

        self.draw(self.win_r, Pos.T, Pos.R, self.location['ip'], self.color_pri)
        self.draw(self.win_r, Pos.T, Pos.L, animation, self.color_ext)
        self.draw(self.win_r, Pos.B, Pos.R, self.last_update_timestamp, self.color_sec)

        for window in self.windows: window.refresh()

        if self.verbose:
            self.stdscr.clrtoeol()
            self.stdscr.addstr(0, 0, json.dumps(self.location))

        self.stdscr.refresh()

    def draw(self, window, v, h, string, color):
        window.addstr(0 if v == Pos.T else self.draw_height/2 if v == Pos.C else self.draw_height-1,
                      self.kMARGIN if h == Pos.L else (self.draw_width/2 - len(string)/2) if h == Pos.C else
                      (self.draw_width - self.kMARGIN - len(string)), string, color)

    def view_resized(self):
        self.stdscr.clear()
        self.height, self.width = self.stdscr.getmaxyx()
        self.draw_width = self.width/3

        self.win_l = curses.newwin(self.draw_height, self.draw_width, 0, 0)
        self.win_c = curses.newwin(self.draw_height, self.draw_width, 0, self.draw_width)
        self.win_r = curses.newwin(self.draw_height, self.draw_width, 0, self.draw_width + self.draw_width)
        self.windows = [self.win_l, self.win_c, self.win_r]

    def find_location(self):
        success = hasattr(self, 'location') and self.location
        while not success: #the server doesn't always respond, keep trying
            try:
                with closing(urllib2.urlopen(self.kGEO_URL)) as web: self.location = json.loads(web.read())
                success = True
            except KeyboardInterrupt: raise
            except: pass

class Driver(object):
    kKEY_ESC = '\x1b'

    def __init__(self, stdscr, args = None):
        self.stdscr = stdscr
        curses.halfdelay(1)
        curses.curs_set(0)
        curses.use_default_colors()

        self.stdscr.addstr(0,0,'Getting location information...')
        self.stdscr.refresh()
        self.forecaster = Podaga(stdscr, args)
        self.running = False

    def start(self):
        self.running = True
        self.stdscr.clear()
        self.run()

    def run(self):
        while self.running:
            self.forecaster.update()
            self.update()

    def update(self):
        try:
            key = self.stdscr.getkey()
        except curses.error as e:
            if str(e) == 'no input': return
            raise e

        lower = key.lower()
        if key == 'KEY_RESIZE': self.forecaster.view_resized()
        elif key==self.kKEY_ESC or lower=='q': self.running = False
        elif lower=='r': self.forecaster.last_update = None
        elif lower=='v': self.forecaster.verbose = True

def init_args():
    # arguments
    parser = ArgumentParser(prog=__program__, description=__description__)
    parser.add_argument('--version', action='version', version='%(prog)s ' + __version__)
    parser.add_argument('-k', '--api-key', type=str, default='', help='your OpenWeatherMap API key', dest='api_key')
    parser.add_argument('-t', '--temp_unit', type=str, default=Podaga.kDEFAULT_TEMP_UNIT, help='temperature unit', dest='temp_unit')
    parser.add_argument('-s', '--save-config', action='store_true', default=False, help='save and add your current arguments to the config file', dest='save_config')

    # config file detection
    try:    from ConfigParser import RawConfigParser
    except: from configparser import RawConfigParser
    config_bases = [os.path.expanduser('~/.')]
    try: from xdg.BaseDirectory import xdg_config_home; config_bases.append(xdg_config_home+'/')
    except: config_bases.append(os.environ.get('XDG_CONFIG_HOME') if os.environ.get('XDG_CONFIG_HOME', None) else os.path.expanduser('~/.config/'))
    config_file = '{}.conf'.format(__program__.lower())
    possible_configs = [dir + config_file for dir in [item for base in config_bases for item in [base, '{}{}/'.format(base,__program__)]]]
    possible_configs.append("{}/{}".format(os.path.dirname(os.path.realpath(__file__)), config_file))

    # config parsing
    config = RawConfigParser()
    found_config = config.read(possible_configs)
    settings = dict(config.items("Settings")) if config.has_section('Settings') else {}
    base_args = parser.parse_args()
    for i, item in settings.items(): settings[i] = literal_eval(item) # fix values that might not be stored correctly (i.e bools)
    parser.set_defaults(**settings)
    full_args = parser.parse_args()

    # save config file
    if len(base_args.api_key) or base_args.save_config:
        dict_args = vars(full_args)
        del dict_args['save_config']

        target_config = found_config[0] if found_config else possible_configs[0]
        print target_config
        with open(target_config,"w") as f:
            string = "".join(['%s = \'%s\'\n' % (key, value) for (key, value) in dict_args.items()])
            f.write("[Settings]\n{}".format(string))

    return parser.parse_args()

args = init_args()
def main(stdscr=None):
    if args.api_key == None or len(args.api_key) == 0:
        print('No OpenWeatherMap API key found.\nPlease register at openweathermap.org for your key.\nEnter it here with the -k argument.')
    elif not stdscr:
        curses.wrapper(main)
    else:
        os.environ.setdefault('ESCDELAY', '25')
        Driver(stdscr, args).start()

if __name__ == '__main__': main()