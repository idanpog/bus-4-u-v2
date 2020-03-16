"""
author: Idan Pogrebinsky

-- server --
"""


#before launching type pip install python-telegram-bot --upgrade in


#TODO: add admin access
#TODO: add heartbeat
#TODO:update bus when it joins the system

from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import socket
import threading
from sqlite3 import *


from tkinter import *
from tkinter.ttk import Treeview
from time import sleep
import random

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
        dp.add_handler(CommandHandler("history", self.history))
        dp.add_handler(CommandHandler("bus", self.bot_bus))
        updater.start_polling()
        # logging.getLogger()
        # updater.idle()

    @staticmethod
    def help(update, context):
        message = update.message.text.lower().split(" ")
        if message[1] == "me":
            update.message.reply_text('if you need help buddy, call 1201 they are good guys and they will help you')

        """Send help when the command /help is issued."""
        update.message.reply_text('/bus {line} {station} \n/history show/clear')

    def log(self, update, output):
        ID = update.message.from_user.id
        name = update.message.from_user.name
        input_text = update.message.text
        header = connect("banlist.db")
        curs = header.cursor()
        if not self.__has_history(ID):
            curs.execute("INSERT INTO history VALUES(?, ?)", (ID, ""))

        curs.execute("SELECT * FROM history WHERE ID = (?)", (ID, ))
        data = curs.fetchall()[0][1]
        data += f"input: {input_text}\noutput:{output}\n" + "-"*30 + "\n"
        curs.execute("UPDATE history SET text = (?) WHERE ID = (?)", (data, ID))
        header.commit()

    @staticmethod
    def __has_history(ID):
        header = connect("banlist.db")
        curs = header.cursor()
        curs.execute("SELECT * FROM history WHERE ID = (?)", (ID,))
        data = curs.fetchall()
        return len(data) >= 1

    def history(self, update, context):
        message = update.message.text.lower().split(" ")
        ID = update.message.from_user.id
        name = update.message.from_user.name
        if message[1] == "show":
            if not self.__has_history(ID):
                output = "you don't have any history"
                update.message.reply_text(output)
                self.log(update, output)
                return
            header = connect("banlist.db")
            curs = header.cursor()
            curs.execute("SELECT * FROM history WHERE ID = (?)", (ID,))
            data = curs.fetchall()[0][1]
            update.message.reply_text(data)
        if message[1] == "clear":
            if not self.has_history(ID):
                update.message.reply_text("you already don't have history")
                return
            header = connect("banlist.db")
            curs = header.cursor()
            curs.execute("DELETE FROM history WHERE ID = (?)", (ID,))
            header.commit()
            output = "clean"
            update.message.reply_text(output)
            self.log(update, output)

    def bot_bus(self, update, context):
        """takes care of the user requests
        /bus {line} {station}
        adds the request into the system, sends a message to the bus and logs the request in the logs"""
        message = update.message.text.lower().split(" ")
        line = int(message[1])
        station = int(message[2])
        output = f"request accepted, the bus is notified"
        if self.bus_controller.check_line(line):
            self.bus_controller.notify_buses_about_people(line, station)
        else:
            output = f"request accepted, but there are no buses available for that line yet"
            self.bus_controller.notify_buses_about_people(line, station)
        self.log(update, output)
        update.message.reply_text(output)


