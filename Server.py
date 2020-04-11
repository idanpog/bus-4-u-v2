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
from copy import deepcopy
import random
from time import time

#TODO: display total session time
#TODO: add a bar on the top of the window with some random settings
#TODO: make it run as an exe file
#TODO: make a loading screen that will display the logo for a a second
#TODO: allow the server to broadcast messages to all buses
#TODO: allow the server to broadcast to all users
#TODO: consider adding a remote server access
#TODO: let the server promote users and demote them
#TODO: go bug hunting
#TODO: when a bus connects to the server, update him regarding how many stations there are
#TODO: when the heartbeat mechanism starts, it should update the bus regarding how long each pulse is.
#fix bug when the bus fails to connect to the server on the first time, the connect window stays open
#fix bug when the bus reconnects to the server after server restart the server kicks the bus again.
#fix bug when a bus is kicked, after the reconnect he'll be kicked again.










class TelegramController:
    """
    the telegram controller takes care of the telegram bot.
    receives commands from the telegram chat and can communicate with the bus controller
    """

    def __init__(self, token: str):
        """loads the needed information for the bot, gets access to the bus_controller and loads the list of bus stations"""
        self.__token = token
        self.data_base = DBManager()
        self.__message_sender = None
        self.bus_controller = None
        self.__updater = None
        self.__dp = None
        self.__users = dict()  # dictonary {id: user} (str: User)
        self.__gui = None

    def connect(self, bus_controller, gui, message_sender):
        """acquires a connection to the bus controller unit"""
        self.bus_controller = bus_controller
        self.__gui = gui
        self.__message_sender = message_sender

    def start(self):
        """
        acquires access to the GUI
        launches the thread that takes care of all the handlers
        """
        if self.bus_controller== None:
            print("connection to the bus controller not established yet")
            return
        if self.__gui == None:
            print("connection to the GUI not established yet")
            return
        if self.__message_sender == None:
            print("Connection to the message sender not established yet")
            return

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
        #TODO: add show buses for line {number}
        #TODO: add show how long till bus
        message = update.message.text.lower().split(" ")
        user = self.User(update)
        if len(message) == 1:
            output = "hey looks like you still don't know how to use this command\n" \
                     "don't worry, I'll teach you :)\n" \
                     "here's a list of what you can do:\n" \
                     "/show requests - this will show you your pending requests\n" \
                     "/show lines - this will show you the lines that are available\n" \
                     "/show buses for line {number} - this will show you the locations of the buses in the line you've specified"
        elif message[1].lower() == "lines":
            print("showing lines")
            available_lines = self.bus_controller.show_available_lines()
            if available_lines == "None":
                output = "there are currently no available lines"
            else:
                output = f"the currently available lines are: {str(available_lines)}"
        elif message[1].lower() == "requests":
            user = self.__find_matching_user(user)
            if len(user.stations) == 0:
                output ="You don't have any pending requests"
            else:
                output = "Your pending requests:\n"
                for station in user.stations:
                    output +=f"{station}\n"
                output = output[:-1:]
        elif message[1:-1:] == ['buses', 'for', 'line']:
            if not message[4].isnumeric(): # checks that the value is a number
                output = f"{message[4]} isn't a number i support, therefor I can't help you."
            elif not (int(message[4])>0 and int(message[4]) <= 999): # checks that the number is within limits
                output = f"sorry, {message[4]} is out of range, we only have lines within the range 1-999"
            else: # gets here if the number is legit and everything is good
                line_num = int(message[4])
                if not self.bus_controller.check_line(line_num):
                    output = "there are no available buses for that line"
                else:
                    output = f"the locations of the buses that are available for that line are: \n" \
                         f"{self.bus_controller.show_buses_for_line(line_num)}"
        else:
            print(message[1:-1:])
            output = "couldn't recognise this command, try /show for the list of options you have for this command"
        self.data_base.log(user, update.message.text, output)
        user.send_message(output)
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
        user = self.__find_matching_user(user)
        message = update.message.text.lower().split(" ")
        if len(message) != 3:
            output = "looks like you have a little mistake in the command\n" \
                     "try /bus {bus number} {station number}" \
                     "for example /bus 14 3"
        else:
            try:
                line = int(message[1])
                station = int(message[2])
                if len(user.stations) >= 3 and not self.data_base.check_admin(user):
                    output = "Sorry you cannot have more than 3 requests at a time."
                elif line in map(lambda x: x.line_number, user.stations) and not self.data_base.check_admin(user):
                    station_to_cancel = "Error"
                    for station in user.stations:
                        if station.line_number == line:
                                station_to_cancel = station.station_number
                    output = "looks like you already have a request for that line so you cannot place another one\n" \
                             f"if that was a mistake you can cancel your request with /cancel {line} {station_to_cancel}"
                elif line <=0 or line > 999:
                    output = f"line {line}, doesn't exist. try a line withing the range of 1-999"
                elif station<=0 or station>BusController.MAX_STATION:
                    output = f"station {station}, doesn't exist. try a station withing the range of 1-{BusController.MAX_STATION}"
                elif self.bus_controller.check_line(line):
                    self.bus_controller.add_person_to_the_station(line, station)
                    output = f"request accepted, the bus is notified"
                    self.__message_sender.send_line(line, update_passengers=True)
                    self.__add_to_users_dict(update)
                else:
                    self.bus_controller.add_person_to_the_station(line, station)
                    output = f"request accepted, but there are no buses available for that line yet"
                    self.__add_to_users_dict(update)
            except Exception as e:
                print(e)
                output = "both of the values you give must be number in order to work" \
                         "for example, /bus 14 3"

        self.data_base.log(user, update.message.text, output)
        update.message.reply_text(output)

    def __find_matching_user(self, user):
        """
        returns the user with the matching ID, if it doesn't find one then it just returnes the user that it recieved
        :param user: a user that needs to find a match
        :return: a user that matches the first user.
        """
        if not user.id in self.__users.keys():
            return user
        return self.__users[user.id]

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
            self.__users[user.id] = user

    class Station:
        """
        internal class used to represent a stations.
        holds s a line number and a station number.
        """
        def __init__(self, line_number, station_number):
            self.__line_number = int(line_number)
            self.__station_number = int(station_number)
        def __str__(self):
            return f"line number: {self.__line_number},  station_number: {self.__station_number}"
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
            """uses the user info (which is actually just an update) to send the user a message"""
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
            name = self.__telegram_info.message.from_user.name
            return name[0].upper()+name[1::]


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
        :param output:  str - the output that the server returns
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
        return md5((str(id)+"admin").encode()).hexdigest() in self.__admins

    def promote_admin(self, user: TelegramController.User=None, id: str=None):
        """
        :param user: User - the user you're trying to promote
        :param id: str - the user's that you're trying to promote ID
        :return: None
        will promote the given user to the admin rank and update the cache
        """
        if id == None:
            id = user.id
        header = connect(self.__path)
        curs = header.cursor()
        encrypted_id = md5((str(id)+"admin").encode()).hexdigest()
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
            header = connect(self.__path)
            curs = header.cursor()
            encrypted_id = md5((str(id) + "admin").encode()).hexdigest()
            curs.execute("DELETE FROM admins WHERE id = (?)", (encrypted_id,))
            header.commit()
            self.__update_admin_cache()


