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
#TODO:limit the amount of request that a single user can make to 3 requests.
#TODO:limit the a user to request only 1 station at each line.
#TODO:when a bus picks up a user all of his requests will be removed.
#fix bug: after server restart the bus doesn't know that the users have been removed




class TelegramController:
    """
    the telegram controller takes care of the telegram bot.
    receives commands from the telegram chat and can communicate with the bus controller
    """

    def __init__(self, token: str, bus_controller: object):
        """loads the needed information for the bot, gets access to the bus_controller and loads the list of bus stations"""
        self.data_base = DBManager()
        self.__token = token
        self.bus_controller = bus_controller
        self.__updater = None
        self.__dp = None
        self.__users = dict()  # dictonary {id: user} (str: User)
        self.__gui = None

    def start(self, gui: object):
        """
        acquires access to the GUI
        launches the thread that takes care of all the handlers
        """
        self.__gui = gui
        update_tracking_thread = threading.Thread(target=self.__luanch_handlers, args=(),
                                                  name="Telegram Controller thread")
        update_tracking_thread.start()

    def stop(self):
        """
        tells all users that the server shuts down
        stops the handlers
        """
        for user in self.__users.values():
            text = f"Hello {user.name.split(' ')[0]}\n" \
                   f"The server is shutting down, your request will be removed\n" \
                   f"Bus4U service wishes you the best"

            self.data_base.log(user, "None", text)
            user.send_message(text)
        self.__updater.stop()

    def __luanch_handlers(self):
        """
            takes up a thread of it's own as it's endless.
            maneges the telegram inputs, and controls other main functions
        """
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

    def stop_all(self, update, context):
        """
        Admin only command
        Stops all the server
        Syntax: /stop server
        """
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
        """
        Accessible to all, but will show more commands to admins
        the syntax is /help
        the log won't see everything but only *helped* so it won't be spammed
        """
        message = update.message.text.lower().split(" ")
        user = self.User(update)
        if len(message) > 1 and message[1] == "me":
            output = 'if you need help buddy, call 1201 they are good guys and they will help you'
        else:
            """Send help when the command /help is issued."""
            output = '/bus {line} {station} \n' \
                     '/history show/clear\n' \
                     '/show lines\n' \
                     '/cancel {line} {station}' \
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
        """
        one of the commands accessible to everyone, but it won't be shown to everyone in help
        displays the Telegram id of the user
        syntax: /whatsmyid
        used when trying to promote a member to be an admin
        will be censored in history logs so the ID won't be accessible if anyone hacks the database
        later will be used in /promote {id}
        """
        user = self.User(update)
        output = f"your ID is: {user.id}"
        user.send_message(output)
        self.data_base.log(user, update.message.text, "*" * len(str(user.id)))

    def show(self, update, context):
        """
        one of the commands accessible to everyone
        syntax /show lines

        """
        #TODO: add show requests
        #TODO: add show how long till bus
        message = update.message.text.lower().split(" ")
        if message[1].lower() == "lines":
            print("showing lines")
            output = f"the currently available lines are: {str(self.bus_controller.show_available_lines())}"
            update.message.reply_text(output)
        else:
            update.message.reply_text("try /show lines")

    def notify_passengers_about_incoming_bus(self, bus):
        """
        tells all the passengers waiting for that line that their bus is arriving soon.
        for example: "Dear Idan pog, your bus line 45 will soon arrive at your station."
        """
        for user in self.__find_relevant_passengers(bus.line_num, bus.station_num+1):
            user.send_message(f"Hey {user.name.split(' ')[0]} your bus line {bus.line_num} will arrive soon at your station.")

    def __find_relevant_passengers(self, line: int, station_num: int ):
        """
        :return: a list that contains all the passengers that are waiting at the given station.
        """
        output = []
        for user in self.__users.values():
            for station in user.stations:
                if station.line_number == line and station.station_number == station_num:
                   output.append(user)
        return output


    def remove_everyone_from_station(self, line: int, station_num: int):
        """

        :param line:
        :param station_num:
        :return: a list with all the users that need to be removed.
        """
        users_to_remove = []
        for user in self.__users.values():
            for station in user.stations:
                if station.line_number == line and station.station_number == station_num:
                    users_to_remove.append(user)
        for user in users_to_remove:
            self.__users.pop(user.id)
        #map( )
        return users_to_remove


    def promote(self, update, context):
        """
        command accessible to everyone
        promotes the requested user
        syntax: /promote {me/id}
        """

        #TODO allow this command only to admins
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
        """
        command accessible to everyone
        demotes the requested user
        syntax: /demote {me/id}
        """
        #TODO: make this only admin accessible command
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
        """
        one of the commands accessible to everyone, but won't be shown in help
        used to check if the user has admin permissions.
        sends the user (True/False)
        syntax: /checkadmin
        """
        user = self.User(update)
        output = self.data_base.check_admin(user)
        user.send_message(output)
        self.data_base.log(user, update.message.text, str(output))

    def history(self, update, context):
        """
        one of the commands accessible to everyone
        used to manage the history of the account.
        syntax:
            /history show - shows the history
            /history clear - clears all the records of the user history.
        """
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
        """
        one of the telegram commands that the user can access.
        the syntax: /bus {line} {station}
        places a request for the bus, and notifies everyone needed.
        """
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
        """
        One of the commands accessible to everyone
        Used to cancel requests for buses
        Syntax: /cancel {line} {station}
        Sends the user an update if it managed to cancel everything or it failed somewhere
        """

        # /cancel {line num} {station}
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
            if not found_match:
                output = "this doesn't match with any of your active requests, so you can't cancel it.\n" \
                         "make sure that you don't have any typing mistakes"
        else:
            output = "the values you entered seem wrong, the values must be number."
        self.data_base.log(user, update.message.text, output)
        user.send_message(output)

    def kick(self, update, context):  # admin command
        """
        A command only accessible to admins
        used to kick the buses or the passengers from the system remotely
        syntax:
        /kick buses - kicks all buses out of the system
        /kick people - kicks all the passengers out of the system
        """
        user = self.User(update)
        if not self.data_base.check_admin(user):
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

    def kick_all_passengers(self, reason: str):
        """
        internal command, sends to all the passengers that they've been kicked for {reason}
        then deletes all the users from the users list. and tells the bus controller as well to kick all the users
        """
        for user in self.__users.values():
            user.send_message(
                f"hello {user.name.split(' ')[0]}, it looks like you've been kicked out of the system for: {reason}")
        self.__users = {}
        self.bus_controller.kick_all_passengers()

    def __kick_passenger(self, user, reason):
        """internal command, kicks a {user} for a {reason}"""
        try:
            user.send_message(
                f"hello {user.name.split(' ')[0]}, it looks like you've been kicked out of the system for: {reason}")
            del self.__users[user.id]
        except Error as e:
            print("the person you're trying to delete doesn't exist.")

    def __add_to_users_dict(self, update):
        """
        takes an update from the message
        creates a "user" class, if there is a user with a matching ID in the self.__users
        then the user in the dictionary will be added another station to the stations storage.
        """
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
        """
        internal class used to represent a stations.
        holds s a line number and a station number.
        """
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
        """
        represents a user
        can send a message to the user if needed
        remembers all the stations that the user has requested in the past.
        """
        def __init__(self, telegram_info: object) -> object:
            self.__telegram_info = telegram_info
            self.__stations = []

        def add_station(self, station):
            """gets a station and just adds it to the list of stations that the user has requested"""
            self.__stations.append(station)

        def remove_station(self, station):
            """removes a station from the list of stations"""

            self.__stations.remove(station)

        def send_message(self, text):
            """uses the userinfo (which is actually just an update) to send the user a message"""
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
            """returnes the full name of the user, for example "Idan pog" """
            return self.__telegram_info.message.from_user.name


