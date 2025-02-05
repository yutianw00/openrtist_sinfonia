import logging
from threading import Thread
from time import sleep

import cv2
from gabriel_client.websocket_client import WebsocketClient

from . import config
from .adapter import Adapter

logger = logging.getLogger(__name__)


class WebcamVideoStream:
    def __init__(self, src=0, name="WebcamVideoStream"):
        self.src = src
        self.stream = cv2.VideoCapture(src)
        (self.grabbed, self.frame) = self.stream.read()
        self.name = name
        self.stopped = False

    def start(self):
        t = Thread(target=self.update, name=self.name, args=())
        t.daemon = True
        t.start()
        return self

    def update(self):
        while not self.stopped:
            self.grabbed, frame = self.stream.read()

            if not self.grabbed:
                logging.info("Lost stream, reconnecting in 1 second")
                sleep(1)
                self.stream = cv2.VideoCapture(self.src)
                continue

            self.frame = frame

    def stop(self):
        self.stopped = True

    def read(self):
        if self.frame is None:
            # slow down if the stream is not ready or failed
            sleep(0.5)
        return self.grabbed, self.frame


class CaptureAdapter:
    @property
    def producer_wrappers(self):
        return self.adapter.producer_wrappers

    @property
    def consumer(self):
        return self.adapter.consumer

    def preprocess(self, frame):
        style_array = self.adapter.get_styles()
        if len(style_array) > 0 and self.current_style_frames >= self.style_interval:
            self.style_num = (self.style_num + 1) % len(style_array)
            self.adapter.set_style(style_array[self.style_num])

            self.current_style_frames = 0
        else:
            self.current_style_frames += 1

        frame = cv2.flip(frame, 1)
        frame = cv2.resize(frame, (config.IMG_WIDTH, config.IMG_HEIGHT))

        return frame

    def __init__(self, consume_rgb_frame_style, video_source=None, capture_device=-1):
        """
        consume_rgb_frame_style should take one rgb_frame parameter and one
        style parameter.
        """

        self.style_num = 0
        self.style_interval = config.STYLE_DISPLAY_INTERVAL
        self.current_style_frames = 0

        if video_source is None:
            video_capture = cv2.VideoCapture(capture_device)
            video_capture.set(cv2.CAP_PROP_FPS, config.CAM_FPS)
        else:
            video_capture = WebcamVideoStream(src=video_source)
            video_capture.start()

        def consume_frame_style(frame, style, style_image):
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            consume_rgb_frame_style(rgb_frame, style, style_image)

        self.adapter = Adapter(
            self.preprocess, consume_frame_style, video_capture, start_style="?"
        )


def create_client(
    server_ip, consume_rgb_frame_style, video_source=None, capture_device=-1
):
    """
    consume_rgb_frame_style should take one rgb_frame parameter and one
    style parameter.
    """

    adapter = CaptureAdapter(
        consume_rgb_frame_style,
        video_source=video_source,
        capture_device=capture_device,
    )
    return WebsocketClient(
        server_ip, config.PORT, adapter.producer_wrappers, adapter.consumer
    )
