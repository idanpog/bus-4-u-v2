"""
author: Idan Pogrebinsky

-- server --
"""

# before launching type pip install python-telegram-bot --upgrade in


from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import socket
import threading
from sqlite3 import *

from tkinter import *
from tkinter.ttk import Treeview
from time import sleep
from hashlib import md5
import random
#TODO: when the user requests for 2 or stations in the same line, upon canceling one of the stations it gets stuck in
#the updating buses proccess. self.notify_buses_about_passenger(str(station.line_number), str(station.station_number))
#this line makes me problems

class TelegramController:
    """
    the telegram controller takes care of the telegram bot.
    receives commands from the telegram chat and can communicate with the bus controller
    """

    def __init__(self, token, bus_controller):
        """starts the bot, gets access to the bus_controller and loads the list of bus stations"""
        self.data_base = DataBaseManager()
        self.__token = token
        self.bus_controller = bus_controller
        self.__updater = None
        self.__dp = None
        self.__users = dict()  # dictonary {id: user} (str: User)
        self.__gui = None

    def start(self, gui):
        self.__gui = gui
        update_tracking_thread = threading.Thread(target=self.__luanch_handlers, args=(),
                                                  name="Telegram Controller thread")
        update_tracking_thread.start()

    def stop(self):
        for user in self.__users.values():
            text = f"Hello {user.name.split(' ')[0]}\n" \
                   f"The server is shutting down, your request will be removed\n" \
                   f"Bus4U service wishes you the best"

            self.data_base.log(user, "None", text)
            user.send_message(text)
        self.__updater.stop()
        print("stopped the telegram controller")

    def __luanch_handlers(self):
        """launch in a thread, from main
        takes care of the telegram inputs, and controls other main functions"""
        self.__updater = Updater(self.__token, use_context=True)
        self.__dp = self.__updater.dispatcher
        # on different commands - answer in Telegram
        self.__dp.add_handler(CommandHandler("help", self.help))
        self.__dp.add_handler(CommandHandler("history", self.history))
        self.__dp.add_handler(CommandHandler("bus", self.bus))
        self.__dp.add_handler(CommandHandler("cancel", self.cancel))
        self.__dp.add_handler(CommandHandler("show", self.show))
        self.__dp.add_handler(CommandHandler("promote", self.promote))
        self.__dp.add_handler(CommandHandler("demote", self.demote))
        self.__dp.add_handler(CommandHandler("checkadmin", self.check_admin))
        self.__dp.add_handler(CommandHandler("kick", self.kick))
        self.__dp.add_handler(CommandHandler("stop", self.stop_all))
        self.__dp.add_handler(CommandHandler("whatsmyid", self.__whatsmyid))
        self.__updater.start_polling()
        # logging.getLogger()
        # updater.idle()

    # handlers
    def stop_all(self, update, context):
        user = self.User(update)
        if not self.data_base.check_admin(user):  # allow access only to admins.
            output = "you cannot access this command, must be an admin"
            self.data_base.log(user, update.message.text, output)
            user.send_message(output)
            return
        message = update.message.text.lower().split(" ")
        if len(message) != 2:
            output = "you must type the full command to stop the server\n" \
                     "try /stop server\n" \
                     "USE ONLY IF YOU MUST"
        elif update.message.text.split(" ")[1] != "server":
            output = "You typed the wrong command.\n" \
                     "If you are sure that you want to stop the server type /stop server\n" \
                     "USE ONLY IF YOU MUST"
        else:
            output = "Stopping server."
            print("stopping by remote request from the Telegram admins.")
            self.__gui.remote_stop = True  # has to be done this way so the threads don't interfer with tkinter.
        self.data_base.log(user, update.message.text, output)
        user.send_message(output)

    def help(self, update, context):
        message = update.message.text.lower().split(" ")
        user = self.User(update)
        if len(message) > 1 and message[1] == "me":
            output = 'if you need help buddy, call 1201 they are good guys and they will help you'
        else:
            """Send help when the command /help is issued."""
            output = '/bus {line} {station} \n' \
                     '/history show/clear\n' \
                     '/show lines\n' \
                     '/help'

            if self.data_base.check_admin(user):
                output += '\n--admin commands --\n' \
                          '/kick\n' \
                          '/promote {me/id}\n' \
                          '/demote {me/id}\n' \
                          '/stop'
        update.message.reply_text(output)
        self.data_base.log(user, update.message.text, "*helped*")

    def __whatsmyid(self, update, context):
        user = self.User(update)
        output = f"your ID is: {user.id}"
        user.send_message(output)
        self.data_base.log(user, update.message.text, "*"*len(str(user.id)))

    def show(self, update, context):
        message = update.message.text.lower().split(" ")
        if message[1].lower() == "lines":
            print("showing lines")
            output = f"the currently available lines are: {str(self.bus_controller.show_available_lines())}"
            update.message.reply_text(output)
        else:
            update.message.reply_text("try /show lines")

    def promote(self, update, context):
        message = update.message.text.lower().split(" ")
        user = self.User(update)
        output = "error"
        if message[1] == "me":
            print(f"promoting {user.name}:{user.id}")
            if not self.data_base.check_admin(user):
                self.data_base.promote_admin(user)
                output = "congratulations sir, you're now an Admin."
            else:
                output = "Cannot promote, you're already an Admin."
        elif len(message) == 2:
            if not self.data_base.check_admin(id=message[1]):
                self.data_base.promote_admin(id=message[1])
                output = f"Promoted user with ID: {message[1]} to Admin role."
            else:
                output = "The user you're trying to Promote is already an admin"
        self.data_base.log(user, update.message.text, output)
        user.send_message(output)

    def demote(self, update, context):
        message = update.message.text.lower().split(" ")
        user = self.User(update)
        output = ""
        if message[1] == "me":
            print(f"demoting {user.name}:{user.id}")
            if self.data_base.check_admin(user):
                self.data_base.demote_admin(user)
                output = "congratulations sir, you're no longer an Admin."
            else:
                output = "Cannot demote, you're already a regular user."
        elif len(message) == 2:
            if self.data_base.check_admin(id=message[1]):
                self.data_base.demote_admin(id=message[1])
                output = f"demoted user  with ID: {message[1]} from Admin role."
            else:
                output = "The user you're trying to demote isn't an admin."
        user.send_message(output)
        self.data_base.log(user, update.message.text, output)

    def check_admin(self, update, context):
        user = self.User(update)
        output = self.data_base.check_admin(user)
        user.send_message(output)
        self.data_base.log(user, update.message.text, output)

    def history(self, update, context):
        message = update.message.text.lower().split(" ")
        user = self.User(update)
        output = ""
        if message[1] == "show":
            if not self.data_base.has_history(user):
                output = "you don't have any history"
                self.data_base.log(user, update.message.text, output)
            else:
                output = self.data_base.show_history(user)
                self.data_base.log(user, update.message.text, "Successful showed history")

        if message[1] == "clear":
            if not self.data_base.has_history(user):
                output = "your history is already clean"
            else:
                self.data_base.clear_history(user)
                output = "Clean"
            self.data_base.log(user, update.message.text, output)
        user.send_message(output)

    def bus(self, update, context):
        """takes care of the user requests
        /bus {line} {station}
        adds the request into the system, sends a message to the bus and logs the request in the logs"""
        user = self.User(update)
        message = update.message.text.lower().split(" ")
        if len(message) != 3:
            output = "looks like you have a little mistake in the command\n" \
                     "try /bus {bus number} {station number}" \
                     "for example /bus 14 3"
        else:
            try:
                line = int(message[1])
                station = int(message[2])
                self.bus_controller.add_person_to_the_station(line, station)
                if self.bus_controller.check_line(line):
                    output = f"request accepted, the bus is notified"
                    self.bus_controller.notify_buses_about_passenger(line, station)
                else:
                    output = f"request accepted, but there are no buses available for that line yet"
                self.__add_to_users_dict(update)
            except:
                output = "both of the values you give must be number in order to work" \
                         "for example, /bus 14 3"

        self.data_base.log(user, update.message.text, output)
        update.message.reply_text(output)

    def cancel(self, update, context):
        #/cancel {line num} {station}
        output = ""
        user = self.User(update)
        message = update.message.text.lower().split(" ")
        print(message[1], message[2])
        if user.id not in self.__users.keys():
            output = "looks like you don't have any requests at all."
        elif message[1].isnumeric() and message[2].isnumeric():
            user = self.__users[user.id]
            line_num = int(message[1])
            station_num = int(message[2])
            found_match = False
            for station in user.stations:
                if station.line_number == line_num and station.station_number == station_num:
                    user.remove_station(station)
                    self.bus_controller.remove_person_from_the_station(station)
                    output = "Canceled the request"
                    found_match = True
                    break
                else:
                    print(f"WRONG{type(station.line_number)} == {type(line_num)} and {type(station.station_number)} == {type(station_num)}")
                    print(
                        f"WRONG{station.line_number} == {line_num} and {station.station_number} == {station_num}")
            if not found_match:
                output = "this doesn't match with any of your active requests, so you can't cancel it.\n" \
                         "make sure that you don't have any typing mistakes"
        else:
            output = "the values you entered seem wrong, the values must be number."
        self.data_base.log(user, update.message.text, output)
        user.send_message(output)

    def kick(self, update, context):  # admin command
        user = self.User(update)

        if not self.data_base.check_admin(user):  # allow access only to admins.
            output = "you cannot access this command, must be an admin"
            self.data_base.log(user, update.message.text, output)
            user.send_message(output)
            return
        message = update.message.text.lower().split(" ")
        if message[1] == "buses":
            if len(self.bus_controller.bus_dict) == 0:
                output = "there are already no buses in the system"
            else:
                self.bus_controller.kick_all_buses()
                output = "kicked all buses"
        elif message[1] == "people":
            self.kick_all_passengers("kicked all users by an admin")
            output = "successfully kicked all the passengers"
        else:
            output = "unrecognized command. try /kick buses or /kick people"
        self.data_base.log(user, update.message.text, output)
        user.send_message(output)

    def kick_all_passengers(self, reason):
        for user in self.__users.values():
            user.send_message(
                f"hello {user.name.split(' ')[0]}, it looks like you've been kicked out of the system for: {reason}")
        self.__users = {}
        self.bus_controller.kick_all_passengers()

    def __kick_passenger(self, user, reason):
        try:
            user.send_message(
                f"hello {user.name.split(' ')[0]}, it looks like you've been kicked out of the system for: {reason}")
            del self.__users[user.id]
        except Error as e:
            print("the person you're trying to delete doesn't exist.")

    def __add_to_users_dict(self, update):
        # creates a "user" class, if there is a user with a matching ID in the self.__users
        # then the user in the dictionary will be added another station to the stations storage.
        message = update.message.text.lower().split(" ")
        line_num = int(message[1])
        station_num = int(message[2])
        station = self.Station(line_num, station_num)
        user = self.User(update)
        user.add_station(station)
        if user.id in self.__users.keys():
            self.__users[user.id].add_station(station)
        else:
            print("added user")
            self.__users[user.id] = user

    class Station:
        def __init__(self, line_number, station_number):
            self.__line_number = int(line_number)
            self.__station_number = int(station_number)

        @property
        def line_number(self):
            return self.__line_number

        @property
        def station_number(self):
            return self.__station_number

    class User:
        def __init__(self, telegram_info):
            self.__telegram_info = telegram_info
            self.__stations = []

        def add_station(self, station):
            self.__stations.append(station)

        def remove_station(self,station):
            self.__stations.remove(station)

        def send_message(self, text):
            print(f"sent message to {self.name}, '{text}'")
            self.__telegram_info.message.reply_text(text)

        @property
        def stations(self):
            return self.__stations

        @property
        def telegram_info(self):
            return self.__telegram_info

        @property
        def id(self):
            return self.__telegram_info.message.from_user.id

        @property
        def name(self):
            return self.__telegram_info.message.from_user.name


