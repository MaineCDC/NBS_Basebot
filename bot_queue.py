class BotQueue:
    def __init__(self, bots):
        self.bots = bots
        self.current_index = 0

    def get_current_bot(self):
        return self.bots[self.current_index]

    def get_next_bot(self):
        self.current_index = (self.current_index + 1) % len(self.bots)
        return self.bots[self.current_index]

    def reset_to_first(self):
        self.current_index = 0
        return self.bots[self.current_index]

    def get_current_bot_name(self):
        return list(self.bots.keys())[self.current_index]

    def get_next_bot_name(self):
        next_index = (self.current_index + 1) % len(self.bots)
        return list(self.bots.keys())[next_index]
