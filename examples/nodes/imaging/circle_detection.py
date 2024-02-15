from yamal import Node
import cv2
import numpy as np


class Circle_detection(Node):

    def __init__(self, name, mgr, args=None):
        super().__init__(name, mgr, args)

    def run(self):
        self.subscribe(self.args['frame subscription'], self.detect_circle)
    
    def detect_circle(self, topic, image):
        
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        rows = gray.shape[0]

        circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, 1, rows / 8,
                                param1=100, param2=30,
                                minRadius=1, maxRadius=30)
        
        self.publish('circle_detection_frame', self.draw_circles(image, circles))
    
    def draw_circles(self, image, circles):

        if circles is not None:
            circles = np.uint16(np.around(circles))
            for i in circles[0, :]:

                center = (i[0], i[1])
                cv2.circle(image, center, 1, (0, 100, 100), 3)
                radius = i[2]
                cv2.circle(image, center, radius, (255, 0, 255), 3)
        
        return image