class DataBaseManager:
    def __init__(self):
        self.__path = "DataBase.db"
        self.__admins = []
        self.__banned = []
        self.__update_admin_cache()

    def has_history(self, user):

        # returnes true if the user is in the system, looks by the ID
        header = connect(self.__path)
        curs = header.cursor()
        curs.execute("SELECT * FROM users WHERE id = (?)", (md5(str(user.id).encode()).hexdigest(),))
        data = curs.fetchall()
        return len(data) >= 1

    def show_history(self, user):
        header = connect(self.__path)
        curs = header.cursor()
        curs.execute("SELECT * FROM users WHERE id = (?)", (md5(str(user.id).encode()).hexdigest(),))
        data = curs.fetchall()[0][1]
        return data

    def clear_history(self, user):
        header = connect(self.__path)
        curs = header.cursor()
        curs.execute("UPDATE users SET history = (?) WHERE id = (?)", ("", md5(str(user.id).encode()).hexdigest()))
        header.commit()

    def log(self, user: TelegramController.User, input: str = "None", output: str = "None") -> NONE:
        # user  :user - the refenced user.
        # input :string - the message that the user sent.
        # output:string - the responce of the server.
        header = connect(self.__path)
        curs = header.cursor()
        encrypted_id = md5(str(user.id).encode()).hexdigest()
        if not self.has_history(user):
            curs.execute("INSERT INTO users VALUES(?, ?)", (encrypted_id, ""))
            user.send_message("Greetings, we're happy that you decided to join and use the Bus4U service!\n"
                              "in order to see all the possible commands you can type /help\n"
                              "Also we want you to know that every command that you type and the server response will"
                              "be logged and you can access your history with /history.\n\n"
                              "we hope you'll enjoy the product and wish you the best.")

        curs.execute("SELECT * FROM users WHERE id = (?)", (encrypted_id,))
        data = curs.fetchall()[0][1]
        data += f"input: {input}\noutput: {output}\n" + "-" * 30 + "\n"
        curs.execute("UPDATE users SET history = (?) WHERE id = (?)", (data, encrypted_id))
        header.commit()

    def __update_admin_cache(self):
        header = connect(self.__path)
        curs = header.cursor()
        curs.execute("SELECT * FROM admins WHERE id IS NOT NULL")
        data = curs.fetchall()
        newlist = []
        for item in data:
            newlist.append(item[0])
        self.__admins = newlist

    def check_admin(self, user=None, id=None):
        if id == None:
            id = user.id
        return md5(str(id).encode()).hexdigest() in self.__admins

    def promote_admin(self, user=None, id=None):
        print("now actually trying to promote admin")
        if id == None:
            id = user.id
        header = connect(self.__path)
        curs = header.cursor()
        encrypted_id = md5(str(id).encode()).hexdigest()
        print(type(encrypted_id))
        curs.execute("INSERT INTO admins(id) VALUES(?)", (encrypted_id,))
        header.commit()
        self.__update_admin_cache()

    def demote_admin(self, user=None, id=None):
        if id == None:
            id = user.id
        if self.check_admin(id=id):
            print("here")
            header = connect(self.__path)
            curs = header.cursor()
            curs.execute("DELETE FROM admins WHERE id = (?)", (md5(str(id).encode()).hexdigest(),))
            header.commit()
            self.__update_admin_cache()


