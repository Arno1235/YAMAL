from yamal import Node, Image_Display


class Display_frame(Node):

    def __init__(self, name, mgr, args=None):
        super().__init__(name, mgr, args)

        self.image_display = Image_Display(name=self.args['frame subscription'])

    def run(self):
        self.subscribe(self.args['frame subscription'], self.display)
    
    def display(self, topic, message):
        self.image_display.display(message)

    def before_close(self):
        self.image_display.close()
        return super().before_close()