class DBManager:
    """
    the data base is responsible for all the information stored about the users
    including their history, and their rank
    """
    def __init__(self):
        """doesn't take anything, but allocates place for all the important things that will be used later"""
        self.__path = "DataBase.db"
        self.__admins = []
        self.__banned = []
        self.__update_admin_cache()

    def has_history(self, user):
        """
        takes an argument from type User
        returns true if the user is in the system, looks by the ID
        """
        #
        header = connect(self.__path)
        curs = header.cursor()
        encrypted_id = md5((str(user.id) + "typicaluser").encode()).hexdigest()
        curs.execute("SELECT * FROM users WHERE id = (?)", (encrypted_id,))
        data = curs.fetchall()
        return len(data) >= 1

    def show_history(self, user:TelegramController.User):
        """
        takes a user:User and returns his usage history from the database.
        """
        header = connect(self.__path)
        curs = header.cursor()
        encrypted_id = md5((str(user.id) + "typicaluser").encode()).hexdigest()
        curs.execute("SELECT * FROM users WHERE id = (?)", (encrypted_id,))
        data = curs.fetchall()[0][1]
        return data

    def clear_history(self, user:TelegramController.User):
        """
        :param user: User
        :return: None
        clears all the history of the user sets it to ""
        """
        header = connect(self.__path)
        curs = header.cursor()
        encrypted_id = md5((str(user.id) + "typicaluser").encode()).hexdigest()
        curs.execute("UPDATE users SET history = (?) WHERE id = (?)", ("", encrypted_id))
        header.commit()

    def log(self, user: TelegramController.User, input: str = "None", output: str = "None") -> NONE:
        """

        :param user: User -  the refenced user
        :param input: str - the message that the user sent.
        :param output:  str - the output that the server returnes
        :return: None
        writes the new information into the storage, separated by lines that look like -----------------.
        """
        header = connect(self.__path)
        curs = header.cursor()
        encrypted_id = md5((str(user.id) + "typicaluser").encode()).hexdigest()
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
        """
        an internal command that's part of the chaching method that the program uses
        each time the admin list changes in the data base this command will also be called so the chached admin list will also be updated
        simply stores a copy of the information in the RAM memory
        """
        header = connect(self.__path)
        curs = header.cursor()
        curs.execute("SELECT * FROM admins WHERE id IS NOT NULL")
        data = curs.fetchall()
        newlist = []
        for item in data:
            newlist.append(item[0])
        self.__admins = newlist

    def check_admin(self, user: TelegramController.User=None, id: str=None):
        """
        used to check if the given User/id is a user
        has to get at least one of the required arguments to work properly
        :returns a bool
        """
        if id == None:
            id = user.id
        return md5(str(id+"admin").encode()).hexdigest() in self.__admins

    def promote_admin(self, user: TelegramController.User=None, id: str=None):
        """
        :param user: User - the user you're trying to promote
        :param id: str - the user's that you're trying to promote ID
        :return: None
        will promote the given user to the admin rank and update the cache
        """
        print("now actually trying to promote admin")
        if id == None:
            id = user.id
        header = connect(self.__path)
        curs = header.cursor()
        encrypted_id = md5((str(id)+"admin").encode()).hexdigest()
        print(type(encrypted_id))
        curs.execute("INSERT INTO admins(id) VALUES(?)", (encrypted_id,))
        header.commit()
        self.__update_admin_cache()

    def demote_admin(self, user=None, id=None):
        """
        :param user: User - the user you're trying to demote
        :param id: str - the user's that you're trying to demote ID
        :return: None
        will demote the given user to the admin rank and update the cache
        """
        if id == None:
            id = user.id
        if self.check_admin(id=id):
            print("here")
            header = connect(self.__path)
            curs = header.cursor()
            encrypted_id = md5((str(id) + "admin").encode()).hexdigest()
            curs.execute("DELETE FROM admins WHERE id = (?)", (encrypted_id,))
            header.commit()
            self.__update_admin_cache()