class BusController:
    """takes control over the buses and the communication with them"""
    NEW_CONNECTION_PORT = 8200
    STATIONS_PORT = 8201
    PASSENGERS_PORT = 8202
    HEART_BEAT_PORT = 8203
    HOST = socket.gethostbyname(socket.gethostname())
    PULSE_DELAY = 3

    def __init__(self):
        # used to accept and listen for new buses that join the system
        self.__new_bus_Socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__new_bus_port = 8200
        # used to get new updates from buses
        self.__bus_stations_Socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__bus_stations_port = 8201

        self.__ipv4 = (socket.gethostbyname(socket.gethostname()))
        self.__bus_dict = {}  # self.__bus_dict[line_num] holds an array that contains all the buses
        self.__stations_dict = {}  # self.__stations_dict[line_num][station] holds the amount of people at the station
        # it's a dictionary in a dictionary stracture
        self.__stop_threads = False  # used to stop all the threads in the server for proper shutdown

    @property
    def bus_dict(self):
        return self.__bus_dict

    @property
    def stations_dict(self):
        return self.__stations_dict

    @property
    def buses_count(self):
        count = 0
        for line in self.__bus_dict.values():
            # for item in buses:
            count += len(line)
        return count

    @property
    def people_count(self):
        count = 0
        for line in self.__stations_dict.values():
            for station in line.values():
                count += station
        return count

    def start(self):
        new_bus_receiver = threading.Thread(target=self.__new_bus_reciever, args=(), name="new_bus_reciever")
        new_bus_receiver.start()
        updates_tracker = threading.Thread(target=self.__track_updates, args=(), name="updates_tracker")
        updates_tracker.start()
        heart_beat = threading.Thread(target=self.__heart, args=(), name="Heart beats")
        heart_beat.start()

    def stop(self):
        self.__stop_threads = True
        self.__new_bus_Socket.close()
        self.__bus_stations_Socket.close()
        print(f"stopped {self}")

    def __track_updates(self):
        self.__bus_stations_Socket.bind((self.__ipv4, self.__bus_stations_port))
        self.__bus_stations_Socket.listen(1)
        while not self.__stop_threads:
            # establish a connection
            try:
                client_socket, addr = self.__bus_stations_Socket.accept()
                data = client_socket.recv(1024)
                # data  = {line_number} {station} {ID}
                line_num, station, ID = data.decode().split(" ")
                try:
                    for bus in self.__bus_dict[int(line_num)]:
                        if bus.id == ID:
                            if station.isnumeric():
                                bus.set_station(station)
                                self.__notify_buses_about_buses(int(line_num))
                            else:
                                print(f"{bus} has attempted to update his station but sent an invalid input")
                            break
                except:
                    print("an unregistered bus tried to access the system, ignored")
            except:
                print("closed track_updates")

    def __new_bus_reciever(self):
        print(f"waiting for buses at {self.__ipv4}:{BusController.NEW_CONNECTION_PORT}")
        self.__new_bus_Socket.bind((self.__ipv4, self.__new_bus_port))
        self.__new_bus_Socket.listen(1)
        while not self.__stop_threads:
            # establish a connection
            try:
                client_socket, addr = self.__new_bus_Socket.accept()
                data = client_socket.recv(1024)
                # data  = {line_number} {station} {ID}
                line_num, station, ID = data.decode().split(" ")
                bus = self.Bus(addr, line_num, station, ID)
                self.__add_bus(bus)
                client_socket.close()
                self.__notify_buses_about_buses(line_num)
            except:
                print("closed the new_bus_reciever thread")

    def __add_bus(self, bus):
        print("in add bus")
        if bus.line_num in self.__bus_dict:
            self.__bus_dict[bus.line_num].append(bus)
        else:
            self.__bus_dict[bus.line_num] = [bus, ]

        if bus.line_num in self.stations_dict.keys():
            print("in the if station")
            self.__update_bus_about_all_stations(bus)
        print(f"added bus {bus}")

    def notify_buses_about_passenger(self, line: int, station: int, number_of_people: int = None) -> None:
        if number_of_people !=None:
            data = f"people {station} {number_of_people}"
        else:
            data = f"people {station} {self.__stations_dict[line][station]}"
        self.__send_to_all_buses(line, data)

    def add_person_to_the_station(self,line , station):
        if line in self.__stations_dict:
            if station in self.__stations_dict[line]:
                self.__stations_dict[line][station] += 1
            else:
                self.__stations_dict[line][station] = 1
        else:
            self.__stations_dict[line] = {station: 1}

    def remove_person_from_the_station(self, station):
        if station.line_number in self.__stations_dict and station.station_number in self.__stations_dict[station.line_number]:
            if self.__stations_dict[station.line_number][station.station_number] == 1:
                del self.__stations_dict[station.line_number][station.station_number]
                self.notify_buses_about_passenger(station.line_number, station.station_number, number_of_people=0)
            elif self.__stations_dict[station.line_number][station.station_number] > 1:
                self.__stations_dict[station.line_number][station.station_number]-=1
                self.notify_buses_about_passenger(station.line_number, station.station_number)
        else:
            print("whoops an error, looks like the current station doesn't exit and there's no person waiting for it.")


    def __notify_buses_about_buses(self, line_num):
        if not self.check_line(line_num):
            return
        data = "buses "
        line_num = int(line_num)
        for bus in self.__bus_dict[line_num]:
            data += str(bus.station_num) + ","
        data = data[0:-1:]
        self.__send_to_all_buses(line_num, data)

    def __send_to_all_buses(self, line_num, data):
        print(f"sending to all buses in line {line_num}, {data}")
        if line_num not in self.__bus_dict.keys():
            return
        for bus in self.__bus_dict[line_num]:
            try:
                bus.send_to_bus(data)
            except:
                print(f"{bus} is unavailable, kicked out of the system")
                self.remove_bus(bus)
                self.__notify_buses_about_buses(bus.line_num)

    def get_bus_dict(self):
        return self.__bus_dict

    def __update_bus_about_all_stations(self, bus): #1-3,4-1,13-0
        """
        tells the bus about the the passengers waiting for him at the stations.
        used when the bus first joins the system.
        """
        data = "all passengers\n"
        try:
            for station_number, people_count in self.__stations_dict[bus.line_num].items():
                data += f"{station_number}-{people_count},"
            data = data[:-1:]
            print(data)
            bus.send_to_bus(data)
        except Error as e:
            pass

    def show_available_lines(self):
        if len(self.__bus_dict) == 0:
            return "None"
        return list(self.__bus_dict.keys())

    def kick_all_buses(self):
        self.__bus_dict = {}
        print("kicked all buses from the system")

    def kick_all_passengers(self):
        changed_lines = self.__stations_dict.keys()
        for line in changed_lines:
            if line in self.__bus_dict:
                    self.__send_to_all_buses(line, "kick all passengers")
        self.__stations_dict = {}

    def __check_duplicates(self):
        buses = []
        for line in self.__bus_dict.values():
            for bus in line:
                buses.append(bus)

        for idx, bus in enumerate(buses):
            for another_bus in buses[idx + 1::]:
                if bus.id == another_bus.id:
                    print(f"found duplicates, {bus}\n\n {another_bus}")
                    self.remove_bus(bus)
                    self.remove_bus(another_bus)

    def __heart(self):
        # will be launched in a separate thread and cycle the command pulse for all the buses every 20 seconds
        while not self.__stop_threads:
            self.__pulse_all()
            self.__check_duplicates()
            sleep(BusController.PULSE_DELAY)
        print("stopped the heartbeats")

    def __pulse_all(self):
        # will launch a thread for each bus that will use the command indevidual_pulse
        if len(self.__bus_dict) == 0:
            return
        for line in self.__bus_dict.values():
            for bus in line:
                threading.Thread(target=self.__indevidual_pulse, args=(bus,), name=f"pulse ID: {bus.id}").start()

    def __indevidual_pulse(self, bus):
        # will send the bus a message
        # data = "Check"
        # and wait for a response from the bus with his ID
        # if the bus isn't responding, or sent the wrong ID he'll be kicked.
        if not bus.check_up():
            print("bus found inactive")
            self.remove_bus(bus)

    def check_line(self, line):
        return int(line) in self.__bus_dict

    def remove_bus(self, bus):
        self.__bus_dict[bus.line_num].remove(bus)
        print(f"removed: {bus}")
        if len(self.__bus_dict[bus.line_num()]) == 0:
            del self.__bus_dict[bus.line_num()]
            print("removed the whole line")
        else:
            self.__notify_buses_about_buses(bus.line_num)

    class Bus:
        def __init__(self, address, line_number, station, ID):
            self.__address = address
            self.__station = int(station)
            self.__line_number = int(line_number)
            self.__id = ID

        @property
        def station_num(self):
            return self.__station
        @property
        def line_num(self):
            return self.__line_number

        @property
        def id(self):
            return self.__id

        def set_station(self, station):
            self.__station = int(station)

        def update_passengers(self, station, passengers):
            # data = {station} {number_of_people}
            print("tying to send_to_bus")
            data = f"people {station} {passengers}"
            self.send_to_bus(data)

        def send_to_bus(self, data):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.__address[0], BusController.PASSENGERS_PORT))
            # data = {people} {station} {number_of_people}
            # data = {buses} {bus1,bus2,bus3,...busn}
            data = str(data).encode()
            s.send(data)
            s.close()

        def check_up(self):
            # send a Check notification
            # returs True if everything is valid and false if the bus returned the wrong ID or didn't respond
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(BusController.PULSE_DELAY * 0.8)
            output = True
            try:
                s.connect((self.__address[0], BusController.HEART_BEAT_PORT))
                data = "Check".encode()
                s.send(data)
                data = s.recv(1024).decode()
                if int(data) != int(self.__id):
                    print(f"bus had the wrong ID\nwas supposed to be {self.__id}, but received {data}")
                    output = False
            # listen for an answer
            except:
                print(f"something went wrong, couldn't establish connection with {self.__address}")
                output = False
            s.close()
            return output

        def __str__(self):
            return f"line number: [{self.__line_number}], Current station [{self.__station}] \naddress: {self.__address}"


