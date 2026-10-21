"""Interfaz TFT horizontal 320x240. No modifica adquisicion ni controladores."""
import config
import local_clock
from ili9341 import rgb565
from graphics import Graphics
from menu import ITEMS
from tft_layout import (MENU_BUTTON, BACK_BUTTON, menu_rect, CLOCK_FIELDS,
                        CLOCK_PREV, CLOCK_NEXT, CLOCK_MINUS, CLOCK_PLUS,
                        CLOCK_APPLY, CLOCK_CANCEL, SETTING_INTERVAL,
                        SETTING_ZONE, SETTING_SAVE, portrait_to_landscape)
from tft_environment import assess, valid
from touch import TARGETS, CHECK_TARGET
from rendering import CALIBRATION_LABELS

BG = rgb565(12,24,27)
PANEL = rgb565(21,39,43)
WHITE = rgb565(237,245,242)
MUTED = rgb565(166,191,189)
ACCENT = rgb565(125,227,204)
BLACK = rgb565(16,46,42)
YELLOW = rgb565(244,200,152)
ALERT = rgb565(243,159,151)
from firmware_version import VERSION as FIRMWARE_VERSION


def clock_text(now=None):
    if now is None:
        now = local_clock.localtime()
    return '--:--' if now[0] < 2025 else '%02d:%02d' % (now[3],now[4])