class BusController:
    """
    takes control over the buses and the communication with them
    holds 3 important communication channels
    new_bus_connections = waits to receive connections from buses that want to join the system
    recieve_updates = waits for buses to send a message with an update regarding their location
    heart_beat = sends pulse to the bus client e very few seconds and if it doens't recieve an answer it kicks the bus

    it stores the information about each bus that is in the system, when it is needed to send a notification
    to the bus, it opens a TCP connection, sends the data, and closes it.
    """
    NEW_CONNECTION_PORT = 8200
    STATIONS_PORT = 8201
    PASSENGERS_PORT = 8202
    HEART_BEAT_PORT = 8203
    HOST = socket.gethostbyname(socket.gethostname())
    PULSE_DELAY = 3
    MAX_STATION = 10

    def __init__(self):
        # used to accept and listen for new buses that join the system
        self.__new_bus_Socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # used to get new updates from buses
        self.__bus_stations_Socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

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
        """return: the amount of people waiting for buses, used as part of the statistics"""
        count = 0
        for line in self.__stations_dict.values():
            for station in line.values():
                count += station
        return count

    def start(self, telegram_bot):
        """
        launches all the important threads
        new_bus_reviever - waits for connections from new buses and adds them to the system
        updates_tracker - waits for connections from buses in the system and updates the relevant information
        heart_beat - keeps track of all the buses and makes sure that there are no offline buses by kicking them
        """
        self.__telegram_bot = telegram_bot
        new_bus_receiver = threading.Thread(target=self.__new_bus_reciever, args=(), name="new_bus_reciever")
        new_bus_receiver.start()
        updates_tracker = threading.Thread(target=self.__track_updates, args=(), name="updates_tracker")
        updates_tracker.start()
        heart_beat = threading.Thread(target=self.__heart, args=(), name="Heart beats")
        heart_beat.start()

    def stop(self):
        """
        stops the bus controller
        stops all the threads and prints into the log, (stopped)
        """
        self.__stop_threads = True
        self.__new_bus_Socket.close()
        self.__bus_stations_Socket.close()
        print(f"stopped {self}")

    def __track_updates(self):
        """
        waits for buses to update their location.
        will continue as long as self.__stop_threads = False
        accepts updates only from buses that already exist in the system, checks by id and ip match
        after every update, it will update all the buses about the change.
        """
        self.__bus_stations_Socket.bind((self.__ipv4, BusController.STATIONS_PORT))
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
                                if int(station) < BusController.MAX_STATION:
                                    bus.set_station(station)
                                    self.__telegram_bot.notify_passengers_about_incoming_bus(bus)
                                    self.try_remove_people_from_the_station(bus=bus)
                                else: self.remove_bus(bus)
                                self.__notify_buses_about_buses(int(line_num))
                            else:
                                print(f"{bus} has attempted to update his station but sent an invalid input")
                            break
                except Exception as e:
                    print(e)
                    print("an unregistered bus tried to access the system, ignored")
            except:
                print("closed track_updates")

    def __new_bus_reciever(self):
        """
        waits for new buses to log in the system
        adds them into the system
        the required syntax from the bus side to join the system is data  = {line_number} {station} {ID}
        after a bus joined the system it notifies all buses about the update.
        :return:
        """
        print(f"waiting for buses at {self.__ipv4}:{BusController.NEW_CONNECTION_PORT}")
        self.__new_bus_Socket.bind((self.__ipv4, BusController.NEW_CONNECTION_PORT))
        self.__new_bus_Socket.listen(1)
        while not self.__stop_threads:
            # establish a connection
            try:
                client_socket, addr = self.__new_bus_Socket.accept()
                data = client_socket.recv(1024)
                print(data)
                # data  = {line_number} {station} {ID}
                line_num, station, ID = data.decode().split(" ")
                if int(station) < BusController.MAX_STATION:
                    bus = self.Bus(addr, line_num, station, ID)
                    self.__add_bus(bus)
                    self.__notify_buses_about_buses(line_num)
                client_socket.close()
            except:
                print("closed the new_bus_reciever thread")

    def __add_bus(self, bus):
        """
        an internal method that adds the bus into the storage of the bus controller
        after it adds the bus into the system it updates all the other buses in the line that there is a change
        """
        if bus.line_num in self.__bus_dict:
            self.__bus_dict[bus.line_num].append(bus)
        else:
            self.__bus_dict[bus.line_num] = [bus, ]
        if bus.line_num in self.stations_dict.keys():
            print("in the if station")
            self.__update_bus_about_all_stations(bus)
        print(f"added bus {bus}")

    def notify_buses_about_passenger(self, line: int, station: int, number_of_people: int = None) -> None:
        """
        a method that is used to notify all the buses in the line about an update
        regarding the location of the users.
        can recieve a line + station and it will look for the amount of people waiting at the station in the memory
        if you have removed the certain station out of the memory bcause there are no people waiting you can pass it
        a third parameter number_of_people=0 and it won't look for it in the memory and just tell the buses that there
        are 0 people waiting at the stations.
        """
        if number_of_people != None:
            data = f"people {station} {number_of_people}"
        else:
            data = f"people {station} {self.__stations_dict[line][station]}"
        self.__send_to_all_buses(line, data)

    def add_person_to_the_station(self, line, station):
        """
        adds the user into the self.__stations_dict.
        :param line: the line that the person waits for
        :param station: the stations that the person waits at
        :return: None
        """
        if line in self.__stations_dict:
            if station in self.__stations_dict[line]:
                self.__stations_dict[line][station] += 1
            else:
                self.__stations_dict[line][station] = 1
        else:
            self.__stations_dict[line] = {station: 1}

    def remove_person_from_the_station(self, station: TelegramController.Station):
        """
        gets a station
        removes the person from the station and notifies the buses about the update."""
        if station.line_number in self.__stations_dict and station.station_number in self.__stations_dict[station.line_number]:
            if self.__stations_dict[station.line_number][station.station_number] == 1:
                del self.__stations_dict[station.line_number][station.station_number]
                if len(self.__stations_dict[station.line_number]) == 0:
                    del self.__stations_dict[station.line_number]
                self.notify_buses_about_passenger(station.line_number, station.station_number, number_of_people=0)
            elif self.__stations_dict[station.line_number][station.station_number] > 1:
                self.__stations_dict[station.line_number][station.station_number] -= 1
                self.notify_buses_about_passenger(station.line_number, station.station_number)
        else:
            print("whoops an error, looks like the current station doesn't exit and there's no person waiting for it.")

    def try_remove_people_from_the_station(self, line: int = None, station_num: int = None, bus = None):
        if bus!=None:
            line = bus.line_num
            station_num = bus.station_num
        if line in self.__stations_dict.keys():
            print("bitch im in")
            thingy = self.__stations_dict[line]
            if station_num in self.__stations_dict[line].keys(): #checks if the bus picked up anybody
                del self.__stations_dict[line][station_num] #clears the Bus controller memory from users in the certain station
                if len(self.__stations_dict[line]) == 0:
                    del self.__stations_dict[line]
                #launches a thread that waits one sec to notify the buses about the change in people, avoids collisions in TCP connections this way
                update_buses_thread = threading.Thread(target=self.__notify_about_people_after_a_second, args=(line, station_num, 0),
                                                          name="notify about people after a second")
                update_buses_thread.start()
                people_that_need_to_be_kicked = self.__telegram_bot.remove_everyone_from_station(line, station_num)
                # a list of Users that have been waiting at the station
                changed_lines = []
                for user in people_that_need_to_be_kicked: #kick them from the memory of the bus controller
                    for station in user.stations:
                        if station.line_number!=line:
                            self.remove_person_from_the_station(station)
                            if station.line_number not in changed_lines and station.station_number != station_num:
                                changed_lines.append(station.line_number)
                for line in changed_lines: #launches a thread for each line in the changed lines to tell all the buses about the change.
                    if line in self.__bus_dict.keys():
                        for bus in self.__bus_dict[line]:
                            threading.Thread(target=self.__update_bus_about_all_stations,args=(bus),
                                                                   name="notify other buses about a picked up user").start()
                print("done")

    def __notify_about_people_after_a_second(self, line, station, number_of_people=0):
        sleep(1)
        self.notify_buses_about_passenger(line, station, number_of_people=number_of_people)

    def __notify_buses_about_buses(self, line_num):
        """
        sends the buses an update about all the buses in the same line as they are
        in the form of buses 3,5,23,8 when the numbers are the locations of the buses.
        """
        if not self.check_line(line_num):
            return
        data = "buses "
        line_num = int(line_num)
        for bus in self.__bus_dict[line_num]:
            data += str(bus.station_num) + ","
        data = data[0:-1:]
        self.__send_to_all_buses(line_num, data)

    def __send_to_all_buses(self, line_num: int, data: str):
        """loops through all the buses in the line and sends them the given data"""
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

    def __update_bus_about_all_stations(self, bus):  # 1-3,4-1,13-0
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
        """just returns a list of all the active lines in the system"""
        if len(self.__bus_dict) == 0:
            return "None"
        return list(self.__bus_dict.keys())

    def kick_all_buses(self):
        """empties the self.__bus_dict"""
        self.__bus_dict = {}
        print("kicked all buses from the system")

    def kick_all_passengers(self):
        """
        kicks all passengers
        notifies all the buses that the passengers have been removed
        """
        changed_lines = self.__stations_dict.keys()
        for line in changed_lines:
            if line in self.__bus_dict:
                self.__send_to_all_buses(line, "kick all passengers")
        self.__stations_dict = {}

    def __check_duplicates(self):
        """
        checks if there are duplicates of the buses, if there are 2 buses with a matching id
        if it finds, it kickes both of them.
        ususally used during the pulse.
        :return:
        """
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

        """
        will be launched in a separate thread
        cycles the command pulse for all the buses every few seconds
        """
        while not self.__stop_threads:
            self.__pulse_all()
            self.__check_duplicates()
            sleep(BusController.PULSE_DELAY)
        print("stopped the heartbeats")

    def __pulse_all(self):
        """launches a thread for each bus that will use the command individual_pulse
        in order to complete the heartbeat mechanism"""
        if len(self.__bus_dict) == 0:
            return
        for line in self.__bus_dict.values():
            for bus in line:
                threading.Thread(target=self.__indevidual_pulse, args=(bus,), name=f"pulse ID: {bus.id}").start()

    def __indevidual_pulse(self, bus):
        """
        will send the bus a message
        data = "Check"
        and wait for a response from the bus with his ID
        if the bus isn't responding, or sent the wrong ID he'll be kicked.
        """
        if not bus.check_up():
            print("bus found inactive")
            self.remove_bus(bus)

    def check_line(self, line):
        """returns wherever the line is in the server or not"""
        return int(line) in self.__bus_dict

    def remove_bus(self, bus):
        """kicks a bus from the memory of the server, and notifies all the important line"""
        self.__bus_dict[bus.line_num].remove(bus)
        print(f"removed: {bus}")
        if len(self.__bus_dict[bus.line_num]) == 0:
            del self.__bus_dict[bus.line_num]
            print("removed the whole line")
        else:
            self.__notify_buses_about_buses(bus.line_num)

    class Bus:
        """
        an internal class that represents a bus.
        stores all the needed information including the location, the ip and id
        """
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
            """
            updates the bus regarding the passengers at the station
            data = {station} {number_of_people}
            """
            data = f"people {station} {passengers}"
            self.send_to_bus(data)

        def send_to_bus(self, data):
            """
            sends the bus the data you give to the command
            :param data:
            :return:
            """
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.__address[0], BusController.PASSENGERS_PORT))
            data = str(data).encode()
            s.send(data)
            s.close()

        def check_up(self):
            """
            part of the heartbeat mechanism
            send a Check notification
            returns True if everything is valid and false if the bus returned the wrong ID or didn't respond
            """
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
    """
    the Gui
    has buttons
        - kick all buses
        - kick all passengers
        - exit
    display that shows all the users in the system and the buses
    has some statistics as well
        - Number of active line
        - Number of buses in the system
        - Number of people waiting
    """
    def __init__(self, bus_controller, telegram_controller):
        """initializes all the important information"""
        self.__telegram_controller = telegram_controller
        self.__bus_controller = bus_controller
        self.__main_window = Tk()
        self.__main_display_table = None
        self.remote_stop = False
        self.__headlines = [" "] + [str(x) for x in range(1, self.find_table_length() + 1)]

    def start(self):
        """
        starts the main window as self.__main_window, shows the table, places the buttons, and at the end
        starts a loops that just keeps updeting the table and the statistics
        """
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
        """
        tries to close the window,
        after that tells the TelegramController unit and the BusControllerunit to stop
        closes the code
        """
        print(f"trying to close because {reason}")
        try:
            self.__main_window.destroy()
        except:
            print("failed to close the main window")

        self.__telegram_controller.stop()
        self.__bus_controller.stop()

        sys.exit(f"properly closed by {reason}")

    def __kick_passengers(self):
        """
        tells the telegram controller unit to kick all
        the passengers for the reason that they have been kicked by an admin
        """
        self.__telegram_controller.kick_all_passengers("kicked all passengers by an admin")

    def __update_table_and_labels(self):
        """
        while the remote stop = False it keeps on looping and updaing the
        statistics and the table every second
        """
        self.__update_Table()
        self.__update_labels()
        if self.remote_stop:
            self.__stop("remote telegram admin")
        self.__main_window.after(1000, self.__update_table_and_labels)

    def find_table_length(self):
        """
        an internal method that is used to search for how big the chart that displays the
        information about the buses and the passengers should be.
        """
        max_x_stations = 0
        for line_num, stations in self.__bus_controller.stations_dict.items():
            max_key = max(stations.keys())
            max_x_stations = max(max_key, max_x_stations)
        max_x_bus = 0

        for buses in self.__bus_controller.bus_dict.values():
            if len(buses) != 0:
                buses.sort(key=lambda bus: bus.station_num)
                max_x_bus = max(buses[-1].station_num, max_x_bus)
        max_x = max(max_x_bus, max_x_stations)
        return max_x

    def __update_Table(self):
        """used to refresh the data in the table, it generates the data and then puts it in."""
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

        """updates all the with the new information"""
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
        """
        places the buttons, just at the first launch
        the buttons:
            - kick all buses
            - kick all passengers
            - stop server
        """
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
        """
        forms the list that contains all the information about the buses and the passengers.
        will display only the relevant lines.
        place a X to represent a bus and a number to represent a person
        :return: None
        """
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
        #buses override passengers if the collide at the same place
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

    myserver.start(steve)
    steve.start(gui)
    gui.start()


if __name__ == '__main__':
    main()