class GUI:

    def __init__(self, bus_controller, telegram_controller):
        self.__telegram_controller = telegram_controller
        self.__bus_controller = bus_controller
        self.__main_window = Tk()
        self.__main_display_table = None
        self.remote_stop = False
        self.__headlines = [" "] + [str(x) for x in range(1, self.find_table_length() + 1)]

    def start(self):
        self.__main_window.geometry("700x500")
        self.__main_window.iconbitmap('childhood dream for project.ico')  # put stuff to icon
        self.__main_window.title("buses")
        scrollX = Scrollbar(self.__main_window, orient=HORIZONTAL)
        scrollY = Scrollbar(self.__main_window, orient=VERTICAL)
        self.__main_window.resizable(OFF, OFF)
        self.__main_display_table = Treeview(self.__main_window, show="headings", columns=self.__headlines,
                                             yscrollcommand=scrollY.set, xscrollcommand=scrollX.set)
        scrollY.config(command=self.__main_display_table.yview)
        scrollY.place(x=480, height=480)
        scrollX.config(command=self.__main_display_table.xview)
        scrollX.place(x=0, y=480, width=480)
        self.__place_buttons()
        for headline in self.__headlines:
            self.__main_display_table.heading(headline, text=headline)
            self.__main_display_table.column(headline, anchor="center", width=35)

        self.__update_table_and_labels()
        self.__main_window.mainloop()

    def __stop(self, reason="user"):
        print(f"trying to close because {reason}")
        try:
            self.__main_window.destroy()
        except:
            print("failed to close the main window")

        self.__telegram_controller.stop()
        self.__bus_controller.stop()

        sys.exit(f"properly closed by {reason}")

    def __kick_passengers(self):
        self.__telegram_controller.kick_all_passengers("kicked all passengers by an admin")

    def __update_table_and_labels(self):
        self.__update_Table()
        self.__update_labels()
        if self.remote_stop:
            self.__stop("remote telegram admin")
        self.__main_window.after(2000, self.__update_table_and_labels)

    def find_table_length(self):
        max_x_stations = 0
        for stations in self.__bus_controller.stations_dict.values():
            max_x_stations = max(max(stations.keys()), max_x_stations)
        max_x_bus = 0

        for buses in self.__bus_controller.bus_dict.values():
            if len(buses) != 0:
                buses.sort(key=lambda bus: bus.station_num)
                max_x_bus = max(buses[-1].station_num, max_x_bus)
        max_x = max(max_x_bus, max_x_stations)
        return max_x

    def __update_Table(self):
        # used to refresh the data in the table, it generates the data and then puts it in.
        headlines = ["", ]
        headlines += range(1, + 1)
        headlines = [" "] + [str(x) for x in range(1, self.find_table_length() + 1)]
        self.__main_display_table.config(columns=headlines)

        for headline in headlines:
            self.__main_display_table.heading(headline, text=headline)
            self.__main_display_table.column(headline, anchor="center", width=35)

        data = self.__display_buses_location()

        for i in self.__main_display_table.get_children():
            # deletes all the data in the chart
            self.__main_display_table.delete(i)
        for line in data:
            # inserts new data into the chart, goes line by line
            self.__main_display_table.insert("", END, values=line)

        self.__main_display_table.place(x=0, y=0, width=480, height=480)

    def __update_labels(self):
        active_lines_label = Label(self.__main_window,
                                   text="Number of active lines: " + str(len(self.__bus_controller.bus_dict)))
        number_of_buses_label = Label(self.__main_window,
                                      text="Number of buses in the system: " + str(self.__bus_controller.buses_count))
        number_of_people_lable = Label(self.__main_window,
                                       text="Number of people waiting: " + str(self.__bus_controller.people_count))

        active_lines_label.place(x=500, y=0)
        number_of_buses_label.place(x=500, y=30)
        number_of_people_lable.place(x=500, y=60)

    def __place_buttons(self):
        self.__kick_buses_button = Button(self.__main_window, text="kick all buses",
                                          command=self.__bus_controller.kick_all_buses,
                                          width=11, height=2, fg="navy", activebackground="snow3")
        self.__kick__all_passengers = Button(self.__main_window, text="kick all passengers",
                                             command=self.__kick_passengers,
                                             width=11, height=2, fg="navy", activebackground="snow3")
        self.__stop_button = Button(self.__main_window, text="stop server", command=self.__stop,
                                    width=11, height=2, fg="red", background="floral white", activebackground="gray18")

        self.__kick_buses_button.place(x=500, y=400)
        self.__kick__all_passengers.place(x=595, y=400)
        self.__stop_button.place(x=595, y=450)

    def __display_buses_location(self):

        if len(self.__bus_controller.bus_dict) == 0 and len(self.__bus_controller.stations_dict) == 0:
            return [[]]  # breaks the run if there are no buses
        data = []
        empty_list = []  # an empty list that has placeholders for later use
        for i in range(self.find_table_length()):
            empty_list.append(" ")
        if len(self.__bus_controller.stations_dict) != 0:
            # makes sure that there are people waiting somewhere before we start marking them
            for line, stations in self.__bus_controller.stations_dict.items():
                list = [str(line)] + empty_list
                # creates the first line that has the placeholders and the line number
                for station, people_count in stations.items():
                    list[station] = people_count
                    # overrides the placeholders with the amount of people waiting at the station
                data.append(list)

        relevant_lines = []
        # just shows all the lines that are already in the list and showing passengers
        if len(self.__bus_controller.stations_dict) != 0:
            for list in data:
                relevant_lines.append(list[0])
        """buses override passengers when they colide in the same line"""
        for line, buses in self.__bus_controller.bus_dict.items():
            # puts an X wherever there's a bus
            if str(line) in str(relevant_lines):
                # if the line is already there it doesn't add another list into data
                for bus in buses:
                    data[relevant_lines.index(str(line))][bus.station_num] = "X"
            else:
                # if the line isn't there yet it adds another list that contains a placeholder and an X for each bus
                list = [str(line)] + empty_list
                for bus in buses:
                    list[bus.station_num] = "X"
                data.append(list)

        data = sorted(data, key=lambda list: int(list[0]))
        # sorts data by the first Value in the list so it would show the lines sorted.
        return data


def main():
    """start the server"""

    myserver = BusController()
    steve = TelegramController("990223452:AAHrln4bCzwGpkR2w-5pqesPHpuMjGKuJUI", myserver)
    gui = GUI(myserver, steve)

    myserver.start()
    steve.start(gui)
    gui.start()


if __name__ == '__main__':
    main()
