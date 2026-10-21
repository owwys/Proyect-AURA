"""Navegacion y calibracion; independiente del controlador fisico."""
from touch import TARGETS, CHECK_TARGET, affine, apply

from tft_layout import (MENU_BUTTON, BACK_BUTTON, menu_rect, CLOCK_FIELDS,
                        CLOCK_PREV, CLOCK_NEXT, CLOCK_MINUS, CLOCK_PLUS,
                        CLOCK_APPLY, CLOCK_CANCEL, TREND_BUTTON,
                        SETTING_INTERVAL, SETTING_ZONE, SETTING_SAVE, LandscapeTouch)

ITEMS = (('Inicio', 'home'), ('Estado de red', 'network'),
         ('Calibrar tactil', 'calibrate'), ('Acerca de AURA', 'about'),
         ('Tendencias', 'trends'), ('Configuracion', 'settings'), ('Fecha y hora', 'clock'), ('Configurar Wi-Fi', 'wifi_confirm'))


def contains(rect, point):
    x, y, w, h = rect
    return x <= point[0] < x+w and y <= point[1] < y+h


class Navigation:
    def __init__(self, touch, settings=None, clock=None):
        self.touch = LandscapeTouch(touch) if touch is not None and hasattr(touch, 'read_raw') else touch
        self.clock = clock
        self.clock_editor = None
        self.settings = settings
        self.metric = 0
        self.interval = settings.interval if settings else 2000
        self.zone = settings.zone if settings else 'Europe/Madrid'
        self.message = ''
        self.wifi_action = None
        self.ota_action = None
        self.ota_state = 'idle'
        self.ota_version = ''
        self.ota_message = ''
        self.page = 'calibrate' if touch is not None and touch.matrix is None else 'home'
        self.samples = []
        self.candidate = None
        self.error = False
        self.saved = True

    def handle(self, raw):
        if self.touch is None:
            return False
        if self.page == 'calibrate':
            if self.candidate is None:
                self.samples.append(raw)
                if len(self.samples) == 3:
                    try:
                        self.candidate = affine(self.samples)
                    except ValueError:
                        self.samples = []
                        self.error = True
            else:
                x, y = apply(self.candidate, raw)
                if (x-CHECK_TARGET[0])**2 + (y-CHECK_TARGET[1])**2 <= 20**2:
                    self.saved = self.touch.save(self.candidate)
                    self.page = 'home'
                    self.error = False
                else:
                    self.samples = []
                    self.candidate = None
                    self.error = True
            return True
        point = self.touch.screen_point(raw)
        if point is None:
            return False
        if self.page == 'settings' and contains((160,112,152,34), point):
            self.page = 'updates'
            self.ota_state = 'checking'
            self.ota_message = ''
            self.ota_action = 'check'
            return True
        if self.page == 'updates':
            if contains((8,196,144,28), point):
                self.ota_action = None
                self.page = 'settings'
                return True
            if contains((160,196,152,28), point):
                if self.ota_state == 'available':
                    self.ota_action = 'install'
                elif self.ota_state in ('error', 'current'):
                    self.ota_action = 'check'
                return True
            return False
        if self.page == 'home' and contains(MENU_BUTTON, point):
            self.page = 'menu'
            return True
        if self.page == 'menu':
            for i, (_, target) in enumerate(ITEMS):
                if contains(menu_rect(i), point):
                    self.page = target
                    if target == 'wifi_confirm':self.message='';self.wifi_action=None
                    if target == 'clock':
                        if self.clock is None:
                            from clock_service import ClockService
                            self.clock = ClockService()
                        import config
                        self.clock_editor = ClockEditor(self.clock, config.TIMEZONE)
                    if target == 'settings' and self.settings:
                        self.interval, self.zone = self.settings.interval, self.settings.zone
                        self.message = 'Sin cambios'
                    if target == 'calibrate':
                        self.samples = []
                        self.candidate = None
                        self.error = False
                    return True
        elif self.page in ('network', 'about', 'trends', 'settings') and contains(BACK_BUTTON, point):
            self.page = 'menu'
            return True
        if self.page == 'wifi_confirm':
            from tft_layout import WIFI_CANCEL,WIFI_CONFIRM
            if contains(WIFI_CANCEL,point):
                self.page='menu';self.message='';self.wifi_action=None
                return True
            if contains(WIFI_CONFIRM,point):
                self.wifi_action='reset'
                return True
            return False
        if self.page == 'clock':
            editor = self.clock_editor
            import config
            if contains(CLOCK_APPLY, point):
                editor.apply(config.TIMEZONE)
            elif contains(CLOCK_CANCEL, point):
                self.clock_editor = None
                self.page = 'menu'
            elif contains(CLOCK_PREV, point):
                editor.select((editor.field-1) % 5)
            elif contains(CLOCK_NEXT, point):
                editor.select((editor.field+1) % 5)
            elif contains(CLOCK_MINUS, point) or contains(CLOCK_PLUS, point):
                if editor.ambiguous:
                    editor.fold = 'summer' if contains(CLOCK_MINUS, point) else 'winter'
                    editor.message = 'Elegido: ' + ('verano' if editor.fold == 'summer' else 'invierno')
                else:
                    editor.step(-1 if contains(CLOCK_MINUS, point) else 1)
            else:
                for rect, field in CLOCK_FIELDS:
                    if contains(rect, point):
                        editor.select(field)
                        return True
                return False
            return True
        if self.page == 'trends' and contains(TREND_BUTTON, point):
            self.metric = (self.metric + (1 if point[0] >= 160 else -1)) % 4
            return True
        if self.page == 'settings' and self.settings:
            from settings import INTERVALS, ZONES
            if contains(SETTING_INTERVAL, point):
                self.interval = INTERVALS[(INTERVALS.index(self.interval)+1) % len(INTERVALS)]
            elif contains(SETTING_ZONE, point):
                self.zone = ZONES[(ZONES.index(self.zone)+1) % len(ZONES)]
            elif contains(SETTING_SAVE, point):
                self.saved = self.settings.save(self.interval, self.zone)
                self.message = 'Guardado' if self.saved else 'ERROR: no guardado'
                if self.saved:
                    self.settings.apply()
                return True
            else:
                return False
            changed = (self.interval, self.zone) != (self.settings.interval, self.settings.zone)
            self.message = 'Pendiente de guardar' if changed else 'Sin cambios'
            return True
        return False


