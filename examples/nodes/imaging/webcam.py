from yamal import Node
import time
import cv2


class Webcam(Node):

    def __init__(self, name, mgr, args=None):
        super().__init__(name, mgr, args)

        try:
            # OPTIONAL
            # For warning fix in MacOS

            # WARNING: AVCaptureDeviceTypeExternal is deprecated for Continuity Cameras.
            # Please use AVCaptureDeviceTypeContinuityCamera and add NSCameraUseContinuityCameraDeviceType to your Info.plist.

            # pip install pyobjc

            from AppKit import NSBundle
            import objc

            # Necessary for MacOS Sonoma, could be fixed in later versions of opencv or MacOS
            objc.loadBundle('AppKit', globals(), bundle_path='/System/Library/Frameworks/AppKit.framework')
            NSBundle.mainBundle().infoDictionary().setValue_forKey_(True, "NSCameraUseContinuityCameraDeviceType")
        
        except ImportError:
            pass

    def run(self):

        self.vid = cv2.VideoCapture(0)

        while not self._close_event.is_set():

            t = time.time()

            frame = self.get_frame()
            self.publish('webcam_frame', frame)

            time.sleep(max(0, (1/self.args['fps']) - (time.time() - t) ))
    
    def get_frame(self):
        ret, frame = self.vid.read()
        return frame

    def before_close(self):
        self.vid.release()
        return super().before_close()    
