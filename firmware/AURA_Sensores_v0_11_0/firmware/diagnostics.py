"""Medidas acumuladas en RAM; modo opcional, sin guardar registros en flash."""
import time
import gc


class Diagnostics:
    def __init__(self):
        self.frames = 0
        self.frame_us = 0
        self.max_frame_us = 0
        self.events = 0
        self.response_events = 0
        self.max_response_ms = 0
        self.max_poll_ms = 0
        self.last_poll = None
        self.pending_event = None
        self.max_network_ms = 0

    def poll(self, now):
        if self.last_poll is not None:
            self.max_poll_ms = max(self.max_poll_ms, time.ticks_diff(now, self.last_poll))
        self.last_poll = now

    def event(self, now):
        self.events += 1
        self.pending_event = now

    def frame(self, now, elapsed_us):
        self.frames += 1
        self.frame_us += elapsed_us
        self.max_frame_us = max(self.max_frame_us, elapsed_us)
        if self.pending_event is not None:
            self.max_response_ms = max(self.max_response_ms,
                                       time.ticks_diff(now, self.pending_event))
            self.response_events += 1
            self.pending_event = None

    def report(self, elapsed_seconds):
        gc.collect()
        average = self.frame_us // self.frames if self.frames else 0
        print('PERF t=%ds frames=%d dibujo_media/max_ms=%.2f/%.2f' %
              (elapsed_seconds, self.frames, average/1000, self.max_frame_us/1000))
        print('PERF eventos=%d respuestas=%d evento_a_imagen_max_ms=%d sondeo_max_ms=%d red_max_ms=%d libre=%d' %
              (self.events, self.response_events, self.max_response_ms,
               self.max_poll_ms, self.max_network_ms, gc.mem_free()))
