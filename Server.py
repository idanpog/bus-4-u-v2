"""
author: Idan Pogrebinsky

-- server --
"""

import socket
import threading

from telegram.ext import Updater, CommandHandler


class TelegramController:
    """
    the telegram controller takes care of the telegram bot.
    receives commands from the telegram chat and can communicate with the bus controller
    """

    def __init__(self, token, bus_controller):
        """starts the bot, gets access to the bus_controller and loads the list of bus stations"""
        self.__token = token
        self.bus_controller = bus_controller

    def start(self):
        """launch in a thread, from main
        takes care of the telegram inputs, and controls other main functions"""
        updater = Updater(self.__token, use_context=True)
        dp = updater.dispatcher
        # on different commands - answer in Telegram
        dp.add_handler(CommandHandler("help", self.help))
        dp.add_handler(CommandHandler("bus", self.bot_bus))
        updater.start_polling()
        # logging.getLogger()
        # updater.idle()
        print("Bot Loaded")

    @staticmethod
    def help(update, context):
        """
        currently a place holder function, used to test if the bot is working
        """
        """Send a message when the command /help is issued."""
        print("helping")
        update.message.reply_text('/bus {line} {station}')

    def bot_bus(self, update, context):
        """takes care of the user requests
        /bus {line} {station}
        adds the request into the system, sends a message to the bus and logs the request in the logs"""
        message = update.message.text.lower().split(" ")
        line = message[1]
        station = message[2]
        output = f"request accepted line:{line} at the {station}'s station"
        if self.bus_controller.check_line(line):
            self.bus_controller.notify_bus(line, station)
        else:
            output = f"request failed line:{line} doesn't exist"
        print(output)
        update.message.reply_text(output)


class BusController:
    """takes care of tracking the buses and the communication with them"""

    NEW_CONNECTION_PORT = 8200
    STATIONS_PORT = 8201
    PASSENGERS_PORT = 8202
    HOST = socket.gethostbyname(socket.gethostname())

    def __init__(self):
        # used to accept and listen for new buses that join the system
        self.__new_bus_Socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__new_bus_port = 8200
        # used to get new updates from buses
        self.__bus_stations_Socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__bus_stations_port = 8201

        self.__ipv4 = (socket.gethostbyname(socket.gethostname()))
        self.__bus_dict = {}
        self.__stations_dict = {}

    def start(self):
        """loads all the threads and the communication sockets, starts the bus controller"""
        new_bus_receiver = threading.Thread(target=self.__new_bus_receiver, args=(), name="new_bus_receiver")
        new_bus_receiver.start()
        updates_tracker = threading.Thread(target=self.__track_updates, args=(), name="updates_tracker")
        updates_tracker.start()

    def __track_updates(self):
        self.__bus_stations_Socket.bind((self.__ipv4, self.__bus_stations_port))
        self.__bus_stations_Socket.listen(1)
        while True:
            # establish a connection
            client_socket, addr = self.__bus_stations_Socket.accept()
            data = client_socket.recv(1024)
            # data  = {line_number} {station} {ID}
            line_num, station, ID = data.decode().split(" ")

            for bus in self.__bus_dict[line_num]:
                if bus.get_ID() == ID:
                    bus.set_station(station)
                    print(f"{bus} has updated his station")
                    break
            client_socket.close()

    def __new_bus_receiver(self):
        print(f"waiting for buses at {self.__ipv4}:{BusController.NEW_CONNECTION_PORT}")
        self.__new_bus_Socket.bind((self.__ipv4, self.__new_bus_port))
        self.__new_bus_Socket.listen(1)
        while True:
            # establish a connection
            client_socket, addr = self.__new_bus_Socket.accept()
            data = client_socket.recv(1024)
            # data  = {line_number} {station} {ID}
            line_num, station, ID = data.decode().split(" ")
            bus = self.Bus(addr, line_num, station, ID)
            self.__add_bus(bus)
            client_socket.close()
            print(f"successfully added Bus -> {bus}")

    def __add_bus(self, bus):

        if bus.get_line_num() in self.__bus_dict:
            self.__bus_dict[bus.get_line_num()].append(bus)
        else:
            self.__bus_dict[bus.get_line_num()] = [bus, ]

    def check_line(self, line):
        """checks if the line is registered in the system"""
        return line in self.__bus_dict

    def remove_bus(self, bus):
        """removes removes the bus out of the system"""
        self.__bus_dict[bus.get_line_num()].remove(bus)

    def notify_bus(self, line, station):

        """updates the dictionary that keeps track for all the passengers"""
        # self.__stations_dict[line][station] = number of people waitig at the current station for that line
        print("in notify bus")
        if line in self.__stations_dict:
            if station in self.__stations_dict[line]:
                self.__stations_dict[line][station] += 1
            else:
                self.__stations_dict[line][station] = 1
        else:
            self.__stations_dict[line] = {station: 1}
        for bus in self.__bus_dict[line]:
            bus.update_passengers(station, self.__stations_dict[line][station])

    class Bus:
        """
        an internal class in the bus controller
        stores the address and line number, the stations and the ID of the bus.
        has a couple of useful functions as well
        """
        def __init__(self, address, line_number, station, ID):
            self.__address = address
            self.__station = station
            self.__line_number = line_number
            self.__ID = ID

        def get_addr(self):
            """
            returns the address of the bus
            """
            return self.__address

        def get_station(self):
            """returns the current station where the bus"""
            return self.__station

        def set_station(self, station):
            """updates the bus location"""
            self.__station = station

        def get_line_num(self):
            """returns the line number"""
            return self.__line_number

        def get_ID(self):
            """returns the bus ID"""
            return self.__ID

        def update_passengers(self, station, passengers):
            """
            sends a message to the bus client that this instance represents
            used to update the bus of the people that are awaiting for him
            """
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.__address[0], BusController.PASSENGERS_PORT))
            # data = {station} {number_of_people}
            data = f"{station} {passengers}"
            s.send(data.encode())
            s.close()

        def __str__(self):
            return f"line number: [{self.__line_number}], Current station [{self.__station}]" \
                   f" \naddress: {self.__address}"

    class Display:
        """used to display the current buses the user GUI"""
        pass


def main():
    """start the server"""

    my_server = BusController()
    my_server.start()

    """start the Telegram Bot"""
    steve = TelegramController("990223452:AAHrln4bCzwGpkR2w-5pqesPHpuMjGKuJUI", my_server)
    threading.Thread(steve.start(), args=())
    print("ServerLoaded")


if __name__ == '__main__':
    main()