class Dashboard:
    def __init__(self, display):
        self.display = display
        self.fb = display.fb
        self.g = Graphics(self.fb)

    def _center(self, text, y, color=WHITE, scale=1, x=0, width=320):
        if text:
            self.g.centered(text,y,color,scale,x=x,width=width)

    def _text(self, text, x, y, color=WHITE, scale=1, chars=38):
        if text:
            self.g.text(str(text)[:chars],x,y,color,scale)

    def _button(self, label, rect):
        x,y,w,h = rect
        self.g.card(x,y,w,h,PANEL,radius=4)
        self._center(label,y+(h-8)//2,ACCENT,x=x,width=w)

    def _base(self, title):
        self.fb.fill(BG)
        self._text(title,8,12,ACCENT)

    def _footer(self, text='AURA / LOCAL'):
        self._text(text,8,230,MUTED,chars=30)
        version = FIRMWARE_VERSION[:8]
        self._text(version,312-self.g.measure(version),230,MUTED,chars=8)

    def _calibration_label(self, state, y):
        self._center(CALIBRATION_LABELS.get(state,'TACTIL: PENDIENTE'),y,
                     YELLOW if state in ('pending','unsaved','disabled') else MUTED)

    def _face(self, state, color):
        f=self.fb
        # Rasgos vectoriales, sin imagenes ni animacion periodica.
        if state == 'unknown':
            for x in (238,276):
                for i in range(9):
                    f.pixel(x+i,72+i,color);f.pixel(x+8-i,72+i,color)
        else:
            for x in (238,276):
                self.g.card(x,72,8,12,color,radius=2)
        if state == 'happy':
            for x,y,w in ((242,101,4),(246,105,4),(250,108,22),(272,105,4),(276,101,4)):
                f.fill_rect(x,y,w,3,color)
        elif state == 'concerned':
            for x,y,w in ((242,109,4),(246,105,4),(250,102,22),(272,105,4),(276,109,4)):
                f.fill_rect(x,y,w,3,color)
        else:
            f.fill_rect(246,105,30,3,color)

    def draw(self,data,elapsed_seconds,network_status=None,clock_ready=True,calibration='loaded',clock=None):
        self._base('AURA One')
        local=clock.snapshot()['local'] if clock is not None else None
        hour=(local[11:16] if local else '--:--') if clock is not None else (clock_text() if clock_ready else '--:--')
        self._text(hour,216,14,MUTED)
        self._button('MENU',MENU_BUTTON)
        state,reason=assess(data)
        color={'happy':ACCENT,'neutral':YELLOW,'concerned':ALERT,'unknown':MUTED}[state]
        self.g.card(8,42,194,112,ACCENT,radius=4)
        self._text('CO2 / ppm',20,54,BLACK)
        c=data.get('co2')
        value=str(int(c)) if valid(c,0,99999) else '--'
        scale=4 if len(value)<=5 else 3
        self._text(value,20,78,BLACK,scale)
        self._text('Ventilacion estimada',20,134,BLACK)
        self.g.card(210,42,102,112,PANEL,radius=4)
        self._face(state,color)
        self._center({'happy':'EN RANGO','neutral':'REVISAR','concerned':'ACTUAR','unknown':'SIN DATOS'}[state],134,color,x=210,width=102)
        self._center(reason,162,color)
        for x,label,key,unit,lo,hi in ((8,'TEMP','temperature',' C',-40,85),
                                      (112,'HUMEDAD','humidity',' %',0,100),
                                      (216,'PRESION','pressure',' hPa',300,1200)):
            self.g.card(x,178,96,44,PANEL,radius=4)
            self._text(label,x+8,184,MUTED)
            v=data.get(key)
            text=(('%.1f' % v) if key=='temperature' else str(int(v)))+unit if valid(v,lo,hi) else '--'
            self._text(text,x+8,204,WHITE,chars=10)
        status=network_status or 'SIN WIFI'
        if status.startswith('WIFI OK'):status='WIFI OK'
        elif status.startswith('WIFI OFF'):status='WIFI OFF'
        if calibration in ('pending','unsaved','disabled'):
            status={'pending':'TACTIL PENDIENTE','unsaved':'TACTIL SIN GUARDAR','disabled':'TACTIL DESACTIVADO'}[calibration]
        self._footer(('DEMO' if data.get('demo',False) else data.get('sensor_caption','REAL'))+' / '+status)
        self.display.show()

    def draw_menu(self,page,link,calibration='loaded',clock=None,api_state=None):
        self._base('MENU AURA' if page=='menu' else ('ESTADO DE RED' if page=='network' else 'ACERCA DE AURA'))
        if page=='menu':
            for i,(label,_) in enumerate(ITEMS):self._button(label,menu_rect(i))
            self._calibration_label(calibration,202)
        else:
            if page=='network':
                connected=link.enabled and link.wlan.isconnected()
                rows=['Wi-Fi: '+('conectado' if connected else 'sin conexion'),
                      'IP: '+(link.wlan.ifconfig()[0] if connected else '--'),
                      'NTP: '+('sincronizado' if link.synced else 'pendiente'),
                      'Zona: '+config.TIMEZONE]
                if clock is not None:
                    from clock_service import SOURCES
                    rows.append('Hora: '+SOURCES.get(clock.source,'SIN AJUSTAR'))
                if api_state is not None:
                    names={'ready':'ACTIVA','waiting':'SIN WIFI','error':'ERROR','disabled':'DESACTIVADA'}
                    rows.append('API: '+names.get(api_state.get('state'),'ERROR'))
                    url=api_state.get('url')
                    if url:
                        rows.extend([url[i:i+37] for i in range(0,min(len(url),74),37)])
            else:
                rows=['AURA One Indoor','Firmware: '+FIRMWARE_VERSION,'ESP32-S3 / ILI9341',
                      'Pantalla: 320x240','Datos: SENSORES','Criterios orientativos', 'No es un detector de seguridad']
            for i,row in enumerate(rows[:9]):self._text(row,8,40+i*16)
            self._button('VOLVER',BACK_BUTTON)
        self._footer()
        self.display.show()

    def draw_calibration(self,samples,checking=False,error=False):
        self._base('CALIBRAR TACTIL')
        self._center('Toca la cruz y suelta',28,MUTED)
        x,y=portrait_to_landscape(CHECK_TARGET if checking else TARGETS[samples])
        self.fb.hline(x-12,y,25,ACCENT)
        self.fb.fill_rect(x,y-12,1,25,ACCENT)
        self.fb.fill_rect(x-2,y-2,5,5,WHITE)
        self._center('COMPROBACION FINAL' if checking else 'PUNTO %d DE 3' % (samples+1),202)
        if error:self._center('Repite con precision',216,YELLOW)
        self._footer()
        self.display.show()

    def draw_settings(self,interval,zone,message='',calibration='loaded'):
        self._base('CONFIGURACION')
        self._calibration_label(calibration,34)
        self._text('Muestreo',8,50,MUTED);self._text('Zona horaria',160,50,MUTED)
        self._button('%d segundos' % (interval//1000),SETTING_INTERVAL)
        self._button(zone,SETTING_ZONE)
        self._button('GUARDAR',SETTING_SAVE)
        self._button('ACTUALIZAR AURA',(160,112,152,34))
        self._center(message,164,YELLOW)
        self._button('VOLVER',BACK_BUTTON)
        self._footer();self.display.show()

    def draw_updates(self, state, version='', message=''):
        self._base('ACTUALIZAR AURA / WI-FI')
        self._center('Instalada: '+FIRMWARE_VERSION,42,MUTED)
        self.g.card(8,62,304,62,PANEL,radius=4)
        labels = {'checking':'BUSCANDO VERSION', 'available':'NUEVA VERSION',
                  'installing':'ACTUALIZANDO', 'error':'NO SE PUDO ACTUALIZAR',
                  'current':'AURA ESTA AL DIA', 'trial':'COMPROBANDO ARRANQUE'}
        self._center(labels.get(state,'ACTUALIZACIONES'),76,ACCENT)
        self._center(version or 'GitHub / versiones estables',101,WHITE)
        self._center('Conserva Wi-Fi, tactil y ajustes',140,MUTED)
        self._center(message[:38],161,YELLOW)
        if state in ('installing','trial'):
            self._center('No desconectes la alimentacion',202,YELLOW)
        else:
            self._button('VOLVER',(8,196,144,28))
            if state in ('available','error','current'):
                self._button('INSTALAR' if state=='available' else 'REINTENTAR',(160,196,152,28))
        self._footer('ACTUALIZACION / CONFIG PROTEGIDA')
        self.display.show()

    def draw_trends(self,history,metric):
        from history import METRICS
        key,label,unit=METRICS[metric]
        self._base('TENDENCIAS')
        self._center(label+' ('+unit+')',30,ACCENT)
        points=history.series(key)
        values=[p[1] for p in points if p[1] is not None]
        f=self.fb
        f.hline(12,138,296,MUTED);f.fill_rect(12,70,1,69,MUTED)
        if not values:self._center('Sin muestras',100,MUTED)
        else:
            low=min(values);high=max(values)
            self._center('Min %.1f / Max %.1f' % (low,high),48)
            span=max(1,high-low);duration=max(1,points[-1][0]-points[0][0]);previous=None
            for seconds,value in points:
                if value is None:
                    previous=None
                    continue
                x=16+int((seconds-points[0][0])*288/duration)
                y=134-int((value-low)*60/span) if high!=low else 104
                if previous is None:f.fill_rect(x-1,y-1,3,3,ACCENT)
                else:
                    px,py=previous;steps=max(abs(x-px),abs(y-py),1)
                    for step in range(steps+1):f.pixel(px+(x-px)*step//steps,py+(y-py)*step//steps,ACCENT)
                previous=(x,y)
            self._center('Ventana: %ds / %d pt' % (points[-1][0]-points[0][0],len(points)),146,MUTED)
        self._button('< ANTERIOR',(8,160,144,28));self._button('SIGUIENTE >',(160,160,152,28))
        self._button('VOLVER',BACK_BUTTON)
        self._footer('LOCAL / TIEMPO RELATIVO');self.display.show()

    def draw_clock(self,editor,zone,source):
        from clock_service import SOURCES
        self._base('FECHA Y HORA')
        self._center(SOURCES.get(source,'SIN AJUSTAR')+' / '+zone.split('/')[-1],32,MUTED)
        for (rect,field),label in zip(CLOCK_FIELDS,('DIA','MES','ANO','HORA','MINUTO')):
            x,y,w,h=rect;color=YELLOW if field==editor.field else ACCENT
            self._center(label,y-12,MUTED,x=x,width=w)
            self.g.card(x,y,w,h,color,radius=4)
            text='%04d' % editor.parts[field] if field==0 else '%02d' % editor.parts[field]
            self._center(text,y+8,BLACK,2,x=x,width=w)
        self._button('< CAMPO',CLOCK_PREV);self._button('CAMPO >',CLOCK_NEXT)
        self._button('VERANO' if editor.ambiguous else '-',CLOCK_MINUS)
        self._button('INVIERNO' if editor.ambiguous else '+',CLOCK_PLUS)
        self._center(editor.message[:38],180,YELLOW)
        self._button('APLICAR',CLOCK_APPLY);self._button('CANCELAR',CLOCK_CANCEL)
        self._footer('AURA / RELOJ LOCAL');self.display.show()

    def draw_setup(self, status, app_code, wifi_key):
        # Misma geometria, paleta y tarjetas que la v0.8.1 original.
        self._base('AURA / CONFIGURAR WI-FI')
        state = status['state']
        if state == 'connected':
            self.g.card(8,42,304,64,ACCENT,radius=4)
            self._center('WI-FI CONECTADA',65,BLACK,2)
            self._center('Vuelve a tu Wi-Fi en el iPhone',124)
            self._center('y abre tus datos en la app AURA.',142,MUTED)
            self._center('http://'+str(status.get('ip'))+':'+str(config.API_PORT),169,ACCENT)
            self._center('Cerrando red temporal en 10 segundos',204,MUTED)
        elif state in ('expired','setup_error'):
            self.g.card(8,42,304,64,PANEL,radius=4)
            self._center('CONFIGURACION DETENIDA',70,YELLOW)
            self._center(str(status.get('error') or 'Tiempo agotado')[:38],127,YELLOW)
            self._center((status.get('notice') or 'Reinicia AURA para volver a intentar.')[:38],166,YELLOW if status.get('notice') else MUTED)
        else:
            self._text('Red: '+status['ap_ssid'],8,42,WHITE)
            self.g.card(8,66,304,84,PANEL,radius=4)
            self._center('CLAVE WI-FI / 8 CARACTERES',78,MUTED)
            self._center(wifi_key,105,ACCENT,3)
            self._center('1 / Ajustes > Wi-Fi > red AURA',157)
            self._center('2 / Abre la app: acceso automatico',174)
            message = 'Conectando a tu Wi-Fi...' if state == 'connecting' else ('Revisa tu red y reintenta' if state == 'failed' else 'Esperando al iPhone / 2.4 GHz')
            if state in ('failed','connecting') or status.get('notice'):
                self.fb.fill_rect(8,174,304,8,BG)
                self._center(status.get('notice') or message,174,YELLOW if state == 'failed' or status.get('notice') else MUTED)
        if state != 'connected':
            from tft_layout import SETUP_SKIP
            self._button('OMITIR POR AHORA',SETUP_SKIP)
        self._footer('CONFIGURACION / LOCAL')
        self.display.show()

    def draw_wifi_confirm(self,message=''):
        from tft_layout import WIFI_CANCEL,WIFI_CONFIRM
        self._base('CONFIGURAR OTRA WI-FI')
        self.g.card(8,42,304,64,PANEL,radius=4)
        self._center('Se borrara la Wi-Fi guardada.',58,YELLOW)
        self._center('Tendras que configurar otra red',79,WHITE)
        self._center('desde la app del iPhone.',94,MUTED)
        self._center('Reloj y calibracion se conservan.',132,MUTED)
        if message:self._center(message[:38],164,YELLOW)
        self._button('CANCELAR',WIFI_CANCEL)
        self._button('BORRAR Y SEGUIR',WIFI_CONFIRM)
        self._footer('CAMBIO DE RED / LOCAL')
        self.display.show()
