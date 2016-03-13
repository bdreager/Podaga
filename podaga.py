#!/usr/bin/env python
# -*- coding: utf-8 -*-

__program__ = 'Podaga'
__version__ = '0.3.0'
__description__ = 'Weather and location display for the terminal'

import os, curses, urllib2, json, locale
from time import strftime
from contextlib import closing
from pyspin.spin import Spinner, Spin1
from pyowm import OWM
from argconfparse import ArgConfParser

def init_args():
    parser = ArgConfParser(prog=__program__, description=__description__)
    parser.add_argument('--version', action='version', version='%(prog)s ' + __version__)
    parser.add_argument('-k', '--api-key', type=str, default='', help='your OpenWeatherMap API key (default: %(default)s)', dest='api_key')
    parser.add_argument('-t', '--temp_unit', type=str, default=Podaga.kDEFAULT_TEMP_UNIT, help='temperature unit (default: %(default)s)', dest='temp_unit')
    return parser.parse_args()

class Podaga(object):
    T, B, C, L, R = range(5)
    kMARGIN = 1
    kUPDATE_INTERVAL = 15 # minutes
    kGEO_URL = 'http://freegeoip.net/json/'
    kDEFAULT_TEMP_UNIT = 'fahrenheit'
    kTIMESTAMP_FORMAT = '%I:%M:%S %p'

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

        locale.setlocale(locale.LC_ALL, '') # for displaying the unicode characters using ncurses

    def update(self):
        time = int(strftime("%M"))
        if not self.forecast or not self.last_update or self.last_update != time and time % self.kUPDATE_INTERVAL == 0:
            self.forecast = self.loc.get_weather()
            self.last_update = time
            self.last_update_timestamp = "Updated: {}".format(strftime(self.kTIMESTAMP_FORMAT))

        animation = self.spinner.next().encode('utf-8')

        for window in self.windows: window.box()

        self.draw(self.win_l, self.T, self.L, self.location_name, self.color_pri)
        self.draw(self.win_l, self.T, self.R, animation, self.color_ext)
        self.draw(self.win_l, self.B, self.L, self.forecast.get_detailed_status().capitalize(), self.color_sec)

        self.draw(self.win_c, self.T, self.C, "{} °{}".format(self.forecast.get_temperature(self.temp_unit)["temp"], self.temp_symbol), self.color_pri)
        self.draw(self.win_c, self.B, self.L, "{} m/s".format(self.forecast.get_wind()["speed"]), self.color_sec)
        self.draw(self.win_c, self.B, self.R, "{} %".format(self.forecast.get_humidity()), self.color_sec)

        self.draw(self.win_r, self.T, self.R, self.location['ip'], self.color_pri)
        self.draw(self.win_r, self.T, self.L, animation, self.color_ext)
        self.draw(self.win_r, self.B, self.R, self.last_update_timestamp, self.color_sec)

        for window in self.windows: window.refresh()

        if self.verbose:
            self.stdscr.clrtoeol()
            self.stdscr.addstr(0, 0, json.dumps(self.location))

        self.stdscr.refresh()

    def draw(self, window, v, h, string, color):
        window.addstr(0 if v == self.T else self.draw_height/2 if v == self.C else self.draw_height-1,
                      self.kMARGIN if h == Podaga.L else (self.draw_width/2 - len(string)/2) if h == self.C else
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
            except KeyboardInterrupt: exit(0)
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

def main(stdscr=None, args=init_args()):
    if not stdscr:
        if args.api_key == None or len(args.api_key) == 0:
            print('No OpenWeatherMap API key found.\n'
                  'Register at openweathermap.com for your key.\n'
                  'Enter it with "{} {} -k [your_key]"'.format(__program__.lower(), ArgConfParser.kARG_SAVE_SHORT))
        else:
            curses.wrapper(main, args=args)
    else:
        os.environ.setdefault('ESCDELAY', '25')
        Driver(stdscr, args).start()

if __name__ == '__main__': main()