class BusController:

    """takes control over the buses and the communication with them"""
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
        self.__bus_dict = {} #self.__bus_dict[line_num] holds an array that contains all the buses
        self.__stations_dict = {}

    def get_bus_dict(self):
        return self.__bus_dict

    def start(self):
        new_bus_reciever =threading.Thread(target=self.__new_bus_reciever, args=(), name="new_bus_reciever")
        new_bus_reciever.start()
        updates_tracker =threading.Thread(target=self.__track_updates, args=(), name="updates_tracker")
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
            try:
                for bus in self.__bus_dict[int(line_num)]:
                    if bus.get_ID() == ID:
                        if station.isnumeric():
                            bus.set_station(station)
                            print(f"{bus} has updated his station")
                        else:
                            print(f"{bus} has attempted to update his station but sent an invalid input")
                        break
            except:
                print("an unregistered bus tried to access the system, ignored")
            client_socket.close()

    def __new_bus_reciever(self):
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
            self.__notify_buses_about_buses(line_num)


    def __add_bus(self, bus):

        if bus.get_line_num() in self.__bus_dict:
            self.__bus_dict[bus.get_line_num()].append(bus)
        else:
            self.__bus_dict[bus.get_line_num()] = [bus,]



    def check_line(self, line):
        return int(line) in self.__bus_dict

    def remove_bus(self, bus):
        self.__bus_dict[bus.get_line_num()].remove(bus)

    def __notify_buses_about_people(self, line, station):
        # updates the dictionary that keeps track for all the passengers
        # self.__stations_dict[line][station] = number of people waitig at the current station for that line
        if line in self.__stations_dict:
            if station in self.__stations_dict[line]:
                self.__stations_dict[line][station] += 1
            else:
                self.__stations_dict[line][station] = 1
        else:
            self.__stations_dict[line] = {station: 1}
        if line not in self.__bus_dict:
            return
        data = f"people {station} {self.__stations_dict[line][station]}"
        self.__send_to_all_buses(line, data)

    def __notify_buses_about_buses(self, line_num):
        data = ""
        line_num = int(line_num)
        for bus in self.__bus_dict[line_num]:
            data += str(bus.get_station()) + ","
        data = data[0:-1:]
        self.__send_to_all_buses(line_num, data)

    def __send_to_all_buses(self, line_num, data):
        for bus in self.__bus_dict[line_num]:
            try:
                bus.send_to_bus(data)
            except:
                print(f"{bus} is unavailable, kicked out of the system")
                self.__bus_dict[line_num].remove(bus)


    """the statiscitcs"""


    def countbuses(self):
        count = 0
        for line in self.__bus_dict.values():
            # for item in buses:
            count += len(line)
        return count

    def find_table_size(self):
        if len(self.__bus_dict) == 0:
            max_y_bus = 0
        else:
            max_y_bus = max(self.__bus_dict.keys())

        if len(self.__stations_dict) == 0:
            max_y_stations = 0
        else:
            max_y_stations = max(self.__stations_dict.keys())
        max_y = max(max_y_bus, max_y_stations)

        max_x_stations = 0
        for stations in self.__stations_dict.values():
            max_x_stations = max(max(stations.keys()), max_x_stations)
        max_x_bus = 0

        for buses in self.__bus_dict.values():
            if len(buses)!=0:
                buses.sort(key=lambda bus: bus.get_station())
                max_x_bus = max(buses[-1].get_station(), max_x_bus)
        max_x = max(max_x_bus, max_x_stations)

        return max_x, max_y
    def displaybuseslocation(self):

        if len(self.__bus_dict) == 0 and len(self.__stations_dict) == 0:
            return [[]]

        max_x, max_y = self.find_table_size()
        bus_Dict = self.__bus_dict
        data = []

        for i in range(max_y):
            data.append([" ",])
            for j in range(max_x):
                data[i].append(" ")

        for i in range(max_y):
            #adds the bus numbers
            data[i][0] = ([f"{i + 1}"])

        for line_bus, buses in bus_Dict.items():
            for bus in buses:
                data[line_bus-1][bus.get_station()] = "X"

        for linenumber, stations in self.__stations_dict.items():
            for station, count in stations.items():
                data[linenumber-1][station] = f"{count}"

        return data

    def countpeople(self):
        count = 0
        for line in self.__stations_dict.values():
            for station in line.values():
                count += station
        return count


    class Bus:
        def __init__(self, address, line_number, station, ID):
            self.__address = address
            self.__station = int(station)
            self.__line_number = int(line_number)
            self.__ID = ID

        def get_addr(self):
            return self.__address

        def get_station(self):
            return self.__station
        def set_station(self, station):
            self.__station = int(station)

        def get_line_num(self):
            return self.__line_number

        def get_ID(self):
            return self.__ID

        def update_passengers(self, station, passengers):
            #data = {station} {number_of_people}
            print("tying to send_to_bus")
            data = f"people {station} {passengers}"
            self.send_to_bus(data)

        def send_to_bus(self, data):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.__address[0], BusController.PASSENGERS_PORT))
            # data = {people} {station} {number_of_people}
            # data = {buses} {bus1,bus2,bus3,...busn}
            data  = str(data).encode()
            s.send(data)
            s.close()

        def __str__(self):
            return f"line number: [{self.__line_number}], Current station [{self.__station}] \naddress: {self.__address}"


def table(bus_controller):
    headlines = ["", "1", "2", "3", "4", "5", "6", "7", "8","9","10","11", "12"]
    window = Tk()
    window.geometry("700x500")
    #window.iconbitmap('childhood dream for project.ico')  # put stuff to icon
    window.title("buses")
    scrollX = Scrollbar(window, orient=HORIZONTAL)
    scrollY = Scrollbar(window, orient=VERTICAL)
    window.resizable(OFF, OFF)
    tree = Treeview(window, show="headings", columns=headlines, yscrollcommand=scrollY.set, xscrollcommand=scrollX.set)
    scrollY.config(command=tree.yview)
    scrollY.place(x=480, height=480)
    scrollX.config(command=tree.xview)
    scrollX.place(x=0, y=480, width=480)

    for headline in headlines:
        tree.heading(headline, text=headline)
        tree.column(headline, anchor="center", width=35)

    update(tree, window, bus_controller)
    window.mainloop()


def update(tree, window, bus_controller):
    update_Table(tree, window, bus_controller)
    update_labels(tree, window, bus_controller)
    window.after(2000, update, tree, window, bus_controller)


def update_Table(tree, window, bus_controller):

    headlines = ["", ]
    headlines+=range(1, bus_controller.find_table_size()[0]+1)
    tree.config(columns=headlines)
    #tree.config(columns=["1","1","1","1","1","1"])
    for headline in headlines:
        tree.heading(headline, text=headline)
        tree.column(headline, anchor="center", width=35)

    data = bus_controller.displaybuseslocation()
    for i in tree.get_children():
        tree.delete(i)
    for line in data:
        tree.insert("", END, values=line)
    tree.place(x=0, y=0, width=480, height=480)


def update_labels(tree, window, bus_controller):
    active_lines_label = Label(window, text="Number of active lines: " + str(len(bus_controller.get_bus_dict())))
    number_of_buses_label = Label(window, text="Number of buses in the system: " + str(bus_controller.countbuses()))
    number_of_people_lable = Label(window, text="Number of people waiting: " + str(bus_controller.countpeople()))

    active_lines_label.place(x=500, y=0)
    number_of_buses_label.place(x=500, y=30)
    number_of_people_lable.place(x=500, y=60)


def main():
    """start the server"""

    myserver = BusController()
    myserver.start()

    """start the Telegram Bot"""
    steve = TelegramController("990223452:AAHrln4bCzwGpkR2w-5pqesPHpuMjGKuJUI", myserver)
    threading.Thread(steve.start(), args=())
    table(myserver)



if __name__ == '__main__':
    main()