class ClockEditor:
    def __init__(self, clock, zone):
        self.clock = clock
        self.zone = zone
        snapshot = clock.snapshot()
        text = snapshot['local']
        self.parts = ([int(text[:4]),int(text[5:7]),int(text[8:10]),int(text[11:13]),int(text[14:16])]
                      if text else [2026,1,1,0,0])
        self.field = 2
        self.fold = None
        self.message = ''
        self.applied = False
        self.ambiguous = False

    def select(self, field):
        if type(field) is not int or not 0 <= field < 5:
            raise ValueError('Campo no valido')
        self.field = field

    def step(self, direction):
        from local_clock import month_days
        if direction not in (-1, 1):
            raise ValueError('Direccion no valida')
        p, f = self.parts, self.field
        if f == 0:
            p[0] = min(2099, max(2025, p[0]+direction))
        else:
            low = 1 if f in (1,2) else 0
            high = month_days(p[0],p[1]) if f == 2 else {1:12,3:23,4:59}[f]
            p[f] = (p[f]-low+direction) % (high-low+1)+low
        p[2] = min(p[2],month_days(p[0],p[1]))
        self.fold = None
        self.ambiguous = False
        self.applied = False
        self.message = 'Pendiente de aplicar'

    def apply(self, zone):
        from clock_service import AmbiguousTimeError
        if zone != self.zone:
            self.fold = None
            self.zone = zone
        self.applied = False
        try:
            self.clock.set_local(self.parts,zone,self.fold)
        except AmbiguousTimeError:
            self.ambiguous = True
            self.message = 'Elegir verano/invierno'
            return False
        except ValueError as error:
            self.ambiguous = False
            self.message = str(error)[:27]
            return False
        except OSError:
            self.message = 'ERROR: no aplicada'
            return False
        self.ambiguous = False
        self.applied = True
        self.message = 'Hora aplicada' if self.clock.retention_available else 'Aplicada, no conservada'
        return True