class MessagesSender:
    """
    have a seperated class that will manage the updates between the buses and the server,
    the class will have a main dict (line_messages) that will have 2 flags and one str for the whole line, update_passengers, update_buses, free_text
    another dict (bus_messages)that will be {line num: [a tuple (buses that need to be addressed, text that needs to be sent to those buses) ]
    """
    SLEEP_TIME = 2  # in seconds  Must be smaller than the heartbeat sleep time
    def __init__(self ):

        self.__bus_dict = None
        self.__passengers_dict = None
        self.__global_messages = dict()
        self.__line_messages = dict()
        """keys are line numbers, values contain an inner dict that contains 2 flags and 1 str, "update_passengers" "update_buses" "free_text" and each one will store important information"""
        self.__bus_messages = dict()
        """keys are line numbers, values store dicts containing the bus as a key, and the same dict as stored above (bool, bool, str)"""
        self.__global_messages_copy = str()
        self.__line_messages_copy = dict()
        self.__bus_messages_copy =dict()
        self.__buses_to_kick = list()
         #aquired later in code
        self.__lock_data = bool()
        self.__socket = None
        self.__stop = bool()
    def connect(self, bus_controller):
        self.__bus_controller = bus_controller
    def start(self):
        if self.__bus_controller == None:
            print("can't start please pass me the needed dictionaries")

        self.__global_messages = ""
        self.__lock_data = False
        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__stop = False
        __main_loop = threading.Thread(target=self.__main_loop, args=(), name="bus updater")
        __main_loop.start()


    """
    data senders, actually don't sent anything but add it to the memory so the __main_loop will send it later
    the logic is 
    check if something already exists regarding this sending group, if yes then add new data to it,
    if no then create new data dict with default values
    each sending group has a dictionary that stores the information that needs to be sent, the dict has 3 keys
    "passengers": bool      - will send the sending group an update regarding the state of all the passengers
    "buses": bool           - will send the sending group an update regarding the state of all the buses
    "free text": str        - will just send the free text
    "kick reason": str      - will just send the kick reason with a prefix "kicked for:{reason}"
    """
    def send_global(self, free_text: str = "", kick_reason =""):
        while self.__lock_data:
            sleep(0.01)

        if free_text!="":
            self.__global_messages["free text"]+= free_text+ "\n"

        if kick_reason != "":
            self.__global_messages["kick reason"] += kick_reason + "\n"
            bus_dict_copy = deepcopy(self.__bus_controller.bus_dict)
            for buses in bus_dict_copy.values():
                for bus in buses:
                    self.__buses_to_kick.append(bus)
        print(f"finished send global, freetext: {self.__global_messages['free text']}, kickreason:{self.__global_messages['kick reason']}")

    def send_line(self, line, update_buses: bool = False, update_passengers: bool = False, free_text: str = "", kick_reason:str = ""):
        """
        adds to the line
        :return:
        """
        while self.__lock_data:
            sleep(0.01)
        if line in self.__line_messages.keys():
            self.__line_messages[line]["passengers"] = self.__line_messages[line]["passengers"] or update_passengers
            self.__line_messages[line]["buses"] = self.__line_messages[line]["buses"] or update_buses
            if free_text != "":
                self.__line_messages[line]["free text"] += free_text + "\n"
            if kick_reason!= "":
                buses_copy = deepcopy(self.__bus_dict[line])
                for bus in buses_copy:
                    if bus not in self.__buses_to_kick:
                        self.__buses_to_kick.append(bus)
                self.__line_messages[line]["kick reason"] += kick_reason + "\n"


        else:
            self.__line_messages[line] = dict()
            self.__line_messages[line]["passengers"] = update_passengers
            self.__line_messages[line]["buses"] = update_buses
            self.__line_messages[line]["free text"] = ""
            self.__line_messages[line]["kick reason"] = ""
            if free_text != "":
                self.__line_messages[line]["free text"] = free_text + "\n"
            if kick_reason != "":
                self.__line_messages[line]["kick reason"] = free_text + "\n"

    def send_bus(self, bus, update_buses: bool = False, update_passengers: bool = False, free_text: str = "", kick_reason:str = ""):
        """
        :type bus: object
        """
        while self.__lock_data:
            sleep(0.01)
        if bus.line_num in self.__bus_messages.keys() and bus.id in self.__bus_messages[bus.line_num].keys():
            self.__bus_messages[bus.line_num][bus.id]["passengers"] = self.__line_messages[bus.line_num][bus.id]["passengers"] or update_passengers
            self.__bus_messages[bus.line_num][bus.id]["buses"] = self.__line_messages[bus.line_num][bus.id]["buses"] or update_buses
            if free_text != "":
                self.__bus_messages[bus.line_num][bus.id]["free text"] += free_text + "\n"
            if kick_reason!= "":
                self.__bus_messages[bus.line_num][bus.id]["kick reason"] += kick_reason + "\n"
        else:
            self.__bus_messages[bus.line_num] = dict()
            self.__bus_messages[bus.line_num][bus.id] = dict()
            self.__bus_messages[bus.line_num][bus.id]["passengers"] = update_passengers
            self.__bus_messages[bus.line_num][bus.id]["buses"] = update_buses
            self.__bus_messages[bus.line_num][bus.id]["free text"] = ""
            self.__bus_messages[bus.line_num][bus.id]["kick reason"] = ""
            if free_text != "":
                self.__bus_messages[bus.line_num][bus.id]["free text"] = free_text + "\n"

            if kick_reason != "":
                self.__bus_messages[bus.line_num][bus.id]["kick reason"] = kick_reason + "\n"


    """
    Base Builders
    organizes the information stored in the dictionaries into str that the bus clients know to translate back into dictionaries
    """
    def __build_update_regarding_buses(self, line: int):
        """
        builds out of the dictionary, in the form of # data  = "buses 1,3,7,9" the word buses and then the locations of the buses
        :param line: the line that needs to be built
        :return: a string
        """
        print("building update regarding buses")
        output = "buses:"
        for bus in self.__bus_controller.bus_dict[line]:
            output +=f"{bus.station_num},"
            print(f"current output is {output}")
        return output[:-1:]

    def __build_update_regarding_passengers(self,line:int):
        """
        builds out of the dictionary, in the form of # data  = "passengers 1-3,3-2,7-4,9-2"
        the word passengers followed by the pairs station_number-people_count
        :param line: the line that needs to be built
        :return: a string
        """
        output = "passengers:"
        if line not in self.__bus_controller.stations_dict.keys():
            return output
        for station_number, people_count in self.__bus_controller.stations_dict[line].items():
            print(output)
        return output[:-1:]


    """
    Group Builders
    build the information given from the Base Builders into a string that's relevant for the group
    the main message form looks like
    buses 2,3,6,9\n
    people 2-5,4-9,9-1\n
    free_text bla bla bla 
    
    """
    def __build_global_update(self):

        if self.__global_messages["free text"] != "":
            return f"free text:{self.__global_messages['free text']}\n"
        return ""

    def __build_line_update(self, line):
        output = ""
        if line not in self.__line_messages_copy.keys():
            return output

        if self.__line_messages_copy[line]["passengers"]:
            output +=self.__build_update_regarding_passengers(line) +"\n"
        if self.__line_messages_copy[line]["buses"]:
            output +=self.__build_update_regarding_buses(line) +"\n"
        if self.__line_messages_copy[line]["kick reason"]!="" and self.__line_messages_copy[line]["kick_reason"] not in self.__global_messages_copy["kick reason"]:
            output +=f"kicked for:{self.__line_messages_copy[line]['kick reason']}" + "\n"
        if self.__line_messages_copy[line]["free text"] != "" and self.__line_messages_copy[line]["free text"] not in self.__global_messages_copy["free text"]:
            output += "free text:" + self.__line_messages_copy[line]["free text"]+"\n"
        return output

    def __build_bus_update(self, bus):
        """builds a per bus layer that is added onto the line layer"""
        output = ""
        if bus.line_num not in self.__bus_messages_copy.keys() or bus.id not in self.__bus_messages_copy[bus.line_num].keys():
            return output

        if self.__bus_messages_copy[bus.line_num][bus.id]["passengers"] and not self.__line_messages_copy[bus.line_num]["passengers"]:
            output += self.__build_update_regarding_passengers(bus.line_num) +"\n"

        if self.__bus_messages_copy[bus.line_num][bus.id]["buses"] and not self.__line_messages_copy[bus.line_num]["buses"]:
            output += self.__build_update_regarding_buses(bus.line_num)+"\n"

        if self.__bus_messages_copy[bus.line_num][bus.id]["free text"] != "" and not (
                self.__bus_messages_copy[bus.line_num][bus.id]["free text"] in self.__line_messages_copy[bus.line_num]["free text"] or
                self.__bus_messages_copy[bus.line_num][bus.id]["free text"] in self.__global_messages_copy["free text"]):
            output += "free text:"+ self.__bus_messages_copy[bus.line_num][bus.id]["free text"] +"\n"

        return output

    def __main_loop(self):
        """
        builds 3 layers and adds them one onto the other
        first layer is global messages, just text, doesn't include any logic in it
        second layer is line messages, could be text, bus updates or passengers update, adds the needed information, doesn't overlap with the global layer
        third layer is bus messages, could be text, bus updates or passengers update, adds the needed information, doesn't overlap with line and global layer
        at the end sends the notification to the bus
        """
        while not self.__stop:
            self.__lock_data = True
            self.__bus_messages_copy = deepcopy(self.__bus_messages)
            self.__line_messages_copy = deepcopy(self.__line_messages)
            self.__global_messages_copy = deepcopy(self.__global_messages)
            self.__bus_messages = {}
            self.__line_messages = {}
            self.__global_messages = {"kick reason": "", "free text": ""}
            buses_to_kick_copy = deepcopy(self.__buses_to_kick)
            self.__buses_to_kick = list()
            self.__lock_data = False

            for bus in buses_to_kick_copy: #handles the buses that need to be kicked
                message = "kicked for reason:"+self.__global_messages_copy["kick reason"]
                if bus.line_num in self.__line_messages_copy.keys():
                    message +=  self.__line_messages_copy[bus.line_num]["kick reason"]
                if bus.line_num in self.__line_messages_copy.keys() and bus.id in self.__bus_messages_copy[bus.line_num].keys():
                    message += self.__bus_messages_copy[bus.line_num][bus.id]["kick reason"]
                print(f"sending message{message.strip()}")
                bus.send_to_bus(message.strip())

            global_message = self.__build_global_update()
            for line, buses in self.__bus_controller.bus_dict.items():
                line_message = self.__build_line_update(line)
                for bus in buses:
                    bus_message= self.__build_bus_update(bus)
                    message = global_message + line_message + bus_message
                    message = message.strip("\n")
                    if message != "":
                        bus.send_to_bus(message)


            sleep(MessagesSender.SLEEP_TIME)

        """send all buses about server shutdown"""
        self.__shut_down()
        print("server shut down")

    def __shut_down(self):
        """sends globally a message telling them that the server stopped"""

        for line, buses in self.__bus_dict.items():
            for bus in buses:
                bus.send_to_bus("Server Shut Down")


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
    MAX_STATION = 14

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
        self.__telegram_bot = None
        self.__message_sender = None

    def connect(self, telegram_bot, message_sender):
        #connects between the buscontroller and the telegram bot
        self.__telegram_bot = telegram_bot
        self.__message_sender = message_sender

    def start(self):
        """
        launches all the important threads
        new_bus_reviever - waits for connections from new buses and adds them to the system
        updates_tracker - waits for connections from buses in the system and updates the relevant information
        heart_beat - keeps track of all the buses and makes sure that there are no offline buses by kicking them
        """
        if self.__telegram_bot == None:
            print("telegram bot connection is not set yet")
            return
        if self.__message_sender == None:
            print("message sender connection is not set yet")
            return
        self.__message_sender.start()
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
                line_num, station_num, id = data.decode().split(" ")
                if not (line_num.isdigit() and station_num.isdigit() and id.isdigit()):
                    print("some bus tried to access the system, but he's values don't match the expectations")
                elif int(line_num) not in self.__bus_dict.keys() or id not in map(lambda bus: bus.id, self.__bus_dict[int(line_num)]):
                    print("an unregistered bus tried to access the system, ignored.")
                else:
                    relevant_bus = None
                    for bus in self.bus_dict[int(line_num)]:
                        if bus.id == id:
                            relevant_bus = bus
                            break

                    relevant_bus.set_station(station_num)
                    self.__telegram_bot.notify_passengers_about_incoming_bus(relevant_bus)
                    self.__try_remove_people_from_the_station(bus=relevant_bus)
                    if int(station_num) >= BusController.MAX_STATION:
                        self.remove_bus(relevant_bus)
                    self.__message_sender.send_line(int(line_num), update_buses=True)

            except Exception as e:
                print(f"exception in __track_updates: {e}")
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
                # data  = {line_number} {station} {ID}
                line_num, station, ID = data.decode().split(" ")
                if int(station) < BusController.MAX_STATION:
                    bus = self.Bus(addr, line_num, station, ID)
                    self.__add_bus(bus)
                    self.__message_sender.send_bus(bus, update_passengers=True)
                    self.__message_sender.send_line(bus.line_num, update_buses=True)
                client_socket.close()
            except:
                print("closed the new_bus_reciever thread")
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

    def add_person_to_the_station(self, line, station):
        """
        used only by outer classes that need to update the bus controller regarding a new user
        for example the telegram controller
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
            elif self.__stations_dict[station.line_number][station.station_number] > 1:
                self.__stations_dict[station.line_number][station.station_number] -= 1
            self.__message_sender.send_line(station.line_number, update_passengers=True)
        else:
            print("whoops an error, looks like the current station doesn't exit and there's no person waiting for it.")

    def __try_remove_people_from_the_station(self, line: int = None, station_num: int = None, bus = None):
        if bus!=None:
            line = bus.line_num
            station_num = bus.station_num
        if line not in self.__stations_dict.keys() or station_num not in self.__stations_dict[line].keys():
            return

        del self.__stations_dict[line][station_num] #clears the Bus controller memory from users in the certain station
        if len(self.__stations_dict[line]) == 0:
            del self.__stations_dict[line]
        #launches a thread that waits one sec to notify the buses about the change in people, avoids collisions in TCP connections this way
        self.__message_sender.send_line(line, update_passengers=True)
        people_that_need_to_be_kicked = self.__telegram_bot.remove_everyone_from_station(line, station_num)
        # a list of Users that have been waiting at the station
        changed_lines = []
        for user in people_that_need_to_be_kicked: #kick them from the memory of the bus controller
            for station in user.stations:
                if station.line_number!=line:
                    self.remove_person_from_the_station(station)

    def show_available_lines(self):
        """just returns a list of all the active lines in the system"""
        if len(self.__bus_dict) == 0:
            return "None"
        return list(self.__bus_dict.keys())

    def show_buses_for_line(self, line: int) -> str:
        """
        shows all the buses that are in the given line
        :param line:
        :return: a string, that has all the buses locations in this line
        """
        if line not in self.__bus_dict.keys():
            return "-None-"
        output = ""
        buses = self.bus_dict[line]
        for bus in self.bus_dict[line]:
            output +=f"station: {bus.station_num}"
        return output

    def kick_all_buses(self, reason: str = ""):
        """
        tells all the buses that they've been kicked
        and then empties the self.__bus_dict
        """
        self.__message_sender.send_global(kick_reason=reason)
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
                self.__message_sender.send_line(line, update_passengers=True)
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
                    self.__message_sender.send_bus(bus, kick_reason="found another bus with he same id")
                    self.__message_sender.send_bus(another_bus, kick_reason="found another bus with he same id")
                    self.remove_bus(bus)
                    self.remove_bus(another_bus)

    def __heart(self):

        """
        will be launched in a separate thread
        cycles the command pulse for all the buses every few seconds
        """
        while not self.__stop_threads:
            start_time = time()
            self.__pulse_all()
           #self.__check_duplicates()
            #print(f"total pulse time = {time()-start_time} seconds")
            sleep(BusController.PULSE_DELAY)
        print("stopped the heartbeats")

    def __pulse_all(self):
        """launches a thread for each bus that will use the command individual_pulse
        in order to complete the heartbeat mechanism"""
        if len(self.__bus_dict) == 0:
            return
        bus_dict_copy = self.__bus_dict.copy()
        for line in bus_dict_copy.values():
            for bus in line:
                #threading.Thread(target=self.__indevidual_pulse, args=(bus,), name=f"pulse ID: {bus.id}").start()
                self.__indevidual_pulse(bus)

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

        def send_to_bus(self, data: str):
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
            start_time = time()
            try:
                s.connect((self.__address[0], BusController.HEART_BEAT_PORT))
                data = "Check".encode()
                s.send(data)
                data = s.recv(1024).decode()
                if int(data) != int(self.__id):
                    print(f"bus had the wrong ID\nwas supposed to be {self.__id}, but received {data}")
                    output = False
            # listen for an answer
            except Exception as e:
                print(f"exception in check_up (heart_beat) look:{e}")
                print(f"something went wrong, couldn't establish connection with {self.__address}")
                output = False
            finally:
                #print(f"waited {time()-start_time} seconds for respond")
                pass
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
                                          command=lambda: self.__bus_controller.kick_all_buses(reason="kicked all buses by the console"),
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

    bus_controller = BusController()
    steve = TelegramController("990223452:AAHrln4bCzwGpkR2w-5pqesPHpuMjGKuJUI")
    gui = GUI(bus_controller, steve)
    message_sender = MessagesSender()

    steve.connect(bus_controller=bus_controller, gui=gui, message_sender=message_sender)
    bus_controller.connect(telegram_bot=steve, message_sender=message_sender)
    message_sender.connect(bus_controller=bus_controller)
    bus_controller.start()
    steve.start()
    gui.start()


if __name__ == '__main__':
    main()
